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
                # Initialize new format fields as empty - they'll be populated below
                provider_config["litellm_chat_models_enabled"] = []
                provider_config["litellm_embedding_models_enabled"] = []
                provider_config["litellm_chat_models_available"] = []
                provider_config["litellm_embedding_models_available"] = []
                update = True
            else:
                # Merge config fields into provider_config, but preserve the token
                for key, value in config.items():
                    if key not in ["token", "token_created_at"]:
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
            
            # Categorize models into chat and embedding
            chat_models_available = []
            embedding_models_available = []
            
            for model in litellm_models:
                try:
                    model_info = litellm.get_model_info(model)
                    mode = model_info.get('mode', 'unknown')
                    
                    if mode == 'chat':
                        chat_models_available.append(model)
                    elif mode == 'embedding':
                        embedding_models_available.append(model)
                    else:
                        # Unknown mode - default to chat for backward compatibility
                        logger.debug(f"Model {model} has unknown mode '{mode}', categorizing as chat")
                        chat_models_available.append(model)
                except Exception as e:
                    logger.warning(f"Could not determine mode for model {model}: {e}, categorizing as chat")
                    chat_models_available.append(model)
            
            # Sort models to maintain consistent order
            chat_models_available = sorted(chat_models_available)
            embedding_models_available = sorted(embedding_models_available)
            
            # Get existing enabled models (preserve user selections)
            existing_chat_enabled = provider_config.get("litellm_chat_models_enabled", [])
            existing_embedding_enabled = provider_config.get("litellm_embedding_models_enabled", [])
            
            # If no existing enabled models in new format, check old format for migration
            if not existing_chat_enabled and not existing_embedding_enabled:
                old_enabled = provider_config.get("litellm_models_enabled", [])
                if old_enabled:
                    logger.info(f"Migrating enabled models from old format for provider {provider}: {old_enabled}")
                    # Categorize old enabled models
                    for model in old_enabled:
                        try:
                            model_info = litellm.get_model_info(model)
                            mode = model_info.get('mode', 'unknown')
                            if mode == 'embedding':
                                existing_embedding_enabled.append(model)
                            else:
                                existing_chat_enabled.append(model)
                        except Exception as e:
                            logger.warning(f"Could not determine mode for {model}, defaulting to chat: {e}")
                            existing_chat_enabled.append(model)
            
            # Filter enabled models to only include available models
            # This ensures we don't keep models that are no longer available from LiteLLM
            chat_models_enabled = [m for m in existing_chat_enabled if m in chat_models_available]
            embedding_models_enabled = [m for m in existing_embedding_enabled if m in embedding_models_available]
            
            # Log if any enabled models were filtered out
            filtered_chat = [m for m in existing_chat_enabled if m not in chat_models_available]
            filtered_embedding = [m for m in existing_embedding_enabled if m not in embedding_models_available]
            if filtered_chat:
                logger.warning(f"Filtered out chat models that are no longer available for {provider}: {filtered_chat}")
                logger.warning(f"These models were previously enabled but are not in LiteLLM's current model list. "
                             f"Available chat models: {chat_models_available[:10]}...")  # Show first 10
            if filtered_embedding:
                logger.warning(f"Filtered out embedding models that are no longer available for {provider}: {filtered_embedding}")
            
            # If no models are enabled after filtering, but we had enabled models before, log a warning
            if not chat_models_enabled and not embedding_models_enabled and (existing_chat_enabled or existing_embedding_enabled):
                logger.error(f"WARNING: All enabled models were filtered out for provider {provider}! "
                           f"Previously enabled: chat={existing_chat_enabled}, embedding={existing_embedding_enabled}. "
                           f"Available: chat={len(chat_models_available)}, embedding={len(embedding_models_available)}")
                logger.error(f"Available chat models for {provider}: {sorted(chat_models_available)}")
                logger.error(f"Trying to find matches for enabled models...")
                # Try to find close matches
                for enabled_model in existing_chat_enabled:
                    matches = [m for m in chat_models_available if enabled_model in m or m in enabled_model]
                    if matches:
                        logger.error(f"  Found potential matches for '{enabled_model}': {matches}")
                    else:
                        logger.error(f"  No matches found for '{enabled_model}'")
            
            # Update provider config if models changed
            if provider_config.get("litellm_chat_models_available") != chat_models_available:
                provider_config["litellm_chat_models_available"] = chat_models_available
                update = True
            
            if provider_config.get("litellm_embedding_models_available") != embedding_models_available:
                provider_config["litellm_embedding_models_available"] = embedding_models_available
                update = True
            
            if provider_config.get("litellm_chat_models_enabled") != chat_models_enabled:
                provider_config["litellm_chat_models_enabled"] = chat_models_enabled
                update = True
            
            if provider_config.get("litellm_embedding_models_enabled") != embedding_models_enabled:
                provider_config["litellm_embedding_models_enabled"] = embedding_models_enabled
                update = True
            
            # Remove old format fields after migration to avoid confusion
            if "litellm_models_available" in provider_config or "litellm_models_enabled" in provider_config:
                provider_config.pop("litellm_models_available", None)
                provider_config.pop("litellm_models_enabled", None)
                update = True

            logger.debug(f"Litellm models: {litellm_models}")
            logger.info(f"Chat models available: {len(chat_models_available)}, enabled: {len(chat_models_enabled)}")
            logger.info(f"Embedding models available: {len(embedding_models_available)}, enabled: {len(embedding_models_enabled)}")
            if chat_models_enabled:
                logger.info(f"Enabled chat models for {provider}: {chat_models_enabled}")
            if embedding_models_enabled:
                logger.info(f"Enabled embedding models for {provider}: {embedding_models_enabled}")

            if update:
                logger.info(f"Updating provider config for {provider}")
                # Only set the fields we want to update, not the entire config
                update_fields = {
                    "litellm_chat_models_available": chat_models_available,
                    "litellm_chat_models_enabled": chat_models_enabled,
                    "litellm_embedding_models_available": embedding_models_available,
                    "litellm_embedding_models_enabled": embedding_models_enabled,
                }
                # Remove old fields if they exist
                unset_fields = {}
                if "litellm_models_available" in provider_config:
                    unset_fields["litellm_models_available"] = ""
                if "litellm_models_enabled" in provider_config:
                    unset_fields["litellm_models_enabled"] = ""
                
                update_op = {"$set": update_fields}
                if unset_fields:
                    update_op["$unset"] = unset_fields
                
                await db.llm_providers.update_one(
                    {"name": provider},
                    update_op,
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
                "claude-opus-4-5-20251101"
                ],
            "litellm_models_enabled": [
                "claude-sonnet-4-20250514",
                "claude-opus-4-1-20250805",
                "claude-sonnet-4-5-20250929",
                "claude-opus-4-5-20251101"
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
            "litellm_models_available": [
                "gpt-4o-mini", 
                "gpt-5.1",
                "gpt-5.2"
            ],
            "litellm_models_enabled": [
                "gpt-4o-mini", 
                "gpt-5.1",
                "gpt-5.2"
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
            "enabled": True,
            "token" : "",
            "token_created_at": None,
            "token_env": "OPENROUTER_API_KEY",
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
            "litellm_models_available": ["xai/grok-4-fast-reasoning"],
            "litellm_models_enabled": ["xai/grok-4-fast-reasoning"],
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