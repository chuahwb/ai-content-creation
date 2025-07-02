"""
Tests for the centralized JSON parsing utilities.
===============================================

These tests ensure the RobustJSONParser can handle various LLM output behaviors
and edge cases that occur across different pipeline stages.
"""

import pytest
import json
from typing import Dict, Any
from pydantic import BaseModel, ValidationError

from churns.core.json_parser import (
    RobustJSONParser, 
    JSONExtractionError,
    extract_json_from_llm_response,
    parse_llm_json_response,
    should_use_manual_parsing
)


# Test Pydantic models
class TestAssessmentModel(BaseModel):
    assessment_scores: Dict[str, int]
    general_score: float
    needs_regeneration: bool = False


class TestStyleModel(BaseModel):
    style_keywords: list
    style_description: str
    marketing_impact: str


class TestJSONParser:
    """Test cases for the RobustJSONParser class."""
    
    def setup_method(self):
        """Set up test parser instance."""
        self.parser = RobustJSONParser(debug_mode=False)
        self.debug_parser = RobustJSONParser(debug_mode=True)
    
    def test_markdown_json_block_extraction(self):
        """Test extraction from ```json...``` blocks."""
        test_cases = [
            # Standard markdown JSON block
            '```json\n{"test": "value", "number": 42}\n```',
            # With explanatory text
            'Here is the result:\n```json\n{"assessment_scores": {"concept": 4}}\n```\nLet me know if you need anything else!',
            # Case insensitive
            '```JSON\n{"style_keywords": ["modern", "clean"]}\n```',
            # With extra whitespace
            '```json   \n  {"data": true}  \n  ```'
        ]
        
        expected_results = [
            {"test": "value", "number": 42},
            {"assessment_scores": {"concept": 4}},
            {"style_keywords": ["modern", "clean"]},
            {"data": True}
        ]
        
        for i, test_case in enumerate(test_cases):
            result = self.parser.extract_json_string(test_case)
            assert result is not None, f"Failed to extract JSON from case {i}: {test_case[:100]}"
            parsed = json.loads(result)
            assert parsed == expected_results[i], f"Parsed result doesn't match expected for case {i}"
    
    def test_generic_code_block_extraction(self):
        """Test extraction from generic ``` blocks."""
        test_cases = [
            # Generic code block with JSON
            '```\n{"response": "success"}\n```',
            # Mixed content - only valid JSON should be extracted
            '```\n{"valid": true}\nsome invalid text\n```',
            # Array in code block
            '```\n[{"item": 1}, {"item": 2}]\n```'
        ]
        
        for test_case in test_cases:
            result = self.parser.extract_json_string(test_case)
            if result:  # Only check if extraction succeeded
                # Should be valid JSON
                parsed = json.loads(result)
                assert isinstance(parsed, (dict, list))
    
    def test_direct_json_extraction(self):
        """Test extraction when entire response is JSON."""
        test_cases = [
            '{"direct": true, "works": "yes"}',
            '[{"array": "item1"}, {"array": "item2"}]',
            '{\n  "formatted": true,\n  "indented": "json"\n}'
        ]
        
        for test_case in test_cases:
            result = self.parser.extract_json_string(test_case)
            assert result is not None
            parsed = json.loads(result)
            original_parsed = json.loads(test_case)
            assert parsed == original_parsed
    
    def test_extra_data_handling(self):
        """Test handling of 'Extra data' JSON parse errors."""
        test_cases = [
            '{"valid": true} extra text after',
            '{"complete": "object"}\n\nSome explanation below',
            '[{"item": 1}]\nAdditional content'
        ]
        
        expected = [
            {"valid": True},
            {"complete": "object"},
            [{"item": 1}]
        ]
        
        for i, test_case in enumerate(test_cases):
            result = self.parser.extract_json_string(test_case)
            assert result is not None, f"Failed to extract JSON from extra data case {i}: {test_case[:100]}"
            parsed = json.loads(result)
            assert parsed == expected[i], f"Parsed result doesn't match expected for extra data case {i}"
    
    def test_bracket_matching_extraction(self):
        """Test fallback bracket matching strategy."""
        test_cases = [
            # Embedded in text
            'The result is {"success": true, "value": 42} which indicates completion.',
            # Array embedded
            'Items found: [{"name": "item1"}, {"name": "item2"}] in the database.',
            # Multiple JSON objects - should get the most complete one
            'First {"partial": true} and then {"complete": true, "final": "result"}'
        ]
        
        for test_case in test_cases:
            result = self.parser.extract_json_string(test_case)
            assert result is not None
            # Should be valid JSON
            parsed = json.loads(result)
            assert isinstance(parsed, (dict, list))
    
    def test_preprocessing_removes_problematic_text(self):
        """Test that preprocessing removes common problematic prefixes/suffixes."""
        test_cases = [
            "Here's the assessment: {'score': 5}",
            "Assessment: {'result': 'good'}",
            "Let me provide the JSON response: {'data': true}",
            "I'll give you the result: {'success': true}",
            "```json\n{'clean': true}\n```",
            "{'answer': 'test'}\nI hope this helps!",
            "{'final': true}\nLet me know if you need anything else.",
        ]
        
        for test_case in test_cases:
            result = self.parser.extract_json_string(test_case)
            assert result is not None
            # Should be extractable after preprocessing
            parsed = json.loads(result)
            assert isinstance(parsed, dict)
    
    def test_json_repair_functionality(self):
        """Test JSON repair for common formatting issues."""
        test_cases = [
            # Trailing comma
            '{"test": "value",}',
            # Unquoted keys
            '{test: "value", other: 123}',
            # Single quotes
            "{'test': 'value', 'number': 42}",
            # Multiple issues combined
            "{test: 'value', number: 123,}"
        ]
        
        for test_case in test_cases:
            result = self.parser.extract_json_string(test_case)
            assert result is not None
            # Should be parseable after repair
            parsed = json.loads(result)
            assert isinstance(parsed, dict)
    
    def test_complex_real_world_cases(self):
        """Test with real-world LLM response patterns."""
        # Realistic assessment response
        assessment_response = '''
Here's the assessment for the image:

```json
{
  "assessment_scores": {
    "concept_adherence": 4,
    "technical_quality": 5,
    "text_rendering_quality": 3
  },
  "assessment_justification": {
    "concept_adherence": "Good alignment with requested style",
    "technical_quality": "High resolution, no artifacts",
    "text_rendering_quality": "Text is mostly legible but slightly blurred"
  },
  "general_score": 4.2,
  "needs_regeneration": false,
  "needs_text_repair": true
}
```

I hope this assessment is helpful!
        '''
        
        result = self.parser.extract_json_string(assessment_response)
        assert result is not None
        parsed = json.loads(result)
        assert "assessment_scores" in parsed
        assert "general_score" in parsed
        assert isinstance(parsed["assessment_scores"], dict)
        
        # Realistic style guidance response
        style_response = '''
Based on the marketing strategies, here are the style guidance sets:

```json
{
  "style_guidance_sets": [
    {
      "style_keywords": ["minimalist", "clean", "modern"],
      "style_description": "Clean, minimalist design with plenty of white space and simple geometric elements.",
      "marketing_impact": "Appeals to modern aesthetic preferences and ensures high readability on mobile devices.",
      "source_strategy_index": 0
    }
  ]
}
```

Let me know if you need any adjustments to these styles.
        '''
        
        result = self.parser.extract_json_string(style_response)
        assert result is not None
        parsed = json.loads(result)
        assert "style_guidance_sets" in parsed
        assert len(parsed["style_guidance_sets"]) == 1
    
    def test_edge_cases_and_failures(self):
        """Test edge cases and expected failures."""
        # Cases that should return None
        failure_cases = [
            "",  # Empty string
            "   ",  # Whitespace only
            "No JSON here at all",
            "Almost JSON but not quite {incomplete",
            "```\nNo JSON in this code block\n```"
        ]
        
        for case in failure_cases:
            result = self.parser.extract_json_string(case)
            assert result is None
    
    def test_extract_and_parse_with_schema_validation(self):
        """Test complete extraction and validation with Pydantic schemas."""
        # Valid assessment response
        valid_assessment = '''
{
  "assessment_scores": {"concept_adherence": 4, "technical_quality": 5},
  "general_score": 4.5,
  "needs_regeneration": false
}
        '''
        
        result = self.parser.extract_and_parse(
            valid_assessment, 
            expected_schema=TestAssessmentModel
        )
        
        assert isinstance(result, dict)
        assert result["general_score"] == 4.5
        assert result["needs_regeneration"] is False
    
    def test_extract_and_parse_with_validation_failure(self):
        """Test validation failure handling."""
        # Invalid schema response
        invalid_response = '{"wrong_field": "value"}'
        
        with pytest.raises(JSONExtractionError) as exc_info:
            self.parser.extract_and_parse(
                invalid_response, 
                expected_schema=TestAssessmentModel
            )
        
        assert "Schema validation failed" in str(exc_info.value)
    
    def test_extract_and_parse_with_fallback_validation(self):
        """Test fallback validation when Pydantic fails."""
        def fallback_validator(data: Dict[str, Any]) -> Dict[str, Any]:
            # Simple fallback that adds missing required fields
            return {
                "assessment_scores": data.get("scores", {}),
                "general_score": data.get("score", 3.0),
                "needs_regeneration": False
            }
        
        invalid_response = '{"scores": {"concept": 4}, "score": 4.2}'
        
        result = self.parser.extract_and_parse(
            invalid_response,
            expected_schema=TestAssessmentModel,
            fallback_validation=fallback_validator
        )
        
        assert result["general_score"] == 4.2
        assert "assessment_scores" in result
    
    def test_truncated_response_detection(self):
        """Test detection of truncated responses."""
        from churns.core.json_parser import TruncatedResponseError
        
        # Test truncated JSON string value
        truncated_response1 = '''```json\n{\n  "style_guidance_sets": [\n    {\n      "style_keywords": ["modern", "clean"],\n      "style_description": "A modern, clean aesthetic with monochromatic color scheme ('''
        with pytest.raises(TruncatedResponseError) as exc_info:
            self.parser.extract_and_parse(truncated_response1)
        assert "truncated mid-generation" in str(exc_info.value)
        
        # Test truncated in middle of key-value pair
        truncated_response2 = '''{\n  "assessment_scores": {\n    "concept_adherence": 4,\n    "technical_quality":'''
        with pytest.raises(TruncatedResponseError) as exc_info:
            self.parser.extract_and_parse(truncated_response2)
        assert "truncated" in str(exc_info.value).lower()
        
        # Test incomplete markdown block
        truncated_response3 = '''Here is the assessment:\n\n```json\n{\n  "assessment_scores": {\n    "concept_adherence": 4\n  },\n  "general_score": 4.2'''
        with pytest.raises(TruncatedResponseError) as exc_info:
            self.parser.extract_and_parse(truncated_response3)
        
        # Test response that looks complete (should not raise TruncatedResponseError)
        complete_response = '''{\n  "assessment_scores": {\n    "concept_adherence": 4\n  },\n  "general_score": 4.2\n}'''
        try:
            # This should raise JSONExtractionError (missing fields) but NOT TruncatedResponseError
            self.parser.extract_and_parse(complete_response)
        except Exception as e:
            assert not isinstance(e, TruncatedResponseError), f"Should not be TruncatedResponseError, got: {type(e)}"
    
    def test_truncation_patterns(self):
        """Test specific truncation patterns in isolation."""
        # Test the pattern matching directly
        parser = RobustJSONParser()
        
        # Should detect truncation
        assert parser._is_likely_truncated_response('"description": "This is truncated')
        assert parser._is_likely_truncated_response('{"key": "value",')
        assert parser._is_likely_truncated_response('[{"item": ')
        
        # Should NOT detect truncation
        assert not parser._is_likely_truncated_response('{"complete": "json"}')
        assert not parser._is_likely_truncated_response('["complete", "array"]')
        assert not parser._is_likely_truncated_response('```json\n{"complete": "json"}\n```')


class TestConvenienceFunctions:
    """Test the convenience functions for backward compatibility."""
    
    def test_extract_json_from_llm_response(self):
        """Test the backward compatibility extraction function."""
        response = '```json\n{"test": true}\n```'
        result = extract_json_from_llm_response(response)
        
        assert result is not None
        parsed = json.loads(result)
        assert parsed["test"] is True
    
    def test_parse_llm_json_response(self):
        """Test the complete parsing convenience function."""
        response = '{"style_keywords": ["modern"], "style_description": "Clean design", "marketing_impact": "High engagement"}'
        
        result = parse_llm_json_response(
            response, 
            expected_schema=TestStyleModel
        )
        
        assert result["style_keywords"] == ["modern"]
        assert result["style_description"] == "Clean design"
    
    def test_should_use_manual_parsing(self):
        """Test the model detection function."""
        # Mock the constants for testing
        import churns.core.json_parser as parser_module
        original_force = parser_module.FORCE_MANUAL_JSON_PARSE
        original_problematic = parser_module.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS
        
        try:
            # Test with problematic model
            parser_module.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = ["openai/o4-mini"]
            assert should_use_manual_parsing("openai/o4-mini") is True
            assert should_use_manual_parsing("openai/gpt-4") is False
            
            # Test with force flag
            parser_module.FORCE_MANUAL_JSON_PARSE = True
            assert should_use_manual_parsing("any-model") is True
            
        finally:
            # Restore original values
            parser_module.FORCE_MANUAL_JSON_PARSE = original_force
            parser_module.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = original_problematic


class TestIntegrationWithConstants:
    """Test integration with the constants from constants.py."""
    
    def test_parser_respects_force_manual_parse(self):
        """Test that parser respects FORCE_MANUAL_JSON_PARSE setting."""
        parser = RobustJSONParser()
        
        # Should be able to determine parsing strategy
        result = parser.should_use_manual_parsing("test-model")
        assert isinstance(result, bool)
    
    def test_problematic_models_detection(self):
        """Test detection of problematic models."""
        from churns.core.constants import INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS
        
        parser = RobustJSONParser()
        
        # Test with a known problematic model
        if INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
            problematic_model = INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS[0]
            assert parser.should_use_manual_parsing(problematic_model) is True
        
        # Test with a non-problematic model
        assert parser.should_use_manual_parsing("definitely-not-problematic-model") is False


if __name__ == "__main__":
    pytest.main([__file__]) 