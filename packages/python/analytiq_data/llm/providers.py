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

            # If the provider is not in MongoDB, create it
            if provider_config is None:
                logger.info(f"Creating provider config for {provider}")
                provider_config = {**config}
                update = True

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
            litellm_models = litellm.models_by_provider[provider]
            
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
            litellm_models_seq = list(litellm.models_by_provider.get(provider, []))
            if isinstance(litellm.models_by_provider.get(provider, []), set):
                litellm_models_seq = sorted(litellm.models_by_provider.get(provider, []))
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
                "claude-3-5-sonnet-latest", 
                "claude-3-7-sonnet-latest",
                "claude-sonnet-4-20250514",
                "claude-opus-4-1-20250805",
                ],
            "litellm_models_enabled": [
                "claude-3-5-sonnet-latest", 
                "claude-3-7-sonnet-latest",
                "claude-sonnet-4-20250514",
                "claude-opus-4-1-20250805",
                ],
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
            "enabled": False,
            "token" : "",
            "token_created_at": None,
            "token_env": "NONE", # No token needed for Bedrock
        },
        "gemini": {
            "display_name": "Gemini",
            "litellm_provider": "gemini",
            "litellm_models_available": ["gemini/gemini-2.0-flash", "gemini/gemini-2.5-flash-preview-05-20", "gemini/gemini-2.5-pro-preview-06-05"],
            "litellm_models_enabled": ["gemini/gemini-2.0-flash", "gemini/gemini-2.5-flash-preview-05-20"],
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
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "MISTRAL_API_KEY",
        },
        "openai": {
            "display_name": "OpenAI",
            "litellm_provider": "openai",
            "litellm_models_available": ["gpt-4o-mini", "gpt-4.1-2025-04-14", "o4-mini", "gpt-5"],
            "litellm_models_enabled": ["gpt-4o-mini", "gpt-4.1-2025-04-14", "o4-mini", "gpt-5"],
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "OPENAI_API_KEY",
        },
        "vertex_ai": {
            "display_name": "Google Vertex AI",
            "litellm_provider": "vertex_ai",
            "litellm_models_available": ["gemini-1.5-flash"],
            "litellm_models_enabled": ["gemini-1.5-flash"],
            "enabled": False,
            "token" : "",
            "token_created_at": None,
            "token_env": "VERTEX_AI_API_KEY",
        },
        "xai": {
            "display_name": "xAI",
            "litellm_provider": "xai",
            "litellm_models_available": ["xai/grok-4-0709"],
            "litellm_models_enabled": ["xai/grok-4-0709"],
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
    # Import litellm here to avoid event loop warnings
    import litellm
    
    if llm_model is None:
        return None

    for litellm_provider, litellm_models in litellm.models_by_provider.items():
        if llm_model in litellm_models:
            return litellm_provider

    # If we get here, the model is not supported by litellm
    return None