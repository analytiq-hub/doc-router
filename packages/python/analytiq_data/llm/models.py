from bson.objectid import ObjectId
import logging
import warnings
import litellm

# Suppress Pydantic deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")

logger = logging.getLogger(__name__)

import analytiq_data as ad

async def get_llm_model(analytiq_client, prompt_revid: str) -> dict:
    """
    Get the LLM model for a prompt

    Args:
        analytiq_client: The AnalytiqClient instance
        prompt_revid: The prompt revision ID

    Returns:
        The LLM model for the prompt
    """
    # Get the MongoDB client
    mongo = analytiq_client.mongodb_async
    db_name = analytiq_client.env
    db = mongo[db_name]
    collection = db["prompt_revisions"]

    default_model = "gpt-4o-mini"

    if prompt_revid == "default":
        return default_model

    prompt = await collection.find_one({"_id": ObjectId(prompt_revid)})
    if prompt is None:
        logger.info(f"Prompt {prompt_revid} not found, falling back to default model {default_model}")
        return default_model
    
    litellm_model = prompt.get("model", default_model)
    if is_chat_model(litellm_model):
        return litellm_model
    else:
        logger.info(f"Model {litellm_model} is not a chat model, falling back to default model {default_model}")
        return default_model

def is_chat_model(llm_model: str) -> bool:  
    """
    Check if the LLM model is a chat model

    Args:
        llm_model: The LLM model

    Returns:
        True if the LLM model is a chat model, False otherwise
    """
    try:
        model_info = litellm.get_model_info(llm_model)
        if model_info.get('mode') == 'chat':
            return True
        logger.info(f"Model {llm_model} is not a chat model")
    except Exception as e:
        logger.error(f"Error checking if {llm_model} is a chat model: {e}")

    return False

def has_cost_information(llm_model: str) -> bool:
    """
    Check if the LLM model has cost information
    """
    if llm_model not in litellm.model_cost.keys():
        logger.info(f"Model {llm_model} is not supported by litellm")
        return False

    max_input_tokens = litellm.model_cost[llm_model].get("max_input_tokens", 0)
    max_output_tokens = litellm.model_cost[llm_model].get("max_output_tokens", 0)
    input_cost_per_token = litellm.model_cost[llm_model].get("input_cost_per_token", 0)
    output_cost_per_token = litellm.model_cost[llm_model].get("output_cost_per_token", 0)

    if max_input_tokens == 0 or max_output_tokens == 0 or input_cost_per_token == 0 or output_cost_per_token == 0:
        logger.info(f"Model {llm_model} is not supported - missing cost information")
        return False

    return True

def is_supported_model(llm_model: str) -> bool:
    """
    Check if the LLM model is supported by litellm

    Args:
        llm_model: The LLM model

    Returns:
        True if the LLM model is supported by litellm, False otherwise
    """
    if llm_model not in ad.llm.get_supported_models():
        logger.info(f"Model {llm_model} is not in list of supported models")
        return False
    
    if not ad.llm.has_cost_information(llm_model):
        return False    
    
    return True