import os
import cv2
import json
import logfire
import logging
import numpy as np
from PIL import Image, ImageOps
from typing import Dict, Any, Optional, List
from pydantic_ai import Agent, RunContext, Tool, ModelRetry
from ..api.schemas import ImageAgentInput, ImageAgentOutput, PlannerOutput, PromptOutput
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger("image-agent")
load_dotenv('.env', override=True)

def make_transparent(input_path: str, alpha: int) -> Optional[str]:
    """
    Adjust the transparency of an image.
    """
    image = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)

    if image is None:
        logger.error(f"Could not load image at {input_path}")
        return None
    if image.shape[2] != 4:
        logger.error("Image does not have an alpha channel")
        return None
    
    bgr_channel = image[:, :, :3]
    alpha_channel = image[:, :, 3]
    alpha_ratio = alpha / 255
    partial_alpha = (alpha_channel * alpha_ratio).astype(np.uint8)
    result_image = np.dstack((bgr_channel, partial_alpha))
    os.makedirs("test-results", exist_ok=True)
    output_path = os.path.join("test-results", 'make_transparent.png')
    cv2.imwrite(output_path, result_image)
    logger.info(f"make_transparent output saved to {output_path}")
    return output_path

def convert_to_single_tone(input_path: str, hex_color: str) -> Optional[str]:
    """
    Convert an image to a single tone color.
    """
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    tone_color = (rgb[2], rgb[1], rgb[0])  # Convert to BGR for OpenCV

    image = cv2.imread(input_path, cv2.IMREAD_UNCHANGED) 
    
    if image is None:
        logger.error(f"Could not load image at {input_path}")
        return None
    if image.shape[2] != 4:
        logger.error("Image does not have an alpha channel")
        return None

    bgr = image[:, :, :3]
    alpha = image[:, :, 3]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    
    # Create a solid color image with the same size
    tone = np.full_like(gray_bgr, tone_color, dtype=np.uint8)
    
    result = cv2.addWeighted(gray_bgr, 0.5, tone, 0.5, 0.0)
    result = cv2.merge([result[:,:,0], result[:,:,1], result[:,:,2], alpha])

    os.makedirs("test-results", exist_ok=True)
    output_path = os.path.join("test-results", 'convert_to_single_tone.png')
    cv2.imwrite(output_path, result)
    logger.info(f"convert_to_single_tone output saved to {output_path}")
    return output_path

def get_image_size(input_path: str) -> Dict[str, int]:
    """
    Get the dimensions of an image.
    """
    try:
        logger.info(f"get_image_size with input_path = {input_path}")
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Image of path {input_path} not found")
        
        with Image.open(input_path) as img:
            logger.info(f"Image size = {img.width}x{img.height}")
            return {
                "width": img.width,
                "height": img.height
            }
    except Exception as e:
        logger.error(f"Failed to get image size: {str(e)}")
        raise

def overlay_on_base(
    ctx: RunContext[ImageAgentInput],
    base_path: str,
    overlay_path: str,
    alpha_value: int = 128,
    hex_color: Optional[str] = None,
    position: Optional[list[int]] = None,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """Overlay one image on top of another with optional transparency and color effects.
    
    The position parameter should be a list of two integers [x, y] representing the 
    top-left corner where the overlay should be placed on the base image.
    
    If position is None, the overlay will be automatically positioned at the 
    bottom-right corner with padding.

    Args:
        ctx: RunContext containing the dependencies
        base_path: Path to the base image
        overlay_path: Path to the overlay image
        alpha_value: Transparency value (0-255)
        hex_color: Hex color code for color effects (e.g., '#FF0000' for red)
        position: Optional list of two integers [x, y] coordinates for the overlay position.
        scale: Scale factor for the overlay image (1.0 = original size)
        
    Returns:
        Dict containing the processing result with output path and metadata
    """        
    try:
        # Validate file paths
        if not os.path.exists(base_path):
            raise ModelRetry(f"Base image not found at: {base_path}")
        if not os.path.exists(overlay_path):
            raise ModelRetry(f"Overlay image not found at: {overlay_path}")
            
        logger.info(f"Processing overlay: base={base_path}, overlay={overlay_path}")

        # Apply transparency and color effects
        overlay_img_path = make_transparent(input_path=overlay_path, alpha=alpha_value)
        if hex_color and overlay_img_path:
            overlay_img_path = convert_to_single_tone(
                input_path=overlay_img_path, 
                hex_color=hex_color
            )
            if not overlay_img_path:
                raise ValueError("Failed to apply color to overlay image")

        # Open and prepare images
        with Image.open(base_path) as _base_img, Image.open(overlay_img_path) as _overlay_img:
            base_img = ImageOps.exif_transpose(_base_img).convert('RGBA')
            overlay_img = ImageOps.exif_transpose(_overlay_img).convert('RGBA')

        # Scale the overlay image if needed
        resized_overlay_img = overlay_img
        if scale != 1.0:
            new_width = int(base_img.width * scale)
            ratio = new_width / overlay_img.width
            new_height = int(overlay_img.height * ratio)
            
            resized_overlay_img = overlay_img.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )
            logger.info(f"Scaled overlay to {new_width}x{new_height}")

        # Determine position (default to bottom-right with padding)
        if position is None:
            padding = 50
            x = base_img.width - resized_overlay_img.width - padding
            y = base_img.height - resized_overlay_img.height - padding
            position = (max(0, x), max(0, y))
            logger.info(f"Auto-positioned at {position} with {padding}px padding")
        else:
            position = tuple(position)

        # Create the composite image
        composite_image = base_img.copy()
        composite_image.paste(resized_overlay_img, position, mask=resized_overlay_img)
        
        # Save the result
        output_dir = "test-results"
        os.makedirs(output_dir, exist_ok=True)
        base_filename = os.path.splitext(os.path.basename(base_path))[0]
        output_path = os.path.join(output_dir, f"{base_filename}_overlay.png")
        composite_image.save(output_path, 'PNG')

        result = {
            "status": "success",
            "output_path": output_path,
            "base_dimensions": {"width": base_img.width, "height": base_img.height},
            "overlay_dimensions": {"width": resized_overlay_img.width, "height": resized_overlay_img.height},
            "position_used": position,
            "scale_used": scale
        }
        
        logger.info(f"Image overlay successful. Result saved to: {output_path}")
        return result

    except Exception as e:
        logger.error(f"Error in overlay_on_base: {e}")
        raise

class ImageProcessingAgent:

    def __init__(self):
        logfire.configure(
            token=os.getenv("LOGFIRE_TOKEN"),
            service_name='image-agent'
        )
        logfire.instrument_pydantic_ai()

    def _create_prompt_agent(self) -> Agent:
        """
        Create and configure a prompt agent for generating image processing instructions.
        """
        return Agent(
            'openai:gpt-5-nano',
            name='prompt-agent',
            output_type=PromptOutput,
            system_prompt=(
                """
                You are a prompt generator agent. Your task is to generate an input instruction for my image processing agent that overlays a logo image on top of a base image.
                Use the provided visual concept to guide the instruction.
                Include the following parameters if possible:
                - hex_color: hex code tint for the logo
                - alpha_value: transparency level of the logo
                - position: where to place the logo on the base image
                - scale: relative size of the logo compared to the base image
                If any parameters cannot be determined, omit them.
                The prompt must be written in an instructive tone, directly addressing the image processing agent.
                Keep the instruction concise, specific, and actionable. Do not mention any elements from the image example the food / drinks.
                Example: Overlay the logo on the image at the bottom-right corner, scale it to 50% of the base image size, and apply a #6a5acd color tint.
                """
            ),
            retries=3,
        )

    def _create_planner_agent(self, planner_deps: ImageAgentInput) -> Agent:
        """
        Create and configure a planner agent.
        """
        return Agent(
            'openai:gpt-5-mini',
            name='planner-agent',
            output_type=PlannerOutput,
            system_prompt=(
                f"""
                You are a planning agent. When the user makes a request about image processing, 
                generate a minimal and correct plan using the available tools.
                
                You are provided with a user input dependency:
                - base_path: {planner_deps.base_path}
                - image_path: {planner_deps.image_path}
                
                AVAILABLE TOOLS:
                1. overlay_on_base(
                        base_path: str, 
                        overlay_path: str, 
                        hex_color: Optional[str],
                        alpha_value: int = 128, 
                        position: Optional[list[int]] = None, 
                        scale: Optional[float] = 0.4,
                   ) -> Dict[str, Any]
                   - base_path: Path to the base image
                   - overlay_path: Path to the image to overlay
                   - hex_color: Hex code for color of the overlay image (default: None)
                   - alpha_value: transparency level the overlay image (default: 128)
                   - position: [x, y] coordinates of the left top corner for overlay
                   - scale: relative size of the overlay (default: 0.2)

                RULES:
                - Use only the tools listed.
                - Return at most 5 steps.
                - Prefer the simplest plan that satisfies the request.
                - Always provide required parameters. Include optional parameters only if different from defaults.
                - Explain your reasoning for parameter choices in the rationale.

                OUTPUT FORMAT (PlannerOutput)
                - rationale: explain tool usage and parameter deductions.
                - steps: list of steps, each step is a dictionary:
                    tool: tool name
                    args: arguments for the tool
                """
            ),
            retries=3
        )

    def _format_execution_prompt(self, user_prompt: str, plan_steps: List[Any]) -> str:
        """
        Format the execution prompt with the user's request and the plan steps.
        """
        step_str = ""
        for idx, step in enumerate(plan_steps):
            step_str += f"Step {idx+1}: {step.tool} - {step.args}\n"
        
        return f"""
        User Request: {user_prompt}
        
        Plan to execute:
        {step_str}
        """

    def _create_vision_agent(self) -> Agent:
        """
        Create and configure a vision agent.
        
        Returns:
            Configured Agent instance
        """
        return Agent(
            'openai:gpt-4.1-mini',
            name='vision-executor-agent',
            deps_type=ImageAgentInput,
            output_type=ImageAgentOutput,
            system_prompt=(
                """
                You're a helpful vision tool executor. 
                You will be given a plan and you will execute the plan step by step.
                Additionally, you are provided with a user input dependency.
                ** DO NOT ** run any other tools except the tools listed above.
                
                Helpful Tips:
                - You are provided with ctx.deps which refers to the dependencies provided by the user 
                  (it contains the base image path and overlay image path)
                - The base image can be obtained from the base path field of ctx.deps if not provided
                - The overlay image can be obtained from the image path field of ctx.deps if not provided
                - If the overlay position isn't provided, it will be placed at the bottom-right corner.
                - If the overlay image size is not provided, it will be scaled to 20% of the base image.
                - If you can't process an image, you'll return an error message.
                - Do not change the orientation of any images.

                Your output will be a dictionary with the following keys:
                    image_path: The path to the processed image file.
                    message: A message detailing the outcome.
                """
            ),
            retries=3,
            tools=[
                Tool(overlay_on_base, takes_ctx=True, max_retries=3),
            ]
        )


    async def process_image(
        self, 
        visual_context: Dict[str, Any],
        base_image_path: str, 
        overlay_image_path: str, 
        output_dir: str = "test-results"
    ) -> Dict[str, Any]:
        """
        Process an image based on the visual context.
        
        Args:
            visual_context: Dictionary containing visual concept and styling information
            base_image_path: Path to the base image
            overlay_image_path: Path to the overlay/logo image
            output_dir: Directory to save output files
            
        Returns:
            Dictionary containing the processing result
        """        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Prepare input dependencies
            input_deps = ImageAgentInput(
                base_path=base_image_path,
                image_path=overlay_image_path
            )
            
            # Generate the input prompt using the visual context
            prompt_agent = self._create_prompt_agent()
            prompt_result = await prompt_agent.run(
                f"""
                Please generate a clear instruction for the image processing agent based on this visual concept:
                {json.dumps(visual_context, indent=2)}
                
                The agent will overlay the image at {overlay_image_path} onto {base_image_path}.
                """
            )
            input_prompt = prompt_result.output.prompt
            logger.info(f"Prompt generated: {input_prompt}")
            
            # Add image size information to the planner's context
            planner_agent = self._create_planner_agent(input_deps)
            @planner_agent.system_prompt  
            async def add_image_size(ctx: RunContext[ImageAgentInput]) -> str:
                base_image_size = get_image_size(ctx.deps.base_path)
                overlay_image_size = get_image_size(ctx.deps.image_path)
                return f"""
                    The base image size is {base_image_size} and 
                    the overlay image size is {overlay_image_size}
                """
            
            # Generate the plan
            logger.info("Generating processing plan...")
            planning_result = await planner_agent.run(input_prompt, deps=input_deps)
            logger.info(f"Planning completed: {planning_result.output}")
            
            # Format and log the execution prompt
            execution_prompt = self._format_execution_prompt(input_prompt, planning_result.output.steps)
            logger.info(f"Executing plan:\n{execution_prompt}")
            
            # Execute the plan with the vision agent
            vision_agent = self._create_vision_agent()
            final_result = await vision_agent.run(execution_prompt, deps=input_deps)
            
            logger.info(f"Image processing completed: {final_result.output}")
            return {
                "status": "success",
                "output": final_result.output,
                "plan": planning_result.output.dict()
            }
            
        except Exception as e:
            error_msg = f"Error processing image: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "message": error_msg,
                "error": str(e)
            }
