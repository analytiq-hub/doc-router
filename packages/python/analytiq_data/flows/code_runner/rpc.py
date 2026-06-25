from __future__ import annotations

import base64
import itertools
import sys
from typing import Any

from .config import SecurityConfig
from .protocol import ProtocolError, read_frame, write_frame


class ChildRpcClient:
    """Synchronous RPC client used inside the child subprocess."""

    def __init__(self, *, max_payload_bytes: int) -> None:
        self._max_payload_bytes = max_payload_bytes
        self._next_id = itertools.count(1)

    def call(self, method: str, args: list[Any]) -> Any:
        rpc_id = str(next(self._next_id))
        write_frame(
            sys.stdout,
            {"type": "rpc", "id": rpc_id, "method": method, "args": args},
        )
        while True:
            msg = read_frame(sys.stdin.buffer, max_size=self._max_payload_bytes)
            msg_type = msg.get("type")
            if msg_type == "rpc_result" and msg.get("id") == rpc_id:
                if msg.get("ok"):
                    return msg.get("result")
                err = msg.get("error") or {}
                raise RuntimeError(err.get("message") or "RPC failed")
            if msg_type not in ("rpc_result",):
                raise ProtocolError(f"Unexpected message type while waiting for rpc_result: {msg_type}")


def make_child_rpc_functions(client: ChildRpcClient) -> tuple[Any, Any]:
    def read_binary(storage_id: str) -> str:
        if not isinstance(storage_id, str) or not storage_id.strip():
            raise ValueError("storage_id must be a non-empty string")
        result = client.call("read_binary", [storage_id])
        if not isinstance(result, str):
            raise RuntimeError("read_binary RPC returned invalid payload")
        return result

    def store_binary(mime_type: str, file_name: str, data_b64: str) -> str:
        if not isinstance(mime_type, str) or not mime_type.strip():
            raise ValueError("mime_type must be a non-empty string")
        if file_name is not None and not isinstance(file_name, str):
            raise ValueError("file_name must be a string")
        if not isinstance(data_b64, str):
            raise ValueError("data must be base64 string")
        result = client.call("store_binary", [mime_type, file_name or "", data_b64])
        if not isinstance(result, str) or not result.strip():
            raise RuntimeError("store_binary RPC returned invalid storage_id")
        return result

    return read_binary, store_binary


class ParentRpcHandler:
    """Parent-process RPC dispatch for ``read_binary`` / ``store_binary``."""

    def __init__(
        self,
        *,
        analytiq_client: Any,
        execution_id: str,
        node_id: str,
        config: SecurityConfig,
    ) -> None:
        self._analytiq_client = analytiq_client
        self._execution_id = execution_id
        self._node_id = node_id
        self._config = config
        self._store_counter = 0

    async def handle(self, method: str, args: list[Any]) -> Any:
        if method == "read_binary":
            if not args or not isinstance(args[0], str):
                raise ValueError("read_binary requires storage_id")
            return await self._read_binary(args[0])
        if method == "store_binary":
            if len(args) < 3:
                raise ValueError("store_binary requires mime_type, file_name, base64")
            idx = self._store_counter
            self._store_counter += 1
            return await self._store_binary(str(args[0]), str(args[1]), str(args[2]), idx)
        raise ValueError(f"Unknown RPC method: {method}")

    async def _read_binary(self, storage_id: str) -> str:
        import analytiq_data as ad

        parts = storage_id.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid storage_id: {storage_id!r}")
        ref = ad.flows.BinaryRef(mime_type="application/octet-stream", storage_id=storage_id)
        blob = await ad.flows.get_binary_stream(ref, self._analytiq_client)
        max_bytes = self._config.binary_read_max_bytes
        if len(blob) > max_bytes:
            raise ValueError(f"Binary exceeds read limit ({max_bytes} bytes)")
        return base64.b64encode(blob).decode("ascii")

    async def _store_binary(
        self,
        mime_type: str,
        file_name: str,
        data_b64: str,
        item_index: int,
    ) -> str:
        import analytiq_data as ad

        try:
            blob = base64.b64decode(data_b64, validate=True)
        except Exception as e:
            raise ValueError(f"Invalid base64 payload: {e}") from e
        ref = await ad.flows.save_execution_binary_blob(
            self._analytiq_client,
            execution_id=self._execution_id,
            node_id=self._node_id,
            item_index=item_index,
            property_name="data",
            blob=blob,
            mime_type=mime_type,
            file_name=file_name or None,
        )
        if not ref.storage_id:
            raise RuntimeError("store_binary did not return storage_id")
        return ref.storage_id
