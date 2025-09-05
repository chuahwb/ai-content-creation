import os
from typing import Dict, Tuple
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class UserSettings(BaseModel):
    presentation_mode: bool = False

def get_user_settings():
    """Get user settings from environment variables"""
    presentation_mode = os.getenv('PRESENTATION_MODE', 'false').lower() in ('true', '1', 'yes', 'on')
    return UserSettings(presentation_mode=presentation_mode)

def get_presentation_mode_config(pipeline_mode: str = "generation") -> Tuple[int, Dict]:
    """Get presentation mode configuration for different pipeline types"""
    
    if pipeline_mode == "refinement":
        total_stages = 3
        presentation_messages = {
            1: "Loading reference image...",
            2: "Applying refinement...",
            3: "Saving refined image...",
        }
    elif pipeline_mode == "caption":
        total_stages = 1
        presentation_messages = {
            1: "Generating social media caption...",
        }
    else:  # generation mode (default)
        total_stages = 7
        presentation_messages = {
            0.5: "Adapting visual style...",
            1: "Analyzing brand and style...",
            1.5: "Adapting visual style...", 
            2: "Developing creative strategy...",
            2.5: "Adapting visual style...",
            3: "Defining visual guidelines...",
            3.5: "Adapting visual style...",
            4: "Generating creative concepts...",
            4.5: "Adapting visual style...",
            5: "Assembling final prompt...",
            5.5: "Adapting visual style...",
            6: "Generating images...",
            6.5: "Adapting visual style...",
            7: "Assessing image quality...",
        }
    
    return total_stages, presentation_messages

def obfuscate_stage_name(stage_order: float, pipeline_mode: str = "generation", has_style_adaptation: bool = False) -> Tuple[str, str]:
    """Generate obfuscated stage name and message for presentation mode"""
    total_stages, presentation_messages = get_presentation_mode_config(pipeline_mode)
    
    # Handle fractional stage orders (like style_adaptation at 4.5)
    if stage_order in presentation_messages:
        # For generation pipeline with fractional stages, always use 8-step format for consistency
        if pipeline_mode == "generation" and (stage_order % 1 != 0):
            # This is a fractional stage (style adaptation), use 8-step format
            stage_order_to_step = {
                1: 1,    # image_eval
                2: 2,    # strategy (skipped in style adaptation)
                3: 3,    # style_guide (skipped in style adaptation)
                4: 4,    # creative_expert (skipped in style adaptation)
                4.5: 5,  # style_adaptation
                5: 6,    # prompt_assembly
                6: 7,    # image_generation
                7: 8,    # image_assessment
            }
            
            if stage_order in stage_order_to_step:
                step_num = stage_order_to_step[stage_order]
                stage_name = f"Step {step_num} of 8"
                message = presentation_messages.get(stage_order, "Processing...")
            else:
                stage_name = f"Step {int(stage_order)} of 8"
                message = "Processing..."
        else:
            # Regular generation pipeline or other pipeline types
            if stage_order == int(stage_order):  # Whole number
                step_num = int(stage_order)
                stage_name = f"Step {step_num} of {total_stages}"
            else:  # This shouldn't happen for non-generation pipelines
                step_num = int(stage_order)
                stage_name = f"Step {step_num} of {total_stages}"
            message = presentation_messages.get(stage_order, "Processing...")
    else:
        # Fallback for unexpected stage orders
        if stage_order <= 0:
            stage_name = "Initialization"
            message = "Preparing pipeline..."
        elif stage_order > total_stages:
            stage_name = f"Step {total_stages} of {total_stages}"
            message = "Finalizing..."
        else:
            stage_name = f"Step {int(stage_order)} of {total_stages}"
            message = "Processing..."
    
    return stage_name, message
