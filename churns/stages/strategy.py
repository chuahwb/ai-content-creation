"""Marketing Strategy Generation Stage

This stage generates N diverse marketing strategy combinations using a 2-stage LLM approach:
1. Stage 1: Niche Identification - identifies relevant F&B niches for the context
2. Stage 2: Goal Combination Generation - generates marketing goal combinations

Extracted from the original monolithic pipeline to preserve 100% of the logic.
"""

import json
import random
import time
import traceback
from typing import Dict, Any, List, Optional, Tuple

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_strategy = None
base_llm_client_strategy = None
STRATEGY_MODEL_ID = None
STRATEGY_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []

# Import task group pools from constants
from churns.core.constants import TASK_GROUP_POOLS
from churns.core.json_parser import RobustJSONParser, JSONExtractionError
from churns.models import (
    RelevantNicheList,
    MarketingGoalSetStage2,
    MarketingStrategyOutputStage2,
    MarketingGoalSetFinal
)
from churns.pipeline.context import PipelineContext

def get_pools_for_task(task_type_str: Optional[str]) -> Dict[str, List[str]]:
    """Returns the appropriate marketing goal option pools based on the task type string."""
    if not task_type_str: return TASK_GROUP_POOLS["default"]
    if task_type_str.startswith('1.') or task_type_str.startswith('4.'): return TASK_GROUP_POOLS["product_focus"]
    if task_type_str.startswith('2.'): return TASK_GROUP_POOLS["promotion"]
    if task_type_str.startswith('3.') or task_type_str.startswith('5.') or task_type_str.startswith('7.') or task_type_str.startswith('8.'): return TASK_GROUP_POOLS["brand_atmosphere"]
    if task_type_str.startswith('6.'): return TASK_GROUP_POOLS["informative"]
    return TASK_GROUP_POOLS["default"]


def simulate_marketing_strategy_fallback_staged(
    user_goals: Optional[Dict], 
    identified_niches: List[str], 
    task_type: Optional[str], 
    num_strategies: int = 3
) -> List[Dict[str, Any]]:
    """Provides N simulated marketing strategies for the staged approach."""
    if not MarketingGoalSetFinal:
        return [{"error": "Pydantic model MarketingGoalSetFinal not defined"}] * num_strategies

    task_pools = get_pools_for_task(task_type)
    audience_pool = task_pools.get("audience", TASK_GROUP_POOLS["default"]["audience"])
    objective_pool = task_pools.get("objective", TASK_GROUP_POOLS["default"]["objective"])
    voice_pool = task_pools.get("voice", TASK_GROUP_POOLS["default"]["voice"])
    strategies = []
    used_combinations = set()
    if not isinstance(identified_niches, list) or not identified_niches:
        identified_niches = [random.choice(TASK_GROUP_POOLS["default"]["niche"])]

    user_provided_niche = (user_goals or {}).get('niche')
    user_provided_audience = (user_goals or {}).get('target_audience')
    user_provided_objective = (user_goals or {}).get('objective')
    user_provided_voice = (user_goals or {}).get('voice')

    for i in range(num_strategies):
        current_niche = user_provided_niche if user_provided_niche else identified_niches[i % len(identified_niches)]
        sim_audience = user_provided_audience or random.choice(audience_pool)
        sim_objective = user_provided_objective or random.choice(objective_pool)
        sim_voice = user_provided_voice or random.choice(voice_pool)
        current_goals = {
            "target_audience": sim_audience, "target_niche": current_niche,
            "target_objective": sim_objective, "target_voice": sim_voice
        }
        if user_goals and all((user_goals or {}).get(k) for k in ['target_audience', 'objective', 'voice', 'niche']) and i > 0:
            current_goals["target_objective"] += f" (SimVar {i})"
        combination_tuple = tuple(current_goals.values())
        attempts = 0
        while combination_tuple in used_combinations and attempts < 10:
            current_goals["target_objective"] = random.choice(objective_pool) + f" (AltSim {attempts})"
            combination_tuple = tuple(current_goals.values())
            attempts += 1
        if combination_tuple not in used_combinations:
            try:
                strategies.append(MarketingGoalSetFinal(**current_goals).model_dump())
                used_combinations.add(combination_tuple)
            except Exception as e:
                strategies.append({"error": f"Fallback strategy {i+1} creation failed: {e}", "target_niche": current_niche})
        elif len(strategies) < num_strategies:
             strategies.append({"error": "Could not generate unique fallback strategy", "target_niche": current_niche, **current_goals})
    while len(strategies) < num_strategies:
        if strategies: strategies.append(strategies[0]) # Duplicate first if any exist
        else: strategies.append({"error": "Fallback failed completely", "target_niche": identified_niches[0] if identified_niches else "DefaultNiche"})
    return strategies[:num_strategies] # Ensure exact number


def run(ctx: PipelineContext) -> None:
    """Generates N diverse marketing strategy combinations using a STAGED LLM approach."""
    ctx.log("Starting marketing strategy generation stage")
    
    # Get number of strategies from context, fallback to default
    num_strategies = getattr(ctx, 'num_variants', None)
    if num_strategies is None:
        # Try to get from data dict for backward compatibility
        num_strategies = ctx.data.get("request_details", {}).get("num_variants", 3) if ctx.data else 3
    # Ensure it's within valid range
    num_strategies = max(1, min(6, num_strategies))  # Clamp between 1 and 6
    
    # Extract inputs from context using direct attributes
    user_goals = ctx.marketing_goals
    user_goals_complete = bool(user_goals and all(user_goals.get(k) for k in ['target_audience', 'objective', 'voice', 'niche']))

    status_message = f"Generating {num_strategies} marketing strategy suggestions..."
    if user_goals_complete: 
        status_message = f"User provided complete marketing goals. Generating {num_strategies} variations..."
    ctx.log(status_message)

    task_type = ctx.task_type or "N/A"
    user_prompt_input = ctx.prompt
    task_description = ctx.task_description
    image_analysis = ctx.image_analysis_result
    image_subject = "N/A"
    if isinstance(image_analysis, dict): 
        image_subject = image_analysis.get("main_subject", "Analysis Failed" if "error" in image_analysis else "N/A")

    task_pools = get_pools_for_task(task_type)
    niche_pool_inspiration = task_pools.get("niche", TASK_GROUP_POOLS["default"]["niche"])

    # Initialize centralized JSON parser
    json_parser = RobustJSONParser(debug_mode=False)

    # Stage 1: Niche Identification
    identified_niches = []
    stage1_status = "Starting Niche Identification..."
    ctx.log(f"  Stage 1: {stage1_status}")
    stage1_status_code = 'INIT'
    num_niches_to_find = 3
    user_provided_niche = (user_goals or {}).get('niche')
    usage_info_stage1 = None
    stage1_duration = 0.0

    # Use global client variables (injected by pipeline executor)
    client_to_use_strat = instructor_client_strategy if instructor_client_strategy and not FORCE_MANUAL_JSON_PARSE else base_llm_client_strategy
    use_instructor_for_strat_call = bool(instructor_client_strategy and not FORCE_MANUAL_JSON_PARSE)

    if user_goals_complete and user_provided_niche:
        identified_niches = [user_provided_niche]
        stage1_status = f"Using user-provided complete goals. Niche fixed to: '{user_provided_niche}'."
        stage1_status_code = 'USER_PROVIDED_COMPLETE'
    elif user_provided_niche:
        identified_niches = [user_provided_niche]
        stage1_status = f"Using user-provided niche: '{user_provided_niche}'. Other goals will be generated."
        stage1_status_code = 'USER_PROVIDED'
    elif client_to_use_strat and RelevantNicheList:
        stage1_call_start_time = time.time()
        try:
            ctx.log(f"    (Attempting LLM call for {num_niches_to_find} Niche Identifications via {STRATEGY_MODEL_PROVIDER} model: {STRATEGY_MODEL_ID}...)")
            niche_system_prompt = f"You are an expert F&B market analyst. Your task is to identify a list of {num_niches_to_find} diverse but MOST relevant F&B niches for the given context. Consider the image subject, task description, and task type. Prioritize the most logical fits. Output ONLY the JSON object matching the Pydantic `RelevantNicheList` model containing the list of niche names."
            niche_user_prompt = f"Identify {num_niches_to_find} diverse but relevant F&B niches for this context:\nTask Type: {task_type or 'N/A'}\nTask-Specific Content/Description: {task_description or 'Not Provided'}\nIdentified Image Subject: {image_subject or 'Not Provided / Not Applicable'}\nDetermine the best `relevant_niches` based on the context. Ensure niches are plausible for the image subject."

            llm_args_niche = {
                "model": STRATEGY_MODEL_ID, 
                "messages": [
                    {"role": "system", "content": niche_system_prompt}, 
                    {"role": "user", "content": niche_user_prompt}
                ], 
                "temperature": 0.4, 
                "max_tokens": 250
            }

            if use_instructor_for_strat_call:
                llm_args_niche["response_model"] = RelevantNicheList

            completion_niche = client_to_use_strat.chat.completions.create(**llm_args_niche)

            if use_instructor_for_strat_call:
                identified_niches = completion_niche.relevant_niches
            else: # Manual parse using centralized parser
                raw_content_niche = completion_niche.choices[0].message.content
                try:
                    parsed_data_niche = json_parser.extract_and_parse(raw_content_niche)
                    # Handle if LLM returns a list directly for relevant_niches
                    if isinstance(parsed_data_niche, list) and "relevant_niches" in RelevantNicheList.model_fields:
                        data_for_pydantic_niche = {"relevant_niches": parsed_data_niche}
                        validated_niche_list = RelevantNicheList(**data_for_pydantic_niche)
                    elif isinstance(parsed_data_niche, dict):
                        validated_niche_list = RelevantNicheList(**parsed_data_niche)
                    else:
                        from pydantic import ValidationError
                        raise ValidationError(f"Parsed JSON for Niche ID is not a list or dict: {type(parsed_data_niche)}")
                    identified_niches = validated_niche_list.relevant_niches
                except JSONExtractionError as parse_err_niche:
                    ctx.log(f"    ERROR: JSON extraction failed for Niche ID: {parse_err_niche}")
                    ctx.log(f"    Raw Niche ID content: {raw_content_niche}")
                    raise Exception(f"Niche ID response parsing error: {parse_err_niche}")
                except Exception as parse_err_niche:
                    ctx.log(f"    ERROR: Manual JSON parsing/validation failed for Niche ID: {parse_err_niche}")
                    ctx.log(f"    Raw Niche ID content: {raw_content_niche}")
                    raise Exception(f"Niche ID response parsing error: {parse_err_niche}")

            raw_response_niche_obj = getattr(completion_niche, '_raw_response', completion_niche)
            if hasattr(raw_response_niche_obj, 'usage') and raw_response_niche_obj.usage: 
                usage_info_stage1 = raw_response_niche_obj.usage.model_dump()
            stage1_status = f"Niches identified via LLM: {identified_niches}"
            stage1_status_code = 'SUCCESS'
        except Exception as e:
            ctx.log(f"    ERROR during Niche Identification LLM call: {e}")
            stage1_status = "Niche Identification LLM call failed. Falling back to simulation."
            identified_niches = random.sample(niche_pool_inspiration, min(len(niche_pool_inspiration), random.randint(1,num_niches_to_find)))
            stage1_status_code = 'API_ERROR'
        finally:
            stage1_duration = time.time() - stage1_call_start_time
            # Cost logging would be handled by the pipeline framework in the future
    else:
        stage1_status = "Niche Identification skipped (Client/Pydantic unavailable or no user niche). Using simulation."
        identified_niches = random.sample(niche_pool_inspiration, min(len(niche_pool_inspiration), random.randint(1,num_niches_to_find)))
        stage1_status_code = 'SIMULATED_NO_API_CONFIG'

    ctx.log(f"    Status (Niche ID): {stage1_status}")
    if not identified_niches:
         ctx.log("    WARNING: No niches identified or simulated, using default.")
         identified_niches = [random.choice(niche_pool_inspiration)]
         stage1_status += " (Used default niche as fallback)"
    ctx.log(f"  Using Niches: {identified_niches} for strategy generation.")

    # Stage 2: Goal Combination Generation
    stage2_status = "Starting Goal Combination Generation..."
    ctx.log(f"  Stage 2: {stage2_status}")
    stage2_status_code = 'INIT'
    suggested_strategies_final = [] # List of MarketingGoalSetFinal dicts
    usage_info_stage2 = None
    stage2_duration = 0.0

    if client_to_use_strat and MarketingStrategyOutputStage2 and MarketingGoalSetStage2 and MarketingGoalSetFinal:
        stage2_call_start_time = time.time()
        try:
            ctx.log(f"    (Attempting LLM call for Goal Combinations via {STRATEGY_MODEL_PROVIDER} model: {STRATEGY_MODEL_ID}...)")
            system_prompt_stage2 = f"You are an expert F&B Marketing Strategist. Your goal is to generate {num_strategies} diverse and strategically sound marketing goal combinations. For each combination: 1. Select ONE niche from the provided 'Relevant Niches List'. If only one niche is provided (especially if it came directly from the user's complete input), ALL strategies must use that niche. Otherwise, aim to use different niches from the list across the {num_strategies} combinations for diversity. 2. Generate a fitting `target_audience`, `target_objective`, and `target_voice` that logically align with the **chosen niche** for that specific combination and the overall context (task type, image subject). **Handling User Input (Very Important):** - If the user provided a value for audience, objective, or voice (or all of them), treat these as **strong thematic guidelines or a complete foundation**. - If the user provided a COMPLETE set of goals (audience, niche, objective, voice), your task is to generate {num_strategies} insightful VARIATIONS or REFINEMENTS based on this foundation. Each variation should be distinct, strategically sound, and explore different angles while staying true to the user's core intent and the fixed niche. Do NOT just copy the user input verbatim for all strategies unless it's the absolute best fit for one specific variation. - If the user provided only PARTIAL goals, generate values for the missing fields that are thematically consistent with the provided ones and the chosen niche. Ensure the {num_strategies} generated combinations are distinct and make sense. Output ONLY the JSON object matching the `MarketingStrategyOutputStage2` model containing a list of exactly {num_strategies} `MarketingGoalSetStage2` objects. The keys in each object inside the list MUST be `target_audience`, `target_objective`, and `target_voice`."
            
            user_goals_guidance_text = ""
            if user_goals_complete: 
                user_goals_guidance_text = f"The user has provided a COMPLETE set of marketing goals as a foundation:\nUser's Target Audience: {user_goals.get('target_audience')}\nUser's Chosen Niche: {user_goals.get('niche')} (All your generated strategies MUST use this niche)\nUser's Target Objective: {user_goals.get('objective')}\nUser's Desired Voice: {user_goals.get('voice')}\nYour task is to generate {num_strategies} distinct and insightful VARIATIONS or REFINEMENTS based on this solid foundation. Explore different angles while adhering to the user's core intent for all four components."
            else: 
                user_goals_guidance_text = f"User-Provided Goals (Use these as strong thematic guidelines for the fields they provided; generate appropriate values for missing fields):\nAudience: {(user_goals or {}).get('target_audience') or 'Not Provided'}\nNiche: {user_provided_niche or 'Not Provided (refer to Relevant Niches List below)'}\nObjective: {(user_goals or {}).get('objective') or 'Not Provided'}\nVoice: {(user_goals or {}).get('voice') or 'Not Provided'}"
            
            platform_name = "N/A"
            if ctx.target_platform:
                platform_name = ctx.target_platform.get("name", "N/A")
            
            user_prompt_context_stage2 = f"Generate {num_strategies} diverse marketing strategy combinations for the following F&B task.\nTask Type: {task_type or 'N/A'}\nTarget Platform: {platform_name}\nUser's General Prompt: {user_prompt_input or 'Not Provided'}\nTask-Specific Content/Description: {task_description or 'Not Provided'}\nIdentified Image Subject: {image_subject or 'Not Provided / Not Applicable'}\n\n**Relevant Niches List (One niche from this list should be used for each strategy. If the user provided a complete set of goals including a niche, that niche is fixed and MUST be used for all strategies):** {identified_niches}\n\n{user_goals_guidance_text}\n\nGenerate {num_strategies} complete, diverse, and strategically relevant combinations. Each item in the 'strategies' list of the output JSON should have keys: `target_audience`, `target_objective`, `target_voice`. Adhere strictly to the output format."

            llm_args_goals = {
                "model": STRATEGY_MODEL_ID, 
                "messages": [
                    {"role": "system", "content": system_prompt_stage2}, 
                    {"role": "user", "content": user_prompt_context_stage2}
                ], 
                "temperature": 0.7, 
                "max_tokens": 1500
            }
            if use_instructor_for_strat_call:
                llm_args_goals["response_model"] = MarketingStrategyOutputStage2

            completion_stage2 = client_to_use_strat.chat.completions.create(**llm_args_goals)

            temp_strategies_stage2 = []
            if use_instructor_for_strat_call:
                temp_strategies_stage2 = [s.model_dump() for s in completion_stage2.strategies]
            else: # Manual parse using centralized parser
                raw_content_goals = completion_stage2.choices[0].message.content
                try:
                    parsed_data_goals = json_parser.extract_and_parse(raw_content_goals)

                    data_for_pydantic_validation = {}

                    # This block handles both when LLM returns a list directly,
                    # or a dict like {"strategies": [...]}, and renames keys.
                    if isinstance(parsed_data_goals, list):
                        # LLM returned a list of strategies directly.
                        # Need to rename keys within each item.
                        transformed_list = []
                        for item in parsed_data_goals:
                            if isinstance(item, dict):
                                transformed_item = {
                                    "target_audience": item.get("audience", item.get("target_audience")),
                                    "target_objective": item.get("objective", item.get("target_objective")),
                                    "target_voice": item.get("voice", item.get("target_voice"))
                                }
                                # Keep only non-None values to avoid Pydantic validation errors if a key was truly missing
                                transformed_list.append({k: v for k, v in transformed_item.items() if v is not None})
                            else:
                                transformed_list.append(item) # Should not happen if LLM follows instructions
                        data_for_pydantic_validation = {"strategies": transformed_list}

                    elif isinstance(parsed_data_goals, dict) and "strategies" in parsed_data_goals and isinstance(parsed_data_goals["strategies"], list):
                        # LLM returned the expected {"strategies": [...]} structure, but keys inside might be wrong.
                        transformed_list = []
                        for item in parsed_data_goals["strategies"]:
                            if isinstance(item, dict):
                                transformed_item = {
                                    "target_audience": item.get("audience", item.get("target_audience")),
                                    "target_objective": item.get("objective", item.get("target_objective")),
                                    "target_voice": item.get("voice", item.get("target_voice"))
                                }
                                transformed_list.append({k: v for k, v in transformed_item.items() if v is not None})
                            else:
                                transformed_list.append(item)
                        data_for_pydantic_validation = {"strategies": transformed_list}
                    else: # Did not get a list or a dict with a "strategies" list
                        from pydantic import ValidationError
                        raise ValidationError(f"Parsed JSON for Goal Gen is not a list or a dict with a 'strategies' list: {type(parsed_data_goals)}")

                    validated_goals_output = MarketingStrategyOutputStage2(**data_for_pydantic_validation)
                    temp_strategies_stage2 = [s.model_dump() for s in validated_goals_output.strategies]

                except JSONExtractionError as parse_err_goals:
                    ctx.log(f"    ERROR: JSON extraction failed for Goal Gen: {parse_err_goals}")
                    ctx.log(f"    Raw Goal Gen content: {raw_content_goals}")
                    raise Exception(f"Goal Gen response parsing error: {parse_err_goals}")
                except Exception as parse_err_goals:
                    ctx.log(f"    ERROR: Manual JSON parsing/validation failed for Goal Gen: {parse_err_goals}")
                    ctx.log(f"    Raw Goal Gen content: {raw_content_goals}")
                    raise Exception(f"Goal Gen response parsing error: {parse_err_goals}")

            for i, strategy_s2_dict in enumerate(temp_strategies_stage2):
                assigned_niche = user_provided_niche if user_goals_complete else identified_niches[i % len(identified_niches)]
                final_strat_dict = {**strategy_s2_dict, 'target_niche': assigned_niche}
                try:
                    suggested_strategies_final.append(MarketingGoalSetFinal(**final_strat_dict).model_dump())
                except Exception as pydantic_error: 
                    ctx.log(f"    WARNING: Failed to validate final strategy structure: {final_strat_dict}. Error: {pydantic_error}")
            
            raw_response_strat_obj = getattr(completion_stage2, '_raw_response', completion_stage2)
            if hasattr(raw_response_strat_obj, 'usage') and raw_response_strat_obj.usage: 
                usage_info_stage2 = raw_response_strat_obj.usage.model_dump()
            
            if len(suggested_strategies_final) != num_strategies: 
                ctx.log(f"    WARNING: LLM generated {len(suggested_strategies_final)} valid strategies, but {num_strategies} were requested.")
            else: 
                ctx.log(f"    Successfully received and validated {len(suggested_strategies_final)} marketing strategies from LLM.")
            stage2_status = "Goal combinations generated successfully."
            stage2_status_code = 'SUCCESS'
        except Exception as e:
            ctx.log(f"    ERROR during LLM API call for goal combinations: {e}")
            ctx.log(f"    Traceback: {traceback.format_exc()}")
            stage2_status = f"Goal Combination generation failed. Falling back to simulation."
            suggested_strategies_final = simulate_marketing_strategy_fallback_staged(user_goals, identified_niches, task_type, num_strategies)
            stage2_status_code = 'API_ERROR'
        finally:
            stage2_duration = time.time() - stage2_call_start_time
    else:
         suggested_strategies_final = simulate_marketing_strategy_fallback_staged(user_goals, identified_niches, task_type, num_strategies)
         stage2_status = "Goal combinations simulated (Client/Pydantic unavailable)."
         stage2_status_code = 'SIMULATED_NO_API_CONFIG'

    ctx.log(f"  Stage 2: {stage2_status}")

    # Store results in context using direct attributes
    ctx.suggested_marketing_strategies = suggested_strategies_final
    
    # Store usage information in the legacy llm_usage dict
    if usage_info_stage1: 
        ctx.llm_usage["strategy_niche_id"] = usage_info_stage1
    if usage_info_stage2: 
        ctx.llm_usage["strategy_goal_gen"] = usage_info_stage2
    
    combined_usage = {**(usage_info_stage1 or {}), **(usage_info_stage2 or {})} # Simple merge for now

    overall_status_code = 'UNKNOWN_STRATEGY_ERROR'
    if stage1_status_code == 'API_ERROR' or stage2_status_code == 'API_ERROR': 
        overall_status_code = 'API_ERROR'
    elif stage1_status_code == 'SIMULATED_NO_API_CONFIG' or stage2_status_code == 'SIMULATED_NO_API_CONFIG': 
        overall_status_code = 'SIMULATED_NO_API_CONFIG'
    elif stage1_status_code in ['USER_PROVIDED', 'USER_PROVIDED_COMPLETE', 'SUCCESS'] and stage2_status_code == 'SUCCESS': 
        overall_status_code = 'SUCCESS'

    final_status_message = f"Marketing strategies generated. (Niche ID: {stage1_status.split('.')[0]}; Goal Gen: {stage2_status.split('.')[0]})"
    if user_goals_complete: 
        final_status_message = f"Marketing strategy variations generated based on user's complete goals. (Niche ID: {stage1_status.split('.')[0]}; Goal Gen: {stage2_status.split('.')[0]})"
    
    ctx.log(f"Marketing strategy generation completed: {final_status_message}")
    
    # Log generated strategies
    if suggested_strategies_final:
        ctx.log(f"Generated {len(suggested_strategies_final)} marketing strategies:")
        for i, strat in enumerate(suggested_strategies_final):
            ctx.log(f"  Strategy {i}: {json.dumps(strat, indent=2)}")
