from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

from .http_spec import build_http_request_spec
from .properties import iter_integration_parameter_tree
from .schema import build_top_level_parameter_schema

MANIFEST_SCHEMA_URI = "https://docrouter.example/schemas/flow-node-manifest/v1.json"

FLOW_PORT_PKG = Path(__file__).resolve().parent
DEFAULT_GENERATED_ROOT = FLOW_PORT_PKG / "generated_nodes"


def _find_repo_root() -> Path:
    """Locate DocRouter checkout (directory containing schemas/flow-node-manifest-v1.json)."""

    p = FLOW_PORT_PKG
    for _ in range(12):
        cand = p / "schemas" / "flow-node-manifest-v1.json"
        if cand.is_file():
            return p
        p = p.parent
    raise FileNotFoundError(
        "schemas/flow-node-manifest-v1.json not found ascending from analytiq_data/flows/port/"
    )


def classify_executor(description: dict[str, Any]) -> str:
    if description.get("requestDefaults"):
        return "declarative"
    for p in iter_integration_parameter_tree(description):
        if p.get("routing"):
            return "declarative"
    return "python_class"


def manifest_key(description: dict[str, Any]) -> str:
    name = str(description.get("name") or "unknown")
    safe = re.sub(r"[^a-z0-9._-]+", "_", name.lower()).strip("._-") or "unknown"
    return f"ext.{safe}"


def _integration_version_key(row: dict[str, Any]) -> Any | None:
    return row.get("integration_type_version_key")


def type_version_int(description: dict[str, Any], row: dict[str, Any]) -> int:
    if _integration_version_key(row) is not None:
        k = _integration_version_key(row)
        try:
            return int(float(str(k)))
        except (TypeError, ValueError):
            pass
    dv = description.get("defaultVersion")
    if isinstance(dv, int):
        return dv
    ver = description.get("version")
    if isinstance(ver, int):
        return ver
    if isinstance(ver, list):
        nums = [x for x in ver if isinstance(x, int)]
        if nums:
            return max(nums)
    return 1


def group_category(description: dict[str, Any]) -> str:
    g = description.get("group")
    if isinstance(g, list) and g:
        return str(g[0])
    return "transform"


def port_layout(description: dict[str, Any]) -> dict[str, Any]:
    ins = description.get("inputs")
    if isinstance(ins, list):
        min_inputs = len(ins)
    elif isinstance(ins, int):
        min_inputs = max(0, ins)
    else:
        min_inputs = 1

    outs = description.get("outputs")
    if isinstance(outs, list):
        n_out = len(outs)
    elif isinstance(outs, int):
        n_out = max(1, outs)
    else:
        n_out = 1

    labels = description.get("outputNames")
    if isinstance(labels, list) and len(labels) == n_out:
        output_labels = [str(x) for x in labels]
    elif n_out == 1:
        output_labels = ["main"]
    else:
        output_labels = [str(i) for i in range(n_out)]

    g0 = None
    g = description.get("group")
    if isinstance(g, list) and g:
        g0 = str(g[0]).lower()

    is_trigger = min_inputs == 0 or (g0 == "trigger" if g0 else False)

    merge_like = isinstance(description.get("name"), str) and "merge" in str(
        description.get("name", "")
    ).lower()
    if merge_like:
        max_inputs = None
    else:
        max_inputs = min_inputs if min_inputs > 0 else None

    return {
        "min_inputs": min_inputs,
        "max_inputs": max_inputs,
        "outputs": n_out,
        "output_labels": output_labels,
        "is_trigger": is_trigger,
    }


def icon_key(description: dict[str, Any]) -> str | None:
    ic = description.get("icon")
    if isinstance(ic, str):
        return ic.removeprefix("file:")
    if isinstance(ic, dict):
        light = ic.get("light") or ic.get("dark")
        if isinstance(light, str):
            return light.removeprefix("file:")
    return None


def map_credentials(description: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for c in description.get("credentials") or []:
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        if not name:
            continue
        nm = str(name)
        out.append(
            {
                "slot": nm,
                "label": str(c.get("displayName") or nm),
                "required": c.get("required") is not False,
                "docrouter_binding": f"organization_credential_kind:{nm}",
            }
        )
    return out


def allocate_slug(desc: dict[str, Any], row: dict[str, Any], tracker: dict[str, int]) -> str:
    base_raw = str(desc.get("name") or "unknown")
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", base_raw).strip("_").lower() or "unknown"
    if not safe.startswith("ext"):
        safe = f"ext_{safe}"
    vk = _integration_version_key(row)
    if vk is not None:
        vv = str(vk).replace(".", "_").replace("-", "_")
        safe = f"{safe}_v_{vv}"

    n = tracker.get(safe, 0)
    tracker[safe] = n + 1
    if n == 0:
        return safe
    return f"{safe}_{n}"


def class_name_from_slug(slug: str) -> str:
    body = slug.removeprefix("ext_") if slug.startswith("ext_") else slug
    parts = [p for p in body.split("_") if p]
    pascal = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return f"Ext{pascal}Node"


def render_stub_py(
    *,
    class_name: str,
    key: str,
    label: str,
    description: str,
    category: str,
    is_trigger: bool,
    min_inputs: int,
    max_inputs: int | None,
    outputs: int,
    output_labels: list[str],
    icon_key_v: str | None,
    source: str,
) -> str:
    err = f"{key}: Python integration stub not implemented"
    max_in = "None" if max_inputs is None else str(int(max_inputs))
    return f'''from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analytiq_data as ad

_SCHEMA_PATH = Path(__file__).resolve().parent / "parameter.schema.json"
_schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class {class_name}:
    """Autogenerated integration stub — implement execute(). Source: {source!r}"""

    key = {key!r}
    label = {label!r}
    description = {description!r}
    category = {category!r}
    palette_group = "app"
    is_trigger = {repr(is_trigger)}
    is_merge = False
    min_inputs = {int(min_inputs)}
    max_inputs = {max_in}
    outputs = {int(outputs)}
    output_labels = {repr(output_labels)}
    icon_key = {repr(icon_key_v)}
    batch_execute_inputs = False
    parameter_schema = _schema

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: ad.flows.ExecutionContext,
        node: dict[str, Any],
        inputs: list[list[ad.flows.FlowItem]],
    ) -> list[list[ad.flows.FlowItem]]:
        raise NotImplementedError({err!r})
'''


def build_manifest(
    *,
    key: str,
    type_version: int,
    label: str,
    description: str,
    category: str,
    is_trigger: bool,
    is_merge: bool,
    min_inputs: int,
    max_inputs: int | None,
    outputs: int,
    output_labels: list[str],
    icon_key_v: str | None,
    parameter_schema: dict[str, Any],
    executor: dict[str, Any],
    credential_slots: list[dict[str, Any]],
) -> dict[str, Any]:
    m: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA_URI,
        "manifest_version": 1,
        "key": key,
        "type_version": int(type_version),
        "label": label,
        "description": description,
        "category": category,
        "is_trigger": is_trigger,
        "is_merge": is_merge,
        "min_inputs": min_inputs,
        "max_inputs": max_inputs,
        "outputs": outputs,
        "output_labels": output_labels,
        "icon_key": icon_key_v,
        "batch_execute_inputs": False,
        "parameter_schema": parameter_schema,
        "executor": executor,
    }
    if credential_slots:
        m["credential_slots"] = credential_slots
    return m


def emit_node_package(
    row: dict[str, Any],
    out_root: Path,
    warnings: list[str],
    slug_tracker: dict[str, int],
) -> Path:
    desc = row.get("description")
    if not isinstance(desc, dict):
        raise ValueError("row missing description object")
    source = str(row.get("source") or "")

    slug = allocate_slug(desc, row, slug_tracker)
    pkg = out_root / slug
    pkg.mkdir(parents=True, exist_ok=True)

    param_schema = build_top_level_parameter_schema(desc)
    (pkg / "parameter.schema.json").write_text(
        json.dumps(param_schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    kind = classify_executor(desc)
    local_warn: list[str] = []
    if kind == "declarative":
        http = build_http_request_spec(desc, local_warn)
        if http is None:
            warnings.append(
                f"{slug}: declarative heuristics matched but no extractable routing.request; using python_class"
            )
            kind = "python_class"
        elif not http.get("url"):
            warnings.append(f"{slug}: http spec missing url after extraction; using python_class")
            kind = "python_class"
        else:
            (pkg / "http.spec.json").write_text(
                json.dumps(http, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    key = manifest_key(desc)
    tv = type_version_int(desc, row)
    label = str(desc.get("displayName") or desc.get("name") or key)
    description = str(desc.get("description") or f"Imported integration node {key}")
    category = group_category(desc)
    layout = port_layout(desc)
    ic = icon_key(desc)
    creds = map_credentials(desc)

    class_name = class_name_from_slug(slug)
    mod_import = f"analytiq_data.flows.port.generated_nodes.{slug}.node_impl"

    if kind == "declarative":
        executor = {
            "kind": "declarative",
            "runtime": "http_request_v1",
            "spec_ref": "http.spec.json",
        }
    else:
        executor = {"kind": "python_class", "import": mod_import, "class": class_name}

    manifest = build_manifest(
        key=key,
        type_version=tv,
        label=label,
        description=description,
        category=category,
        is_trigger=bool(layout["is_trigger"]),
        is_merge=False,
        min_inputs=int(layout["min_inputs"]),
        max_inputs=layout["max_inputs"],
        outputs=int(layout["outputs"]),
        output_labels=list(layout["output_labels"]),
        icon_key_v=ic,
        parameter_schema=param_schema,
        executor=executor,
        credential_slots=creds,
    )

    (pkg / "node.manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if kind == "python_class":
        stub = render_stub_py(
            class_name=class_name,
            key=key,
            label=label,
            description=description,
            category=category,
            is_trigger=bool(layout["is_trigger"]),
            min_inputs=int(layout["min_inputs"]),
            max_inputs=layout["max_inputs"],
            outputs=int(layout["outputs"]),
            output_labels=list(layout["output_labels"]),
            icon_key_v=ic,
            source=source,
        )
        (pkg / "node_impl.py").write_text(stub, encoding="utf-8")

    (pkg / "__init__.py").write_text(
        '"""Autogenerated upstream integration package."""\n',
        encoding="utf-8",
    )

    for w in local_warn:
        warnings.append(f"{slug}: {w}")
    return pkg


def iter_flow_node_dump_rows(text: str) -> Iterator[dict[str, Any]]:
    """
    Parse ``tools/flow_node_dump.jsonl`` content: one JSON object per line (legacy)
    or pretty-printed objects separated by whitespace (indent-aware ``JSONDecoder.raw_decode``).
    """

    dec = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, end = dec.raw_decode(text, i)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in flow node dump at offset {i}: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError("Flow node dump rows must be JSON objects at top level")
        i = end
        yield obj


def convert_jsonl_file(
    jsonl_path: Path,
    out_root: Path,
    *,
    limit: int = 0,
    only_key_prefix: str | None = None,
) -> list[Path]:
    """Read dump JSONL and write packages under out_root."""

    body = jsonl_path.read_text(encoding="utf-8")
    written: list[Path] = []
    warnings: list[str] = []
    slug_tracker: dict[str, int] = {}

    for row in iter_flow_node_dump_rows(body):
        desc = row.get("description") or {}
        if only_key_prefix:
            if not manifest_key(desc).startswith(only_key_prefix):
                continue
        written.append(emit_node_package(row, out_root, warnings, slug_tracker))
        if limit and len(written) >= limit:
            break

    for w in warnings:
        print(w, file=sys.stderr)
    return written


def validate_packages(packages: list[Path]) -> None:
    """Optional: validate manifests and parameter schemas (requires jsonschema)."""

    try:
        import jsonschema
    except ImportError as e:
        raise RuntimeError("pip install jsonschema for --validate") from e

    repo = _find_repo_root()
    manifest_schema_path = repo / "schemas" / "flow-node-manifest-v1.json"
    http_schema_path = repo / "schemas" / "runtimes" / "http_request_v1.schema.json"
    if not manifest_schema_path.is_file():
        raise FileNotFoundError(manifest_schema_path)

    mschema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(mschema)
    mv = jsonschema.Draft7Validator(mschema)

    hschema = None
    hv = None
    if http_schema_path.is_file():
        hschema = json.loads(http_schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator.check_schema(hschema)
        hv = jsonschema.Draft7Validator(hschema)

    for pkg in packages:
        mf = pkg / "node.manifest.json"
        data = json.loads(mf.read_text(encoding="utf-8"))
        mv.validate(data)
        ps = pkg / "parameter.schema.json"
        jsonschema.Draft7Validator.check_schema(
            json.loads(ps.read_text(encoding="utf-8"))
        )
        hf = pkg / "http.spec.json"
        if hf.is_file() and hv is not None:
            hv.validate(json.loads(hf.read_text(encoding="utf-8")))
