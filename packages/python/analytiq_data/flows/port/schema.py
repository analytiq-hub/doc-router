from __future__ import annotations

from typing import Any


def build_top_level_parameter_schema(description: dict[str, Any]) -> dict[str, Any]:
    """Map top-level `description.properties` to a single JSON Schema object."""

    props_out: dict[str, Any] = {}
    required: list[str] = []

    for p in description.get("properties") or []:
        if not isinstance(p, dict):
            continue
        name = p.get("name")
        if not name:
            continue
        if p.get("type") == "notice":
            continue
        props_out[str(name)] = inode_property_to_schema(p)
        if p.get("required") and p.get("default") is None:
            required.append(str(name))

    schema: dict[str, Any] = {
        "type": "object",
        "properties": props_out,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = sorted(set(required))
    return schema


def inode_property_to_schema(p: dict[str, Any]) -> dict[str, Any]:
    t = p.get("type")
    sch: dict[str, Any]

    if t == "string":
        sch = {"type": "string"}
    elif t == "number":
        sch = {"type": "number"}
    elif t == "boolean":
        sch = {"type": "boolean"}
    elif t == "options":
        sch = _options_schema(p)
    elif t == "multiOptions":
        sch = _multi_options_schema(p)
    elif t == "json":
        sch = {"anyOf": [{"type": "object"}, {"type": "string"}]}
    elif t == "code":
        sch = {"type": "string"}
    elif t == "color":
        sch = {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}
    elif t == "dateTime":
        sch = {"type": "string", "format": "date-time"}
    elif t == "resourceLocator":
        sch = {"type": "string"}
    elif t == "hidden":
        sch = {"type": "string"}
    elif t == "collection":
        sub_props: dict[str, Any] = {}
        for inner in p.get("options") or []:
            if isinstance(inner, dict) and inner.get("name"):
                sub_props[str(inner["name"])] = inode_property_to_schema(inner)
        sch = {"type": "object", "properties": sub_props, "additionalProperties": False}
    elif t == "fixedCollection":
        sub_props = {}
        for block in p.get("values") or []:
            if not isinstance(block, dict):
                continue
            block_name = str(block.get("name") or "section")
            inner: dict[str, Any] = {}
            for ip in block.get("values") or []:
                if isinstance(ip, dict) and ip.get("name"):
                    inner[str(ip["name"])] = inode_property_to_schema(ip)
            sub_props[block_name] = {
                "type": "object",
                "properties": inner,
                "additionalProperties": False,
            }
        sch = {"type": "object", "properties": sub_props, "additionalProperties": False}
    else:
        sch = {"type": "string", "x-source-type": str(t)}

    if p.get("default") is not None:
        sch = {**sch, "default": p["default"]}
    return sch


def _options_schema(p: dict[str, Any]) -> dict[str, Any]:
    opts = p.get("options") or []
    values: list[Any] = []
    names: list[str] = []
    for o in opts:
        if isinstance(o, dict) and "value" in o:
            values.append(o["value"])
            names.append(str(o.get("name") if o.get("name") is not None else o.get("value")))
    if not values:
        return {"type": "string"}
    str_vals = [str(v) for v in values]
    sch: dict[str, Any] = {"type": "string", "enum": str_vals}
    if names and len(names) == len(str_vals):
        sch["x-enumNames"] = names
    return sch


def _multi_options_schema(p: dict[str, Any]) -> dict[str, Any]:
    inner = _options_schema(p)
    if inner.get("type") == "string" and "enum" in inner:
        return {"type": "array", "items": {"type": "string", "enum": inner["enum"]}}
    return {"type": "array", "items": {"type": "string"}}
