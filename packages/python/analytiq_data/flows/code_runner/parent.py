from __future__ import annotations

import asyncio
import json
import struct
import sys
from typing import Any

from .analyzer import SecurityValidationError, TaskAnalyzer
from .bootstrap import CHILD_BOOTSTRAP, minimal_env
from .config import SecurityConfig
from .protocol import FrameBuffer, ProtocolError
from .rpc import ParentRpcHandler


class CodeExecutionError(RuntimeError):
    """Raised when a code snippet fails or returns invalid output."""


async def _run_protocol_loop(
    proc: asyncio.subprocess.Process,
    *,
    task_message: dict[str, Any],
    config: SecurityConfig,
    rpc_handler: ParentRpcHandler,
    timeout_seconds: float,
) -> dict[str, Any]:
    if proc.stdin is None or proc.stdout is None:
        raise CodeExecutionError("Subprocess missing stdin/stdout pipes")

    payload = json.dumps(task_message, ensure_ascii=False).encode("utf-8")
    frame = struct.pack(">I", len(payload)) + payload
    proc.stdin.write(frame)
    await proc.stdin.drain()

    buffer = FrameBuffer(config.max_payload_bytes)
    stderr_chunks: list[bytes] = []

    async def _read_stdout() -> dict[str, Any]:
        assert proc.stdout is not None
        while True:
            for msg in buffer.feed(await proc.stdout.read(65536)):
                msg_type = msg.get("type")
                if msg_type == "rpc":
                    rpc_id = msg.get("id")
                    method = msg.get("method")
                    args = msg.get("args")
                    if not isinstance(rpc_id, str) or not isinstance(method, str) or not isinstance(
                        args, list
                    ):
                        raise CodeExecutionError("Invalid rpc message from child")
                    try:
                        result = await rpc_handler.handle(method, args)
                        reply = {"type": "rpc_result", "id": rpc_id, "ok": True, "result": result}
                    except Exception as e:
                        reply = {
                            "type": "rpc_result",
                            "id": rpc_id,
                            "ok": False,
                            "error": {"message": str(e)},
                        }
                    reply_bytes = json.dumps(reply, ensure_ascii=False).encode("utf-8")
                    proc.stdin.write(struct.pack(">I", len(reply_bytes)) + reply_bytes)
                    await proc.stdin.drain()
                elif msg_type == "task_result":
                    return msg
                else:
                    raise CodeExecutionError(f"Unexpected child message type: {msg_type}")
            if proc.stdout.at_eof():
                break
        raise CodeExecutionError("Child exited without task_result")

    async def _read_stderr() -> None:
        assert proc.stderr is not None
        while True:
            chunk = await proc.stderr.read(65536)
            if not chunk:
                break
            stderr_chunks.append(chunk)

    try:
        result_msg, _ = await asyncio.wait_for(
            asyncio.gather(_read_stdout(), _read_stderr()),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise CodeExecutionError("Code execution timed out") from None

    proc.stdin.close()
    await proc.wait()

    if not result_msg.get("ok"):
        err = result_msg.get("error") or {}
        msg = err.get("message") or "Unknown error"
        stack = err.get("stack")
        stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        detail = msg
        if stack:
            detail = f"{msg}\n{stack}"
        if stderr_text.strip():
            detail = f"{detail}\nstderr: {stderr_text}"
        raise CodeExecutionError(detail)

    return result_msg


async def run_python_code(
    *,
    code: str,
    items: list[dict[str, Any]],
    context: dict[str, Any],
    mode: str = "all_items",
    timeout_seconds: float = 30.0,
    continue_on_fail: bool = False,
    analytiq_client: Any = None,
    node_id: str = "",
    execution_id: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Execute user code in an isolated Python subprocess with framed stdin/stdout protocol.

    ``items`` must use the sandbox item shape (``json``, ``binary`` metadata, etc.).
    Returns normalized item dicts and captured print/log lines.
    """

    config = SecurityConfig.from_env()
    if not config.enabled:
        raise CodeExecutionError("Python code execution is disabled (FLOW_CODE_ENABLED=false)")

    try:
        TaskAnalyzer().validate(code, config)
    except SecurityValidationError as e:
        raise CodeExecutionError(str(e)) from e

    task_message = {
        "type": "task",
        "code": code,
        "mode": mode,
        "items": items,
        "context": context,
        "continue_on_fail": continue_on_fail,
    }
    encoded = json.dumps(task_message, ensure_ascii=False).encode("utf-8")
    if len(encoded) > config.max_payload_bytes:
        raise CodeExecutionError("Task payload exceeds FLOW_CODE_MAX_PAYLOAD_BYTES")

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-S",
        "-c",
        CHILD_BOOTSTRAP,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=minimal_env(),
    )

    rpc_handler = ParentRpcHandler(
        analytiq_client=analytiq_client,
        execution_id=execution_id,
        node_id=node_id,
        config=config,
    )

    try:
        result_msg = await _run_protocol_loop(
            proc,
            task_message=task_message,
            config=config,
            rpc_handler=rpc_handler,
            timeout_seconds=timeout_seconds,
        )
    except ProtocolError as e:
        proc.kill()
        await proc.wait()
        raise CodeExecutionError(f"Protocol error: {e}") from e
    except CodeExecutionError:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise

    out_items = result_msg.get("items")
    if not isinstance(out_items, list):
        raise CodeExecutionError("Runner returned invalid items")
    logs = result_msg.get("logs")
    if logs is None:
        logs_out: list[str] = []
    elif isinstance(logs, list) and all(isinstance(x, str) for x in logs):
        logs_out = logs
    else:
        raise CodeExecutionError("Runner returned invalid logs")
    return out_items, logs_out
