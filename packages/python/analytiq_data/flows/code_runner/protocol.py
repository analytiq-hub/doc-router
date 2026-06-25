from __future__ import annotations

import json
import struct
import sys
from typing import Any, BinaryIO, TextIO


class ProtocolError(RuntimeError):
    pass


def read_frame(stream: BinaryIO, *, max_size: int) -> dict[str, Any]:
    header = stream.read(4)
    if len(header) < 4:
        raise ProtocolError("Unexpected end of stream while reading frame header")
    (length,) = struct.unpack(">I", header)
    if length > max_size:
        raise ProtocolError(f"Frame size {length} exceeds limit {max_size}")
    body = stream.read(length)
    if len(body) < length:
        raise ProtocolError("Unexpected end of stream while reading frame body")
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        raise ProtocolError(f"Invalid JSON frame: {e}") from e
    if not isinstance(payload, dict):
        raise ProtocolError("Frame payload must be a JSON object")
    return payload


def write_frame(stream: TextIO | BinaryIO, message: dict[str, Any]) -> None:
    data = json.dumps(message, ensure_ascii=False).encode("utf-8")
    frame = struct.pack(">I", len(data)) + data
    if hasattr(stream, "buffer"):
        stream.buffer.write(frame)
        stream.buffer.flush()
    else:
        stream.write(frame)
        stream.flush()


class FrameBuffer:
    """Incremental framed-message reader for asyncio StreamReader."""

    def __init__(self, max_size: int) -> None:
        self._buf = bytearray()
        self._max_size = max_size

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        self._buf.extend(chunk)
        out: list[dict[str, Any]] = []
        while True:
            if len(self._buf) < 4:
                break
            (length,) = struct.unpack(">I", self._buf[:4])
            if length > self._max_size:
                raise ProtocolError(f"Frame size {length} exceeds limit {self._max_size}")
            total = 4 + length
            if len(self._buf) < total:
                break
            body = bytes(self._buf[4:total])
            del self._buf[:total]
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception as e:
                raise ProtocolError(f"Invalid JSON frame: {e}") from e
            if not isinstance(payload, dict):
                raise ProtocolError("Frame payload must be a JSON object")
            out.append(payload)
        return out
