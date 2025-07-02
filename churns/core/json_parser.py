"""
Centralized JSON Parsing Utilities for LLM Responses
===================================================

This module provides robust JSON extraction and parsing capabilities
for handling various LLM output behaviors across all pipeline stages.

Key Features:
- Markdown code block detection and extraction
- JSON repair for common formatting issues  
- Multiple fallback strategies for finding JSON
- Integration with FORCE_MANUAL_JSON_PARSE and problematic model handling
- Comprehensive error reporting and debugging support

Usage:
    from churns.core.json_parser import RobustJSONParser
    
    parser = RobustJSONParser()
    result = parser.extract_and_parse(raw_llm_response, expected_schema=MyModel)
"""

import json
import re
import traceback
from typing import Dict, Any, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from .constants import FORCE_MANUAL_JSON_PARSE, INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS


class JSONExtractionError(Exception):
    """Custom exception for JSON extraction failures."""
    pass


class TruncatedResponseError(JSONExtractionError):
    """Specific exception for truncated LLM responses that create malformed JSON."""
    pass


class RobustJSONParser:
    """
    Centralized, robust JSON parser for LLM responses.
    
    Handles various LLM output behaviors including:
    - Markdown code blocks (```json...``` and ```...```)
    - Explanatory text before/after JSON
    - Common JSON formatting issues
    - Partial JSON responses
    - Multiple fallback extraction strategies
    - Detection of truncated responses
    """
    
    def __init__(self, debug_mode: bool = False):
        """
        Initialize the JSON parser.
        
        Args:
            debug_mode: Enable detailed logging for debugging
        """
        self.debug_mode = debug_mode
        
    def should_use_manual_parsing(self, model_id: str) -> bool:
        """
        Determine if manual parsing should be used based on configuration.
        
        Args:
            model_id: The LLM model identifier
            
        Returns:
            True if manual parsing should be used, False if instructor should be tried first
        """
        return (FORCE_MANUAL_JSON_PARSE or 
                model_id in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS)
    
    def extract_and_parse(
        self, 
        raw_response: str, 
        expected_schema: Optional[Type[BaseModel]] = None,
        fallback_validation: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Extract and parse JSON from LLM response with validation.
        
        Args:
            raw_response: Raw text response from LLM
            expected_schema: Optional Pydantic model for validation
            fallback_validation: Optional custom validation function
            
        Returns:
            Parsed and validated JSON as dictionary
            
        Raises:
            JSONExtractionError: If JSON cannot be extracted or validated
            TruncatedResponseError: If response appears to be truncated
        """
        # Step 1: Check for truncated response before attempting extraction
        if self._is_likely_truncated_response(raw_response):
            raise TruncatedResponseError(
                f"Response appears to be truncated mid-generation. "
                f"Last 100 characters: ...{raw_response[-100:]}"
            )
        
        # Step 2: Extract JSON string
        json_str = self.extract_json_string(raw_response)
        if not json_str:
            # Check if the failure was due to truncation in a different pattern
            if self._contains_incomplete_json_patterns(raw_response):
                raise TruncatedResponseError(
                    f"Response contains incomplete JSON patterns, likely truncated. "
                    f"Raw content preview: {raw_response[:200]}..."
                )
            
            raise JSONExtractionError(
                f"Could not extract JSON from response. "
                f"Raw content preview: {raw_response[:200]}..."
            )
        
        # Step 3: Parse JSON string
        try:
            parsed_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Check if this is a truncation-related decode error
            if self._is_truncation_json_error(json_str, e):
                raise TruncatedResponseError(
                    f"JSON parsing failed due to truncated content. "
                    f"JSONDecodeError: {e}. Last 100 chars: ...{json_str[-100:]}"
                )
            
            if self.debug_mode:
                print(f"Initial JSON parse failed: {e}")
                print(f"Attempting repair on: {json_str[:200]}...")
            
            # Attempt repair and re-parse
            repaired_json = self._attempt_json_repair(json_str)
            if repaired_json:
                try:
                    parsed_data = json.loads(repaired_json)
                    if self.debug_mode:
                        print("JSON repair successful!")
                except json.JSONDecodeError:
                    pass
            
            if 'parsed_data' not in locals():
                raise JSONExtractionError(
                    f"Failed to parse JSON after extraction and repair attempts. "
                    f"JSONDecodeError: {e}. Extracted JSON: {json_str[:500]}..."
                )
        
        # Step 4: Validate with schema if provided
        if expected_schema:
            try:
                validated_model = expected_schema(**parsed_data)
                return validated_model.model_dump()
            except ValidationError as e:
                if self.debug_mode:
                    print(f"Pydantic validation failed: {e}")
                
                # Try fallback validation if provided
                if fallback_validation:
                    try:
                        return fallback_validation(parsed_data)
                    except Exception as fallback_err:
                        raise JSONExtractionError(
                            f"Both Pydantic and fallback validation failed. "
                            f"Pydantic error: {e}. Fallback error: {fallback_err}"
                        )
                else:
                    raise JSONExtractionError(f"Schema validation failed: {e}")
        
        return parsed_data
    
    def extract_json_string(self, raw_text: str) -> Optional[str]:
        """
        Extract JSON string from LLM response using multiple strategies.
        
        Args:
            raw_text: Raw text response from LLM
            
        Returns:
            Extracted JSON string or None if not found
        """
        if not isinstance(raw_text, str) or not raw_text.strip():
            return None
        
        # Preprocess text to remove common problematic elements
        cleaned_text = self._preprocess_response(raw_text)
        
        # Strategy 1: Extract from markdown code blocks
        json_str = self._extract_from_markdown_blocks(cleaned_text)
        if json_str:
            return json_str
        
        # Strategy 2: Parse entire text directly
        json_str = self._extract_direct_json(cleaned_text)
        if json_str:
            return json_str
        
        # Strategy 3: Handle "Extra data" JSON parse errors
        json_str = self._extract_partial_json(cleaned_text)
        if json_str:
            return json_str
        
        # Strategy 4: Find JSON by brace/bracket matching
        json_str = self._extract_by_bracket_matching(cleaned_text)
        if json_str:
            return json_str
        
        if self.debug_mode:
            print(f"All extraction strategies failed for text: {raw_text[:300]}...")
        
        return None
    
    def _preprocess_response(self, raw_text: str) -> str:
        """Remove common problematic prefixes and suffixes from LLM responses."""
        text = raw_text.strip()
        
        # Remove common prefixes
        prefix_patterns = [
            r'^(Here\'s the|Here is the|Here\'s|Here is)\s*(assessment|response|answer|result|json|output)[:.]?\s*',
            r'^(Assessment|Response|Answer|Result|JSON|Output)[:.]?\s*',
            r'^```json\s*',
            r'^Let me\s+\w+.*?[:.]?\s*',
            r'^I\'ll\s+\w+.*?[:.]?\s*',
        ]
        
        for pattern in prefix_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove common suffixes
        suffix_patterns = [
            r'\s*```\s*$',
            r'\s*(Let me know if you need.*|I hope this helps.*|Feel free to ask.*|Is there anything else.*)$',
            r'\s*(Please let me know.*|Any questions.*|Happy to help.*)$',
        ]
        
        for pattern in suffix_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _extract_from_markdown_blocks(self, text: str) -> Optional[str]:
        """Extract JSON from markdown code blocks."""
        # Try ```json ... ``` blocks first
        match = re.search(r"```json\s*([\s\S]+?)\s*```", text, re.IGNORECASE)
        if match:
            json_str = match.group(1).strip()
            if self._is_valid_json(json_str):
                return json_str
        
        # Try generic ``` ... ``` blocks
        match = re.search(r"```\s*([\s\S]+?)\s*```", text, re.IGNORECASE)
        if match:
            potential_json = match.group(1).strip()
            if (self._looks_like_json(potential_json) and 
                self._is_valid_json(potential_json)):
                return potential_json
        
        return None
    
    def _extract_direct_json(self, text: str) -> Optional[str]:
        """Try to parse the text directly as JSON, with repair attempt."""
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            # Try repairing the JSON and parsing again
            repaired = self._attempt_json_repair(text)
            if repaired and self._is_valid_json(repaired):
                return repaired
            return None
    
    def _extract_partial_json(self, text: str) -> Optional[str]:
        """Handle 'Extra data' JSON parse errors by extracting valid prefix."""
        try:
            json.loads(text)
            return text  # Should not reach here, but just in case
        except json.JSONDecodeError as e:
            if "Extra data" in str(e) and hasattr(e, 'pos') and e.pos > 0:
                potential_json = text[:e.pos].strip()
                if self._is_valid_json(potential_json):
                    return potential_json
        return None
    
    def _extract_by_bracket_matching(self, text: str) -> Optional[str]:
        """Find JSON by matching opening and closing braces/brackets."""
        # Find object-like JSON
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        json_candidate = None
        
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            potential_obj = text[first_brace:last_brace + 1]
            if self._is_valid_json(potential_obj):
                json_candidate = potential_obj
        
        # Find array-like JSON
        first_bracket = text.find('[')
        last_bracket = text.rfind(']')
        
        if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
            potential_arr = text[first_bracket:last_bracket + 1]
            if self._is_valid_json(potential_arr):
                # Prefer object over array if both found, unless array wraps object
                if json_candidate:
                    if not (first_bracket > first_brace and last_bracket < last_brace):
                        json_candidate = potential_arr
                else:
                    json_candidate = potential_arr
        
        return json_candidate
    
    def _looks_like_json(self, text: str) -> bool:
        """Quick heuristic to check if text looks like JSON."""
        text = text.strip()
        return ((text.startswith('{') and text.endswith('}')) or
                (text.startswith('[') and text.endswith(']')))
    
    def _is_valid_json(self, text: str) -> bool:
        """Check if text is valid JSON."""
        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False
    
    def _attempt_json_repair(self, json_str: str) -> Optional[str]:
        """Attempt to repair common JSON formatting issues."""
        if not json_str:
            return None
        
        repaired = json_str
        
        # Fix single quotes to double quotes first (preserves string integrity)
        repaired = repaired.replace("'", '"')
        
        # Fix trailing commas
        repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
        
        # Fix unquoted keys (only match keys that aren't already quoted)
        repaired = re.sub(r'(?<!")(\w+)(?!"):', r'"\1":', repaired)
        
        # Fix line breaks in strings (basic attempt)
        repaired = re.sub(r'"\s*\n\s*"', '" "', repaired)
        
        # Fix missing quotes around string values (only unquoted values)
        repaired = re.sub(r':\s*([a-zA-Z][a-zA-Z0-9_\s]*[a-zA-Z0-9])(?=\s*[,}])', r': "\1"', repaired)
        
        # Verify the repair worked
        if self._is_valid_json(repaired):
            return repaired
        
        return None
    
    def _is_likely_truncated_response(self, raw_text: str) -> bool:
        """
        Detect if a response is likely truncated based on common patterns.
        
        Args:
            raw_text: The raw response text
            
        Returns:
            True if response appears truncated
        """
        if not raw_text or not raw_text.strip():
            return False
        
        text = raw_text.strip()
        
        # Pattern 1: Ends with incomplete JSON string (quote without closing)
        if re.search(r':\s*"[^"]*$', text):
            return True
        
        # Pattern 2: Ends in the middle of a key-value pair
        if re.search(r'[,{]\s*"[^"]*"?\s*:?\s*$', text):
            return True
        
        # Pattern 3: Ends with incomplete array or object
        if re.search(r'[,\[\{]\s*$', text):
            return True
        
        # Pattern 4: Contains markdown code block start but no end
        if '```json' in text and not text.strip().endswith('```'):
            # Check if the JSON inside is incomplete
            json_match = re.search(r'```json\s*(.*?)(?:```|$)', text, re.DOTALL)
            if json_match:
                json_content = json_match.group(1).strip()
                if json_content and not self._is_likely_complete_json(json_content):
                    return True
        
        return False
    
    def _contains_incomplete_json_patterns(self, raw_text: str) -> bool:
        """
        Check if text contains patterns suggesting incomplete JSON generation.
        
        Args:
            raw_text: The raw response text
            
        Returns:
            True if incomplete JSON patterns are detected
        """
        if not raw_text:
            return False
        
        # Look for JSON-like structures that are clearly incomplete
        patterns = [
            r'\{\s*"[^"]*"\s*:\s*"[^"]*$',  # Object with unclosed string value
            r'\[\s*"[^"]*$',                # Array with unclosed string
            r'"\s*:\s*\{\s*"[^"]*$',       # Nested object with unclosed string
            r'"[^"]*"\s*:\s*\[\s*$',       # Array value that's just opened
        ]
        
        for pattern in patterns:
            if re.search(pattern, raw_text):
                return True
        
        return False
    
    def _is_truncation_json_error(self, json_str: str, error: json.JSONDecodeError) -> bool:
        """
        Determine if a JSONDecodeError is likely due to truncation.
        
        Args:
            json_str: The JSON string that failed to parse
            error: The JSONDecodeError that occurred
            
        Returns:
            True if error is likely due to truncation
        """
        error_msg = str(error).lower()
        
        # Common truncation-related JSON errors
        truncation_indicators = [
            "unterminated string",
            "expecting ',' delimiter",
            "expecting '}'" and json_str.strip().endswith('"'),
            "expecting ']'" and json_str.strip().endswith('"'),
            "end of json input",
        ]
        
        for indicator in truncation_indicators:
            if isinstance(indicator, str) and indicator in error_msg:
                return True
            elif isinstance(indicator, bool) and indicator:  # For composite conditions
                return True
        
        # Check if error position is near the end of the string
        if hasattr(error, 'pos') and error.pos > len(json_str) * 0.8:
            return True
        
        return False
    
    def _is_likely_complete_json(self, json_str: str) -> bool:
        """
        Quick heuristic to check if JSON string appears complete.
        
        Args:
            json_str: JSON string to check
            
        Returns:
            True if JSON appears complete
        """
        if not json_str.strip():
            return False
        
        text = json_str.strip()
        
        # Must start and end with proper JSON delimiters
        if text.startswith('{') and text.endswith('}'):
            return True
        if text.startswith('[') and text.endswith(']'):
            return True
        
        return False


# Convenience functions for backward compatibility and easy usage
def extract_json_from_llm_response(
    raw_response: str, 
    model_id: str = "", 
    debug: bool = False
) -> Optional[str]:
    """
    Extract JSON string from LLM response (backward compatibility function).
    
    Args:
        raw_response: Raw text response from LLM
        model_id: LLM model identifier (for problematic model detection)
        debug: Enable debug mode
        
    Returns:
        Extracted JSON string or None
    """
    parser = RobustJSONParser(debug_mode=debug)
    return parser.extract_json_string(raw_response)


def parse_llm_json_response(
    raw_response: str, 
    expected_schema: Optional[Type[BaseModel]] = None,
    model_id: str = "",
    fallback_validation: Optional[callable] = None,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Complete JSON extraction and parsing with validation.
    
    Args:
        raw_response: Raw text response from LLM
        expected_schema: Optional Pydantic model for validation
        model_id: LLM model identifier
        fallback_validation: Optional custom validation function  
        debug: Enable debug mode
        
    Returns:
        Parsed and validated JSON dictionary
        
    Raises:
        JSONExtractionError: If extraction or validation fails
    """
    parser = RobustJSONParser(debug_mode=debug)
    return parser.extract_and_parse(
        raw_response, 
        expected_schema=expected_schema,
        fallback_validation=fallback_validation
    )


def should_use_manual_parsing(model_id: str) -> bool:
    """
    Determine if manual parsing should be used for a given model.
    
    Args:
        model_id: The LLM model identifier
        
    Returns:
        True if manual parsing should be used
    """
    return (FORCE_MANUAL_JSON_PARSE or 
            model_id in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS) 