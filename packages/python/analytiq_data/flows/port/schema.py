from __future__ import annotations

from typing import Any


def _apply_inode_ui_extensions(p: dict[str, Any], sch: dict[str, Any]) -> dict[str, Any]:
    """Map `INodeProperty`-style UI hints onto JSON Schema vendor keys consumed by the flows UI."""
    out = dict(sch)
    ph = p.get("placeholder")
    if isinstance(ph, str) and ph.strip():
        out["x-ui-placeholder"] = ph.strip()
    t = p.get("type")
    if t == "code":
        out["x-ui-widget"] = "code"
    do = p.get("displayOptions")
    if isinstance(do, dict):
        show = do.get("show")
        if isinstance(show, dict) and show:
            clauses: list[dict[str, Any]] = []
            for field, values in show.items():
                if not isinstance(field, str) or not isinstance(values, list) or not values:
                    continue
                if len(values) == 1:
                    clauses.append({"field": field, "equals": values[0]})
                else:
                    clauses.append({"field": field, "in": list(values)})
            if len(clauses) == 1:
                out["x-ui-show-when"] = clauses[0]
            elif len(clauses) > 1:
                out["x-ui-show-when"] = {"all": clauses}
        # `hide` is not mapped; fields with only ``hide`` stay always visible.
    return out


def _merge_options_properties(variants: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge duplicate ``options`` parameters (e.g. per-resource ``operation`` blocks)."""

    by_resource: dict[str, dict[str, Any]] = {}
    value_labels: dict[str, str] = {}
    all_values: list[str] = []
    default_value: Any = None

    for p in variants:
        show = (p.get("displayOptions") or {}).get("show") if isinstance(p.get("displayOptions"), dict) else {}
        resources = show.get("resource") if isinstance(show, dict) else None
        resource_key = str(resources[0]) if isinstance(resources, list) and resources else "_all"
        opts = p.get("options") or []
        enum_vals: list[str] = []
        enum_names: list[str] = []
        for o in opts:
            if not isinstance(o, dict) or "value" not in o:
                continue
            val = str(o["value"])
            enum_vals.append(val)
            label = str(o.get("name") if o.get("name") is not None else val)
            enum_names.append(label)
            if val not in value_labels:
                value_labels[val] = label
                all_values.append(val)
        if enum_vals:
            by_resource[resource_key] = {
                "enum": enum_vals,
                "x-ui-enum-names": enum_names,
            }
    file_default: Any = None
    for p in variants:
        show = (p.get("displayOptions") or {}).get("show") if isinstance(p.get("displayOptions"), dict) else {}
        if show.get("resource") == ["file"] and p.get("default") is not None:
            file_default = p.get("default")
    if file_default is not None:
        default_value = file_default
    elif default_value is None and variants[0].get("default") is not None:
        default_value = variants[0].get("default")

    sch: dict[str, Any] = {
        "type": "string",
        "enum": all_values,
        "x-ui-enum-names": [value_labels[v] for v in all_values],
    }
    if default_value is not None:
        sch["default"] = default_value
    if len(by_resource) > 1:
        sch["x-ui-enum-by"] = {"field": "resource", "variants": by_resource}
    return sch


def _show_clause_from_display_options(p: dict[str, Any]) -> dict[str, Any] | None:
    do = p.get("displayOptions")
    if not isinstance(do, dict):
        return None
    show = do.get("show")
    if not isinstance(show, dict) or not show:
        return None
    clauses: list[dict[str, Any]] = []
    for field, values in show.items():
        if not isinstance(field, str) or not isinstance(values, list) or not values:
            continue
        if len(values) == 1:
            clauses.append({"field": field, "equals": values[0]})
        else:
            clauses.append({"field": field, "in": list(values)})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"all": clauses}


def _merge_property_variants(variants: list[dict[str, Any]]) -> dict[str, Any]:
    """One schema property from several upstream rows that share a ``name``."""

    base = inode_property_to_schema(variants[0])
    visibility: list[dict[str, Any]] = []
    for p in variants:
        clause = _show_clause_from_display_options(p)
        if clause and clause not in visibility:
            visibility.append(clause)
    if len(visibility) == 1:
        base["x-ui-show-when"] = visibility[0]
    elif len(visibility) > 1:
        base["x-ui-show-when-any"] = visibility
    return base


def build_top_level_parameter_schema(description: dict[str, Any]) -> dict[str, Any]:
    """Map top-level `description.properties` to a single JSON Schema object."""

    props_out: dict[str, Any] = {}
    required: list[str] = []
    options_by_name: dict[str, list[dict[str, Any]]] = {}
    variants_by_name: dict[str, list[dict[str, Any]]] = {}

    for p in description.get("properties") or []:
        if not isinstance(p, dict):
            continue
        name = p.get("name")
        if not name:
            continue
        if p.get("type") == "notice":
            continue
        key = str(name)
        if key == "authentication":
            continue
        if p.get("type") == "options":
            options_by_name.setdefault(key, []).append(p)
            continue
        variants_by_name.setdefault(key, []).append(p)

    for key, variants in variants_by_name.items():
        if len(variants) == 1:
            props_out[key] = inode_property_to_schema(variants[0])
        else:
            props_out[key] = _merge_property_variants(variants)
        if any(v.get("required") and v.get("default") is None for v in variants):
            required.append(key)

    for key, variants in options_by_name.items():
        if len(variants) == 1:
            props_out[key] = inode_property_to_schema(variants[0])
        else:
            props_out[key] = _merge_options_properties(variants)

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
        if isinstance(p.get("default"), dict):
            val = p["default"].get("value")
            if val is not None:
                sch["default"] = str(val)
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

    if p.get("default") is not None and t != "resourceLocator":
        sch = {**sch, "default": p["default"]}
    return _apply_inode_ui_extensions(p, sch)


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
        sch["x-ui-enum-names"] = names
    return sch


def _multi_options_schema(p: dict[str, Any]) -> dict[str, Any]:
    inner = _options_schema(p)
    if inner.get("type") == "string" and "enum" in inner:
        return {"type": "array", "items": {"type": "string", "enum": inner["enum"]}}
    return {"type": "array", "items": {"type": "string"}}
