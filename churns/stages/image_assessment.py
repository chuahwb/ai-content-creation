"""
Image Assessment Stage - Evaluates generated images using OpenAI's multimodal LLM.

This stage assesses the quality of generated images based on:
- Concept adherence (alignment with visual concept)
- Subject preservation (when reference image is provided)  
- Technical quality (artifacts, proportions, lighting)
- Text rendering quality (when text was requested)

The assessment provides scores (1-5), justifications, and boolean flags
indicating specific refinement needs.
"""

import json
import base64
import traceback
import os
import asyncio
import warnings
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
from pydantic import ValidationError

from ..pipeline.context import PipelineContext
from ..models import ImageAssessmentResult
from ..core.constants import IMAGE_ASSESSMENT_MODEL_ID
from ..core.token_cost_manager import get_token_cost_manager
from ..core.json_parser import (
    RobustJSONParser, 
    JSONExtractionError,
    TruncatedResponseError,
    should_use_manual_parsing
)

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_image_assessment = None
base_llm_client_image_assessment = None
IMAGE_ASSESSMENT_MODEL_ID = None
IMAGE_ASSESSMENT_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []


class ImageAssessmentError(Exception):
    """Custom exception for image assessment failures."""
    pass


# Centralized JSON parser will be initialized when needed


class ImageAssessor:
    """Handles image assessment using OpenAI's multimodal capabilities."""
    
    def __init__(self, model_id: str = None, client: Optional[Any] = None):
        """Initialize the assessor with configured client."""
        # Use injected client or fall back to direct OpenAI client
        self.client = client or base_llm_client_image_assessment
        if self.client is None:
            # Fallback to direct OpenAI client (for backward compatibility)
            self.client = OpenAI()
        
        # Use injected model ID or fall back to constant
        self.model_id = model_id or IMAGE_ASSESSMENT_MODEL_ID
        self.token_manager = get_token_cost_manager()
    
    async def assess_image_async(
        self, 
        image_path: str,
        visual_concept: Dict[str, Any],
        creativity_level: int,
        has_reference_image: bool,
        render_text_enabled: bool,
        task_type: str,
        platform: str,
        reference_image_data: Optional[Tuple[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Assess a single image using OpenAI's vision capabilities (async version).
        
        Args:
            image_path: Path to the generated image to assess
            visual_concept: The visual concept from creative expert stage
            creativity_level: Creativity level (1-3)
            has_reference_image: Whether reference image is available
            render_text_enabled: Whether text rendering was requested
            task_type: Type of marketing task
            platform: Target platform
            reference_image_data: Optional (base64, content_type) tuple for reference image
            
        Returns:
            Assessment result dictionary (without _meta to avoid duplication)
        """
        # Load the generated image
        image_data = await self._load_image_as_base64(image_path)
        if not image_data:
            raise ImageAssessmentError(f"Failed to load image: {image_path}")
        
        image_base64, content_type = image_data
        
        # Calculate expected image tokens for cost tracking
        image_token_breakdown = await self._calculate_image_tokens_breakdown(
            image_base64, reference_image_data, self.model_id
        )
        
        # Check if this is a problematic model that needs special handling
        is_problematic_model = IMAGE_ASSESSMENT_MODEL_ID in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS
        
        # Create assessment prompt
        prompt = self._create_assessment_prompt(
            visual_concept, creativity_level, has_reference_image,
            render_text_enabled, task_type, platform, is_problematic_model
        )
        
        # Prepare content based on single or multi-image scenario
        user_content = self._prepare_user_content(
            prompt, image_base64, content_type, 
            has_reference_image, reference_image_data
        )
        
        # Adjust system prompt for problematic models
        if is_problematic_model:
            system_content = """You are an expert art director. You MUST respond with valid JSON in the exact format specified. Do not include any markdown code blocks, explanatory text, or any other formatting. Your response should start directly with { and end with }. Only return the JSON object."""
            temperature = 0.1  # Lower temperature for more consistent responses
            max_tokens = 2000  # Slightly higher token limit
        else:
            system_content = "You are an expert art director. You MUST respond ONLY with valid JSON in the exact format specified. Do not include any markdown, explanatory text, or formatting - just pure JSON."
            temperature = 0.1
            max_tokens = 1500
        
        # Special handling for o4-mini model which has known JSON issues
        if "o4-mini" in self.model_id.lower():
            system_content = """You are an expert art director. CRITICAL: Your response must be ONLY a valid JSON object. No explanations, no markdown, no text before or after the JSON. Start with { and end with }."""
            temperature = 0.05  # Very low temperature for consistency
            max_tokens = 2500  # More tokens to avoid truncation
            # Add JSON schema hint in system prompt for better reliability
            system_content += "\n\nJSON SCHEMA REMINDER: The response must match this exact structure:\n{\"assessment_scores\": {\"concept_adherence\": 1-5, ...}, \"assessment_justification\": {...}, \"general_score\": 0.0-5.0, \"needs_subject_repair\": false, \"needs_regeneration\": false, \"needs_text_repair\": false}"
        
        # Make API call to OpenAI with improved retry logic
        max_retries = 2 if is_problematic_model else 1
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Log the attempt for debugging
                if attempt > 0:
                    print(f"Image assessment retry attempt {attempt + 1}/{max_retries} for model {self.model_id}")
                
                # Shorter timeout for retries to fail fast
                timeout = 30 if attempt == 0 else 15
                
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model_id,
                    messages=[
                        {
                            "role": "system",
                            "content": system_content
                        },
                        {
                            "role": "user",
                            "content": user_content
                        }
                    ],
                    temperature=temperature,
                    max_completion_tokens=max_tokens,
                    timeout=timeout  # Progressive timeout reduction
                )
                
                # Check if response is None
                if response is None:
                    raise ImageAssessmentError("API call returned None response")
                
                # Check if response has choices
                if not hasattr(response, 'choices') or not response.choices:
                    raise ImageAssessmentError("API response missing choices")
                
                # Check if first choice exists and has message
                if not response.choices[0] or not hasattr(response.choices[0], 'message'):
                    raise ImageAssessmentError("API response missing message in first choice")
                
                # Parse and validate response
                raw_content = response.choices[0].message.content
                if not raw_content:
                    raise ImageAssessmentError("Empty response from OpenAI")
                
                # Extract and validate JSON with enhanced error reporting
                try:
                    assessment_data = self._parse_assessment_response(raw_content, has_reference_image, render_text_enabled)
                except ImageAssessmentError as parse_err:
                    # For JSON extraction failures, log the raw content for debugging
                    if "Could not extract JSON" in str(parse_err) and len(raw_content) < 2000:
                        print(f"JSON extraction failed for attempt {attempt + 1}. Raw content: {raw_content[:500]}...")
                    raise parse_err
                
                # Store token usage info for aggregated tracking (but not in individual result)
                token_info = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else image_token_breakdown["total_image_tokens"] + 100,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 150,
                    "total_tokens": response.usage.total_tokens if response.usage else image_token_breakdown["total_image_tokens"] + 250,
                    "model": self.model_id,
                    "image_token_breakdown": image_token_breakdown,
                    "estimated_text_tokens": max(0, (response.usage.prompt_tokens if response.usage else image_token_breakdown["total_image_tokens"] + 100) - image_token_breakdown["total_image_tokens"]),
                    "detail_level": "high"
                }
                
                # Return assessment data with token info separate for aggregation
                return {
                    **assessment_data,
                    "_token_info": token_info  # Temporary field for aggregation, will be removed
                }
                
            except Exception as e:
                last_exception = e
                # Log the specific error for debugging
                print(f"Image assessment attempt {attempt + 1} failed: {type(e).__name__}: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Shorter wait time to fail faster (reduce from exponential backoff)
                    wait_time = min(1.0, 0.5 * (attempt + 1))  # 0.5s, 1s instead of 1s, 2s
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed
                    break
        
        # All retries failed - provide detailed error context
        error_context = f"Model: {self.model_id}, Attempts: {max_retries}"
        if "Could not extract JSON" in str(last_exception):
            error_context += " (JSON parsing issue - may need model-specific handling)"
        
        raise ImageAssessmentError(f"OpenAI API call failed after {max_retries} attempts: {str(last_exception)}. Context: {error_context}")

    def assess_image(
        self, 
        image_path: str,
        visual_concept: Dict[str, Any],
        creativity_level: int,
        has_reference_image: bool,
        render_text_enabled: bool,
        task_type: str,
        platform: str,
        reference_image_data: Optional[Tuple[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Assess a single image using OpenAI's vision capabilities (sync version for compatibility).
        
        .. deprecated::
            This method is for backward compatibility only. Use assess_image_async
            in an asynchronous context for better performance and true parallelism.
        
        Args:
            image_path: Path to the generated image to assess
            visual_concept: The visual concept from creative expert stage
            creativity_level: Creativity level (1-3)
            has_reference_image: Whether reference image is available
            render_text_enabled: Whether text rendering was requested
            task_type: Type of marketing task
            platform: Target platform
            reference_image_data: Optional (base64, content_type) tuple for reference image
            
        Returns:
            Assessment result dictionary
        """
        warnings.warn(
            "assess_image is deprecated and will be removed in a future version. "
            "Use assess_image_async instead for better performance and true parallelism.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Run the async version in sync context
        return asyncio.run(self.assess_image_async(
            image_path, visual_concept, creativity_level, has_reference_image,
            render_text_enabled, task_type, platform, reference_image_data
        ))
    
    def _load_image_as_base64_sync(self, image_path: str) -> Optional[Tuple[str, str]]:
        """Load image file and convert to base64 format (synchronous helper)."""
        try:
            # Check if file exists first
            if not os.path.exists(image_path):
                raise ImageAssessmentError(f"Image file does not exist: {image_path}")
            
            # Check if it's a file (not directory)
            if not os.path.isfile(image_path):
                raise ImageAssessmentError(f"Path is not a file: {image_path}")
            
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
                if not image_data:
                    raise ImageAssessmentError(f"Image file is empty: {image_path}")
                
                base64_encoded = base64.b64encode(image_data).decode('utf-8')
                content_type = self._get_content_type_from_filename(image_path)
                
                return base64_encoded, content_type
                
        except Exception as e:
            # Re-raise with more context instead of returning None
            raise ImageAssessmentError(f"Failed to load image {image_path}: {str(e)}")
    
    async def _load_image_as_base64(self, image_path: str) -> Optional[Tuple[str, str]]:
        """Load image file and convert to base64 format (asynchronous)."""
        return await asyncio.to_thread(self._load_image_as_base64_sync, image_path)
    
    def _get_content_type_from_filename(self, filename: str) -> str:
        """Determine image content type from filename."""
        filename_lower = filename.lower()
        if filename_lower.endswith('.png'):
            return 'image/png'
        elif filename_lower.endswith(('.jpg', '.jpeg')):
            return 'image/jpeg'
        elif filename_lower.endswith('.webp'):
            return 'image/webp'
        elif filename_lower.endswith('.gif'):
            return 'image/gif'
        else:
            return 'image/jpeg'  # Default
    
    def _prepare_user_content(
        self, 
        prompt: str, 
        image_base64: str, 
        content_type: str,
        has_reference_image: bool,
        reference_image_data: Optional[Tuple[str, str]]
    ) -> List[Dict[str, Any]]:
        """Prepare user content for single or multi-image assessment."""
        
        if has_reference_image and reference_image_data:
            ref_base64, ref_content_type = reference_image_data
            
            # Multi-image prompt with explicit instructions
            multi_prompt = (
                f"{prompt}\n\n"
                "INSTRUCTIONS ON IMAGES: You have been provided two images. "
                "The first is the 'Generated Image' that you must assess. "
                "The second is the 'Reference Image' to be used for the subject preservation assessment. "
                "Evaluate the first image based on the full criteria, using the second image where specified."
            )
            
            return [
                {"type": "text", "text": multi_prompt},
                {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{image_base64}", "detail": "high"}},
                {"type": "image_url", "image_url": {"url": f"data:{ref_content_type};base64,{ref_base64}", "detail": "high"}}
            ]
        else:
            # Single image
            return [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{image_base64}", "detail": "high"}}
            ]
    
    def _create_assessment_prompt(
        self,
        visual_concept: Dict[str, Any],
        creativity_level: int,
        has_reference_image: bool,
        render_text_enabled: bool,
        task_type: str,
        platform: str,
        is_problematic_model: bool
    ) -> str:
        """Create the detailed prompt for image assessment."""
        
        sections = [
            self._create_role_and_context_section(task_type, platform, creativity_level),
            self._create_scoring_scale_section(),
            self._create_assessment_criteria_section(has_reference_image, render_text_enabled, creativity_level),
            self._create_visual_concept_section(visual_concept),
            self._create_json_format_section(has_reference_image, render_text_enabled, is_problematic_model),
            self._create_final_instructions_section(is_problematic_model)
        ]
        
        return "\n\n".join(sections)
    
    def _create_role_and_context_section(self, task_type: str, platform: str, creativity_level: int) -> str:
        """Create the role definition and context section."""
        return f"""# ROLE & CONTEXT
You are an expert art director and quality assurance specialist for F&B marketing.

**Task Context:** {task_type} for {platform}
**Creativity Level:** {creativity_level} (1=Low/Photorealistic, 2-3=Medium-High/Artistic)

Your mission is to evaluate the generated image against specific quality criteria and provide structured feedback."""

    def _create_scoring_scale_section(self) -> str:
        """Create the scoring scale definition section."""
        return """# SCORING SCALE (1-5)
**5: Excellent** - Flawless execution that meets or exceeds all expectations
**4: Good** - High quality with minor, non-critical issues
**3: Acceptable** - Noticeable flaws that detract from quality, but core objective is met. Refinement recommended
**2: Poor** - Significant issues that render the result unusable for its primary purpose  
**1: Very Poor** - Complete failure to address the criterion"""

    def _create_assessment_criteria_section(self, has_reference_image: bool, render_text_enabled: bool, creativity_level: int) -> str:
        """Create the detailed assessment criteria section."""
        criteria_parts = [
            "# ASSESSMENT CRITERIA",
            "",
            self._get_concept_adherence_criteria(),
            self._get_technical_quality_criteria()
        ]
        
        if has_reference_image:
            criteria_parts.append(self._get_subject_preservation_criteria(creativity_level))
            
        if render_text_enabled:
            criteria_parts.append(self._get_text_rendering_criteria(has_reference_image))
            
        return "\n".join(criteria_parts)

    def _get_concept_adherence_criteria(self) -> str:
        """Get detailed concept adherence scoring criteria."""
        return """## 1. CONCEPT ADHERENCE
**Question:** How well does the generated image align with the visual concept?

**Detailed Scoring Guide:**
- **5:** Perfectly captures the specified themes, mood, color palette, composition, and all key elements
- **4:** Captures the overall mood and most key elements, but with minor deviations  
- **3:** Adheres to the main theme but misses some secondary elements or misinterprets the mood
- **2:** Major deviation from the concept; key elements are missing or incorrect
- **1:** Completely ignores or contradicts the visual concept

**Focus Areas:** themes, mood, color palette, composition, described elements"""

    def _get_technical_quality_criteria(self) -> str:
        """Get detailed technical quality scoring criteria."""
        return """## 2. TECHNICAL QUALITY
**Question:** Is the image technically sound (excluding rendered text)?

**Detailed Scoring Guide:**
- **5:** Flawless execution: high resolution, perfect lighting, no artifacts or anatomical issues
- **4:** Minor, hard-to-spot technical flaws (e.g., slight blurriness)
- **3:** Noticeable issues like minor artifacts, awkward proportions, or unnatural lighting
- **2:** Significant technical problems: obvious artifacts, major anatomical errors, low resolution
- **1:** A technical mess, plagued by severe artifacts and distortions

**Focus Areas:** artifacts, proportions, lighting, resolution, aspect ratio, anatomical accuracy"""

    def _get_subject_preservation_criteria(self, creativity_level: int) -> str:
        """Get detailed subject preservation scoring criteria based on creativity level."""
        if creativity_level == 1:
            scoring_guide = """**Detailed Scoring Guide (Low Creativity - Photorealistic):**
- **5:** Near-identical, photorealistic preservation of all features and details
- **4:** Perfectly recognizable with only minuscule differences in texture or lighting
- **3:** Recognizable, but with noticeable inaccuracies in some features
- **2:** The subject's identity is distorted or partially lost
- **1:** The subject is unrecognizable"""
        else:
            scoring_guide = """**Detailed Scoring Guide (Medium/High Creativity - Artistic):**
- **5:** The subject's core identity and all defining visual details are unmistakably preserved and accurately represented within the new artistic style.
- **4:** The subject's identity is clear and most details are preserved, but with very minor artistic alterations that do not compromise recognition.
- **3:** The likeness is maintained, but some noticeable details are lost, altered, or overly stylized, weakening the connection to the reference subject.
- **2:** The subject's identity is distorted or partially lost due to significant loss of detail or excessive stylization.
- **1:** The subject is unrecognizable"""
        
        return f"""## 3. SUBJECT PRESERVATION
**Question:** How faithfully is the reference subject represented considering the creativity level?

{scoring_guide}

**Focus Areas:** facial features, distinctive characteristics, overall likeness, identity preservation

**IMPORTANT - Text Assessment Scope:** This criterion also evaluates any text that appears ON or WITHIN the main subject (e.g., text overlaid on the subject, text integrated into the subject's clothing/accessories, text that is part of the subject itself). Text that appears separately from or around the subject is handled by the Text Rendering Quality criterion."""

    def _get_text_rendering_criteria(self, has_reference_image: bool) -> str:
        """Get detailed text rendering quality scoring criteria."""
        
        # Define scope based on whether reference image is provided
        if has_reference_image:
            scope_clarification = """**IMPORTANT - Text Assessment Scope:** This criterion evaluates text that appears AROUND or SEPARATE FROM the main subject (e.g., background text, standalone text elements, text in margins/borders). Text that appears ON or WITHIN the main subject is handled by the Subject Preservation criterion."""
        else:
            scope_clarification = """**IMPORTANT - Text Assessment Scope:** This criterion evaluates ALL text elements in the image, as no reference subject is provided for comparison."""
        
        return f"""## 4. TEXT RENDERING QUALITY
**Question:** If text was requested, is it rendered correctly and integrated well?

**Detailed Scoring Guide:**
- **5:** Text is perfectly legible, correctly spelled, and seamlessly integrated with the image style
- **4:** Text is legible and correct, but its integration has minor stylistic flaws
- **3:** Legible but with minor errors (e.g., one misspelled letter, slight warping)
- **2:** Significant rendering issues: misspelled, illegible, or heavily distorted
- **1:** The text is garbled, nonsensical, or absent

**Focus Areas:** spelling accuracy, legibility, visual integration, stylistic coherence

{scope_clarification}"""

    def _create_visual_concept_section(self, visual_concept: Dict[str, Any]) -> str:
        """Create the visual concept reference section."""
        return f"""# VISUAL CONCEPT REFERENCE
The following is the target visual concept you must assess against:

```json
{json.dumps(visual_concept, indent=2)}
```"""

    def _create_json_format_section(self, has_reference_image: bool, render_text_enabled: bool, is_problematic_model: bool) -> str:
        """Create the JSON format specification section."""
        
        # Build the JSON structure dynamically
        scores_structure = [
            '    "concept_adherence": <integer 1-5>',
            '    "technical_quality": <integer 1-5>'
        ]
        
        justification_structure = [
            '    "concept_adherence": "<detailed explanation>"',
            '    "technical_quality": "<detailed explanation>"'
        ]
        
        if has_reference_image:
            scores_structure.insert(1, '    "subject_preservation": <integer 1-5>')
            justification_structure.insert(1, '    "subject_preservation": "<detailed explanation>"')
            
        if render_text_enabled:
            scores_structure.append('    "text_rendering_quality": <integer 1-5>')
            justification_structure.append('    "text_rendering_quality": "<detailed explanation>"')
        
        # Pre-calculate the joined strings to avoid backslashes in f-string expressions
        scores_joined = ',\n'.join(scores_structure)
        justifications_joined = ',\n'.join(justification_structure)
        
        if is_problematic_model:
            # More explicit instructions for problematic models
            json_structure = f"""# REQUIRED JSON RESPONSE FORMAT

Your response must be EXACTLY this JSON structure with no additional text:

{{
  "assessment_scores": {{
{scores_joined}
  }},
  "assessment_justification": {{
{justifications_joined}
  }}
}}

CRITICAL INSTRUCTIONS:
- Start your response with {{ and end with }}
- Do NOT use markdown code blocks (no ``` symbols)
- Do NOT include any explanatory text before or after the JSON
- Replace <integer 1-5> with actual numbers (1, 2, 3, 4, or 5)
- Replace "<detailed explanation>" with your actual assessment text
- Ensure all JSON syntax is correct (proper quotes, commas, brackets)"""
        else:
            json_structure = f"""# REQUIRED JSON RESPONSE FORMAT

```json
{{
  "assessment_scores": {{
{scores_joined}
  }},
  "assessment_justification": {{
{justifications_joined}
  }}
}}
```

**CRITICAL:** Respond ONLY with this JSON structure. No markdown, no explanatory text."""
        
        return json_structure

    def _create_final_instructions_section(self, is_problematic_model: bool) -> str:
        """Create the final instructions section."""
        if is_problematic_model:
            return """# FINAL INSTRUCTIONS

1. **Analyze the image systematically** against each applicable criterion
2. **Provide integer scores (1-5)** based on the detailed scoring guides above
3. **Write detailed justifications** explaining your scoring decisions
4. **Focus on what is visually present** - be critical but fair
5. **Return ONLY the JSON object** - no additional text, no markdown, no explanations

CRITICAL: Your entire response must be the JSON object only. Start with { and end with }. Do not include any other text.

Begin your assessment now."""
        else:
            return """# FINAL INSTRUCTIONS

1. **Analyze the image systematically** against each applicable criterion
2. **Provide integer scores (1-5)** based on the detailed scoring guides above
3. **Write detailed justifications** explaining your scoring decisions
4. **Calculate general_score** using the specified formula
5. **Determine refinement flags** based on the threshold conditions
6. **Focus on what is visually present** - be critical but fair
7. **Return only the JSON object** - no additional commentary

Begin your assessment now."""
    
    def _calculate_general_score(self, assessment_scores: Dict[str, int]) -> float:
        """Calculate general score using weighted formula."""
        concept_score = assessment_scores.get("concept_adherence", 3)
        technical_score = assessment_scores.get("technical_quality", 3)
        return (concept_score * 0.6) + (technical_score * 0.4)

    def _calculate_refinement_flags(self, assessment_data: Dict[str, Any], has_reference_image: bool, render_text_enabled: bool) -> Dict[str, Any]:
        """Calculate refinement flags based on assessment scores."""
        scores = assessment_data.get("assessment_scores", {})
        general_score = assessment_data.get("general_score", 0.0)
        
        # Calculate flags based on thresholds
        flags = {
            "needs_regeneration": general_score < 3.5
        }
        
        if has_reference_image and "subject_preservation" in scores:
            flags["needs_subject_repair"] = scores["subject_preservation"] < 4
        else:
            flags["needs_subject_repair"] = False
            
        if render_text_enabled and "text_rendering_quality" in scores:
            flags["needs_text_repair"] = scores["text_rendering_quality"] < 4
        else:
            flags["needs_text_repair"] = False
        
        return flags
    
    def _parse_assessment_response(self, raw_content: str, has_reference_image: bool, render_text_enabled: bool) -> Dict[str, Any]:
        """Parse and validate assessment response from OpenAI using centralized parser."""
        # Initialize parser instance
        json_parser = RobustJSONParser(debug_mode=False)
        
        try:
            # Try with centralized parser first
            result_data = json_parser.extract_and_parse(
                raw_content,
                expected_schema=ImageAssessmentResult
            )
            
            # Calculate derived fields that aren't directly in the schema
            if "general_score" not in result_data:
                general_score = self._calculate_general_score(result_data["assessment_scores"])
                result_data["general_score"] = general_score
                
            if "needs_regeneration" not in result_data:
                refinement_flags = self._calculate_refinement_flags(result_data, has_reference_image, render_text_enabled)
                result_data.update(refinement_flags)
            
            return result_data
            
        except TruncatedResponseError as truncate_err:
            # Handle truncated responses specifically
            raise ImageAssessmentError(
                f"Image assessment response was truncated mid-generation. "
                f"Consider increasing max_tokens or trying a different model. "
                f"Truncation details: {truncate_err}"
            )
        except JSONExtractionError as e:
            # Fallback: try manual parsing and validation
            try:
                parsed_data = json_parser.extract_and_parse(raw_content)  # Just extract, no schema
                result_data = self._validate_and_fix_assessment_data(parsed_data)
                
                # Calculate derived fields
                general_score = self._calculate_general_score(result_data["assessment_scores"])
                result_data["general_score"] = general_score
                
                refinement_flags = self._calculate_refinement_flags(result_data, has_reference_image, render_text_enabled)
                result_data.update(refinement_flags)
                
                return result_data
            except Exception as fallback_error:
                raise ImageAssessmentError(f"JSON extraction and fallback validation failed: {str(e)} | Fallback error: {str(fallback_error)}")
    
    # Old JSON extraction and repair functions removed - now using centralized parser
    
    def _validate_and_fix_assessment_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Manually validate and fix assessment data structure."""
        
        # Initialize with default structure (general score and flags will be calculated separately)
        result = {
            "assessment_scores": {},
            "assessment_justification": {}
        }
        
        # Extract scores (required) - now using 1-5 scale
        scores = data.get("assessment_scores", {})
        if isinstance(scores, dict):
            for key in ["concept_adherence", "subject_preservation", "technical_quality", "text_rendering_quality"]:
                if key in scores:
                    try:
                        score = int(scores[key])
                        result["assessment_scores"][key] = max(1, min(5, score))  # Clamp to 1-5
                    except (ValueError, TypeError):
                        result["assessment_scores"][key] = 3  # Default fallback (middle of 1-5 scale)
        
        # Extract justifications
        justifications = data.get("assessment_justification", {})
        if isinstance(justifications, dict):
            for key in ["concept_adherence", "subject_preservation", "technical_quality", "text_rendering_quality"]:
                if key in justifications and key in result["assessment_scores"]:
                    result["assessment_justification"][key] = str(justifications[key])
        
        return result

    def _calculate_image_tokens_breakdown_sync(
        self, 
        image_base64: str, 
        reference_image_data: Optional[Tuple[str, str]], 
        model_id: str
    ) -> Dict[str, Any]:
        """Calculate detailed breakdown of image tokens for cost tracking (synchronous helper)."""
        breakdown = {
            "model_id": model_id,
            "detail_level": "high",
            "images": [],
            "total_image_tokens": 0
        }
        
        try:
            # Calculate tokens for main assessment image
            main_image_tokens = self.token_manager.calculate_tokens_from_base64(
                image_base64, model_id, "high"
            )
            breakdown["images"].append({
                "type": "assessment_target",
                "tokens": main_image_tokens
            })
            breakdown["total_image_tokens"] += main_image_tokens
            
            # Calculate tokens for reference image if present
            if reference_image_data:
                ref_base64, ref_content_type = reference_image_data
                ref_image_tokens = self.token_manager.calculate_tokens_from_base64(
                    ref_base64, model_id, "high"
                )
                breakdown["images"].append({
                    "type": "reference_image",
                    "tokens": ref_image_tokens
                })
                breakdown["total_image_tokens"] += ref_image_tokens
            
        except Exception as e:
            # Fallback calculation if image token calculation fails
            breakdown["images"].append({
                "type": "fallback",
                "tokens": 1000,  # Conservative estimate
                "error": str(e)
            })
            breakdown["total_image_tokens"] = 1000
        
        return breakdown
    
    async def _calculate_image_tokens_breakdown(
        self, 
        image_base64: str, 
        reference_image_data: Optional[Tuple[str, str]], 
        model_id: str
    ) -> Dict[str, Any]:
        """Calculate detailed breakdown of image tokens for cost tracking (asynchronous)."""
        return await asyncio.to_thread(
            self._calculate_image_tokens_breakdown_sync,
            image_base64,
            reference_image_data,
            model_id
        )


def _create_simulation_fallback(has_reference_image: bool, render_text_enabled: bool) -> Dict[str, Any]:
    """Create simulated assessment when real assessment fails."""
    scores = {
        "concept_adherence": 4,  # 1-5 scale
        "technical_quality": 4   # 1-5 scale
    }
    
    justifications = {
        "concept_adherence": "Simulated assessment - good alignment with concept",
        "technical_quality": "Simulated assessment - good technical quality"
    }
    
    if has_reference_image:
        scores["subject_preservation"] = 4  # 1-5 scale
        justifications["subject_preservation"] = "Simulated assessment - good subject preservation"
    
    if render_text_enabled:
        scores["text_rendering_quality"] = 3  # 1-5 scale
        justifications["text_rendering_quality"] = "Simulated assessment - acceptable text quality"
    
    # Create realistic image token breakdown for simulation
    simulated_image_tokens = 1500 if has_reference_image else 1000  # Estimate for 1-2 images
    simulated_text_tokens = 500
    
    # Return assessment data with token info for aggregation
    return {
        "assessment_scores": scores,
        "assessment_justification": justifications,
        "_token_info": {
            "prompt_tokens": simulated_image_tokens + simulated_text_tokens,
            "completion_tokens": 150,  # Simulated completion tokens  
            "total_tokens": simulated_image_tokens + simulated_text_tokens + 150,
            "model": IMAGE_ASSESSMENT_MODEL_ID,
            "image_token_breakdown": {
                "model_id": IMAGE_ASSESSMENT_MODEL_ID,
                "detail_level": "high",
                "images": [{"type": "simulated", "tokens": simulated_image_tokens}],
                "total_image_tokens": simulated_image_tokens
            },
            "estimated_text_tokens": simulated_text_tokens,
            "detail_level": "high",
            "fallback": True
        }
    }


async def _assess_images_parallel(
    assessor: ImageAssessor,
    image_tasks: List[Dict[str, Any]],
    reference_image_data: Optional[Tuple[str, str]]
) -> List[Dict[str, Any]]:
    """Process multiple image assessments in parallel."""
    
    async def assess_single_image(task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess a single image with error handling."""
        try:
            result = await assessor.assess_image_async(
                image_path=task_data["image_path"],
                visual_concept=task_data["visual_concept"],
                creativity_level=task_data["creativity_level"],
                has_reference_image=task_data["has_reference_image"],
                render_text_enabled=task_data["render_text_enabled"],
                task_type=task_data["task_type"],
                platform=task_data["platform"],
                reference_image_data=reference_image_data
            )
            return {
                "image_index": task_data["image_index"],
                "status": "success",
                "result": result
            }
        except Exception as e:
            return {
                "image_index": task_data["image_index"],
                "status": "error",
                "error": str(e)
            }
    
    # Run all assessments in parallel
    tasks = [assess_single_image(task_data) for task_data in image_tasks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any exceptions that weren't caught
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "image_index": image_tasks[i]["image_index"],
                "status": "error", 
                "error": str(result)
            })
        else:
            processed_results.append(result)
    
    return processed_results


async def run(ctx: PipelineContext) -> None:
    """Main entry point for image assessment stage."""
    ctx.log("Starting image assessment stage")
    
    # Validate prerequisites
    if not ctx.generated_image_results or len(ctx.generated_image_results) == 0:
        ctx.log("No generated images found for assessment")
        return
    
    visual_concepts = ctx.generated_image_prompts
    if not visual_concepts or len(visual_concepts) == 0:
        ctx.log("No visual concepts found from creative expert stage")
        return
    
    # Initialize assessor with configured client
    assessor = ImageAssessor(
        model_id=IMAGE_ASSESSMENT_MODEL_ID,
        client=base_llm_client_image_assessment
    )
    
    # Prepare reference image data if available
    reference_image_data = None
    if ctx.image_reference:
        ref_base64 = ctx.image_reference.get("image_content_base64")
        ref_filename = ctx.image_reference.get("filename", "")
        if ref_base64 and ref_filename:
            ref_content_type = assessor._get_content_type_from_filename(ref_filename)
            reference_image_data = (ref_base64, ref_content_type)
    
    # Prepare tasks for parallel processing
    image_tasks = []
    
    for image_result in ctx.generated_image_results:
        if image_result.get("status") != "success":
            ctx.log(f"Skipping assessment for failed image generation (index {image_result.get('index', 'unknown')})")
            continue
            
        image_filename = image_result.get("result_path")
        if not image_filename:
            ctx.log(f"No image path found for result index {image_result.get('index', 'unknown')}")
            continue
        
        # Construct full path using output directory + filename
        image_path = None
        
        if hasattr(ctx, 'output_directory') and ctx.output_directory:
            image_path = os.path.join(ctx.output_directory, image_filename)
        else:
            # Fallback: try to find the output directory from any previous stage
            data_dir = os.path.join(os.getcwd(), "data", "runs")
            if os.path.exists(data_dir):
                for dir_name in os.listdir(data_dir):
                    run_dir_path = os.path.join(data_dir, dir_name)
                    if os.path.isdir(run_dir_path):
                        potential_image_path = os.path.join(run_dir_path, image_filename)
                        if os.path.exists(potential_image_path):
                            image_path = potential_image_path
                            ctx.log(f"Found image in run directory: {image_path}")
                            break
            
            # If still not found, try filename as-is (relative to current directory)
            if image_path is None:
                image_path = image_filename
        
        # Find corresponding visual concept
        image_index = image_result.get("index", 0)
        visual_concept = None
        for concept in visual_concepts:
            if concept.get("source_strategy_index") == image_index:
                visual_concept = concept.get("visual_concept", {})
                break
        
        if not visual_concept:
            ctx.log(f"No visual concept found for image index {image_index}")
            continue
        
        # Determine assessment context
        has_reference_image = bool(reference_image_data)
        render_text_enabled = bool(ctx.render_text)
        task_type = ctx.task_type or "Marketing Asset"
        platform = ctx.target_platform.get("name", "Unknown Platform") if ctx.target_platform else "Unknown Platform"
        
        # Add to parallel processing queue
        image_tasks.append({
            "image_index": image_index,
            "image_path": image_path,
            "visual_concept": visual_concept,
            "creativity_level": ctx.creativity_level,
            "has_reference_image": has_reference_image,
            "render_text_enabled": render_text_enabled,
            "task_type": task_type,
            "platform": platform
        })
    
    # Process all images in parallel
    ctx.log(f"Processing {len(image_tasks)} images in parallel")
    
    try:
        # Run parallel assessments
        parallel_results = await _assess_images_parallel(assessor, image_tasks, reference_image_data)
        
        # Initialize aggregated usage tracking (dictionary format for cost calculation compatibility)
        if "image_assessment" not in ctx.llm_usage:
            ctx.llm_usage["image_assessment"] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "image_tokens": 0,
                "text_tokens": 0,
                "model": IMAGE_ASSESSMENT_MODEL_ID,
                "assessment_count": 0,
                "individual_assessments": []
            }
        
        stage_usage = ctx.llm_usage["image_assessment"]
        assessment_results = []
        
        # Process results and aggregate usage
        for parallel_result in parallel_results:
            image_index = parallel_result["image_index"]
            
            if parallel_result["status"] == "success":
                assessment_result = parallel_result["result"]
                
                # Extract token info for aggregation
                token_info = assessment_result.pop("_token_info", {})
                
                # Log results
                general_score = assessment_result.get("general_score", 0)
                tokens_used = token_info.get("total_tokens", 0)
                
                ctx.log(f"✅ Assessment completed - Image {image_index + 1}: General score: {general_score:.1f}/5, Tokens: {tokens_used}")
                
                # Check refinement flags
                flags = {
                    'needs_subject_repair': assessment_result.get('needs_subject_repair', False),
                    'needs_regeneration': assessment_result.get('needs_regeneration', False),
                    'needs_text_repair': assessment_result.get('needs_text_repair', False)
                }
                
                if any(flags.values()):
                    flag_names = [k for k, v in flags.items() if v]
                    ctx.log(f"Refinement flags triggered for image {image_index + 1}: {', '.join(flag_names)}")
                else:
                    ctx.log(f"No refinement flags triggered for image {image_index + 1}")
                
                # Aggregate token usage
                current_prompt = token_info.get("prompt_tokens", 0)
                current_completion = token_info.get("completion_tokens", 0)
                current_total = token_info.get("total_tokens", 0)
                
                image_breakdown = token_info.get("image_token_breakdown", {})
                current_image_tokens = image_breakdown.get("total_image_tokens", 0)
                current_text_tokens = token_info.get("estimated_text_tokens", current_prompt - current_image_tokens)
                
                stage_usage["prompt_tokens"] += current_prompt
                stage_usage["completion_tokens"] += current_completion
                stage_usage["total_tokens"] += current_total
                stage_usage["image_tokens"] += current_image_tokens
                stage_usage["text_tokens"] += current_text_tokens
                stage_usage["assessment_count"] += 1
                
                # Store individual assessment for detailed reference
                stage_usage["individual_assessments"].append({
                    "image_index": image_index,
                    "prompt_tokens": current_prompt,
                    "completion_tokens": current_completion,
                    "total_tokens": current_total,
                    "image_tokens": current_image_tokens,
                    "text_tokens": current_text_tokens,
                    "image_breakdown": image_breakdown
                })
                
                # Store result (without _meta to avoid duplication)
                assessment_results.append({
                    "image_index": image_index,
                    "image_path": [task for task in image_tasks if task["image_index"] == image_index][0]["image_path"],
                    **assessment_result
                })
                
            else:
                # Handle assessment failure with fallback
                error_msg = parallel_result.get("error", "Unknown error")
                ctx.log(f"Assessment failed for image {image_index + 1}: {error_msg}")
                ctx.log(f"Using simulation fallback for image {image_index + 1}")
                
                # Get task data for fallback
                task_data = [task for task in image_tasks if task["image_index"] == image_index][0]
                
                assessment_result = _create_simulation_fallback(
                    task_data["has_reference_image"], 
                    task_data["render_text_enabled"]
                )
                
                # Calculate general score and refinement flags for fallback
                general_score = assessor._calculate_general_score(assessment_result["assessment_scores"])
                assessment_result["general_score"] = general_score
                refinement_flags = assessor._calculate_refinement_flags(
                    assessment_result, 
                    task_data["has_reference_image"], 
                    task_data["render_text_enabled"]
                )
                assessment_result.update(refinement_flags)
                
                # Extract token info for aggregation
                token_info = assessment_result.pop("_token_info", {})
                
                # Aggregate fallback token usage
                current_prompt = token_info.get("prompt_tokens", 0)
                current_completion = token_info.get("completion_tokens", 0)
                current_total = token_info.get("total_tokens", 0)
                
                image_breakdown = token_info.get("image_token_breakdown", {})
                current_image_tokens = image_breakdown.get("total_image_tokens", 0)
                current_text_tokens = token_info.get("estimated_text_tokens", current_prompt - current_image_tokens)
                
                stage_usage["prompt_tokens"] += current_prompt
                stage_usage["completion_tokens"] += current_completion
                stage_usage["total_tokens"] += current_total
                stage_usage["image_tokens"] += current_image_tokens
                stage_usage["text_tokens"] += current_text_tokens
                stage_usage["assessment_count"] += 1
                
                # Store individual assessment for detailed reference
                stage_usage["individual_assessments"].append({
                    "image_index": image_index,
                    "prompt_tokens": current_prompt,
                    "completion_tokens": current_completion,
                    "total_tokens": current_total,
                    "image_tokens": current_image_tokens,
                    "text_tokens": current_text_tokens,
                    "image_breakdown": image_breakdown,
                    "fallback": True
                })
                
                # Store result (without _meta to avoid duplication)
                assessment_results.append({
                    "image_index": image_index,
                    "image_path": task_data["image_path"],
                    **assessment_result
                })
        
        # Log final aggregated usage
        ctx.log(f"Parallel processing completed: {stage_usage['total_tokens']} total tokens "
               f"({stage_usage['image_tokens']} image + {stage_usage['text_tokens']} text + {stage_usage['completion_tokens']} completion) "
               f"across {stage_usage['assessment_count']} assessments")
        
        # Calculate consistency metrics for STYLE_RECIPE presets
        if hasattr(ctx, 'preset_type') and ctx.preset_type == "STYLE_RECIPE":
            await _calculate_consistency_metrics(ctx, assessment_results)
        
    except Exception as e:
        ctx.log(f"Parallel processing failed: {str(e)}")
        ctx.log(f"Traceback: {traceback.format_exc()}")
        assessment_results = []
    
    # Store results in pipeline context
    if assessment_results:
        ctx.image_assessments = assessment_results
        ctx.log(f"Image assessment completed for {len(assessment_results)} images (processed in parallel)")
    else:
        ctx.log("No images were successfully assessed")
    
    ctx.log("Image assessment stage completed")


async def _calculate_consistency_metrics(ctx: PipelineContext, assessment_results: List[Dict[str, Any]]) -> None:
    """Calculate consistency metrics for STYLE_RECIPE presets."""
    try:
        from churns.core.metrics import calculate_consistency_metrics
        from churns.api.database import PresetType
        
        ctx.log("🔍 Calculating consistency metrics for STYLE_RECIPE preset")
        
        # Get the original image path from the preset data
        original_image_path = None
        if ctx.preset_data and ctx.preset_data.get('original_image_path'):
            original_image_path = ctx.preset_data['original_image_path']
        else:
            # Try to get from the preset metadata (if available)
            ctx.log("Warning: No original image path found in preset data")
            return
        
        # Check if the original image exists
        if not os.path.exists(original_image_path):
            ctx.log(f"Warning: Original image not found at {original_image_path}")
            return
        
        # Calculate consistency metrics for each generated image
        for result in assessment_results:
            try:
                image_path = result.get("image_path")
                if not image_path or not os.path.exists(image_path):
                    ctx.log(f"Warning: Generated image not found at {image_path}")
                    continue
                
                # Calculate consistency metrics
                metrics = calculate_consistency_metrics(
                    original_image_path=original_image_path,
                    new_image_path=image_path,
                    original_recipe=ctx.preset_data
                )
                
                # Add metrics to assessment result
                result["consistency_metrics"] = metrics
                
                # Log the metrics
                clip_score = metrics.get("clip_similarity")
                hist_score = metrics.get("color_histogram_similarity")
                overall_score = metrics.get("overall_consistency_score")
                
                ctx.log(f"Consistency metrics for image {result.get('image_index', 'unknown')}: "
                       f"CLIP={clip_score:.3f if clip_score else 'N/A'}, "
                       f"Color={hist_score:.3f if hist_score else 'N/A'}, "
                       f"Overall={overall_score:.3f if overall_score else 'N/A'}")
                
            except Exception as e:
                ctx.log(f"Error calculating consistency metrics for image {result.get('image_index', 'unknown')}: {e}")
                result["consistency_metrics"] = {"error": str(e)}
        
        ctx.log("✅ Consistency metrics calculation completed")
        
    except Exception as e:
        ctx.log(f"Error in consistency metrics calculation: {e}")
        ctx.log(f"Traceback: {traceback.format_exc()}")
        # Don't fail the stage - just log the error 