import asyncio
import json
import os
import sys
import traceback
import logging
import time
import resource
from datetime import datetime, UTC
from typing import Dict, Any
from bson import ObjectId
import analytiq_data as ad

logger = logging.getLogger(__name__)

def create_lambda_context(execution_id: str, function_name: str, timeout: int, memory_size: int) -> Dict[str, Any]:
    """Create AWS Lambda-like context object"""
    return {
        "function_name": function_name,
        "function_version": "1",
        "invoked_function_arn": f"arn:aws:lambda:us-east-1:123456789012:function:{function_name}",
        "memory_limit_in_mb": str(memory_size),
        "remaining_time_in_millis": timeout * 1000,  # Will be updated during execution
        "log_group_name": f"/aws/lambda/{function_name}",
        "log_stream_name": f"2024/01/01/[1]{execution_id}",
        "aws_request_id": execution_id
    }

class LambdaExecutionEnvironment:
    """Execution environment for lambda functions with logging capture and resource monitoring"""
    
    def __init__(self, execution_id: str, function_name: str, timeout: int, memory_size: int, environment_variables: Dict[str, str]):
        self.execution_id = execution_id
        self.function_name = function_name
        self.timeout = timeout
        self.memory_size = memory_size
        self.environment_variables = environment_variables or {}
        self.logs = []
        self.start_time = None
        self.end_time = None
        self.original_print = None
        
    def capture_print(self, *args, **kwargs):
        """Capture print statements as logs"""
        message = " ".join(str(arg) for arg in args)
        timestamp = datetime.now(UTC).isoformat()
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        
        # Also print to original stdout for debugging
        if self.original_print:
            self.original_print(*args, **kwargs)
    
    def get_memory_usage_mb(self) -> int:
        """Get current memory usage in MB"""
        try:
            # Get memory usage in bytes, convert to MB
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # On Linux, ru_maxrss is in KB, on macOS it's in bytes
            if sys.platform == "linux":
                return usage // 1024  # KB to MB
            else:
                return usage // (1024 * 1024)  # bytes to MB
        except:
            return 0
    
    async def execute_function(self, code: str, event: Dict[str, Any], context: Dict[str, str]) -> Dict[str, Any]:
        """Execute the lambda function code safely"""
        self.start_time = time.time()
        
        # Create lambda context object
        lambda_context = create_lambda_context(
            self.execution_id, 
            self.function_name, 
            self.timeout, 
            self.memory_size
        )
        
        # Merge provided context
        lambda_context.update(context)
        
        # Set up environment variables
        original_env = {}
        for key, value in self.environment_variables.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        # Capture print statements
        import builtins
        self.original_print = builtins.print
        builtins.print = self.capture_print
        
        try:
            # Create execution namespace with AWS Lambda-like globals
            exec_globals = {
                '__builtins__': __builtins__,
                'print': self.capture_print,
                'json': json,
                'datetime': datetime,
                'time': time,
                # Add common imports that lambda functions might need
                'os': __import__('os'),
                'sys': sys,
                'logging': logging,
                'asyncio': asyncio,
            }
            
            # Execute the function code
            exec(code, exec_globals)
            
            # The code should define a lambda_handler function
            if 'lambda_handler' not in exec_globals:
                raise ValueError("Lambda function must define a 'lambda_handler(event, context)' function")
            
            lambda_handler = exec_globals['lambda_handler']
            
            # Execute with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.coroutine(lambda_handler)(event, lambda_context) 
                    if asyncio.iscoroutinefunction(lambda_handler)
                    else asyncio.get_event_loop().run_in_executor(None, lambda_handler, event, lambda_context),
                    timeout=self.timeout
                )
                
                self.end_time = time.time()
                
                return {
                    "success": True,
                    "result": result,
                    "execution_time_ms": int((self.end_time - self.start_time) * 1000),
                    "memory_used_mb": self.get_memory_usage_mb(),
                    "logs": self.logs
                }
                
            except asyncio.TimeoutError:
                self.end_time = time.time()
                error_msg = f"Function execution timed out after {self.timeout} seconds"
                self.logs.append(f"[ERROR] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "execution_time_ms": int((self.end_time - self.start_time) * 1000),
                    "memory_used_mb": self.get_memory_usage_mb(),
                    "logs": self.logs
                }
                
        except Exception as e:
            self.end_time = time.time()
            error_msg = f"Function execution failed: {str(e)}"
            error_trace = traceback.format_exc()
            self.logs.append(f"[ERROR] {error_msg}")
            self.logs.append(f"[ERROR] {error_trace}")
            
            return {
                "success": False,
                "error": error_msg,
                "execution_time_ms": int((self.end_time - self.start_time) * 1000) if self.end_time else 0,
                "memory_used_mb": self.get_memory_usage_mb(),
                "logs": self.logs
            }
            
        finally:
            # Restore original print and environment
            builtins.print = self.original_print
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

async def process_lambda_msg(analytiq_client, msg):
    """Process lambda execution message"""
    logger.info(f"Processing lambda execution msg: {msg}")
    
    execution_id = msg["msg"]["execution_id"]
    function_revid = msg["msg"]["function_revid"]
    organization_id = msg["msg"]["organization_id"]
    
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    
    try:
        # Update execution status to running
        await db.lambda_execution_results.update_one(
            {"_id": ObjectId(execution_id)},
            {
                "$set": {
                    "status": "running",
                    "started_at": datetime.now(UTC)
                }
            }
        )
        
        # Get the function revision
        function_revision = await db.lambda_function_revisions.find_one({
            "_id": ObjectId(function_revid)
        })
        
        if not function_revision:
            raise Exception(f"Function revision {function_revid} not found")
        
        # Get the execution request
        execution_result = await db.lambda_execution_results.find_one({
            "_id": ObjectId(execution_id)
        })
        
        if not execution_result:
            raise Exception(f"Execution result {execution_id} not found")
        
        # Create execution environment
        executor = LambdaExecutionEnvironment(
            execution_id=execution_id,
            function_name=function_revision["name"],
            timeout=function_revision.get("timeout", 30),
            memory_size=function_revision.get("memory_size", 128),
            environment_variables=function_revision.get("environment_variables", {})
        )
        
        logger.info(f"Executing lambda function {function_revision['name']} for execution {execution_id}")
        
        # Execute the function
        execution_response = await executor.execute_function(
            code=function_revision["code"],
            event=execution_result["event"],
            context=execution_result["context"]
        )
        
        # Update the execution result
        update_data = {
            "completed_at": datetime.now(UTC),
            "logs": execution_response["logs"],
            "execution_time_ms": execution_response["execution_time_ms"],
            "memory_used_mb": execution_response["memory_used_mb"]
        }
        
        if execution_response["success"]:
            update_data.update({
                "status": "completed",
                "result": execution_response["result"]
            })
        else:
            update_data.update({
                "status": "failed" if "timeout" not in execution_response.get("error", "") else "timeout",
                "error": execution_response["error"]
            })
        
        await db.lambda_execution_results.update_one(
            {"_id": ObjectId(execution_id)},
            {"$set": update_data}
        )
        
        logger.info(f"Lambda execution {execution_id} completed with status: {update_data['status']}")
        
    except Exception as e:
        logger.error(f"Error processing lambda execution message: {e}")
        logger.error(traceback.format_exc())
        
        # Update execution status to failed
        await db.lambda_execution_results.update_one(
            {"_id": ObjectId(execution_id)},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now(UTC)
                }
            }
        )
    
    # Clean up the message
    await ad.queue.delete_msg(analytiq_client, "lambda", msg["_id"])