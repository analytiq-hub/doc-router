# Dynamic Node Types — Design and Implementation Guide

A **dynamic node type** is a reusable node type whose definition — display
metadata, parameter schema, and Python execution code — is stored in MongoDB
rather than in Python source files. Once created via the API, a dynamic type
appears in the node-type registry for that organisation and can be used in any
flow revision exactly like a built-in type.

This document is the authoritative design and implementation guide for the
feature. It covers motivation, data model, engine integration, HTTP API, and
testing strategy.

---

## 1. Motivation

Built-in node types (`flows.code`, `docrouter.ocr`, etc.) are defined in Python
and deployed with the application. They are available to all organisations and
cannot be customised per organisation.

The one-off escape hatch is `flows.code`: a node that runs an inline Python
snippet stored on the *node instance*. It works but does not scale — the same
logic must be copied into every node in every flow that needs it, and there is
no shared parameter schema or shared label.

Dynamic node types fill the gap:

| | `flows.code` | Dynamic node type |
|---|---|---|
| Logic location | Per node instance | Per type definition (MongoDB) |
| Reusable across flows | No | Yes |
| Shared parameter schema | No | Yes |
| Org-scoped | N/A (global type) | Yes |
| Requires a deployment | No | No |

The closest n8n analogy is a community node installed per instance, except
dynamic types are created via the API with no deployment step.

---

## 2. Data model

### `flow_node_type_definitions` collection

One document per dynamic node type. Scoped to an organisation.

```json
{
  "_id":             "<ObjectId>",
  "organization_id": "<org_id>",
  "key":             "custom.invoice_parser",
  "label":           "Invoice Parser",
  "description":     "Extracts line items from an invoice JSON payload.",
  "category":        "Custom",
  "is_trigger":      false,
  "is_merge":        false,
  "min_inputs":      1,
  "max_inputs":      1,
  "outputs":         1,
  "output_labels":   ["output"],
  "parameter_schema": {
    "type": "object",
    "properties": {
      "currency": { "type": "string", "default": "USD" }
    },
    "additionalProperties": false
  },
  "python_code":      "def run(items, context):\n    ...",
  "timeout_seconds":  5.0,
  "created_at":       "<ISO datetime>",
  "created_by":       "<user_id>",
  "updated_at":       "<ISO datetime>",
  "updated_by":       "<user_id>"
}
```

#### Field rules

| Field | Constraint |
|-------|-----------|
| `key` | Unique within the org; must not collide with any key in the global in-memory registry; may not start with `flows.` or `docrouter.` |
| `is_trigger` | Always `false` in v1. Trigger registration is a separate subsystem. |
| `is_merge` | May be `true`; merge semantics are identical to built-in merge nodes. |
| `min_inputs` | `>= 0`; `0` only makes sense when `is_trigger` is eventually supported. |
| `max_inputs` | `null` means unbounded (same semantics as the engine's `max_inputs`). |
| `outputs` | `>= 1`. |
| `output_labels` | Length must equal `outputs`. |
| `parameter_schema` | Valid JSON Schema (Draft 7). Validated at type save time via `jsonschema`. |
| `python_code` | Must define a top-level `run(items, context)` function. Validated by `ast.parse` at save time; execution correctness is not checked until runtime. |
| `timeout_seconds` | `> 0` and `<= 30`. Default `5.0`. |

---

## 3. `DynamicNodeType` class

**File**: `analytiq_data/flows/dynamic_node_type.py`

Implements the `NodeType` protocol. Execution delegates to `run_python_code`
(the same subprocess runner used by `flows.code`); the code is taken from
`self.python_code`, not from the node instance's parameters.

```python
@dataclass
class DynamicNodeType:
    key: str
    label: str
    description: str
    category: str
    is_trigger: bool
    is_merge: bool
    min_inputs: int
    max_inputs: int | None
    outputs: int
    output_labels: list[str]
    parameter_schema: dict[str, Any]
    python_code: str
    timeout_seconds: float = 5.0

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: ExecutionContext,
        node: dict[str, Any],
        inputs: list[list[FlowItem]],
    ) -> list[list[FlowItem]]:
        # Delegates to run_python_code with self.python_code.
        # Identical contract to FlowsCodeNode.execute, except the
        # snippet comes from the type definition rather than node.parameters.
        ...
```

### Loader

```python
async def load_org_node_types(
    analytiq_client: Any,
    organization_id: str,
) -> dict[str, DynamicNodeType]:
    """Return all dynamic node types for org as a key → DynamicNodeType map."""
    db = ad.common.get_async_db(analytiq_client)
    docs = await db.flow_node_type_definitions.find(
        {"organization_id": organization_id}
    ).to_list(None)
    return {doc["key"]: _doc_to_dynamic_type(doc) for doc in docs}
```

`load_org_node_types` is called once at the start of each `run_flow` call. The
result is a short-lived, per-execution dict; it is never written into the global
in-memory registry.

---

## 4. Engine integration

### 4.1 The `local_types` overlay

The engine resolves node types by key with `ad.flows.get(key)`, which reads the
global in-memory registry. Dynamic types are org-scoped and must not pollute
that registry. The solution is a module-level helper and a `local_types`
parameter threaded through the call chain.

```python
# engine.py
def _resolve_type(
    key: str,
    local_types: dict[str, Any] | None,
) -> "ad.flows.NodeType":
    if local_types and key in local_types:
        return local_types[key]
    return ad.flows.get(key)
```

Every call to `ad.flows.get(node["type"])` in `validate_revision` and
`_execute_loop` becomes `_resolve_type(node["type"], local_types)`.

### 4.2 Signature changes

| Function | New keyword parameter |
|----------|-----------------------|
| `validate_revision(nodes, connections, settings, pin_data)` | `local_types: dict[str, Any] \| None = None` |
| `_execute_loop(context, nodes_by_id, connections, ...)` | `local_types: dict[str, Any] \| None = None` |
| `run_flow(*, context, revision)` | unchanged externally; loads `local_types` internally |

### 4.3 `run_flow` loading sequence

```python
async def run_flow(*, context, revision):
    nodes      = revision.get("nodes") or []
    connections = coerce_json_connections_to_dataclasses(revision.get("connections"))
    settings   = revision.get("settings") or {}
    pin_data   = revision.get("pin_data")

    # Load org dynamic types before validation so validate_revision can
    # resolve them.  Falls back to empty dict for unit tests (no client).
    local_types: dict[str, Any] = {}
    if context.analytiq_client is not None:
        local_types = await load_org_node_types(
            context.analytiq_client, context.organization_id
        )

    validate_revision(nodes, connections, settings, pin_data,
                      local_types=local_types)

    nodes_by_id = {n["id"]: n for n in nodes}
    trigger = next(n for n in nodes if _resolve_type(n["type"], local_types).is_trigger)

    merge_waiting = {}
    work = deque([_WorkItem(node_id=trigger["id"], inputs=[])])

    timeout = settings.get("execution_timeout_seconds")
    coro = _execute_loop(context, nodes_by_id, connections, pin_data,
                         work, merge_waiting, local_types=local_types)
    if timeout:
        return await asyncio.wait_for(coro, timeout=float(timeout))
    return await coro
```

### 4.4 No global registry mutation

Dynamic types are never written into `_registry` (the global dict in
`node_registry.py`). This keeps the global registry stable across concurrent
executions and avoids leaking org data between organisations.

---

## 5. HTTP API

### 5.1 Existing route — extended

```
GET /v0/orgs/{org_id}/flows/node-types
```

Currently returns only the global in-memory registry. After the change it also
queries `flow_node_type_definitions` for the org and appends those entries. The
response shape per entry gains one extra field:

```json
{
  "type_id": "<ObjectId string>",   // present only for dynamic types
  "key": "custom.invoice_parser",
  "label": "Invoice Parser",
  ...
}
```

Static entries have no `type_id` field.

### 5.2 New CRUD routes

All routes are under `/v0/orgs/{org_id}/flows/node-types/custom` and require
the same org-member authentication as other flow routes.

#### Create

```
POST /v0/orgs/{org_id}/flows/node-types/custom
```

Request body:

```json
{
  "key":              "custom.invoice_parser",
  "label":            "Invoice Parser",
  "description":      "Extracts line items from an invoice JSON payload.",
  "category":         "Custom",
  "is_merge":         false,
  "min_inputs":       1,
  "max_inputs":       1,
  "outputs":          1,
  "output_labels":    ["output"],
  "parameter_schema": { ... },
  "python_code":      "def run(items, context):\n    ...",
  "timeout_seconds":  5.0
}
```

Validation performed before insert:

1. `key` not already present in the global registry (reject if it collides with
   a built-in key).
2. `key` unique within the org (check `flow_node_type_definitions` by
   `{organization_id, key}`).
3. `key` does not start with `flows.` or `docrouter.`.
4. `parameter_schema` passes `Draft7Validator` schema-of-schema check.
5. `python_code` parses without syntax errors (`ast.parse`).
6. `len(output_labels) == outputs`.

Response `201`:

```json
{
  "type_id": "<ObjectId string>",
  "key":     "custom.invoice_parser"
}
```

#### List org custom types

```
GET /v0/orgs/{org_id}/flows/node-types/custom
```

Returns only the org's dynamic types (not the global registry). Suitable for
management UIs.

Response `200`:

```json
{
  "items": [ { "type_id": "...", "key": "...", "label": "...", ... } ],
  "total": 1
}
```

#### Get one

```
GET /v0/orgs/{org_id}/flows/node-types/custom/{type_id}
```

Returns the full document including `python_code`.

#### Update

```
PUT /v0/orgs/{org_id}/flows/node-types/custom/{type_id}
```

Same body as create (all fields). The `key` may not be changed after creation
(to avoid silently breaking active flow revisions that reference the old key).
If the key needs to change, delete and recreate.

Runs the same validation as create (minus uniqueness check on the same
document).

#### Delete

```
DELETE /v0/orgs/{org_id}/flows/node-types/custom/{type_id}
```

**Usage check before deletion**: queries `flow_revisions` for any revision
where `organization_id` matches and `nodes[].type` equals the type key. If any
are found, returns `409 Conflict`:

```json
{
  "detail": "Node type is referenced by flow revisions",
  "flow_revids": ["<revid1>", "<revid2>"]
}
```

If no revisions reference the type, deletes the document and returns `204`.

---

## 6. Execution contract

A dynamic node type executes its `python_code` via `run_python_code` (the same
subprocess runner as `flows.code`). The snippet must define:

```python
def run(items: list[dict], context: dict) -> list[dict]:
    ...
```

- `items` — list of the current input slot's item JSON dicts.
- `context` — same execution context dict as `flows.code` (trigger data, node
  id, mode, prior node outputs, org/flow/execution IDs).
- Return value — list of output JSON dicts, one per output item.

The resolved `node.parameters` (after expression evaluation) are available
inside the snippet via `context["parameters"]`:

```python
def run(items, context):
    currency = context["parameters"].get("currency", "USD")
    for item in items:
        item["currency"] = currency
    return items
```

`context["parameters"]` is populated by the engine before calling `execute`,
exactly as for all other node types.

---

## 7. Module layout

```
analytiq_data/flows/
  dynamic_node_type.py    DynamicNodeType dataclass
                          load_org_node_types(client, org_id) → dict
  engine.py               _resolve_type(key, local_types) helper
                          validate_revision  — gains local_types kwarg
                          _execute_loop      — gains local_types kwarg
                          run_flow           — calls load_org_node_types,
                                               threads local_types through
  __init__.py             re-exports DynamicNodeType, load_org_node_types

app/routes/flows.py       5 new CRUD routes for /node-types/custom
                          extend list_node_types to include org types

tests_flow/
  test_dynamic_node_types.py  unit tests (no MongoDB)
tests/
  test_flows_e2e.py           integration test additions
```

---

## 8. Testing strategy

### Unit tests (`tests_flow/test_dynamic_node_types.py`)

All tests run without MongoDB. `load_org_node_types` is not called; instead,
`local_types` is constructed directly in each test and passed to `validate_revision`
or used via `run_flow` by injecting a stub into the context.

| Test | What it covers |
|------|---------------|
| `test_dynamic_type_executes` | A `DynamicNodeType` instance runs its code and produces the expected output. |
| `test_dynamic_type_in_flow` | A minimal flow (trigger → dynamic node) runs end-to-end with `local_types` override; asserts `run_data` output. |
| `test_dynamic_type_parameter_expression` | Parameters with `=` expressions are resolved before the snippet sees them. |
| `test_key_not_in_local_types_raises` | Using an unknown key in a revision raises `FlowValidationError`. |
| `test_dynamic_type_does_not_shadow_builtin` | A `local_types` dict whose key matches a built-in is rejected at validation time (API-level check). |

### Integration tests (`tests/test_flows_e2e.py`)

| Test | What it covers |
|------|---------------|
| `test_create_and_run_dynamic_node_type` | POST to create a type, save a revision that uses it, run the flow, assert execution status and `run_data`. |
| `test_delete_blocked_by_active_revision` | DELETE returns 409 when a revision references the type. |
| `test_update_dynamic_node_type` | PUT updates the code; subsequent run uses the new code. |

---

## 9. Known limitations (v1)

- **No trigger or schedule support.** `is_trigger` is always `false`. Dynamic
  trigger nodes require a separate activation subsystem (see `flows2.md` §10
  roadmap).
- **Single output slot only for v1.** `outputs > 1` is allowed by the schema
  but the `run()` contract returns a flat list, which maps to slot 0. Multi-output
  support requires a richer return contract (e.g. `list[list[dict]]`).
- **No key rename.** Changing the key requires delete + recreate. Active
  revisions are protected by the deletion check.
- **`flows.code` sandbox limits apply.** The same restricted-builtins subprocess
  environment is used; `__import__` and file system access are unavailable.
- **No version history for type definitions.** Updates are in-place. Revisions
  that reference a type always see the current definition at execution time, not
  the definition at the time the revision was saved.
