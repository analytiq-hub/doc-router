from bson.objectid import ObjectId
import os
import logging
import warnings
import litellm
from datetime import datetime
import analytiq_data as ad

# Suppress Pydantic deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")

logger = logging.getLogger(__name__)

# Models not yet in litellm's built-in registry.
# Add entries here when a model is available but litellm hasn't added it yet.
# The "litellm_provider" key must match the models_by_provider key used in get_llm_providers().
LITELLM_MODEL_PATCHES: dict = {
    "vertex_ai/gemini-2.5-pro": {
        "cache_read_input_token_cost": 1.25e-07,
        "cache_read_input_token_cost_above_200k_tokens": 2.5e-07,
        "input_cost_per_token": 1.25e-06,
        "input_cost_per_token_above_200k_tokens": 2.5e-06,
        "litellm_provider": "vertex_ai",
        "max_audio_length_hours": 8.4,
        "max_audio_per_prompt": 1,
        "max_images_per_prompt": 3000,
        "max_input_tokens": 1048576,
        "max_output_tokens": 65535,
        "max_pdf_size_mb": 30,
        "max_tokens": 65535,
        "max_video_length": 1,
        "max_videos_per_prompt": 10,
        "mode": "chat",
        "output_cost_per_token": 1e-05,
        "output_cost_per_token_above_200k_tokens": 1.5e-05,
        "supported_endpoints": ["/v1/chat/completions", "/v1/completions"],
        "supported_modalities": ["text", "image", "audio", "video"],
        "supported_output_modalities": ["text"],
        "supports_audio_input": True,
        "supports_function_calling": True,
        "supports_pdf_input": True,
        "supports_prompt_caching": True,
        "supports_reasoning": True,
        "supports_response_schema": True,
        "supports_system_messages": True,
        "supports_tool_choice": True,
        "supports_video_input": True,
        "supports_vision": True,
        "supports_web_search": True,
        "supports_native_streaming": True,
    },
    "vertex_ai/gemini-2.5-flash": {
        "cache_read_input_token_cost": 3e-08,
        "input_cost_per_audio_token": 1e-06,
        "cache_read_input_token_cost_per_audio_token": 1e-07,
        "input_cost_per_token": 3e-07,
        "litellm_provider": "vertex_ai",
        "max_audio_length_hours": 8.4,
        "max_audio_per_prompt": 1,
        "max_images_per_prompt": 3000,
        "max_input_tokens": 1048576,
        "max_output_tokens": 65535,
        "max_pdf_size_mb": 30,
        "max_tokens": 65535,
        "max_video_length": 1,
        "max_videos_per_prompt": 10,
        "mode": "chat",
        "output_cost_per_token": 2.5e-06,
        "output_cost_per_reasoning_token": 2.5e-06,
        "output_cost_per_image": 3e-05,
        "supported_endpoints": ["/v1/chat/completions", "/v1/completions", "/v1/batch"],
        "supported_modalities": ["text", "image", "audio", "video"],
        "supported_output_modalities": ["text"],
        "supports_audio_input": True,
        "supports_audio_output": False,
        "supports_function_calling": True,
        "supports_parallel_function_calling": True,
        "supports_pdf_input": True,
        "supports_prompt_caching": True,
        "supports_reasoning": True,
        "supports_response_schema": True,
        "supports_system_messages": True,
        "supports_tool_choice": True,
        "supports_url_context": True,
        "supports_video_input": True,
        "supports_vision": True,
        "supports_web_search": True,
        "supports_native_streaming": True,
    },
    "vertex_ai/gemini-3.1-pro-preview": {
        "cache_read_input_token_cost": 2e-07,
        "cache_read_input_token_cost_above_200k_tokens": 4e-07,
        "input_cost_per_token": 2e-06,
        "input_cost_per_token_above_200k_tokens": 4e-06,
        "litellm_provider": "vertex_ai",
        "max_audio_length_hours": 8.4,
        "max_audio_per_prompt": 1,
        "max_images_per_prompt": 3000,
        "max_input_tokens": 1048576,
        "max_output_tokens": 65536,
        "max_pdf_size_mb": 30,
        "max_tokens": 65536,
        "max_video_length": 1,
        "max_videos_per_prompt": 10,
        "mode": "chat",
        "output_cost_per_token": 1.2e-05,
        "output_cost_per_token_above_200k_tokens": 1.8e-05,
        "output_cost_per_image": 1.2e-04,
        "supported_endpoints": ["/v1/chat/completions", "/v1/completions", "/v1/batch"],
        "supported_modalities": ["text", "image", "audio", "video"],
        "supported_output_modalities": ["text"],
        "supports_audio_input": True,
        "supports_function_calling": True,
        "supports_pdf_input": True,
        "supports_prompt_caching": True,
        "supports_reasoning": True,
        "supports_response_schema": True,
        "supports_system_messages": True,
        "supports_tool_choice": True,
        "supports_video_input": True,
        "supports_vision": True,
        "supports_web_search": True,
        "supports_url_context": True,
        "supports_native_streaming": True,
    },
    "vertex_ai/gemini-3.1-flash-lite-preview": {
        "cache_read_input_token_cost": 2.5e-08,
        "cache_read_input_token_cost_per_audio_token": 5e-08,
        "input_cost_per_audio_token": 5e-07,
        "input_cost_per_token": 2.5e-07,
        "litellm_provider": "vertex_ai",
        "max_audio_length_hours": 8.4,
        "max_audio_per_prompt": 1,
        "max_images_per_prompt": 3000,
        "max_input_tokens": 1048576,
        "max_output_tokens": 65536,
        "max_pdf_size_mb": 30,
        "max_tokens": 65536,
        "max_video_length": 1,
        "max_videos_per_prompt": 10,
        "mode": "chat",
        "output_cost_per_reasoning_token": 1.5e-06,
        "output_cost_per_token": 1.5e-06,
        "supported_endpoints": ["/v1/chat/completions", "/v1/completions", "/v1/batch"],
        "supported_modalities": ["text", "image", "audio", "video"],
        "supported_output_modalities": ["text"],
        "supports_audio_input": True,
        "supports_audio_output": False,
        "supports_code_execution": True,
        "supports_file_search": True,
        "supports_function_calling": True,
        "supports_parallel_function_calling": True,
        "supports_pdf_input": True,
        "supports_prompt_caching": True,
        "supports_reasoning": True,
        "supports_response_schema": True,
        "supports_system_messages": True,
        "supports_tool_choice": True,
        "supports_url_context": True,
        "supports_video_input": True,
        "supports_vision": True,
        "supports_web_search": True,
        "supports_native_streaming": True,
    },
}


def patch_litellm_models() -> None:
    """Patch litellm's model registry with models not yet in its built-in list."""
    for model_name, model_data in LITELLM_MODEL_PATCHES.items():
        # Add to model_cost for token/cost lookups
        if model_name not in litellm.model_cost:
            logger.info(f"Patching litellm model_cost with {model_name}")
            litellm.model_cost[model_name] = model_data

        # Add to models_by_provider for provider validation
        provider = model_data.get("litellm_provider", "vertex_ai")
        if provider not in litellm.models_by_provider:
            logger.info(f"Creating litellm models_by_provider[{provider}] with {model_name}")
            litellm.models_by_provider[provider] = [model_name]
        else:
            provider_models = litellm.models_by_provider[provider]
            if model_name not in provider_models:
                logger.info(f"Patching litellm models_by_provider[{provider}] with {model_name}")
                if isinstance(provider_models, set):
                    provider_models.add(model_name)
                else:
                    provider_models.append(model_name)

# Apply patches at module load time
patch_litellm_models()

async def list_llm_providers(analytiq_client) -> dict:
    """
    List the LLM providers

    Args:
        analytiq_client: The AnalytiqClient instance

    Returns:
        The LLM model for the prompt
    """
    providers = ad.llm.get_llm_providers()
    return list(providers.keys())

async def setup_llm_providers(analytiq_client):
    """Set up default LLM providers by upserting based on provider name"""
    
    env = analytiq_client.env
    db = analytiq_client.mongodb_async[env]

    providers = get_llm_providers()
    try:        
        # Upsert each provider individually using the name as the unique identifier
        for provider, config in providers.items():
            # Skip if the provider is not supported by litellm
            if config["litellm_provider"] not in litellm.models_by_provider.keys():
                logger.error(f"Provider {config['litellm_provider']} is not supported by litellm, skipping")
                continue
            
            # Get the current provider config from MongoDB
            provider_config = await db.llm_providers.find_one({"name": provider})
            update = False

            # Preserve the token if the provider already exists
            existing_token = None
            existing_token_created_at = None
            if provider_config is not None:
                existing_token = provider_config.get("token")
                existing_token_created_at = provider_config.get("token_created_at")

            # If the provider is not in MongoDB, create it
            if provider_config is None:
                logger.info(f"Creating provider config for {provider}")
                provider_config = {**config}
                update = True
            else:
                # Merge config fields into provider_config, but preserve the token and user-set chat agent models
                for key, value in config.items():
                    if key not in ["token", "token_created_at", "litellm_models_chat_agent"]:
                        if provider_config.get(key) != value:
                            provider_config[key] = value
                            update = True
                
                # Restore the preserved token
                if existing_token is not None:
                    provider_config["token"] = existing_token
                if existing_token_created_at is not None:
                    provider_config["token_created_at"] = existing_token_created_at
                
                # Ensure name field is set
                provider_config["name"] = provider

            # Should we update the token?
            if provider_config.get("token") in [None, ""]:
                # If the token is available in the environment, set it in the config
                if os.getenv(config["token_env"]):
                    logger.info(f"Updating token for {provider}")
                    token = os.getenv(config["token_env"])
                    if len(token) > 0:
                        provider_config["token"] = ad.crypto.encrypt_token(token)
                    provider_config["token_created_at"] = datetime.now()
                    update = True

            # Get the litellm_models for the provider
            litellm_models = litellm.models_by_provider[config["litellm_provider"]]
            
            # Get the available models for the provider
            models_available = provider_config.get("litellm_models_available", [])
            if models_available != config["litellm_models_available"]:
                logger.info(f"Updating litellm_models_available for {provider} from {models_available} to {config['litellm_models_available']}")
                provider_config["litellm_models_available"] = config["litellm_models_available"]
                models_available = config["litellm_models_available"]
                update = True
            
            # Get the models for the provider
            models_enabled = provider_config.get("litellm_models_enabled", [])
            if len(models_enabled) == 0:
                provider_config["litellm_models_enabled"] = []
                models_enabled = []
                update = True

            logger.debug(f"Litellm models: {litellm_models}")
            logger.info(f"Models available: {models_available}")
            logger.info(f"Models enabled: {models_enabled}")

            # Avaliable models should be a subset of litellm_models
            for model in models_available:
                if model not in litellm_models:
                    logger.info(f"Model {model} is not supported by {provider}, removing from provider config")
                    provider_config["litellm_models_available"].remove(model)
                    update = True
            
            # Enabled models should be a subset of litellm_models_available
            for model in models_enabled:
                if model not in provider_config["litellm_models_available"]:
                    logger.info(f"Model {model} is not supported by {provider}, removing from provider config")
                    provider_config["litellm_models_enabled"].remove(model)
                    update = True

            # Order the litellm_models_available using same order from litellm.models_by_provider. If order changes, set the update flag
            # litellm may return a set for models; normalize to an ordered sequence for stable indexing
            litellm_provider_key = config["litellm_provider"]
            litellm_models_seq = list(litellm.models_by_provider.get(litellm_provider_key, []))
            if isinstance(litellm.models_by_provider.get(litellm_provider_key, []), set):
                litellm_models_seq = sorted(litellm.models_by_provider.get(litellm_provider_key, []))
            model_position = {model_name: idx for idx, model_name in enumerate(litellm_models_seq)}
            models_available_ordered = sorted(
                provider_config["litellm_models_available"],
                key=lambda x: model_position.get(x, float("inf"))
            )
            if models_available_ordered != provider_config["litellm_models_available"]:
                logger.info(f"Litellm models available ordered: {models_available_ordered}")
                logger.info(f"Provider config litellm_models_available: {provider_config['litellm_models_available']}")
                provider_config["litellm_models_available"] = models_available_ordered
                update = True
            
            # Order the litellm_models_enabled using same order from litellm.models_by_provider. If order changes, set the update flag
            models_ordered = sorted(
                provider_config["litellm_models_enabled"],
                key=lambda x: model_position.get(x, float("inf"))
            )
            if models_ordered != provider_config["litellm_models_enabled"]:
                logger.info(f"Litellm models ordered: {models_ordered}")
                logger.info(f"Provider config litellm_models_enabled: {provider_config['litellm_models_enabled']}")
                provider_config["litellm_models_enabled"] = models_ordered
                update = True

            # litellm_models_chat_agent: subset of litellm_models_available for agent chat
            # Ensure the key exists in provider_config (may be missing in older DB documents)
            if "litellm_models_chat_agent" not in provider_config:
                provider_config["litellm_models_chat_agent"] = config.get("litellm_models_chat_agent", [])
                update = True
            models_chat_agent = provider_config["litellm_models_chat_agent"]
            if not models_chat_agent and config.get("litellm_models_chat_agent"):
                provider_config["litellm_models_chat_agent"] = config["litellm_models_chat_agent"]
                models_chat_agent = config["litellm_models_chat_agent"]
                update = True
            for model in list(provider_config.get("litellm_models_chat_agent", [])):
                if model not in provider_config["litellm_models_available"]:
                    provider_config["litellm_models_chat_agent"].remove(model)
                    update = True
            models_chat_agent_ordered = sorted(
                provider_config["litellm_models_chat_agent"],
                key=lambda x: model_position.get(x, float("inf"))
            )
            if models_chat_agent_ordered != provider_config["litellm_models_chat_agent"]:
                provider_config["litellm_models_chat_agent"] = models_chat_agent_ordered
                update = True

            if update:
                logger.info(f"Updating provider config for {provider}")
                logger.info(f"Provider config: {provider_config}")
                await db.llm_providers.update_one(
                    {"name": provider},
                    {"$set": provider_config},
                    upsert=True
                )

        # Remove any unsupported providers
        litellm_provider_list = list(litellm.models_by_provider.keys())
        # Get the list of provider litellm_provider from MongoDB    
        provider_list = []
        for provider in await db.llm_providers.find().to_list(length=None):
            provider_list.append(provider["litellm_provider"])

        logger.info(f"Provider list: {provider_list}")
        logger.info(f"Litellm provider list: {litellm_provider_list}")

        # Remove any unsupported providers
        for provider_name in provider_list:
            if provider_name not in litellm_provider_list:
                logger.info(f"Removing unsupported provider {provider_name}")
                await db.llm_providers.delete_one({"litellm_provider": provider_name})

    except Exception as e:
        logger.error(f"Failed to upsert LLM providers: {e}")

def get_llm_providers() -> dict:
    """
    Get the LLM providers
    """
    providers = {
        "anthropic": {
            "display_name": "Anthropic",
            "litellm_provider": "anthropic",
            "litellm_models_available": [
                "claude-sonnet-4-20250514",
                "claude-opus-4-1-20250805",
                "claude-sonnet-4-5-20250929",
                "claude-opus-4-5-20251101",
                "claude-sonnet-4-6",
                "claude-opus-4-6",
                ],
            "litellm_models_enabled": [
                "claude-sonnet-4-20250514",
                "claude-opus-4-1-20250805",
                "claude-sonnet-4-5-20250929",
                "claude-opus-4-5-20251101",
                "claude-sonnet-4-6",
                "claude-opus-4-6",
                ],
            "litellm_models_chat_agent": [
                "claude-sonnet-4-6",
                "claude-opus-4-6",
                ],
            "litellm_models_ocr": [],
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "ANTHROPIC_API_KEY",
        },
        "azure": {
            "display_name": "Azure OpenAI",
            "litellm_provider": "azure",
            "litellm_models_available": ["azure/gpt-4.1-nano"],
            "litellm_models_enabled": ["azure/gpt-4.1-nano"],
            "litellm_models_chat_agent": [],
            "litellm_models_ocr": [],
            "enabled": False,
            "token" : "",
            "token_created_at": None,
            "token_env": "AZURE_OPENAI_API_KEY",
        },
        "azure_ai": {
            "display_name": "Azure AI Studio",
            "litellm_provider": "azure_ai",
            "litellm_models_available": ["azure_ai/deepseek-v3"],
            "litellm_models_enabled": ["azure_ai/deepseek-v3"],
            "litellm_models_chat_agent": ["azure_ai/deepseek-v3"],
            "litellm_models_ocr": [],
            "enabled": False,
            "token" : "",
            "token_created_at": None,
            "token_env": "AZURE_AI_STUDIO_API_KEY",
        },
        "bedrock": {
            "display_name": "AWS Bedrock",
            "litellm_provider": "bedrock",
            "litellm_models_available": [
                "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "us.anthropic.claude-opus-4-20250514-v1:0",
                "us.anthropic.claude-opus-4-1-20250805-v1:0"
            ],
            "litellm_models_enabled": [
                "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "us.anthropic.claude-opus-4-20250514-v1:0",
                "us.anthropic.claude-opus-4-1-20250805-v1:0"
            ],
            "litellm_models_chat_agent": [
                "us.anthropic.claude-opus-4-1-20250805-v1:0"
            ],
            "litellm_models_ocr": [],
            "enabled": False,
            "token" : "",
            "token_created_at": None,
            "token_env": "NONE", # No token needed for Bedrock
        },
        "gemini": {
            "display_name": "Gemini",
            "litellm_provider": "gemini",
            "litellm_models_available": [
                "gemini/gemini-2.5-flash", 
                "gemini/gemini-2.5-pro",
                "gemini/gemini-3-flash-preview",
                "gemini/gemini-3-pro-preview"
            ],
            "litellm_models_enabled": [
                "gemini/gemini-2.5-flash", 
                "gemini/gemini-2.5-pro",
                "gemini/gemini-3-flash-preview",
                "gemini/gemini-3-pro-preview"
            ],
            "litellm_models_chat_agent": [
                "gemini/gemini-3-flash-preview",
                "gemini/gemini-3-pro-preview"
            ],
            "litellm_models_ocr": [
                "gemini/gemini-3-flash-preview",
                "gemini/gemini-3-pro-preview"
            ],
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "GEMINI_API_KEY",
        },
        "groq": {
            "display_name": "Groq",
            "litellm_provider": "groq",
            "litellm_models_available": ["groq/deepseek-r1-distill-llama-70b"],
            "litellm_models_enabled": ["groq/deepseek-r1-distill-llama-70b"],
            "litellm_models_chat_agent": [],
            "litellm_models_ocr": [],
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "GROQ_API_KEY",
        },
        "mistral": {
            "display_name": "Mistral",
            "litellm_provider": "mistral",
            "litellm_models_available": ["mistral/mistral-tiny"],
            "litellm_models_enabled": ["mistral/mistral-tiny"],
            "litellm_models_chat_agent": [],
            "litellm_models_ocr": [],
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "MISTRAL_API_KEY",
        },
        "openai": {
            "display_name": "OpenAI",
            "litellm_provider": "openai",
            "litellm_models_available": [
                "gpt-4o-mini", 
                "gpt-5.1",
                "gpt-5.2",
                "text-embedding-3-small",
                "text-embedding-3-large"
            ],
            "litellm_models_enabled": [
                "gpt-4o-mini", 
                "gpt-5.1",
                "gpt-5.2",
                "text-embedding-3-small",
                "text-embedding-3-large"
            ],
            "litellm_models_chat_agent": [
                "gpt-5.2"
            ],
            "litellm_models_ocr": [
                "gpt-5.2",
            ],
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "OPENAI_API_KEY",
        },
        "openrouter": {
            "display_name": "OpenRouter",
            "litellm_provider": "openrouter",
            "litellm_models_available": ["openrouter/openai/gpt-5.2-chat"],
            "litellm_models_enabled": ["openrouter/openai/gpt-5.2-chat"],
            "litellm_models_chat_agent": ["openrouter/openai/gpt-5.2-chat"],
            "litellm_models_ocr": ["openrouter/openai/gpt-5.2-chat"],
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "OPENROUTER_API_KEY",
        },
        "vertex_ai": {
            "display_name": "Google Vertex AI",
            "litellm_provider": "vertex_ai",
            "litellm_models_available": [
                "vertex_ai/gemini-2.5-flash",
                "vertex_ai/gemini-2.5-pro",
                "vertex_ai/gemini-3.1-flash-lite-preview",
                "vertex_ai/gemini-3.1-pro-preview",
            ],
            "litellm_models_enabled": [
                "vertex_ai/gemini-2.5-flash",
                "vertex_ai/gemini-2.5-pro",
                "vertex_ai/gemini-3.1-flash-lite-preview",
                "vertex_ai/gemini-3.1-pro-preview",
            ],
            "litellm_models_chat_agent": [
                "vertex_ai/gemini-3.1-flash-lite-preview",
                "vertex_ai/gemini-3.1-pro-preview",
            ],
            "litellm_models_ocr": [
                "vertex_ai/gemini-3.1-flash-lite-preview",
                "vertex_ai/gemini-3.1-pro-preview",
            ],
            "enabled": False,
            "token" : "",
            "token_created_at": None,
            "token_env": "VERTEX_AI_API_KEY",
        },
        "xai": {
            "display_name": "xAI",
            "litellm_provider": "xai",
            "litellm_models_available": ["xai/grok-4-1-fast-reasoning"],
            "litellm_models_enabled": ["xai/grok-4-1-fast-reasoning"],
            "litellm_models_chat_agent": ["xai/grok-4-1-fast-reasoning"],
            "litellm_models_ocr": [],
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "XAI_API_KEY",
        },
    }

    return providers

def get_supported_models() -> list[str]:
    """
    Get the list of supported models
    """
    llm_providers = get_llm_providers()
    llm_models = []
    for provider, config in llm_providers.items():
        llm_models.extend(config["litellm_models_enabled"])

    return llm_models


def get_chat_agent_models() -> list[str]:
    """
    Get the list of models enabled for the chat agent (subset of enabled per provider).
    """
    llm_providers = get_llm_providers()
    llm_models = []
    for provider, config in llm_providers.items():
        llm_models.extend(config.get("litellm_models_chat_agent", config["litellm_models_enabled"]))

    return llm_models

def get_available_models() -> list[str]:
    """
    Get the list of available models
    """
    llm_providers = get_llm_providers()
    llm_models = []
    for provider, config in llm_providers.items():
        llm_models.extend(config["litellm_models_available"])

    return llm_models

def get_llm_model_provider(llm_model: str) -> str | None:
    """
    Get the provider for a given LLM model

    Args:
        llm_model: The LLM model

    Returns:
        The provider for the given LLM model
    """
    if llm_model is None:
        return None

    for litellm_provider, litellm_models in litellm.models_by_provider.items():
        if llm_model in litellm_models:
            return litellm_provider

    # If we get here, the model is not supported by litellm
    return None