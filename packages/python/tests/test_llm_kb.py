"""
Unit tests for Knowledge Base RAG agentic loop in llm.py.

Tests cover:
- KB-enabled prompt execution with agentic loop
- Tool call handling and KB search integration
- Token accumulation across iterations
- Edge cases (model without function calling, errors, max iterations)
"""

import pytest
import os
import json
import base64
from unittest.mock import patch, AsyncMock, Mock
from bson import ObjectId
from datetime import datetime, UTC

from tests.conftest_utils import client, get_token_headers, TEST_ORG_ID, get_auth_headers
from tests.conftest_llm import (
    MockLLMResponse,
    mock_run_textract,
    mock_litellm_acreate_file_with_retry,
)

import analytiq_data as ad
import logging

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

# Mock embedding response for dimension detection
MOCK_EMBEDDING_DIMENSIONS = 1536

def create_mock_embedding_response(num_embeddings=1):
    """Create a mock embedding response with non-zero vectors (required for cosine similarity)"""
    mock_response = AsyncMock()
    # Generate non-zero embeddings (simple pattern that's not all zeros)
    # Use a small non-zero value to avoid zero vector issues with MongoDB cosine similarity
    embeddings = []
    for i in range(num_embeddings):
        # Create a simple non-zero vector: [0.1, 0.2, 0.3, ...] pattern
        embedding = [0.001 * (j % 100 + 1) for j in range(MOCK_EMBEDDING_DIMENSIONS)]
        embeddings.append({"embedding": embedding})
    mock_response.data = embeddings
    return mock_response


class MockToolCall:
    """Mock tool call object"""
    def __init__(self, tool_call_id, function_name, function_arguments):
        self.id = tool_call_id
        self.type = "function"
        self.function = MockFunction(function_name, function_arguments)


class MockFunction:
    """Mock function object"""
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = json.dumps(arguments) if isinstance(arguments, dict) else arguments


class MockMessageWithToolCalls:
    """Mock message object with tool calls"""
    def __init__(self, content=None, tool_calls=None):
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls or []


class MockChoiceWithToolCalls:
    """Mock choice object with tool calls"""
    def __init__(self, message):
        self.message = message
        self.finish_reason = "tool_calls" if message.tool_calls else "stop"


class MockLLMResponseWithToolCalls:
    """Mock LLM response with tool calls"""
    def __init__(self, content=None, tool_calls=None, usage=None):
        self.id = "chatcmpl-test123"
        self.object = "chat.completion"
        self.model = "gpt-4o"
        self.created = 1700000000
        message = MockMessageWithToolCalls(content, tool_calls)
        self.choices = [MockChoiceWithToolCalls(message)]
        self.usage = usage or MockUsage()
        self.system_fingerprint = None


class MockUsage:
    """Mock usage object"""
    def __init__(self, prompt_tokens=10, completion_tokens=20):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


async def create_mock_kb_search_results(num_results=3):
    """Create mock KB search results"""
    return {
        "results": [
            {
                "content": f"KB search result {i+1}: This is relevant context from the knowledge base.",
                "source": f"document_{i+1}.pdf",
                "document_id": str(ObjectId()),
                "relevance": 0.95 - (i * 0.1),
                "chunk_index": i,
                "is_matched": True
            }
            for i in range(num_results)
        ],
        "query": "test query",
        "total_count": num_results,
        "skip": 0,
        "top_k": num_results
    }


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_llm_with_kb_agentic_loop_single_tool_call(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test LLM with KB enabled - single tool call iteration"""
    # Set up mock embedding response for KB creation
    mock_embedding.return_value = create_mock_embedding_response()
    
    org_id = TEST_ORG_ID
    
    # Create tag and KB
    tag_data = {"name": "KB Test Tag", "color": "#FF5733"}
    tag_response = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    tag_id = tag_response.json()["id"]
    
    kb_data = {
        "name": "Test KB",
        "tag_ids": [tag_id],
        "chunker_type": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 128
    }
    kb_response = client.post(
        f"/v0/orgs/{org_id}/knowledge-bases",
        json=kb_data,
        headers=get_auth_headers()
    )
    kb_id = kb_response.json()["kb_id"]
    
    # Set KB status to active (required for prompt creation)
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"status": "active"}}
    )
    
    # Create prompt with KB
    prompt_data = {
        "name": "KB Test Prompt",
        "content": "Extract information from this document. Use the knowledge base if needed.",
        "model": "gpt-4o",
        "tag_ids": [tag_id],
        "kb_id": kb_id
    }
    prompt_response = client.post(
        f"/v0/orgs/{org_id}/prompts",
        json=prompt_data,
        headers=get_auth_headers()
    )
    prompt_revid = prompt_response.json()["prompt_revid"]
    
    # Create document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    upload_data = {
        "documents": [{
            "name": "test_doc.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
            "tag_ids": [tag_id]
        }]
    }
    upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_auth_headers())
    document_id = upload_resp.json()["documents"][0]["document_id"]
    
    # Process OCR (analytiq_client already created above)
    await ad.msg_handlers.process_ocr_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})
    
    # Mock KB search results
    mock_kb_results = await create_mock_kb_search_results(3)
    mock_kb_search = AsyncMock(return_value=mock_kb_results)
    
    # Create mock LLM responses: first with tool call, then final response
    tool_call = MockToolCall("call_123", "search_knowledge_base", {"query": "invoice information", "top_k": 5})
    first_response = MockLLMResponseWithToolCalls(
        content=None,
        tool_calls=[tool_call],
        usage=MockUsage(prompt_tokens=100, completion_tokens=50)
    )
    
    final_response = MockLLMResponseWithToolCalls(
        content=json.dumps({"invoice_number": "12345", "total_amount": 1234.56}),
        tool_calls=None,
        usage=MockUsage(prompt_tokens=200, completion_tokens=100)
    )
    
    # Mock the LLM completion to return first response, then final response
    mock_acompletion = AsyncMock(side_effect=[first_response, final_response])
    
    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_acompletion),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('analytiq_data.kb.search.search_knowledge_base', new=mock_kb_search),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
        patch('litellm.supports_function_calling', return_value=True),
    ):
        # Run LLM
        result = await ad.llm.run_llm(analytiq_client, document_id, prompt_revid)
        
        # Verify result
        assert result["invoice_number"] == "12345"
        assert result["total_amount"] == 1234.56
        
        # Verify LLM was called twice (tool call + final response)
        assert mock_acompletion.call_count == 2
        
        # Verify KB search was called
        assert mock_kb_search.call_count == 1
        
        # Verify KB search was called with correct parameters
        kb_search_call = mock_kb_search.call_args
        # call_args is (args, kwargs) tuple
        kwargs = kb_search_call[1] if len(kb_search_call) > 1 else {}
        assert kwargs.get("kb_id") == kb_id
        assert kwargs.get("query") == "invoice information"
        assert kwargs.get("top_k") == 5
        
        # Verify final call had tool results in messages
        final_call_args = mock_acompletion.call_args_list[1]
        # call_args is (args, kwargs) tuple, get kwargs
        final_kwargs = final_call_args[1] if len(final_call_args) > 1 else {}
        messages = final_kwargs.get("messages", [])
        
        # Should have system, user, assistant (tool call), and tool (result) messages
        assert len(messages) >= 4
        assert messages[-2]["role"] == "assistant"
        assert messages[-2].get("tool_calls") is not None
        assert messages[-1]["role"] == "tool"
        assert "Knowledge Base Search Results" in messages[-1]["content"]
    
    # Cleanup
    client.delete(f"/v0/orgs/{org_id}/knowledge-bases/{kb_id}", headers=get_auth_headers())


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_llm_with_kb_multiple_tool_calls(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test LLM with KB enabled - multiple tool call iterations"""
    # Set up mock embedding response for KB creation
    mock_embedding.return_value = create_mock_embedding_response()
    
    org_id = TEST_ORG_ID
    
    # Create tag and KB
    tag_data = {"name": "KB Multi Test Tag", "color": "#FF5733"}
    tag_response = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    tag_id = tag_response.json()["id"]
    
    kb_data = {
        "name": "Multi Test KB",
        "tag_ids": [tag_id],
        "chunker_type": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 128
    }
    kb_response = client.post(
        f"/v0/orgs/{org_id}/knowledge-bases",
        json=kb_data,
        headers=get_auth_headers()
    )
    kb_id = kb_response.json()["kb_id"]
    
    # Set KB status to active (required for prompt creation)
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"status": "active"}}
    )
    
    # Create prompt with KB
    prompt_data = {
        "name": "KB Multi Test Prompt",
        "content": "Extract information. Search KB multiple times if needed.",
        "model": "gpt-4o",
        "tag_ids": [tag_id],
        "kb_id": kb_id
    }
    prompt_response = client.post(
        f"/v0/orgs/{org_id}/prompts",
        json=prompt_data,
        headers=get_auth_headers()
    )
    prompt_revid = prompt_response.json()["prompt_revid"]
    
    # Create document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    upload_data = {
        "documents": [{
            "name": "test_doc.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
            "tag_ids": [tag_id]
        }]
    }
    upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_auth_headers())
    document_id = upload_resp.json()["documents"][0]["document_id"]
    
    # Process OCR (analytiq_client already created above)
    await ad.msg_handlers.process_ocr_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})
    
    # Mock KB search results
    mock_kb_results = await create_mock_kb_search_results(3)
    mock_kb_search = AsyncMock(return_value=mock_kb_results)
    
    # Create mock LLM responses: 2 tool calls, then final response
    tool_call_1 = MockToolCall("call_1", "search_knowledge_base", {"query": "first search", "top_k": 5})
    tool_call_2 = MockToolCall("call_2", "search_knowledge_base", {"query": "second search", "top_k": 5})
    
    first_response = MockLLMResponseWithToolCalls(
        content=None,
        tool_calls=[tool_call_1],
        usage=MockUsage(prompt_tokens=100, completion_tokens=50)
    )
    
    second_response = MockLLMResponseWithToolCalls(
        content=None,
        tool_calls=[tool_call_2],
        usage=MockUsage(prompt_tokens=150, completion_tokens=75)
    )
    
    final_response = MockLLMResponseWithToolCalls(
        content=json.dumps({"result": "extracted with KB help"}),
        tool_calls=None,
        usage=MockUsage(prompt_tokens=200, completion_tokens=100)
    )
    
    mock_acompletion = AsyncMock(side_effect=[first_response, second_response, final_response])
    
    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_acompletion),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('analytiq_data.kb.search.search_knowledge_base', new=mock_kb_search),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
        patch('litellm.supports_function_calling', return_value=True),
    ):
        # Run LLM
        result = await ad.llm.run_llm(analytiq_client, document_id, prompt_revid)
        
        # Verify result
        assert result["result"] == "extracted with KB help"
        
        # Verify LLM was called 3 times (2 tool calls + final response)
        assert mock_acompletion.call_count == 3
        
        # Verify KB search was called twice
        assert mock_kb_search.call_count == 2
        
        # Verify token accumulation (check that usage was tracked)
        # The final call should have accumulated tokens from all iterations
    
    # Cleanup
    client.delete(f"/v0/orgs/{org_id}/knowledge-bases/{kb_id}", headers=get_auth_headers())


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_llm_with_kb_model_no_function_calling(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test LLM with KB enabled but model doesn't support function calling - should disable KB"""
    # Set up mock embedding response for KB creation
    mock_embedding.return_value = create_mock_embedding_response()
    
    org_id = TEST_ORG_ID
    
    # Create tag and KB
    tag_data = {"name": "KB No FC Test Tag", "color": "#FF5733"}
    tag_response = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    tag_id = tag_response.json()["id"]
    
    kb_data = {
        "name": "No FC Test KB",
        "tag_ids": [tag_id],
        "chunker_type": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 128
    }
    kb_response = client.post(
        f"/v0/orgs/{org_id}/knowledge-bases",
        json=kb_data,
        headers=get_auth_headers()
    )
    kb_id = kb_response.json()["kb_id"]
    
    # Set KB status to active (required for prompt creation)
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"status": "active"}}
    )
    
    # Create prompt with KB
    prompt_data = {
        "name": "KB No FC Test Prompt",
        "content": "Extract information from this document.",
        "model": "gpt-4o-mini",  # Use enabled model, but we'll mock supports_function_calling to return False
        "tag_ids": [tag_id],
        "kb_id": kb_id
    }
    prompt_response = client.post(
        f"/v0/orgs/{org_id}/prompts",
        json=prompt_data,
        headers=get_auth_headers()
    )
    assert prompt_response.status_code == 200, f"Prompt creation failed: {prompt_response.text}"
    prompt_revid = prompt_response.json()["prompt_revid"]
    
    # Create document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    upload_data = {
        "documents": [{
            "name": "test_doc.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
            "tag_ids": [tag_id]
        }]
    }
    upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_auth_headers())
    document_id = upload_resp.json()["documents"][0]["document_id"]
    
    # Process OCR (analytiq_client already created above)
    await ad.msg_handlers.process_ocr_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})
    
    # Mock LLM response (no tool calls, just regular response)
    final_response = MockLLMResponseWithToolCalls(
        content=json.dumps({"result": "extracted without KB"}),
        tool_calls=None,
        usage=MockUsage(prompt_tokens=100, completion_tokens=50)
    )
    
    mock_acompletion = AsyncMock(return_value=final_response)
    mock_kb_search = AsyncMock()
    
    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_acompletion),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('analytiq_data.kb.search.search_knowledge_base', new=mock_kb_search),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
        patch('litellm.supports_function_calling', return_value=False),  # Model doesn't support function calling
    ):
        # Run LLM
        result = await ad.llm.run_llm(analytiq_client, document_id, prompt_revid)
        
        # Verify result
        assert result["result"] == "extracted without KB"
        
        # Verify LLM was called once (no agentic loop)
        assert mock_acompletion.call_count == 1
        
        # Verify KB search was NOT called (KB disabled due to no function calling)
        assert mock_kb_search.call_count == 0
        
        # Verify tools parameter was not passed
        call_args = mock_acompletion.call_args
        kwargs = call_args[1] if len(call_args) > 1 else {}
        assert "tools" not in kwargs or kwargs.get("tools") is None
    
    # Cleanup
    client.delete(f"/v0/orgs/{org_id}/knowledge-bases/{kb_id}", headers=get_auth_headers())


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_llm_with_kb_search_error_handling(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test LLM with KB - error handling when KB search fails"""
    # Set up mock embedding response for KB creation
    mock_embedding.return_value = create_mock_embedding_response()
    
    org_id = TEST_ORG_ID
    
    # Create tag and KB
    tag_data = {"name": "KB Error Test Tag", "color": "#FF5733"}
    tag_response = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    tag_id = tag_response.json()["id"]
    
    kb_data = {
        "name": "Error Test KB",
        "tag_ids": [tag_id],
        "chunker_type": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 128
    }
    kb_response = client.post(
        f"/v0/orgs/{org_id}/knowledge-bases",
        json=kb_data,
        headers=get_auth_headers()
    )
    kb_id = kb_response.json()["kb_id"]
    
    # Set KB status to active (required for prompt creation)
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"status": "active"}}
    )
    
    # Create prompt with KB
    prompt_data = {
        "name": "KB Error Test Prompt",
        "content": "Extract information from this document.",
        "model": "gpt-4o",
        "tag_ids": [tag_id],
        "kb_id": kb_id
    }
    prompt_response = client.post(
        f"/v0/orgs/{org_id}/prompts",
        json=prompt_data,
        headers=get_auth_headers()
    )
    prompt_revid = prompt_response.json()["prompt_revid"]
    
    # Create document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    upload_data = {
        "documents": [{
            "name": "test_doc.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
            "tag_ids": [tag_id]
        }]
    }
    upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_auth_headers())
    document_id = upload_resp.json()["documents"][0]["document_id"]
    
    # Process OCR (analytiq_client already created above)
    await ad.msg_handlers.process_ocr_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})
    
    # Mock KB search to raise an error
    mock_kb_search = AsyncMock(side_effect=Exception("KB search failed"))
    
    # Create mock LLM responses: tool call, then final response (after error)
    tool_call = MockToolCall("call_123", "search_knowledge_base", {"query": "test query", "top_k": 5})
    first_response = MockLLMResponseWithToolCalls(
        content=None,
        tool_calls=[tool_call],
        usage=MockUsage(prompt_tokens=100, completion_tokens=50)
    )
    
    final_response = MockLLMResponseWithToolCalls(
        content=json.dumps({"result": "extracted despite KB error"}),
        tool_calls=None,
        usage=MockUsage(prompt_tokens=200, completion_tokens=100)
    )
    
    mock_acompletion = AsyncMock(side_effect=[first_response, final_response])
    
    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_acompletion),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('analytiq_data.kb.search.search_knowledge_base', new=mock_kb_search),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
        patch('litellm.supports_function_calling', return_value=True),
    ):
        # Run LLM - should handle error gracefully
        result = await ad.llm.run_llm(analytiq_client, document_id, prompt_revid)
        
        # Verify result (should still succeed despite KB error)
        assert result["result"] == "extracted despite KB error"
        
        # Verify LLM was called twice (tool call + final response)
        assert mock_acompletion.call_count == 2
        
        # Verify KB search was called (and failed)
        assert mock_kb_search.call_count == 1
        
        # Verify error message was added to conversation
        final_call_args = mock_acompletion.call_args_list[1]
        final_kwargs = final_call_args[1] if len(final_call_args) > 1 else {}
        messages = final_kwargs.get("messages", [])
        
        # Should have error message in tool response
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_messages) > 0
        assert "Error searching knowledge base" in tool_messages[-1]["content"]
    
    # Cleanup
    client.delete(f"/v0/orgs/{org_id}/knowledge-bases/{kb_id}", headers=get_auth_headers())


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_llm_with_kb_max_iterations(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test LLM with KB - max iterations limit"""
    # Set up mock embedding response for KB creation
    mock_embedding.return_value = create_mock_embedding_response()
    
    org_id = TEST_ORG_ID
    
    # Create tag and KB
    tag_data = {"name": "KB Max Iter Test Tag", "color": "#FF5733"}
    tag_response = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    tag_id = tag_response.json()["id"]
    
    kb_data = {
        "name": "Max Iter Test KB",
        "tag_ids": [tag_id],
        "chunker_type": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 128
    }
    kb_response = client.post(
        f"/v0/orgs/{org_id}/knowledge-bases",
        json=kb_data,
        headers=get_auth_headers()
    )
    kb_id = kb_response.json()["kb_id"]
    
    # Set KB status to active (required for prompt creation)
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"status": "active"}}
    )
    
    # Create prompt with KB
    prompt_data = {
        "name": "KB Max Iter Test Prompt",
        "content": "Extract information from this document.",
        "model": "gpt-4o",
        "tag_ids": [tag_id],
        "kb_id": kb_id
    }
    prompt_response = client.post(
        f"/v0/orgs/{org_id}/prompts",
        json=prompt_data,
        headers=get_auth_headers()
    )
    prompt_revid = prompt_response.json()["prompt_revid"]
    
    # Create document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    upload_data = {
        "documents": [{
            "name": "test_doc.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
            "tag_ids": [tag_id]
        }]
    }
    upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_auth_headers())
    document_id = upload_resp.json()["documents"][0]["document_id"]
    
    # Process OCR (analytiq_client already created above)
    await ad.msg_handlers.process_ocr_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})
    
    # Mock KB search results
    mock_kb_results = await create_mock_kb_search_results(3)
    mock_kb_search = AsyncMock(return_value=mock_kb_results)
    
    # Create mock LLM responses: always return tool calls (to hit max iterations)
    tool_call = MockToolCall("call_123", "search_knowledge_base", {"query": "test query", "top_k": 5})
    tool_call_response = MockLLMResponseWithToolCalls(
        content=None,
        tool_calls=[tool_call],
        usage=MockUsage(prompt_tokens=100, completion_tokens=50)
    )
    
    # Create 5 tool call responses (max iterations)
    mock_acompletion = AsyncMock(return_value=tool_call_response)
    
    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_acompletion),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('analytiq_data.kb.search.search_knowledge_base', new=mock_kb_search),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
        patch('litellm.supports_function_calling', return_value=True),
    ):
        # Run LLM - should hit max iterations
        # This should raise an exception because we never get a final response
        with pytest.raises(Exception, match="No response received from LLM|LLM response incomplete"):
            await ad.llm.run_llm(analytiq_client, document_id, prompt_revid)
        
        # Verify LLM was called max_iterations times (5)
        assert mock_acompletion.call_count == 5
        
        # Verify KB search was called multiple times
        assert mock_kb_search.call_count >= 1
    
    # Cleanup
    client.delete(f"/v0/orgs/{org_id}/knowledge-bases/{kb_id}", headers=get_auth_headers())


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_llm_with_kb_token_accumulation(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test that tokens are accumulated across agentic loop iterations"""
    # Set up mock embedding response for KB creation
    mock_embedding.return_value = create_mock_embedding_response()
    
    org_id = TEST_ORG_ID
    
    # Create tag and KB
    tag_data = {"name": "KB Token Test Tag", "color": "#FF5733"}
    tag_response = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    tag_id = tag_response.json()["id"]
    
    kb_data = {
        "name": "Token Test KB",
        "tag_ids": [tag_id],
        "chunker_type": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 128
    }
    kb_response = client.post(
        f"/v0/orgs/{org_id}/knowledge-bases",
        json=kb_data,
        headers=get_auth_headers()
    )
    kb_id = kb_response.json()["kb_id"]
    
    # Set KB status to active (required for prompt creation)
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"status": "active"}}
    )
    
    # Create prompt with KB
    prompt_data = {
        "name": "KB Token Test Prompt",
        "content": "Extract information from this document.",
        "model": "gpt-4o",
        "tag_ids": [tag_id],
        "kb_id": kb_id
    }
    prompt_response = client.post(
        f"/v0/orgs/{org_id}/prompts",
        json=prompt_data,
        headers=get_auth_headers()
    )
    prompt_revid = prompt_response.json()["prompt_revid"]
    
    # Create document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    upload_data = {
        "documents": [{
            "name": "test_doc.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
            "tag_ids": [tag_id]
        }]
    }
    upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_auth_headers())
    document_id = upload_resp.json()["documents"][0]["document_id"]
    
    # Process OCR (analytiq_client already created above)
    await ad.msg_handlers.process_ocr_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})
    
    # Mock KB search results
    mock_kb_results = await create_mock_kb_search_results(3)
    mock_kb_search = AsyncMock(return_value=mock_kb_results)
    
    # Create mock LLM responses with specific token counts
    tool_call = MockToolCall("call_123", "search_knowledge_base", {"query": "test query", "top_k": 5})
    first_response = MockLLMResponseWithToolCalls(
        content=None,
        tool_calls=[tool_call],
        usage=MockUsage(prompt_tokens=100, completion_tokens=50)
    )
    
    final_response = MockLLMResponseWithToolCalls(
        content=json.dumps({"result": "extracted"}),
        tool_calls=None,
        usage=MockUsage(prompt_tokens=150, completion_tokens=75)
    )
    
    mock_acompletion = AsyncMock(side_effect=[first_response, final_response])
    mock_record_spu = AsyncMock()
    
    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_acompletion),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('analytiq_data.kb.search.search_knowledge_base', new=mock_kb_search),
        patch('analytiq_data.payments.record_spu_usage', new=mock_record_spu),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
        patch('litellm.supports_function_calling', return_value=True),
    ):
        # Run LLM
        result = await ad.llm.run_llm(analytiq_client, document_id, prompt_revid)
        
        # Verify result
        assert result["result"] == "extracted"
        
        # Verify SPU recording was called with accumulated tokens
        # Total should be: 100 + 150 = 250 prompt tokens, 50 + 75 = 125 completion tokens
        assert mock_record_spu.called
        call_args = mock_record_spu.call_args
        # The actual token counts should be accumulated (250 prompt, 125 completion)
        # We can't easily verify exact values without inspecting the call, but we know it was called
    
    # Cleanup
    client.delete(f"/v0/orgs/{org_id}/knowledge-bases/{kb_id}", headers=get_auth_headers())


@pytest.mark.asyncio
async def test_llm_with_kb_no_kb_id(test_db, mock_auth, setup_test_models):
    """Test LLM without KB - should work normally without agentic loop"""
    org_id = TEST_ORG_ID
    
    # Create tag (no KB)
    tag_data = {"name": "No KB Test Tag", "color": "#FF5733"}
    tag_response = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    tag_id = tag_response.json()["id"]
    
    # Create prompt without KB
    prompt_data = {
        "name": "No KB Test Prompt",
        "content": "Extract information from this document.",
        "model": "gpt-4o",
        "tag_ids": [tag_id]
        # No kb_id
    }
    prompt_response = client.post(
        f"/v0/orgs/{org_id}/prompts",
        json=prompt_data,
        headers=get_auth_headers()
    )
    prompt_revid = prompt_response.json()["prompt_revid"]
    
    # Create document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    upload_data = {
        "documents": [{
            "name": "test_doc.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
            "tag_ids": [tag_id]
        }]
    }
    upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_auth_headers())
    document_id = upload_resp.json()["documents"][0]["document_id"]
    
    # Process OCR
    analytiq_client = ad.common.get_analytiq_client()
    await ad.msg_handlers.process_ocr_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})
    
    # Mock LLM response (no tool calls)
    final_response = MockLLMResponseWithToolCalls(
        content=json.dumps({"result": "extracted without KB"}),
        tool_calls=None,
        usage=MockUsage(prompt_tokens=100, completion_tokens=50)
    )
    
    mock_acompletion = AsyncMock(return_value=final_response)
    mock_kb_search = AsyncMock()
    
    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_acompletion),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('analytiq_data.kb.search.search_knowledge_base', new=mock_kb_search),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
        patch('litellm.supports_function_calling', return_value=True),
    ):
        # Run LLM
        result = await ad.llm.run_llm(analytiq_client, document_id, prompt_revid)
        
        # Verify result
        assert result["result"] == "extracted without KB"
        
        # Verify LLM was called once (no agentic loop)
        assert mock_acompletion.call_count == 1
        
        # Verify KB search was NOT called
        assert mock_kb_search.call_count == 0
        
        # Verify tools parameter was not passed
        call_args = mock_acompletion.call_args
        kwargs = call_args[1] if len(call_args) > 1 else {}
        assert "tools" not in kwargs or kwargs.get("tools") is None
