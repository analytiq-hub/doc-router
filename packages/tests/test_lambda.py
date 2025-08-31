import pytest
from bson import ObjectId
import os
from datetime import datetime, UTC
import logging

# Import shared test utilities
from .test_utils import (
    client, TEST_ORG_ID, 
    get_auth_headers
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

@pytest.mark.asyncio
async def test_lambda_function_lifecycle(test_db, mock_auth, setup_test_models):
    """Test the complete lambda function lifecycle"""
    logger.info(f"test_lambda_function_lifecycle() start")
    
    # Step 1: Create a lambda function
    function_data = {
        "name": "hello_world",
        "description": "A simple Hello World lambda function",
        "code": '''def lambda_handler(event, context):
    print("Hello World from Lambda!")
    print(f"Received event: {event}")
    print(f"Context function name: {context.get('function_name', 'unknown')}")
    
    return {
        "statusCode": 200,
        "body": "Hello World!",
        "message": f"Processed event with {len(event)} keys",
        "timestamp": "2024-01-01T00:00:00Z"
    }''',
        "timeout": 30,
        "memory_size": 128,
        "environment_variables": {"ENV": "test", "DEBUG": "true"},
        "tag_ids": []
    }
    
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions",
        json=function_data,
        headers=get_auth_headers()
    )
    
    assert create_response.status_code == 200
    function_result = create_response.json()
    assert "function_revid" in function_result
    assert function_result["name"] == "hello_world"
    assert "code" in function_result
    
    function_id = function_result["function_id"]
    function_revid = function_result["function_revid"]
    
    # Step 2: List lambda functions to verify it was created
    list_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions",
        headers=get_auth_headers()
    )
    
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert "functions" in list_data
    
    # Find our function in the list
    created_function = next((func for func in list_data["functions"] if func["function_revid"] == function_revid), None)
    assert created_function is not None
    assert created_function["name"] == "hello_world"
    
    # Step 3: Get the specific function to verify its content
    get_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}",
        headers=get_auth_headers()
    )
    
    assert get_response.status_code == 200
    function_data = get_response.json()
    assert function_data["function_id"] == function_id
    assert function_data["name"] == "hello_world"
    assert "def lambda_handler" in function_data["code"]
    
    # Step 4: Update the lambda function
    update_data = {
        "name": "updated_hello_world",
        "description": "Updated Hello World lambda function",
        "code": '''def lambda_handler(event, context):
    print("Updated Hello World from Lambda!")
    return {
        "statusCode": 200,
        "body": "Updated Hello World!",
        "version": "2.0"
    }''',
        "timeout": 60,
        "memory_size": 256,
        "environment_variables": {"ENV": "test", "VERSION": "2.0"},
        "tag_ids": []
    }
    
    update_response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}",
        json=update_data,
        headers=get_auth_headers()
    )
    
    assert update_response.status_code == 200
    updated_function_result = update_response.json()
    updated_function_id = updated_function_result["function_id"]
    updated_function_revid = updated_function_result["function_revid"]
    
    # Step 5: Get the function again to verify the update
    get_updated_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{updated_function_id}",
        headers=get_auth_headers()
    )
    
    assert get_updated_response.status_code == 200
    updated_function_data = get_updated_response.json()
    assert updated_function_data["function_id"] == updated_function_id
    assert updated_function_data["name"] == "updated_hello_world"
    assert updated_function_data["timeout"] == 60
    assert updated_function_data["memory_size"] == 256
    assert "Updated Hello World from Lambda!" in updated_function_data["code"]
    
    # Step 6: Delete the lambda function
    delete_response = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}",
        headers=get_auth_headers()
    )
    
    assert delete_response.status_code == 200
    
    # Step 7: Verify that getting the deleted function returns 404
    get_deleted_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}",
        headers=get_auth_headers()
    )
    
    assert get_deleted_response.status_code == 404
    
    logger.info(f"test_lambda_function_lifecycle() end")

@pytest.mark.asyncio
async def test_lambda_function_execution(test_db, mock_auth, setup_test_models):
    """Test lambda function execution"""
    logger.info(f"test_lambda_function_execution() start")
    
    # Step 1: Create a simple lambda function
    function_data = {
        "name": "test_execution",
        "description": "Test execution lambda function",
        "code": '''def lambda_handler(event, context):
    print(f"Processing event: {event}")
    
    result = {
        "statusCode": 200,
        "input_data": event.get("data", "no data"),
        "function_name": context.get("function_name", "unknown"),
        "processed": True
    }
    
    print(f"Returning result: {result}")
    return result''',
        "timeout": 30,
        "memory_size": 128,
        "environment_variables": {"TEST": "value"},
        "tag_ids": []
    }
    
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions",
        json=function_data,
        headers=get_auth_headers()
    )
    
    assert create_response.status_code == 200
    function_result = create_response.json()
    function_id = function_result["function_id"]
    
    # Step 2: Execute the lambda function
    execution_request = {
        "event": {
            "action": "test",
            "data": "hello world",
            "timestamp": "2024-01-01T00:00:00Z"
        },
        "context": {
            "request_id": "test-123"
        }
    }
    
    run_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}/run",
        json=execution_request,
        headers=get_auth_headers()
    )
    
    assert run_response.status_code == 200
    execution_result = run_response.json()
    assert "execution_id" in execution_result
    assert execution_result["function_id"] == function_id
    assert execution_result["status"] == "pending"
    assert execution_result["event"] == execution_request["event"]
    assert execution_result["context"] == execution_request["context"]
    
    execution_id = execution_result["execution_id"]
    
    # Step 3: Process the execution using the message handler directly
    # (In real scenario, this would be done by the worker)
    from analytiq_data.msg_handlers.lambda_executor import process_lambda_msg
    
    # Get the message from the queue using the same environment as the sender
    analytiq_client = ad.common.get_analytiq_client()  # Will use current ENV
    msg = await ad.queue.recv_msg(analytiq_client, "lambda")
    assert msg is not None
    assert msg["msg"]["execution_id"] == execution_id
    
    # Process the message
    await process_lambda_msg(analytiq_client, msg)
    
    # Step 4: Get the execution result
    result_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}/results/{execution_id}",
        headers=get_auth_headers()
    )
    
    assert result_response.status_code == 200
    result_data = result_response.json()
    assert result_data["execution_id"] == execution_id
    assert result_data["status"] == "completed"
    assert result_data["result"] is not None
    assert result_data["result"]["statusCode"] == 200
    assert result_data["result"]["input_data"] == "hello world"
    assert result_data["result"]["processed"] is True
    assert len(result_data["logs"]) > 0
    assert result_data["execution_time_ms"] >= 0  # Could be 0 in fast test environment
    
    # Step 5: List execution results
    list_results_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}/results",
        headers=get_auth_headers()
    )
    
    assert list_results_response.status_code == 200
    results_list = list_results_response.json()
    assert "results" in results_list
    assert len(results_list["results"]) >= 1
    
    found_result = next((r for r in results_list["results"] if r["execution_id"] == execution_id), None)
    assert found_result is not None
    assert found_result["status"] == "completed"
    
    # Step 6: Clean up
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}",
        headers=get_auth_headers()
    )
    
    logger.info(f"test_lambda_function_execution() end")

@pytest.mark.asyncio
async def test_lambda_function_with_error(test_db, mock_auth, setup_test_models):
    """Test lambda function that throws an error"""
    logger.info(f"test_lambda_function_with_error() start")
    
    # Create a lambda function that throws an error
    function_data = {
        "name": "error_function",
        "description": "Function that throws an error",
        "code": '''def lambda_handler(event, context):
    print("About to throw an error...")
    raise ValueError("This is a test error!")
    return {"status": "should not reach here"}''',
        "timeout": 30,
        "memory_size": 128,
        "environment_variables": {},
        "tag_ids": []
    }
    
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions",
        json=function_data,
        headers=get_auth_headers()
    )
    
    assert create_response.status_code == 200
    function_result = create_response.json()
    function_id = function_result["function_id"]
    
    # Execute the function
    execution_request = {
        "event": {"test": "data"},
        "context": {"test": "context"}
    }
    
    run_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}/run",
        json=execution_request,
        headers=get_auth_headers()
    )
    
    assert run_response.status_code == 200
    execution_result = run_response.json()
    execution_id = execution_result["execution_id"]
    
    # Process the execution
    from analytiq_data.msg_handlers.lambda_executor import process_lambda_msg
    analytiq_client = ad.common.get_analytiq_client()  # Will use current ENV
    msg = await ad.queue.recv_msg(analytiq_client, "lambda")
    await process_lambda_msg(analytiq_client, msg)
    
    # Get the result
    result_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}/results/{execution_id}",
        headers=get_auth_headers()
    )
    
    assert result_response.status_code == 200
    result_data = result_response.json()
    assert result_data["status"] == "failed"
    assert "This is a test error!" in result_data["error"]
    assert len(result_data["logs"]) > 0
    assert "About to throw an error..." in " ".join(result_data["logs"])
    
    # Clean up
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/lambda_functions/{function_id}",
        headers=get_auth_headers()
    )
    
    logger.info(f"test_lambda_function_with_error() end")