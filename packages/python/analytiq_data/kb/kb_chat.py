"""Knowledge base chat: LLM with search_knowledge_base tool calling."""

import json
import logging
from bson import ObjectId

import analytiq_data as ad
import litellm
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from analytiq_data.llm.llm import _litellm_acompletion_with_retry, get_temperature
from analytiq_data.payments.exceptions import SPUCreditException

logger = logging.getLogger(__name__)


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

    if not ad.llm.is_chat_model(request.model):
        raise HTTPException(
            status_code=400,
            detail="Model must be a chat model (same as prompt configuration). Embedding and non-chat models are not supported.",
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

    if request.thread_id:
        scoped = await ad.agent.agent_threads.get_thread_scoped(
            analytiq_client,
            request.thread_id,
            organization_id,
            current_user.user_id,
            kb_id=kb_id,
        )
        if not scoped:
            raise HTTPException(status_code=404, detail="Thread not found")
    
    try:
        # Use KB-level system prompt (if configured) so LLM "prompt caching"
        # can kick in for providers that support it (e.g. Anthropic/Bedrock).
        system_prompt = (kb.get("system_prompt") or "").strip()

        # Prepare messages for litellm
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        if system_prompt and (not messages or messages[0].get("role") != "system"):
            # Ensure the cached prompt is at index 0 and has role="system".
            messages.insert(0, {"role": "system", "content": system_prompt})

        # Capture the message count before the agentic loop so we can identify the
        # delta (current user turn + loop additions) for thread persistence, excluding
        # the injected system prompt.
        initial_len = len(messages)

        # Get the provider and API key for this model
        llm_provider = ad.llm.get_llm_model_provider(request.model)
        
        # Get the API key for the provider
        api_key = await ad.llm.get_llm_key(analytiq_client, llm_provider)
        if not api_key and llm_provider not in ("bedrock", "azure_ai"):
            raise HTTPException(
                status_code=400,
                detail=f"No API key found for provider {llm_provider}"
            )
        
        
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
                                "description": "Number of neighboring chunks to include for context (default: 1)"
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

                    # Call LLM (non-streaming)
                    response = await _litellm_acompletion_with_retry(
                        analytiq_client,
                        model=request.model,
                        messages=messages,
                        api_key=api_key,
                        tools=tools,
                        tool_choice="auto",
                        use_prompt_caching=True,
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
                                    
                                    # Format search results for LLM (merge overlapping spans per document)
                                    formatted_context = ad.kb.format_kb_search_results_for_llm(
                                        search_results.get("results", [])
                                    )
                                    
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

                # Persist turn to thread (user msg + loop additions, excluding system prompt)
                if request.thread_id and initial_len > 0:
                    try:
                        turn_messages = messages[initial_len - 1:]
                        await ad.agent.agent_threads.append_turn(
                            analytiq_client,
                            request.thread_id,
                            organization_id,
                            current_user.user_id,
                            turn_messages,
                            truncate_to=request.truncate_thread_to_message_count,
                        )
                    except Exception as e:
                        logger.error(f"Error persisting KB chat thread: {e}")

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
                        analytiq_client,
                        model=request.model,
                        messages=messages,
                        api_key=api_key,
                        tools=tools,
                        tool_choice="auto",
                        use_prompt_caching=True,
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
                                    formatted_context = ad.kb.format_kb_search_results_for_llm(
                                        search_results.get("results", [])
                                    )
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

                # Persist turn to thread (user msg + loop additions, excluding system prompt)
                if request.thread_id and initial_len > 0:
                    try:
                        turn_messages = messages[initial_len - 1:]
                        await ad.agent.agent_threads.append_turn(
                            analytiq_client,
                            request.thread_id,
                            organization_id,
                            current_user.user_id,
                            turn_messages,
                            truncate_to=request.truncate_thread_to_message_count,
                        )
                    except Exception as e:
                        logger.error(f"Error persisting KB chat thread: {e}")

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
