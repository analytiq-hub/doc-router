import asyncio
import analytiq_data as ad
import litellm
from litellm.utils import supports_pdf_input  # Add this import
import json
from datetime import datetime, UTC
from pydantic import BaseModel, create_model
from typing import Optional, Dict, Any, Union, List
from collections import OrderedDict
import logging
from bson import ObjectId
import base64
import os
import re
import stamina
from .llm_output_utils import process_llm_resp_content

logger = logging.getLogger(__name__)

# Drop unsupported provider/model params automatically (e.g., O-series temperature)
litellm.drop_params = True

async def get_extracted_text(analytiq_client, document_id: str) -> str | None:
    """
    Get extracted text from a document.

    For OCR-supported files, returns OCR text.
    For txt/md files, returns the original file content as text.
    For other non-OCR files, returns None.

    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID

    Returns:
        str | None: The extracted text, or None if file needs to be attached
    """
    # Get document info
    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    if not doc:
        return None

    file_name = doc.get("user_file_name", "")

    # Check if OCR is supported
    if ad.common.doc.ocr_supported(file_name):
        # Use OCR text
        return await ad.common.get_ocr_text(analytiq_client, document_id)

    # For non-OCR files, check if it's a text file we can read
    if file_name:
        ext = os.path.splitext(file_name)[1].lower()
        if ext in {'.txt', '.md'}:
            # Get the original file and decode as text
            original_file = await ad.common.get_file_async(analytiq_client, doc["mongo_file_name"])
            if original_file and original_file["blob"]:
                try:
                    return original_file["blob"].decode("utf-8")
                except UnicodeDecodeError:
                    # Fallback to latin-1 if UTF-8 fails
                    return original_file["blob"].decode("latin-1")

    # For other files (csv, xls, xlsx), return None to indicate file attachment needed
    return None

async def get_file_attachment(analytiq_client, doc: dict, llm_provider: str, llm_model: str):
    """
    Get file attachment for LLM processing.

    Args:
        analytiq_client: The AnalytiqClient instance
        doc: Document dictionary
        llm_provider: LLM provider name
        llm_model: LLM model name

    Returns:
        File blob and file name, or None, None
    """
    file_name = doc.get("user_file_name", "")
    if not file_name:
        return None, None

    ext = os.path.splitext(file_name)[1].lower()

    # Check if model supports vision
    # Note: XAI doesn't support the complex file attachment format, so we exclude it here
    # XAI will use OCR text-only approach instead
    model_supports_vision = supports_pdf_input(llm_model, None)

    if model_supports_vision and doc.get("pdf_file_name"):
        # For vision-capable models, prefer PDF version
        pdf_file = await ad.common.get_file_async(analytiq_client, doc["pdf_file_name"])
        if pdf_file and pdf_file["blob"]:
            return pdf_file["blob"], doc["pdf_file_name"]

    # For CSV, Excel files, or when PDF not available, use original file
    if ext in {'.csv', '.xls', '.xlsx'} or not model_supports_vision:
        original_file = await ad.common.get_file_async(analytiq_client, doc["mongo_file_name"])
        if original_file and original_file["blob"]:
            return original_file["blob"], file_name

    return None, None

def is_o_series_model(model_name: str) -> bool:
    """Return True for OpenAI O-series models (e.g., o1, o1-mini, o3, o4-mini)."""
    if not model_name:
        return False
    name = model_name.strip().lower()
    # O-series models start with 'o' (not to be confused with gpt-4o which starts with 'gpt')
    return name.startswith("o") and not name.startswith("gpt")

def get_temperature(model: str) -> float:
    """
    Get the temperature setting for a given model.
    
    Args:
        model: The model name
        
    Returns:
        float: Temperature value (1.0 for o-series models or gemini models, 0.1 otherwise)
    """
    if not model:
        return 0.1
    
    model_lower = model.strip().lower()
    
    # O-series models require temperature=1
    if is_o_series_model(model):
        return 1.0
    
    # Gemini models use temperature=1
    if model_lower.startswith("gemini/"):
        return 1.0
    
    # Default temperature for other models
    return 0.1

def is_retryable_error(exception) -> bool:
    """
    Check if an exception is retryable based on error patterns.
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if the exception is retryable, False otherwise
    """
    # First check if it's an exception
    if not isinstance(exception, Exception):
        return False
    
    error_message = str(exception).lower()
    
    # Check for specific retryable error patterns
    retryable_patterns = [
        "503",
        "model is overloaded",
        "unavailable",
        "rate limit",
        "timeout",
        "connection error",
        "internal server error",
        "service unavailable",
        "temporarily unavailable"
    ]
    
    for pattern in retryable_patterns:
        if pattern in error_message:
            return True
    
    return False

@stamina.retry(on=is_retryable_error)
async def _litellm_acompletion_with_retry(
    model: str,
    messages: list,
    api_key: str,
    response_format: Optional[Dict] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_region_name: Optional[str] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[Union[str, Dict]] = None
):
    """
    Make an LLM call with stamina retry mechanism.
    
    Args:
        model: The LLM model to use
        messages: The messages to send
        api_key: The API key
        response_format: The response format
        aws_access_key_id: AWS access key (for Bedrock)
        aws_secret_access_key: AWS secret key (for Bedrock)
        aws_region_name: AWS region (for Bedrock)
        tools: Optional list of tools/functions for the model to call
        tool_choice: Optional tool choice parameter ("auto", "none", or specific function)
        
    Returns:
        The LLM response
        
    Raises:
        Exception: If the call fails after all retries
    """
    temperature = get_temperature(model)
    params = {
        "model": model,
        "messages": messages,
        "api_key": api_key,
        "temperature": temperature,
        "response_format": response_format,
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "aws_region_name": aws_region_name
    }
    
    # Add tools if provided
    if tools:
        params["tools"] = tools
        params["tool_choice"] = tool_choice if tool_choice is not None else "auto"
    
    return await litellm.acompletion(**params)


async def agent_completion(
    model: str,
    messages: list,
    api_key: str,
    response_format: Optional[Dict] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_region_name: Optional[str] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[Union[str, Dict]] = None
):
    """
    Public wrapper for agent/chat use. Makes one LLM completion call with optional tools.
    Each call checks SPU at the caller; this only performs the litellm call with retry.
    """
    return await _litellm_acompletion_with_retry(
        model=model,
        messages=messages,
        api_key=api_key,
        response_format=response_format,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region_name=aws_region_name,
        tools=tools,
        tool_choice=tool_choice,
    )


@stamina.retry(on=is_retryable_error)
async def _litellm_acreate_file_with_retry(
    file: tuple,
    purpose: str,
    custom_llm_provider: str,
    api_key: str
):
    """
    Create a file with litellm with stamina retry mechanism.
    
    Args:
        file: The file tuple (filename, file_content)
        purpose: The purpose of the file (e.g., "assistants")
        custom_llm_provider: The LLM provider (e.g., "openai")
        api_key: The API key
        
    Returns:
        The file creation response
        
    Raises:
        Exception: If the call fails after all retries
    """
    return await litellm.acreate_file(
        file=file,
        purpose=purpose,
        custom_llm_provider=custom_llm_provider,
        api_key=api_key
    )

async def run_llm(analytiq_client, 
                  document_id: str,
                  prompt_revid: str = "default",
                  llm_model: str = None,
                  force: bool = False) -> dict:
    """
    Run the LLM for the given document and prompt.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID
        llm_model: The model to use (e.g. "gpt-4", "claude-3-sonnet", "mixtral-8x7b-32768")
               If not provided, the model will be retrieved from the prompt.
        force: If True, run the LLM even if the result is already cached
    
    Returns:
        dict: The LLM result
    """
    # Check for existing result unless force is True
    if not force:
        existing_result = await get_llm_result(analytiq_client, document_id, prompt_revid)
        if existing_result:
            logger.info(f"Using cached LLM result for doc_id/prompt_revid {document_id}/{prompt_revid}")
            return existing_result["llm_result"]
    else:
        # Delete the existing result
        await delete_llm_result(analytiq_client, document_id, prompt_revid)

    if not llm_model:
        logger.info(f"Running new LLM analysis for doc_id/prompt_revid {document_id}/{prompt_revid}")
    else:
        logger.info(f"Running new LLM analysis for doc_id/prompt_revid {document_id}/{prompt_revid} with passed-in model {llm_model}")

    # 1. Get the document and organization_id
    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    org_id = doc.get("organization_id")
    if not org_id:
        raise Exception("Document missing organization_id")

    # 2. Determine LLM model
    if llm_model is None:
        llm_model = await ad.llm.get_llm_model(analytiq_client, prompt_revid)

    # 3. Determine SPU cost for this LLM
    spu_cost = await ad.payments.get_spu_cost(llm_model)

    # 4. Determine number of pages (example: from doc['num_pages'] or OCR)
    num_pages = doc.get("num_pages", 1)  # You may need to adjust this

    total_spu_needed = spu_cost * num_pages

    # 5. Check if org has enough credits (throws SPUCreditException if insufficient)
    await ad.payments.check_spu_limits(org_id, total_spu_needed)

    if not ad.llm.is_chat_model(llm_model) and not ad.llm.is_supported_model(llm_model):
        logger.info(f"{document_id}/{prompt_revid}: LLM model {llm_model} is not a chat model, falling back to default llm_model")
        llm_model = "gpt-4o-mini"

    # Get the provider for the given LLM model
    llm_provider = ad.llm.get_llm_model_provider(llm_model)
    if llm_provider is None:
        logger.info(f"{document_id}/{prompt_revid}: LLM model {llm_model} not supported, falling back to default llm_model")
        llm_model = "gpt-4o-mini"
        llm_provider = "openai"
        
    api_key = await ad.llm.get_llm_key(analytiq_client, llm_provider)
    logger.info(f"{document_id}/{prompt_revid}: LLM model: {llm_model}, provider: {llm_provider}, api_key: {api_key[:16]}********")

    extracted_text = await get_extracted_text(analytiq_client, document_id)
    file_attachment_blob, file_attachment_name = await get_file_attachment(analytiq_client, doc, llm_provider, llm_model)

    if not extracted_text and not file_attachment_blob:
        raise Exception(f"{document_id}/{prompt_revid}: Document has no extracted text and no file attachment, so cannot use vision")

    prompt1 = await ad.common.get_prompt_content(analytiq_client, prompt_revid)
    
    # Check if prompt has KB ID for RAG (do this early to modify system prompt if needed)
    kb_id = await ad.common.get_prompt_kb_id(analytiq_client, prompt_revid)
    
    # Define system_prompt before using it
    if kb_id:
        system_prompt = (
            "You are a helpful assistant that extracts document information into JSON format. "
            "You have access to a knowledge base that contains additional context from related documents. "
            "Use the search_knowledge_base tool when you need additional information beyond what's in the current document. "
            "Always respond with valid JSON only, no other text. "
            "Format your entire response as a JSON object."
        )
    else:
        system_prompt = (
            "You are a helpful assistant that extracts document information into JSON format. "
            "Always respond with valid JSON only, no other text. "
            "Format your entire response as a JSON object."
        )
    
    # Determine how to handle the document content
    # XAI doesn't support complex file attachment formats, so use text-only for XAI
    if file_attachment_blob and llm_provider != "xai":
        # For vision models, we can pass both the PDF and OCR text
        # The PDF provides visual context, OCR text provides structured text
        prompt = f"""{prompt1}

        Please analyze this document. You have access to both the visual PDF and the extracted text.
        
        Extracted text from the document:
        {extracted_text}
        
        Please provide your analysis based on both the visual content and the text."""
        
        # Different approaches for different providers
        if llm_provider == "openai":
            # For OpenAI, we need to upload the file first
            try:
                # Upload file to OpenAI
                file_response = await _litellm_acreate_file_with_retry(
                    file=(file_attachment_name, file_attachment_blob),
                    purpose="assistants",
                    custom_llm_provider="openai",
                    api_key=api_key
                )
                file_id = file_response.id
                
                # Create messages with file reference
                file_content = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "file",
                        "file": {
                            "file_id": file_id,
                        }
                    },
                ]
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": file_content}
                ]
                logger.info(f"{document_id}/{prompt_revid}: Attaching OCR and PDF to prompt using OpenAI file_id: {file_id}")
                
            except Exception as e:
                logger.error(f"{document_id}/{prompt_revid}: Failed to upload file to OpenAI: {e}")
                raise e
                
        else:
            # For other providers (Anthropic, Gemini), use base64 approach
            encoded_file = base64.b64encode(file_attachment_blob).decode("utf-8")
            base64_url = f"data:application/pdf;base64,{encoded_file}"
            
            file_content = [
                {"type": "text", "text": prompt},
                {
                    "type": "file",
                    "file": {
                        "file_data": base64_url,
                    }
                },
            ]
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": file_content}
            ]
            logger.info(f"{document_id}/{prompt_revid}: Attaching OCR and PDF to prompt using base64 for {llm_provider}")
    
    # Use OCR-only approach if no file attachment or if provider is XAI (which doesn't support file attachments)
    if not file_attachment_blob or llm_provider == "xai":
        # Original OCR-only approach
        prompt = f"""{prompt1}

        Now extract from this text: 
        
        {extracted_text}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"{document_id}/{prompt_revid}: Attaching OCR-only to prompt")

    response_format = None
    
    # Most but not all models support response_format
    # See https://platform.openai.com/docs/guides/structured-outputs?format=without-parse
    if prompt_revid == "default":
        # Use a default response format
        response_format = {"type": "json_object"}
    elif litellm.supports_response_schema(model=llm_model):
        # Get the prompt response format, if any
        response_format = await ad.common.get_prompt_response_format(analytiq_client, prompt_revid)
        logger.info(f"{document_id}/{prompt_revid}: Response format: {response_format}")
    
    if response_format is None:
        logger.info(f"{document_id}/{prompt_revid}: No response format found for prompt")

    # Bedrock models require aws_access_key_id, aws_secret_access_key, aws_region_name
    if llm_provider == "bedrock":
        aws_client = await ad.aws.get_aws_client_async(analytiq_client, region_name="us-east-1")
        aws_access_key_id = aws_client.aws_access_key_id
        aws_secret_access_key = aws_client.aws_secret_access_key
        aws_region_name = aws_client.region_name
    else:
        aws_access_key_id = None
        aws_secret_access_key = None
        aws_region_name = None

    # Set up tools if KB is enabled (kb_id already retrieved above)
    tools = None
    max_iterations = 5  # Maximum number of tool call iterations
    
    if kb_id:
        # Check if model supports function calling
        if litellm.supports_function_calling(model=llm_model):
            logger.info(f"{document_id}/{prompt_revid}: KB {kb_id} specified, enabling RAG with function calling")
            
            # Define the search_knowledge_base tool
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_knowledge_base",
                        "description": "Search the knowledge base for relevant information to answer questions about documents. Use this when you need additional context beyond what's in the current document.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query to find relevant information in the knowledge base"
                                },
                                "top_k": {
                                    "type": "integer",
                                    "description": "Number of results to return (default: 5)",
                                    "default": 5
                                },
                                "metadata_filter": {
                                    "type": "object",
                                    "description": "Optional metadata filters (document_name, tag_ids, etc.)"
                                },
                                "coalesce_neighbors": {
                                    "type": "integer",
                                    "description": "Number of neighboring chunks to include for context (default: 0)"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]
        else:
            logger.warning(f"{document_id}/{prompt_revid}: KB {kb_id} specified but model {llm_model} doesn't support function calling. RAG disabled.")
            kb_id = None  # Disable KB if model doesn't support it

    # 6. Call the LLM with agentic loop if KB is enabled, otherwise single call
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    
    if kb_id and tools:
        # Agentic loop: handle tool calls iteratively
        iteration = 0
        response = None
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"{document_id}/{prompt_revid}: LLM call iteration {iteration}/{max_iterations}")
            
            response = await _litellm_acompletion_with_retry(
                model=llm_model,
                messages=messages,
                api_key=api_key,
                response_format=response_format,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_region_name=aws_region_name,
                tools=tools,
                tool_choice="auto"  # Always allow tool calls in agentic mode
            )
            
            # Accumulate token usage
            if hasattr(response, 'usage') and response.usage:
                total_prompt_tokens += response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
                total_completion_tokens += response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
                total_cost += litellm.completion_cost(completion_response=response) if hasattr(response, 'usage') else 0.0
            
            # Check if LLM wants to call a tool
            message = response.choices[0].message
            tool_calls = message.tool_calls if hasattr(message, 'tool_calls') and message.tool_calls else []
            
            if not tool_calls:
                # No tool calls - LLM is done, break the loop
                logger.info(f"{document_id}/{prompt_revid}: LLM completed after {iteration} iteration(s)")
                break
            
            # Handle tool calls
            for tool_call in tool_calls:
                if tool_call.function.name == "search_knowledge_base":
                    # Parse function arguments
                    try:
                        args = json.loads(tool_call.function.arguments)
                        search_query = args.get("query", "")
                        top_k = args.get("top_k", 5)
                        metadata_filter = args.get("metadata_filter")
                        coalesce_neighbors = args.get("coalesce_neighbors")
                        
                        logger.info(f"{document_id}/{prompt_revid}: LLM requested KB search: query='{search_query}', top_k={top_k}")
                        
                        # Perform KB search
                        search_results = await ad.kb.search.search_knowledge_base(
                            analytiq_client=analytiq_client,
                            kb_id=kb_id,
                            query=search_query,
                            organization_id=org_id,
                            top_k=top_k,
                            metadata_filter=metadata_filter,
                            coalesce_neighbors=coalesce_neighbors
                        )
                        
                        # Format search results for LLM
                        formatted_context = "Knowledge Base Search Results:\n"
                        for i, result in enumerate(search_results.get("results", []), 1):
                            formatted_context += f"\n[{i}] {result.get('content', '')}\n"
                            formatted_context += f"Source: {result.get('source', 'Unknown')}\n"
                            if result.get('relevance'):
                                formatted_context += f"Relevance: {result.get('relevance'):.3f}\n"
                        
                        # Add tool response to messages
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments
                                    }
                                }
                            ]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": formatted_context
                        })
                        
                        logger.info(f"{document_id}/{prompt_revid}: Added {len(search_results.get('results', []))} KB search results to conversation")
                    except Exception as e:
                        error_msg = str(e)
                        # Check if this is a vector index timing issue
                        if "INITIAL_SYNC" in error_msg or "NOT_STARTED" in error_msg or "cannot query vector index" in error_msg.lower():
                            logger.warning(
                                f"{document_id}/{prompt_revid}: KB search index not ready yet (timing issue). "
                                f"Error: {error_msg[:200]}"
                            )
                            error_content = (
                                "The knowledge base search index is still building. "
                                "This is a temporary issue - please try again in a few moments."
                            )
                        else:
                            logger.error(f"{document_id}/{prompt_revid}: Error handling KB search tool call: {e}")
                            error_content = f"Error searching knowledge base: {error_msg[:200]}"
                        
                        # Add error message to conversation
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments
                                    }
                                }
                            ]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_content
                        })
                else:
                    logger.warning(f"{document_id}/{prompt_revid}: Unknown tool call: {tool_call.function.name}")
            
            # Continue loop to get LLM response with tool results
            if iteration >= max_iterations:
                logger.warning(f"{document_id}/{prompt_revid}: Reached max iterations ({max_iterations}), using last response")
                break
        
        if response is None:
            raise Exception(f"{document_id}/{prompt_revid}: No response received from LLM")
    else:
        # No KB or tools - single LLM call
        response = await _litellm_acompletion_with_retry(
            model=llm_model,
            messages=messages,  # Use the vision-aware messages
            api_key=api_key,
            response_format=response_format,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region_name=aws_region_name
        )
        
        # Get token usage for single call
        if hasattr(response, 'usage') and response.usage:
            total_prompt_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
            total_completion_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
            total_cost = litellm.completion_cost(completion_response=response) if hasattr(response, 'usage') else 0.0

    # 7. Get actual usage and cost from LLM response
    # For agentic loops, tokens are already accumulated above
    total_tokens = total_prompt_tokens + total_completion_tokens

    # 8. Deduct credits with actual metrics
    await ad.payments.record_spu_usage(
        org_id, 
        total_spu_needed,
        llm_provider=llm_provider,
        llm_model=llm_model,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        actual_cost=total_cost
    )

    # Skip any <think> ... </think> blocks
    resp_content = response.choices[0].message.content
    if resp_content is None:
        # If content is None after agentic loop, the LLM made tool calls but didn't provide final content
        # This shouldn't happen if we break the loop correctly, but handle it gracefully
        if kb_id and tools:
            logger.warning(f"{document_id}/{prompt_revid}: LLM response has no content after agentic loop, may have incomplete tool calls")
            raise Exception(f"LLM response incomplete: model made tool calls but didn't provide final response after {max_iterations} iterations")
        else:
            # For non-agentic calls, content should always be present
            logger.error(f"{document_id}/{prompt_revid}: LLM response has no content")
            raise Exception(f"LLM response has no content")

    # Process response based on LLM provider
    resp_content1 = process_llm_resp_content(resp_content, llm_provider)

    # 9. Return the response
    resp_dict = json.loads(resp_content1)

    # If this is not the default prompt, reorder the response to match schema
    if prompt_revid != "default":
        # Get the prompt response format
        response_format = await ad.common.get_prompt_response_format(analytiq_client, prompt_revid)
        if response_format and response_format.get("type") == "json_schema":
            schema = response_format["json_schema"]["schema"]
            # Get ordered properties from schema
            ordered_properties = list(schema.get("properties", {}).keys())
            
            #logger.info(f"Ordered properties: {ordered_properties}")

            # Create new ordered dictionary based on schema property order
            ordered_resp = OrderedDict()
            for key in ordered_properties:
                if key in resp_dict:
                    ordered_resp[key] = resp_dict[key]

            #logger.info(f"Ordered response: {ordered_resp}")
            
            # Add any remaining keys that might not be in schema
            for key in resp_dict:
                if key not in ordered_resp:
                    ordered_resp[key] = resp_dict[key]
                    
            resp_dict = dict(ordered_resp)  # Convert back to regular dict

            #logger.info(f"Reordered response: {resp_dict}")

    # 10. Save the new result
    await save_llm_result(analytiq_client, document_id, prompt_revid, resp_dict)

    # Optional per-org webhook: per-prompt completion (non-default prompts only)
    if prompt_revid != "default":
        try:
            prompt_id, prompt_version = await get_prompt_info_from_rev_id(analytiq_client, prompt_revid)
            await ad.webhooks.enqueue_event(
                analytiq_client,
                organization_id=org_id,
                event_type="llm.completed",
                document_id=document_id,
                prompt={
                    "prompt_revid": prompt_revid,
                    "prompt_id": prompt_id,
                    "prompt_version": prompt_version,
                },
                llm_output=resp_dict,
            )
        except Exception as e:
            logger.warning(f"{document_id}/{prompt_revid}: webhook enqueue failed: {e}")
    
    return resp_dict

async def get_llm_result(analytiq_client,
                         document_id: str,
                         prompt_revid: str,
                         fallback: bool = False) -> dict | None:
    """
    Retrieve the latest LLM result from MongoDB.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID
        fallback: If True, return the latest LLM result available for the prompt_id
    
    Returns:
        dict | None: The latest LLM result if found, None otherwise
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    
    if not fallback:
        result = await db.llm_runs.find_one(
            {
                "document_id": document_id,
                "prompt_revid": prompt_revid
            },
            sort=[("_id", -1)]
        )
    else:
        # Get the prompt_id and prompt_version from the prompt_revid
        prompt_id, _ = await get_prompt_info_from_rev_id(analytiq_client, prompt_revid)
        # Sort by _id in descending order to get the latest available result for the prompt_id
        result = await db.llm_runs.find_one(
            {
                "document_id": document_id,
                "prompt_id": prompt_id,
            },
            sort=[("prompt_version", -1)]
        )

    return result

async def get_prompt_info_from_rev_id(analytiq_client, prompt_revid: str) -> tuple[str, int]:
    """
    Get prompt_id and prompt_version from prompt_revid.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        prompt_revid: The prompt revision ID
        
    Returns:
        tuple[str, int]: (prompt_id, prompt_version)
    """
    # Special case for the default prompt
    if prompt_revid == "default":
        return "default", 1
    
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    
    # Get the prompt revision
    elem = await db.prompt_revisions.find_one({"_id": ObjectId(prompt_revid)})
    if elem is None:
        raise ValueError(f"Prompt revision {prompt_revid} not found")
    
    return str(elem["prompt_id"]), elem["prompt_version"]

async def save_llm_result(analytiq_client, 
                          document_id: str,
                          prompt_revid: str, 
                          llm_result: dict) -> str:
    """
    Save the LLM result to MongoDB.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID
        llm_result: The LLM result
    """

    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]

    current_time_utc = datetime.now(UTC)
    
    # Get prompt_id and prompt_version from prompt_revid
    prompt_id, prompt_version = await get_prompt_info_from_rev_id(analytiq_client, prompt_revid)

    element = {
        "prompt_revid": prompt_revid,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "document_id": document_id,
        "llm_result": llm_result,
        "updated_llm_result": llm_result.copy(),
        "is_edited": False,
        "is_verified": False,
        "created_at": current_time_utc,
        "updated_at": current_time_utc
    }

    logger.info(f"Saving LLM result: {element}")

    # Save the result, return the ID
    result = await db.llm_runs.insert_one(element)
    return str(result.inserted_id)

async def delete_llm_result(analytiq_client,
                            document_id: str,
                            prompt_revid: str | None = None) -> bool:
    """
    Delete an LLM result from MongoDB.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID. If None, delete all LLM results for the document.
    
    Returns:
        bool: True if deleted, False if not found
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]

    delete_filter = {
        "document_id": document_id
    }

    if prompt_revid is not None:
        delete_filter["prompt_revid"] = prompt_revid

    result = await db.llm_runs.delete_many(delete_filter)
    
    return result.deleted_count > 0


async def run_llm_for_prompt_revids(analytiq_client, document_id: str, prompt_revids: list[str], llm_model: str = None) -> None:
    """
    Run the LLM for the given prompt IDs.

    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revids: The prompt revision IDs to run the LLM for
    """

    n_prompts = len(prompt_revids)

    # Create n_prompts concurrent tasks
    tasks = [run_llm(analytiq_client, document_id, prompt_revid, llm_model) for prompt_revid in prompt_revids]

    # Run the tasks
    results = await asyncio.gather(*tasks)

    logger.info(f"LLM run completed for {document_id} with {n_prompts} prompts: {results}")

    return results

async def update_llm_result(analytiq_client,
                            document_id: str,
                            prompt_revid: str,
                            updated_llm_result: dict,
                            is_verified: bool = False) -> str:
    """
    Update an existing LLM result with edits and verification status.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID
        updated_llm_result: The updated LLM result
        is_verified: Whether this result has been verified
    
    Returns:
        str: The ID of the updated document
        
    Raises:
        ValueError: If no existing result found or if result signatures don't match
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    
    # Get the latest result
    existing = await db.llm_runs.find_one(
        {
            "document_id": document_id,
            "prompt_revid": prompt_revid
        },
        sort=[("_id", -1)]
    )
    
    if not existing:
        raise ValueError(f"No existing LLM result found for document_id: {document_id}, prompt_revid: {prompt_revid}")
    
    # Validate that the updated result has the same structure as the original
    existing_keys = set(existing["llm_result"].keys())
    updated_keys = set(updated_llm_result.keys())
    
    if existing_keys != updated_keys:
        raise ValueError(
            f"Updated result signature does not match original. "
            f"Original keys: {sorted(existing_keys)}, "
            f"Updated keys: {sorted(updated_keys)}"
        )

    current_time_utc = datetime.now(UTC)
    created_at = existing.get("created_at", current_time_utc)
    updated_at = current_time_utc
    
    # Update the document
    update_data = {
        "llm_result": existing["llm_result"],
        "updated_llm_result": updated_llm_result,
        "is_edited": True,
        "is_verified": is_verified,
        "created_at": created_at,
        "updated_at": updated_at
    }
    
    result = await db.llm_runs.update_one(
        {"_id": existing["_id"]},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise ValueError("Failed to update LLM result")
        
    return str(existing["_id"])

async def run_llm_chat(
    request: "LLMPromptRequest",
    current_user: "User"
) -> Union[dict, "StreamingResponse"]:
    """
    Test LLM with arbitrary prompt (admin only).
    Supports both streaming and non-streaming responses.
    
    Args:
        request: The LLM prompt request
        current_user: The current user making the request
    
    Returns:
        Union[dict, StreamingResponse]: Either a chat completion response or a streaming response
    """
    
    logger.info(f"run_llm_chat() start: model: {request.model}, stream: {request.stream}")

    # Verify the model exists and is enabled
    db = ad.common.get_async_db()
    found = False
    for provider in await db.llm_providers.find({}).to_list(None):
        if request.model in provider["litellm_models_enabled"]:
            found = True
            break
    if not found:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {request.model}"
        )

    try:
        # Prepare messages for litellm
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Prepare parameters
        params = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }
        
        if request.max_tokens:
            params["max_tokens"] = request.max_tokens
        
        # Get the provider and API key for this model
        llm_provider = ad.llm.get_llm_model_provider(request.model)
        analytiq_client = ad.common.get_analytiq_client()
        
        # Get the API key for the provider
        api_key = await ad.llm.get_llm_key(analytiq_client, llm_provider)
        if api_key:
            params["api_key"] = api_key
            logger.info(f"Using API key for provider {llm_provider}: {api_key[:16]}********")
        
        # Handle Bedrock-specific configuration
        if llm_provider == "bedrock":
            aws_client = await ad.aws.get_aws_client_async(analytiq_client, region_name="us-east-1")
            params["aws_access_key_id"] = aws_client.aws_access_key_id
            params["aws_secret_access_key"] = aws_client.aws_secret_access_key
            params["aws_region_name"] = aws_client.region_name
            logger.info(f"Bedrock config: region={aws_client.region_name}")
        
        if request.stream:
            # Streaming response
            async def generate_stream():
                try:
                    params["temperature"] = get_temperature(params["model"])
                    response = await litellm.acompletion(**params, stream=True)
                    async for chunk in response:
                        if chunk.choices[0].delta.content:
                            yield f"data: {json.dumps({'chunk': chunk.choices[0].delta.content, 'done': False})}\n\n"
                    # Send final done signal
                    yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                except Exception as e:
                    logger.error(f"Error in streaming LLM response: {str(e)}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        else:
            # Non-streaming response
            params["temperature"] = get_temperature(params["model"])
            response = await litellm.acompletion(**params)
            
            return {
                "id": response.id,
                "object": "chat.completion",
                "created": int(datetime.now(UTC).timestamp()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response.choices[0].message.content
                        },
                        "finish_reason": response.choices[0].finish_reason
                    }
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
    except Exception as e:
        logger.error(f"Error in LLM test: {str(e)}")
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Error processing LLM request: {str(e)}"
        )


async def run_kb_chat(
    analytiq_client,
    kb_id: str,
    organization_id: str,
    request: "KBChatRequest",
    current_user: "User"
):
    """
    Chat with a knowledge base using LLM with tool calling support.
    Supports both streaming and non-streaming responses with tool use reporting.

    When request.stream is True, returns a StreamingResponse (SSE).
    When request.stream is False, returns a dict with keys: text, tool_calls (optional), tool_results (optional).
    
    Args:
        analytiq_client: The analytiq client
        kb_id: Knowledge base ID
        organization_id: Organization ID
        request: The KB chat request
        current_user: The current user making the request
    
    Returns:
        StreamingResponse if request.stream else dict with text, tool_calls, tool_results
    """
    import json
    from fastapi.responses import StreamingResponse
    from fastapi import HTTPException
    from app.routes.payments import SPUCreditException
    
    logger.info(f"run_kb_chat() start: kb_id={kb_id}, model={request.model}, stream={request.stream}")
    
    # Verify KB exists and is active
    db = ad.common.get_async_db(analytiq_client)
    kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id), "organization_id": organization_id})
    if not kb:
        raise HTTPException(
            status_code=404,
            detail=f"Knowledge base {kb_id} not found"
        )
    
    if kb.get("status") != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Knowledge base {kb_id} is not active (status: {kb.get('status')}). Please wait for indexing to complete."
        )
    
    # Verify the model exists and is enabled
    found = False
    for provider in await db.llm_providers.find({}).to_list(None):
        if request.model in provider["litellm_models_enabled"]:
            found = True
            break
    if not found:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {request.model}"
        )
    
    # Verify model supports function calling
    if not litellm.supports_function_calling(model=request.model):
        raise HTTPException(
            status_code=400,
            detail=f"Model {request.model} does not support function calling. Please select a different model."
        )
    
    # Determine SPU cost for this LLM (1 SPU per chat conversation)
    spu_cost = await ad.payments.get_spu_cost(request.model)
    total_spu_needed = spu_cost  # 1 SPU per chat conversation
    
    # Check if org has enough credits (throws SPUCreditException if insufficient)
    await ad.payments.check_spu_limits(organization_id, total_spu_needed)
    
    try:
        # Prepare messages for litellm
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Get the provider and API key for this model
        llm_provider = ad.llm.get_llm_model_provider(request.model)
        
        # Get the API key for the provider
        api_key = await ad.llm.get_llm_key(analytiq_client, llm_provider)
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail=f"No API key found for provider {llm_provider}"
            )
        
        # Handle Bedrock-specific configuration
        aws_access_key_id = None
        aws_secret_access_key = None
        aws_region_name = None
        if llm_provider == "bedrock":
            aws_client = await ad.aws.get_aws_client_async(analytiq_client, region_name="us-east-1")
            aws_access_key_id = aws_client.aws_access_key_id
            aws_secret_access_key = aws_client.aws_secret_access_key
            aws_region_name = aws_client.region_name
        
        # Define the search_knowledge_base tool
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge_base",
                    "description": "Search the knowledge base for relevant information to answer questions. Use this when you need additional context from the knowledge base.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find relevant information in the knowledge base"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of results to return (default: 5)",
                                "default": 5
                            },
                            "metadata_filter": {
                                "type": "object",
                                "description": "Optional metadata filters (document_name, tag_ids, etc.)"
                            },
                            "coalesce_neighbors": {
                                "type": "integer",
                                "description": "Number of neighboring chunks to include for context (default: 0)"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
        
        max_iterations = 5
        
        # Streaming response with agentic loop
        # Use non-streaming for agentic loop to properly handle tool calls,
        # then stream the final response
        async def generate_stream():
            # Initialize cost tracking (outside try block so accessible in exception handler)
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_cost = 0.0
            
            try:
                iteration = 0
                
                while iteration < max_iterations:
                    iteration += 1
                    logger.info(f"KB chat iteration {iteration}/{max_iterations}")
                    
                    # Prepare parameters for LLM call (non-streaming for agentic loop)
                    params = {
                        "model": request.model,
                        "messages": messages,
                        "api_key": api_key,
                        "temperature": get_temperature(request.model),
                        "tools": tools,
                        "tool_choice": "auto",
                        "stream": False  # Non-streaming for proper tool call handling
                    }
                    
                    if request.max_tokens:
                        params["max_tokens"] = request.max_tokens
                    
                    if aws_access_key_id:
                        params["aws_access_key_id"] = aws_access_key_id
                        params["aws_secret_access_key"] = aws_secret_access_key
                        params["aws_region_name"] = aws_region_name
                    
                    # Call LLM (non-streaming)
                    response = await _litellm_acompletion_with_retry(
                        model=request.model,
                        messages=messages,
                        api_key=api_key,
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key,
                        aws_region_name=aws_region_name,
                        tools=tools,
                        tool_choice="auto"
                    )
                    
                    # Accumulate token usage and cost
                    if hasattr(response, 'usage') and response.usage:
                        total_prompt_tokens += response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
                        total_completion_tokens += response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
                        total_cost += litellm.completion_cost(completion_response=response) if hasattr(response, 'usage') else 0.0
                    
                    # Check if LLM wants to call a tool
                    message = response.choices[0].message
                    tool_calls = message.tool_calls if hasattr(message, 'tool_calls') and message.tool_calls else []
                    
                    if not tool_calls:
                        # No tool calls - LLM is done, stream the final response
                        final_content = message.content or ""
                        if final_content:
                            # Stream the final content character by character for better UX
                            for char in final_content:
                                yield f"data: {json.dumps({'chunk': char, 'done': False})}\n\n"
                        
                        # Add final message to conversation
                        messages.append({
                            "role": "assistant",
                            "content": final_content
                        })
                        break
                    
                    # Handle tool calls
                    for tool_call in tool_calls:
                        if tool_call.function.name == "search_knowledge_base":
                            # Parse function arguments
                            try:
                                args = json.loads(tool_call.function.arguments)
                                search_query = args.get("query", "")
                                top_k = args.get("top_k", 5)
                                metadata_filter = args.get("metadata_filter")
                                coalesce_neighbors = args.get("coalesce_neighbors")
                                
                                # Emit tool call event
                                yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': 'search_knowledge_base', 'arguments': args, 'iteration': iteration, 'done': False})}\n\n"
                                
                                # Perform KB search
                                # Merge request-level filters (from UI) with LLM tool call filters
                                # Request filters take precedence as they come from user's explicit filter settings
                                final_metadata_filter = request.metadata_filter if request.metadata_filter else metadata_filter
                                # If both exist, merge them (request filters override LLM filters)
                                if request.metadata_filter and metadata_filter:
                                    final_metadata_filter = {**metadata_filter, **request.metadata_filter}
                                
                                try:
                                    search_results = await ad.kb.search.search_knowledge_base(
                                        analytiq_client=analytiq_client,
                                        kb_id=kb_id,
                                        query=search_query,
                                        organization_id=organization_id,
                                        top_k=top_k,
                                        metadata_filter=final_metadata_filter,
                                        upload_date_from=request.upload_date_from,
                                        upload_date_to=request.upload_date_to,
                                        coalesce_neighbors=coalesce_neighbors
                                    )
                                    
                                    results_count = len(search_results.get("results", []))
                                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': 'search_knowledge_base', 'results_count': results_count, 'iteration': iteration, 'done': False})}\n\n"
                                    
                                    # Format search results for LLM
                                    formatted_context = "Knowledge Base Search Results:\n"
                                    for i, result in enumerate(search_results.get("results", []), 1):
                                        formatted_context += f"\n[{i}] {result.get('content', '')}\n"
                                        formatted_context += f"Source: {result.get('source', 'Unknown')}\n"
                                        if result.get('relevance'):
                                            formatted_context += f"Relevance: {result.get('relevance'):.3f}\n"
                                    
                                except SPUCreditException as e:
                                    error_content = f"Insufficient SPU credits: {str(e)}"
                                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': 'search_knowledge_base', 'error': error_content, 'iteration': iteration, 'done': False})}\n\n"
                                    formatted_context = error_content
                                    
                                except Exception as e:
                                    error_msg = str(e)
                                    if "INITIAL_SYNC" in error_msg or "NOT_STARTED" in error_msg or "cannot query vector index" in error_msg.lower():
                                        error_content = "The knowledge base search index is still building. Please try again in a few moments."
                                    else:
                                        error_content = f"Error searching knowledge base: {error_msg[:200]}"
                                    
                                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': 'search_knowledge_base', 'error': error_content, 'iteration': iteration, 'done': False})}\n\n"
                                    formatted_context = error_content
                                
                                # Add tool response to messages
                                messages.append({
                                    "role": "assistant",
                                    "content": message.content if message.content else None,
                                    "tool_calls": [
                                        {
                                            "id": tool_call.id,
                                            "type": "function",
                                            "function": {
                                                "name": tool_call.function.name,
                                                "arguments": tool_call.function.arguments
                                            }
                                        }
                                    ]
                                })
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": formatted_context
                                })
                                
                            except json.JSONDecodeError as e:
                                logger.error(f"Error parsing tool call arguments: {e}")
                                continue
                        else:
                            logger.warning(f"Unknown tool call: {tool_call.function.name}")
                    
                    # Continue loop to get LLM response with tool results
                    if iteration >= max_iterations:
                        logger.warning(f"Reached max iterations ({max_iterations})")
                        # Stream any content we have
                        if message.content:
                            for char in message.content:
                                yield f"data: {json.dumps({'chunk': char, 'done': False})}\n\n"
                        break
                
                # Send final done signal
                yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                
                # Record SPU usage after stream completes
                total_tokens = total_prompt_tokens + total_completion_tokens
                try:
                    await ad.payments.record_spu_usage(
                        org_id=organization_id,
                        spus=total_spu_needed,
                        llm_provider=llm_provider,
                        llm_model=request.model,
                        prompt_tokens=total_prompt_tokens,
                        completion_tokens=total_completion_tokens,
                        total_tokens=total_tokens,
                        actual_cost=total_cost
                    )
                    logger.info(f"Recorded {total_spu_needed} SPU usage for KB chat, actual cost: ${total_cost:.6f}, tokens: {total_tokens}")
                except Exception as e:
                    logger.error(f"Error recording SPU usage for KB chat: {e}")
                    # Don't fail the chat if SPU recording fails
                
            except SPUCreditException as e:
                logger.warning(f"SPU credit exhausted in KB chat: {str(e)}")
                yield f"data: {json.dumps({'error': f'Insufficient SPU credits: {str(e)}', 'done': True})}\n\n"
            except Exception as e:
                logger.error(f"Error in KB chat streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
                # Try to record usage even on error (if we have any cost data)
                if total_cost > 0 or total_prompt_tokens > 0:
                    try:
                        total_tokens = total_prompt_tokens + total_completion_tokens
                        await ad.payments.record_spu_usage(
                            org_id=organization_id,
                            spus=total_spu_needed,
                            llm_provider=llm_provider,
                            llm_model=request.model,
                            prompt_tokens=total_prompt_tokens,
                            completion_tokens=total_completion_tokens,
                            total_tokens=total_tokens,
                            actual_cost=total_cost
                        )
                        logger.info(f"Recorded {total_spu_needed} SPU usage for KB chat (error case), actual cost: ${total_cost:.6f}")
                    except Exception as record_error:
                        logger.error(f"Error recording SPU usage for KB chat after error: {record_error}")
        
        async def run_non_streaming():
            """Run the same agentic loop but collect into a single dict (text, tool_calls, tool_results)."""
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_cost = 0.0
            result = {"text": "", "tool_calls": [], "tool_results": []}
            try:
                iteration = 0
                while iteration < max_iterations:
                    iteration += 1
                    logger.info(f"KB chat iteration {iteration}/{max_iterations}")
                    response = await _litellm_acompletion_with_retry(
                        model=request.model,
                        messages=messages,
                        api_key=api_key,
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key,
                        aws_region_name=aws_region_name,
                        tools=tools,
                        tool_choice="auto"
                    )
                    if hasattr(response, 'usage') and response.usage:
                        total_prompt_tokens += response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
                        total_completion_tokens += response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
                        total_cost += litellm.completion_cost(completion_response=response) if hasattr(response, 'usage') else 0.0
                    message = response.choices[0].message
                    tool_calls = message.tool_calls if hasattr(message, 'tool_calls') and message.tool_calls else []
                    if not tool_calls:
                        final_content = message.content or ""
                        result["text"] = final_content
                        messages.append({"role": "assistant", "content": final_content})
                        break
                    for tool_call in tool_calls:
                        if tool_call.function.name == "search_knowledge_base":
                            try:
                                args = json.loads(tool_call.function.arguments)
                                search_query = args.get("query", "")
                                top_k = args.get("top_k", 5)
                                metadata_filter = args.get("metadata_filter")
                                coalesce_neighbors = args.get("coalesce_neighbors")
                                result["tool_calls"].append({
                                    "type": "tool_call",
                                    "tool_name": "search_knowledge_base",
                                    "arguments": args,
                                    "iteration": iteration,
                                    "done": False
                                })
                                final_metadata_filter = request.metadata_filter if request.metadata_filter else metadata_filter
                                if request.metadata_filter and metadata_filter:
                                    final_metadata_filter = {**metadata_filter, **request.metadata_filter}
                                try:
                                    search_results = await ad.kb.search.search_knowledge_base(
                                        analytiq_client=analytiq_client,
                                        kb_id=kb_id,
                                        query=search_query,
                                        organization_id=organization_id,
                                        top_k=top_k,
                                        metadata_filter=final_metadata_filter,
                                        upload_date_from=request.upload_date_from,
                                        upload_date_to=request.upload_date_to,
                                        coalesce_neighbors=coalesce_neighbors
                                    )
                                    results_count = len(search_results.get("results", []))
                                    result["tool_results"].append({
                                        "type": "tool_result",
                                        "tool_name": "search_knowledge_base",
                                        "results_count": results_count,
                                        "iteration": iteration,
                                        "done": False
                                    })
                                    formatted_context = "Knowledge Base Search Results:\n"
                                    for i, result_item in enumerate(search_results.get("results", []), 1):
                                        formatted_context += f"\n[{i}] {result_item.get('content', '')}\n"
                                        formatted_context += f"Source: {result_item.get('source', 'Unknown')}\n"
                                        if result_item.get('relevance'):
                                            formatted_context += f"Relevance: {result_item.get('relevance'):.3f}\n"
                                except SPUCreditException as e:
                                    error_content = f"Insufficient SPU credits: {str(e)}"
                                    result["tool_results"].append({
                                        "type": "tool_result",
                                        "tool_name": "search_knowledge_base",
                                        "error": error_content,
                                        "iteration": iteration,
                                        "done": False
                                    })
                                    formatted_context = error_content
                                except Exception as e:
                                    error_msg = str(e)
                                    if "INITIAL_SYNC" in error_msg or "NOT_STARTED" in error_msg or "cannot query vector index" in error_msg.lower():
                                        error_content = "The knowledge base search index is still building. Please try again in a few moments."
                                    else:
                                        error_content = f"Error searching knowledge base: {error_msg[:200]}"
                                    result["tool_results"].append({
                                        "type": "tool_result",
                                        "tool_name": "search_knowledge_base",
                                        "error": error_content,
                                        "iteration": iteration,
                                        "done": False
                                    })
                                    formatted_context = error_content
                                messages.append({
                                    "role": "assistant",
                                    "content": message.content if message.content else None,
                                    "tool_calls": [{
                                        "id": tool_call.id,
                                        "type": "function",
                                        "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments}
                                    }]
                                })
                                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": formatted_context})
                            except json.JSONDecodeError as e:
                                logger.error(f"Error parsing tool call arguments: {e}")
                        else:
                            logger.warning(f"Unknown tool call: {tool_call.function.name}")
                    if iteration >= max_iterations:
                        if message.content:
                            result["text"] = message.content
                        break
                total_tokens = total_prompt_tokens + total_completion_tokens
                try:
                    await ad.payments.record_spu_usage(
                        org_id=organization_id,
                        spus=total_spu_needed,
                        llm_provider=llm_provider,
                        llm_model=request.model,
                        prompt_tokens=total_prompt_tokens,
                        completion_tokens=total_completion_tokens,
                        total_tokens=total_tokens,
                        actual_cost=total_cost
                    )
                    logger.info(f"Recorded {total_spu_needed} SPU usage for KB chat (non-streaming), actual cost: ${total_cost:.6f}, tokens: {total_tokens}")
                except Exception as e:
                    logger.error(f"Error recording SPU usage for KB chat: {e}")
                return result
            except SPUCreditException as e:
                logger.warning(f"SPU credit exhausted in KB chat: {str(e)}")
                result["error"] = f"Insufficient SPU credits: {str(e)}"
                return result
            except Exception as e:
                logger.error(f"Error in KB chat non-streaming: {str(e)}")
                result["error"] = str(e)
                if total_cost > 0 or total_prompt_tokens > 0:
                    try:
                        total_tokens = total_prompt_tokens + total_completion_tokens
                        await ad.payments.record_spu_usage(
                            org_id=organization_id,
                            spus=total_spu_needed,
                            llm_provider=llm_provider,
                            llm_model=request.model,
                            prompt_tokens=total_prompt_tokens,
                            completion_tokens=total_completion_tokens,
                            total_tokens=total_tokens,
                            actual_cost=total_cost
                        )
                    except Exception as record_error:
                        logger.error(f"Error recording SPU usage for KB chat after error: {record_error}")
                return result
        
        if request.stream:
            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        return await run_non_streaming()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KB chat: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing KB chat request: {str(e)}"
        )


def get_embedding_models(provider: str = "openai") -> List[Dict[str, Any]]:
    """
    Get all embedding models for a given provider.
    
    Args:
        provider: The litellm provider name (e.g., "openai", "cohere", "azure")
    
    Returns:
        List of dictionaries, each containing:
        - name: Model name
        - dimensions: Embedding vector dimensions (output_vector_size)
        - input_cost_per_token: Cost per token for input
        - input_cost_per_token_batches: Cost per token for batched input (if available)
    """
    models = litellm.models_by_provider.get(provider, [])
    embedding_models = []
    
    for model in models:
        try:
            model_info = litellm.get_model_info(model)
            # Check if this is an embedding model
            if model_info.get('mode') == 'embedding':
                # Get cost information from model_cost
                input_cost_per_token = 0.0
                input_cost_per_token_batches = 0.0
                if model in litellm.model_cost:
                    input_cost_per_token = litellm.model_cost[model].get("input_cost_per_token", 0.0)
                    input_cost_per_token_batches = litellm.model_cost[model].get("input_cost_per_token_batches", 0.0)
                
                embedding_models.append({
                    'name': model,
                    'dimensions': model_info.get('output_vector_size'),
                    'input_cost_per_token': input_cost_per_token,
                    'input_cost_per_token_batches': input_cost_per_token_batches
                })
        except Exception as e:
            # Skip models that can't be queried
            logger.debug(f"Could not get model info for {model}: {e}")
            pass
    
    return embedding_models