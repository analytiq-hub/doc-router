from __future__ import annotations

"""Connection port typing for flow graph edges."""

from typing import Any, Literal

MAIN_CONNECTION_TYPE = "main"
DOCROUTER_OCR_CONNECTION_TYPE = "docrouter.ocr"
FLOWS_TOOL_CONNECTION_TYPE = "flows.tool"

ConnectionType = Literal["main", "docrouter.ocr", "flows.tool"]
CONNECTION_TYPES: frozenset[str] = frozenset(
    {MAIN_CONNECTION_TYPE, DOCROUTER_OCR_CONNECTION_TYPE, FLOWS_TOOL_CONNECTION_TYPE}
)


def normalize_connection_type(raw: Any) -> str:
    if raw is None or raw == "":
        return MAIN_CONNECTION_TYPE
    if not isinstance(raw, str):
        raise ValueError("connection_type must be a string")
    ct = raw.strip()
    if ct not in CONNECTION_TYPES:
        raise ValueError(f"Unsupported connection_type: {ct!r}")
    return ct


def input_port_count(node_type: Any) -> int:
    max_inputs = getattr(node_type, "max_inputs", None)
    if max_inputs is not None:
        return max(0, int(max_inputs))
    return max(0, int(getattr(node_type, "min_inputs", 0) or 0))


def _port_types_list(raw: Any, count: int, *, default: str = MAIN_CONNECTION_TYPE) -> list[str]:
    if count <= 0:
        return []
    if isinstance(raw, list) and raw:
        out = [str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()]
        if out:
            while len(out) < count:
                out.append(default)
            return out[:count]
    return [default] * count


def input_port_types_for(node_type: Any) -> list[str]:
    return _port_types_list(
        getattr(node_type, "input_port_types", None),
        input_port_count(node_type),
    )


def output_port_types_for(node_type: Any) -> list[str]:
    outputs = max(0, int(getattr(node_type, "outputs", 0) or 0))
    return _port_types_list(getattr(node_type, "output_port_types", None), outputs)
