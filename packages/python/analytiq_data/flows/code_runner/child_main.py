from __future__ import annotations

import sys
import traceback

from .config import SecurityConfig
from .executor import ExecutionFailure, execute_task
from .protocol import ProtocolError, read_frame, write_frame


def main() -> None:
    config = SecurityConfig.from_env()
    try:
        task = read_frame(sys.stdin.buffer, max_size=config.max_payload_bytes)
    except Exception as e:
        write_frame(
            sys.stdout,
            {
                "type": "task_result",
                "ok": False,
                "error": {"message": f"Failed to read task: {e}"},
            },
        )
        return

    if task.get("type") != "task":
        write_frame(
            sys.stdout,
            {
                "type": "task_result",
                "ok": False,
                "error": {"message": "First message must be type 'task'"},
            },
        )
        return

    code = task.get("code")
    items = task.get("items")
    context = task.get("context")
    mode = task.get("mode") or "all_items"
    continue_on_fail = bool(task.get("continue_on_fail"))

    if not isinstance(code, str):
        write_frame(
            sys.stdout,
            {"type": "task_result", "ok": False, "error": {"message": "code must be a string"}},
        )
        return
    if not isinstance(items, list):
        write_frame(
            sys.stdout,
            {"type": "task_result", "ok": False, "error": {"message": "items must be a list"}},
        )
        return
    if not isinstance(context, dict):
        write_frame(
            sys.stdout,
            {"type": "task_result", "ok": False, "error": {"message": "context must be a dict"}},
        )
        return

    try:
        out_items, logs = execute_task(
            code=code,
            mode=str(mode),
            items=items,
            context=context,
            config=config,
            continue_on_fail=continue_on_fail,
            max_payload_bytes=config.max_payload_bytes,
        )
        write_frame(
            sys.stdout,
            {"type": "task_result", "ok": True, "items": out_items, "logs": logs},
        )
    except ExecutionFailure as e:
        write_frame(
            sys.stdout,
            {
                "type": "task_result",
                "ok": False,
                "error": {
                    "message": e.message,
                    "stack": e.stack or traceback.format_exc(),
                },
            },
        )
    except Exception as e:
        write_frame(
            sys.stdout,
            {
                "type": "task_result",
                "ok": False,
                "error": {
                    "message": str(e),
                    "stack": traceback.format_exc(),
                },
            },
        )


if __name__ == "__main__":
    main()
