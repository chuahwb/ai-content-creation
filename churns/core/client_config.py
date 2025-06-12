"""
Client Configuration Module

Handles API key loading, LLM client setup, and model configuration.
Extracted from the original combined_pipeline.py to maintain identical functionality.
"""

import os
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# Import configuration constants from central location
from .constants import (
    MAX_LLM_RETRIES,
    FORCE_MANUAL_JSON_PARSE,
    INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS,
    IMG_EVAL_MODEL_PROVIDER,
    IMG_EVAL_MODEL_ID,
    STRATEGY_MODEL_PROVIDER,
    STRATEGY_MODEL_ID,
    STYLE_GUIDER_MODEL_PROVIDER,
    STYLE_GUIDER_MODEL_ID,
    CREATIVE_EXPERT_MODEL_PROVIDER,
    CREATIVE_EXPERT_MODEL_ID,
    IMAGE_ASSESSMENT_MODEL_PROVIDER,
    IMAGE_ASSESSMENT_MODEL_ID,
    IMAGE_GENERATION_MODEL_ID
)

# Import OpenAI and related libraries
try:
    from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError
    import instructor
    print("✅ OpenAI and instructor libraries imported successfully")
except ImportError as e:
    print(f"❌ Error importing OpenAI/instructor libraries: {e}")
    OpenAI = None
    instructor = None


class ClientConfig:
    """Manages API client configuration and setup."""
    
    def __init__(self, env_path: Optional[str] = None):
        """Initialize client configuration."""
        self.env_path = env_path or ".env"
        
        # API Keys
        self.openrouter_api_key = None
        self.gemini_api_key = None
        self.openai_api_key = None
        
        # Use centralized configuration (from constants.py)
        self.max_llm_retries = MAX_LLM_RETRIES
        self.force_manual_json_parse = FORCE_MANUAL_JSON_PARSE
        self.instructor_tool_mode_problem_models = INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS
        
        # Model configurations (from constants.py)
        self.model_config = {
            "IMG_EVAL_MODEL_PROVIDER": IMG_EVAL_MODEL_PROVIDER,
            "IMG_EVAL_MODEL_ID": IMG_EVAL_MODEL_ID,
            
            "STRATEGY_MODEL_PROVIDER": STRATEGY_MODEL_PROVIDER, 
            "STRATEGY_MODEL_ID": STRATEGY_MODEL_ID,
            
            "STYLE_GUIDER_MODEL_PROVIDER": STYLE_GUIDER_MODEL_PROVIDER,
            "STYLE_GUIDER_MODEL_ID": STYLE_GUIDER_MODEL_ID,
            
            "CREATIVE_EXPERT_MODEL_PROVIDER": CREATIVE_EXPERT_MODEL_PROVIDER,
            "CREATIVE_EXPERT_MODEL_ID": CREATIVE_EXPERT_MODEL_ID,
            
            "IMAGE_ASSESSMENT_MODEL_PROVIDER": IMAGE_ASSESSMENT_MODEL_PROVIDER,
            "IMAGE_ASSESSMENT_MODEL_ID": IMAGE_ASSESSMENT_MODEL_ID,
            
            "IMAGE_GENERATION_MODEL_ID": IMAGE_GENERATION_MODEL_ID
        }
        
        # Initialize clients storage
        self.clients = {}
        
        # Load environment and configure clients
        self._load_environment()
        self._configure_clients()
    
    def _load_environment(self):
        """Load API keys from environment file and check for model configuration overrides."""
        print(f"🔧 Loading environment from: {self.env_path}")
        
        if os.path.exists(self.env_path):
            load_dotenv(dotenv_path=self.env_path)
            print(f"✅ Loaded .env file from: {self.env_path}")
            
            self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
            self.gemini_api_key = os.getenv("GEMINI_API_KEY")
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
            
            # Check for model configuration overrides via environment variables
            self._check_model_config_overrides()
            
            # Log which keys are available (without showing the actual keys)
            keys_status = {
                "OPENROUTER_API_KEY": "✅ Available" if self.openrouter_api_key else "❌ Missing",
                "GEMINI_API_KEY": "✅ Available" if self.gemini_api_key else "❌ Missing", 
                "OPENAI_API_KEY": "✅ Available" if self.openai_api_key else "❌ Missing"
            }
            
            for key, status in keys_status.items():
                print(f"  {key}: {status}")
                
        else:
            print(f"⚠️ Warning: .env file not found at {self.env_path}")
            print("  API keys should be set as environment variables or the pipeline will use simulation mode")
    
    def _check_model_config_overrides(self):
        """Check for environment variable overrides of model configuration."""
        overrides = {}
        
        # Define mapping of environment variables to model config keys
        env_to_config_map = {
            "IMG_EVAL_MODEL_PROVIDER": "IMG_EVAL_MODEL_PROVIDER",
            "IMG_EVAL_MODEL_ID": "IMG_EVAL_MODEL_ID",
            "STRATEGY_MODEL_PROVIDER": "STRATEGY_MODEL_PROVIDER",
            "STRATEGY_MODEL_ID": "STRATEGY_MODEL_ID",
            "STYLE_GUIDER_MODEL_PROVIDER": "STYLE_GUIDER_MODEL_PROVIDER",
            "STYLE_GUIDER_MODEL_ID": "STYLE_GUIDER_MODEL_ID",
            "CREATIVE_EXPERT_MODEL_PROVIDER": "CREATIVE_EXPERT_MODEL_PROVIDER",
            "CREATIVE_EXPERT_MODEL_ID": "CREATIVE_EXPERT_MODEL_ID",
            "IMAGE_ASSESSMENT_MODEL_PROVIDER": "IMAGE_ASSESSMENT_MODEL_PROVIDER",
            "IMAGE_ASSESSMENT_MODEL_ID": "IMAGE_ASSESSMENT_MODEL_ID",
            "IMAGE_GENERATION_MODEL_ID": "IMAGE_GENERATION_MODEL_ID"
        }
        
        # Check each possible environment variable override
        for env_var, config_key in env_to_config_map.items():
            env_value = os.getenv(env_var)
            if env_value:
                original_value = self.model_config[config_key]
                self.model_config[config_key] = env_value
                overrides[config_key] = {"original": original_value, "override": env_value}
                print(f"🔧 Model config override: {config_key} = {env_value} (was: {original_value})")
        
        if overrides:
            print(f"✅ Applied {len(overrides)} model configuration overrides from environment variables")
        else:
            print("📋 Using default model configuration from constants.py (no environment overrides found)")
    
    def _configure_llm_client(self, provider_name: str, model_id: str, purpose: str) -> Tuple[Optional[Any], Optional[Any]]:
        """Configure a base OpenAI client and an instructor-patched client (from original monolith)."""
        base_client = None
        instructor_client_patched = None
        api_key_to_use = None
        base_url_to_use = None

        if provider_name == "OpenRouter":
            if not self.openrouter_api_key:
                print(f"⚠️ OpenRouter API Key not found for {purpose}. Client not configured.")
                return None, None
            api_key_to_use = self.openrouter_api_key
            base_url_to_use = "https://openrouter.ai/api/v1"
            print(f"🔧 Configuring OpenRouter client for {purpose} with model {model_id}")
        elif provider_name == "Gemini":
            if not self.gemini_api_key:
                print(f"⚠️ Gemini API Key not found for {purpose}. Client not configured.")
                return None, None
            api_key_to_use = self.gemini_api_key
            base_url_to_use = "https://generativelanguage.googleapis.com/v1beta/openai/"
            print(f"🔧 Configuring Gemini client for {purpose} with model {model_id}")
            print("NOTE: Direct Gemini integration might require 'google-generativeai' library")
        elif provider_name == "OpenAI":
            if not self.openai_api_key:
                print(f"⚠️ OpenAI API Key not found for {purpose}. Client not configured.")
                return None, None
            api_key_to_use = self.openai_api_key
            base_url_to_use = None  # Use default OpenAI base URL
            print(f"🔧 Configuring OpenAI client for {purpose} with model {model_id}")
        else:
            print(f"❌ Unsupported provider: {provider_name} for {purpose}")
            return None, None

        if OpenAI and api_key_to_use:
            try:
                base_client = OpenAI(
                    api_key=api_key_to_use,
                    base_url=base_url_to_use,
                    max_retries=self.max_llm_retries
                )
                
                if instructor and not self.force_manual_json_parse:
                    instructor_client_patched = instructor.patch(base_client)
                    print(f"✅ {provider_name} client for {purpose} configured (Instructor patched). Model: {model_id}")
                elif instructor and self.force_manual_json_parse:
                    instructor_client_patched = base_client
                    print(f"✅ {provider_name} client for {purpose} configured (Manual JSON parsing). Model: {model_id}")
                else:
                    instructor_client_patched = base_client
                    print(f"✅ {provider_name} client for {purpose} configured (Instructor not available). Model: {model_id}")

            except Exception as e:
                print(f"❌ Error initializing {provider_name} client for {purpose}: {e}")
                base_client = None
                instructor_client_patched = None
        
        return base_client, instructor_client_patched
    
    def _configure_clients(self):
        """Configure all LLM and image generation clients."""
        print("\n🔧 Configuring API Clients...")
        
        # Configure clients for each purpose (from original monolith)
        base_llm_client_img_eval, instructor_client_img_eval = self._configure_llm_client(
            self.model_config["IMG_EVAL_MODEL_PROVIDER"], 
            self.model_config["IMG_EVAL_MODEL_ID"], 
            "Image Evaluation"
        )
        
        base_llm_client_strategy, instructor_client_strategy = self._configure_llm_client(
            self.model_config["STRATEGY_MODEL_PROVIDER"], 
            self.model_config["STRATEGY_MODEL_ID"], 
            "Strategy Generation"
        )
        
        base_llm_client_style_guide, instructor_client_style_guide = self._configure_llm_client(
            self.model_config["STYLE_GUIDER_MODEL_PROVIDER"], 
            self.model_config["STYLE_GUIDER_MODEL_ID"], 
            "Style Guidance"
        )
        
        base_llm_client_creative_expert, instructor_client_creative_expert = self._configure_llm_client(
            self.model_config["CREATIVE_EXPERT_MODEL_PROVIDER"], 
            self.model_config["CREATIVE_EXPERT_MODEL_ID"], 
            "Creative Expert"
        )
        
        base_llm_client_image_assessment, instructor_client_image_assessment = self._configure_llm_client(
            self.model_config["IMAGE_ASSESSMENT_MODEL_PROVIDER"], 
            self.model_config["IMAGE_ASSESSMENT_MODEL_ID"], 
            "Image Assessment"
        )
        
        # Configure Image Generation Client (typically OpenAI)
        image_gen_client = None
        if OpenAI and self.openai_api_key:
            try:
                image_gen_client = OpenAI(
                    api_key=self.openai_api_key,
                    max_retries=self.max_llm_retries
                )
                print(f"✅ Image Generation client (OpenAI) configured. Model: {self.model_config['IMAGE_GENERATION_MODEL_ID']}")
            except Exception as e:
                print(f"❌ Error initializing Image Generation client: {e}")
                image_gen_client = None
        elif not self.openai_api_key:
            print("⚠️ OPENAI_API_KEY not found. Image Generation client not configured.")
        else:
            print("⚠️ OpenAI library not available. Image Generation client not configured.")
        
        # Store all clients
        self.clients = {
            'base_llm_client_img_eval': base_llm_client_img_eval,
            'instructor_client_img_eval': instructor_client_img_eval,
            'base_llm_client_strategy': base_llm_client_strategy,
            'instructor_client_strategy': instructor_client_strategy,
            'base_llm_client_style_guide': base_llm_client_style_guide,
            'instructor_client_style_guide': instructor_client_style_guide,
            'base_llm_client_creative_expert': base_llm_client_creative_expert,
            'instructor_client_creative_expert': instructor_client_creative_expert,
            'base_llm_client_image_assessment': base_llm_client_image_assessment,
            'instructor_client_image_assessment': instructor_client_image_assessment,
            'image_gen_client': image_gen_client
        }
        
        # Also store model configurations for stages to use
        self.clients.update({
            'model_config': self.model_config,
            'force_manual_json_parse': self.force_manual_json_parse,
            'instructor_tool_mode_problem_models': self.instructor_tool_mode_problem_models
        })
        
        print("✅ Client configuration completed")
    
    def get_clients(self) -> Dict[str, Any]:
        """Get all configured clients."""
        return self.clients
    
    def get_client_summary(self) -> Dict[str, str]:
        """Get a summary of client configuration status."""
        summary = {}
        for client_name, client in self.clients.items():
            if client_name in ['model_config', 'force_manual_json_parse', 'instructor_tool_mode_problem_models']:
                continue  # Skip configuration items
            
            if client is not None:
                summary[client_name] = "✅ Configured"
            else:
                summary[client_name] = "❌ Not configured"
        
        return summary
    
    def print_configuration_summary(self):
        """Print a summary of the current configuration."""
        print("\n📊 Client Configuration Summary:")
        print("=" * 50)
        
        summary = self.get_client_summary()
        for client_name, status in summary.items():
            print(f"  {client_name}: {status}")
        
        print(f"\n🔧 Model Configuration:")
        for key, value in self.model_config.items():
            print(f"  {key}: {value}")
        
        print(f"\n⚙️ Parsing Configuration:")
        print(f"  Force Manual JSON Parse: {self.force_manual_json_parse}")
        print(f"  Problematic Models: {self.instructor_tool_mode_problem_models}")
        
        configured_count = sum(1 for status in summary.values() if "✅" in status)
        total_count = len(summary)
        print(f"\n📈 Status: {configured_count}/{total_count} clients configured")


# Global client configuration instance
_client_config = None

def get_client_config(env_path: Optional[str] = None) -> ClientConfig:
    """Get or create the global client configuration instance."""
    global _client_config
    if _client_config is None:
        _client_config = ClientConfig(env_path)
    return _client_config

def get_configured_clients(env_path: Optional[str] = None) -> Dict[str, Any]:
    """Get all configured clients (convenience function)."""
    return get_client_config(env_path).get_clients() 