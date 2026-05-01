# Porting n8n nodes to DocRouter

This guide describes the **programmatic pipeline** for converting n8n node types (from the sibling `../n8n` clone) into DocRouter node packages — the `node.manifest.json` + `parameter.schema.json` + optional executor spec layout described in [`docrouter_nodes.md`](./docrouter_nodes.md) (declarative **`executor.kind`** + **`http_request_v1`** etc.: §6.2 there).

Goal: quickly bootstrap the DocRouter node ecosystem by translating the large n8n integration library rather than hand-authoring each node from scratch.

Related references: [`n8n_nodes.md`](./n8n_nodes.md) (n8n node inventory and type contracts), [`flows_workflow_interop.md`](./flows_workflow_interop.md) (broader interop goals).

---

## 1. Core observation: two tracks

Most n8n SaaS connectors are not really TypeScript programs — they are **declarative HTTP specs dressed in TypeScript**. They use `requestDefaults` plus `routing` on `INodeProperties` entries to describe HTTP calls. These map cleanly to DocRouter's `http_request_v1` declarative executor and can be ported fully automatically.

A smaller set have real imperative `execute()` logic (transforms, code nodes, database drivers). These get a **stub manifest** with a `python_class` executor; the Python behavior must be ported by hand.

```
../n8n  *.node.ts
         │
         ├─ uses requestDefaults / routing? ──→  declarative executor (http_request_v1)
         │                                        fully automatable
         │
         └─ has custom execute()? ────────────→  python_class stub (NotImplementedError)
                                                  metadata automatable, behavior manual
```

---

## 2. Input source

Do not parse TypeScript AST — it is fragile across n8n versions. Instead, **require() the compiled JS** from `../n8n/packages/nodes-base/dist/` after `pnpm build`. A small Node.js shim instantiates each node class and dumps `.description` as JSONL:

```js
// tools/dump_n8n_nodes.js
const { globSync } = require('glob');
const path = require('path');

const patterns = [
  '../n8n/packages/nodes-base/dist/nodes/**/*.node.js',
  '../n8n/packages/@n8n/nodes-langchain/dist/nodes/**/*.node.js',
];

for (const file of globSync(patterns.flatMap(p => p))) {
  try {
    const mod = require(path.resolve(file));
    for (const cls of Object.values(mod)) {
      if (typeof cls !== 'function') continue;
      const inst = new cls();
      if (!inst.description) continue;
      process.stdout.write(JSON.stringify({ source: file, description: inst.description }) + '\n');
    }
  } catch (e) {
    process.stderr.write(`skip ${file}: ${e.message}\n`);
  }
}
```

Run once per n8n version bump:

```bash
node tools/dump_n8n_nodes.js > tools/n8n_node_dump.jsonl
```

The Python converter reads `n8n_node_dump.jsonl`. No TypeScript toolchain needed at conversion time.

---

## 3. Executor classification

Heuristic only: n8n can combine **`routing`** / **`requestDefaults`** with imperative **`execute()`** logic that ignores or extends the declarative path.

```python
def classify(description: dict, has_body_execute: bool) -> str:
    """Return 'declarative' or 'python_class'."""

    if has_body_execute:
        # Instantiating the version-specific class and inspecting whether
        # `execute` is the generic routing helper vs overridden is ideal; if unknown, err on python_class.
        return "python_class"

    if description.get("requestDefaults"):
        return "declarative"
    for prop in iter_properties(description):
        if prop.get("routing"):
            return "declarative"
    return "python_class"
```

When you only have the dump of **`.description`** (no class), treat nodes that **also** ship non-trivial **`execute`** as **`python_class`** after sampling the compiled module. If you cannot detect `execute` reliably, prefer **`python_class`** stubs for anything that is not a **pure routing** HTTP connector.

`iter_properties` flattens all nested `INodeProperties` entries including those inside `options[].values` and versioned node slices.

---

## 4. Metadata mapping

Manifest top-level fields derived from `INodeTypeDescription`:

| n8n field | DocRouter manifest field | Notes |
|---|---|---|
| `displayName` | `label` | |
| `name` | `key` | Prefix with integration namespace, e.g. `n8n.slack` |
| `description` | `description` | |
| `group[0]` | `category` | e.g. `"output"`, `"transform"` |
| `defaultVersion` \| `version` | `type_version` | Use `defaultVersion` when present; for arrays take the max |
| `inputs` | `min_inputs`, `max_inputs` | Count `Main` entries; `0` inputs → `is_trigger: true` |
| `outputs` | `outputs`, `output_labels` | Count `Main` outputs; use `outputNames` for labels if present |
| `trigger`/`poll`/`webhook` present | `is_trigger: true` | |
| `credentials[*]` | `credential_slots` | See §7 |
| `icon` | `icon_key` | Strip `file:` prefix; store path relative to package root |
| `usableAsTool` | (future) | Skip for now |

**`key` convention:** `n8n.<integration>.<operation>` for single-operation ports, `n8n.<integration>` for multi-operation nodes that expose an `operation` parameter.

---

## 5. Parameter mapping: `INodeProperties[]` → JSON Schema

Build a single `parameter.schema.json` `object` whose `properties` are the top-level parameters. Recurse into `collection` and `fixedCollection` types.

| n8n `type` | JSON Schema | Notes |
|---|---|---|
| `string` | `{"type": "string"}` | |
| `number` | `{"type": "number"}` | |
| `boolean` | `{"type": "boolean"}` | |
| `options` | `{"type": "string", "enum": [...]}` | `options[].value` → enum values; `options[].name` → **`x-enumNames`** (UI hint array, same order as `enum`) |
| `multiOptions` | `{"type": "array", "items": {"type": "string", "enum": [...]}}` | |
| `collection` | `{"type": "object", "properties": {...}}` | Recurse into `options` |
| `fixedCollection` | `{"type": "object", "properties": {...}}` | Flatten `values` arrays into properties |
| `json` | `{"type": ["object", "string"]}` | n8n accepts either |
| `code` | `{"type": "string"}` | Add `$content_ref` if `default` is non-empty (write default to sidecar) |
| `color` | `{"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}` | |
| `dateTime` | `{"type": "string", "format": "date-time"}` | |
| `resourceLocator` | `{"type": "string"}` | Loses resource-picker UI; acceptable for first pass |
| `notice` | drop | UI-only display element, carries no data |
| `hidden` | include as optional | Often carries `default` values used by routing |

**`default` values:** carry through as JSON Schema `default` on the property.

**`displayOptions`** (conditional visibility) has no JSON Schema equivalent. In the first pass, include all properties as optional regardless of display conditions. A future `x-display-options` extension can preserve them for the UI layer.

**`required` fields:** a parameter is required in the schema if `required: true` is set on the `INodeProperty` and it has no `default`.

---

## 6. Declarative executor: assembling `http.spec.json`

For nodes classified as `declarative`, assemble an `http_request_v1` spec from:

| n8n source | `http.spec.json` field |
|---|---|
| `requestDefaults.baseURL` | prepended to per-operation `url` |
| `requestDefaults.headers` | merged into `headers` |
| `routing.request.method` | `method` |
| `routing.request.url` | `url` (append to baseURL) |
| `routing.request.qs.*` | `query_params` |
| `routing.request.body.*` | `body` (inline) or `$content_ref` sidecar if large |
| `routing.request.headers` | merged into `headers` |
| `routing.output.postReceive[].type === 'rootProperty'` | `response_jmespath` |
| `routing.output.postReceive[].type === 'set'` | `response_set` |

Credential token injection uses Jinja2 expressions referencing `credentials.*`:

```json
{
  "headers": {
    "Authorization": "Bearer {{ credentials.slackToken }}"
  }
}
```

Parameter values in the spec use `{{ parameters.<name> }}`. Boolean/numeric parameters that gate request fields should be expressed as Jinja2 conditionals:

```
{% if parameters.include_metadata %},"metadata": true{% endif %}
```

If the assembled spec body exceeds ~200 characters of inline JSON, write it to `templates/body.json.tpl` and use `$content_ref`:

```json
{
  "body": {
    "$content_ref": "templates/body.json.tpl",
    "$content_media_type": "application/json"
  }
}
```

---

## 7. Credential slots

Map each `INodeCredentialDescription` entry to a `credential_slots` item:

```python
def map_credential(cred: dict) -> dict:
    return {
        "slot": cred["name"],          # e.g. "slackApi"
        "label": cred.get("displayName", cred["name"]),
        "required": not cred.get("required") == False,
        "docrouter_binding": f"organization_credential_kind:{cred['name']}"
    }
```

---

## 8. Output layout

One directory per ported node under `nodes/`:

```
nodes/
└── n8n_slack_post_message/
    ├── node.manifest.json       ← generated
    ├── parameter.schema.json    ← generated
    ├── http.spec.json           ← generated (declarative track only)
    └── templates/
        └── body.json.tpl        ← generated if body is large
```

For `python_class` stubs, also emit a skeleton Python file:

```
nodes/
└── n8n_postgres_query/
    ├── node.manifest.json
    ├── parameter.schema.json
    └── node_impl.py             ← stub; behavior must be ported by hand
```

**`node_impl.py` stub template:** (duck-types the **`NodeType`** protocol — do not subclass it; match fields and method signatures like existing nodes, e.g. [`packages/python/analytiq_data/flows/nodes/code.py`](../packages/python/analytiq_data/flows/nodes/code.py).)

```python
from typing import Any

import analytiq_data as ad


class N8nPostgresQueryNode:
    """Ported from n8n packages/nodes-base/nodes/Postgres/Postgres.node.ts — stub."""

    key = "n8n.postgres_query"
    label = "Postgres (n8n)"
    description = "Stub: implement execute() for DocRouter."
    category = "Database"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["main"]
    icon_key = None
    batch_execute_inputs = False
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: ad.flows.ExecutionContext,
        node: dict[str, Any],
        inputs: list[list[ad.flows.FlowItem]],
    ) -> list[list[ad.flows.FlowItem]]:
        raise NotImplementedError("n8n.postgres_query: Python port not yet implemented")
```

---

## 9. Known gaps and first-pass limitations

| Gap | Impact | Mitigation |
|---|---|---|
| `displayOptions` conditions dropped | All parameters visible in UI regardless of current operation | Acceptable for v1; add `x-display-options` extension later |
| `loadOptions` / `listSearch` methods | Dynamic dropdowns become plain `string` fields | Schema gets `{"type": "string"}`; user types value manually |
| Binary data nodes (files, images) | Cannot be ported declaratively | `python_class` stub; manual Python port |
| Sub-workflow nodes (`ExecuteWorkflow`) | DocRouter has a different sub-flow model | Stub only |
| n8n-specific helpers (`$node`, `$workflow`, `$execution`) | Used in some `execute()` bodies | Manual port only; no equivalent in DocRouter today |
| Multi-output routing (Switch, If) | n8n uses multiple `Main` outputs; DocRouter supports `outputs > 1` | Port is possible but routing logic needs Python |
| Versioned nodes (`VersionedNodeType`) | Multiple `typeVersion` slices | Port the `defaultVersion` slice only; bump `type_version` manually if re-porting |

---

## 10. Validation after generation

Run the standard §8 pipeline from [`docrouter_nodes.md`](./docrouter_nodes.md) on every generated package. The PyPI **`jsonschema`** package does not always install a working **`jsonschema` CLI** — use **`check-jsonschema`** ([PyPI](https://pypi.org/project/check-jsonschema/)) or a small Python harness:

```bash
# Manifests (Draft 7 validator; requires: pip install jsonschema)
python <<'PY'
import json, glob, jsonschema

def main():
    with open("schemas/flow-node-manifest-v1.json") as f:
        manifest_schema = json.load(f)
    jsonschema.Draft7Validator.check_schema(manifest_schema)
    mv = jsonschema.Draft7Validator(manifest_schema)
    for path in sorted(glob.glob("nodes/*/node.manifest.json")):
        with open(path) as f:
            mv.validate(json.load(f))
        print(path, "ok")

main()
PY

# Parameter schemas (Draft 7 meta-schema check only)
for f in nodes/*/parameter.schema.json; do
  python -c "import jsonschema, json; jsonschema.Draft7Validator.check_schema(json.load(open('$f')))"
done

# Declarative specs (when present)
python <<'PY'
import json, glob, jsonschema
with open("schemas/runtimes/http_request_v1.schema.json") as f:
    spec_schema = json.load(f)
jsonschema.Draft7Validator.check_schema(spec_schema)
sv = jsonschema.Draft7Validator(spec_schema)
for path in sorted(glob.glob("nodes/*/http.spec.json")):
    with open(path) as f:
        sv.validate(json.load(f))
    print(path, "ok")
PY
```

Alternatively: `check-jsonschema --schemafile schemas/flow-node-manifest-v1.json nodes/*/node.manifest.json` (and similarly for **`http.spec.json`**). Add this as a CI step when the dump or converter changes.

---

## 11. Suggested implementation order

1. Write `tools/dump_n8n_nodes.js` and generate `n8n_node_dump.jsonl` from the current n8n checkout.
2. Write `tools/port_n8n_nodes.py`: reads JSONL, emits node packages under `nodes/`.
3. Start with a single well-understood declarative node (e.g. Slack `postMessage`) to validate the full pipeline end to end.
4. Run against all 506 `n8n-nodes-base` entries; triage the `python_class` stubs by priority.
5. Commit `n8n_node_dump.jsonl` to the repo and re-run the converter in CI whenever the dump is refreshed.

---

## 12. DocRouter prerequisites

The following DocRouter capabilities must exist before the porting pipeline can be used end to end. They are listed in the recommended build order.

### Blockers — nothing works without these

#### 12.1 `$content_ref` resolver utility

Not implemented anywhere in the codebase. Both the manifest loader (§12.2) and the declarative runtime (§12.3) need a shared utility that walks a schema or spec dict, finds `$content_ref` keys, loads the referenced files relative to the package root, and substitutes the content in place. Build this first — it is small and everything else depends on it.

#### 12.2 Node manifest loader

Currently all nodes are hardcoded Python classes registered at startup. There is no mechanism to scan a `nodes/` directory, read `node.manifest.json` files, and register them as `NodeType` instances. Needed:

- Walk `nodes/*/node.manifest.json`; resolve `parameter_schema_ref` and run the `$content_ref` resolver on the schema
- For `python_class` executors: dynamically import the specified module and class
- For `declarative` executors: instantiate the appropriate runtime interpreter with the resolved spec

#### 12.3 Declarative executor runtime (`http_request_v1`)

No generic HTTP request node exists. The declarative track emits `http.spec.json` files that have nothing to run them. The runtime interpreter must:

- Resolve `$content_ref` sidecars in the spec
- Interpolate Jinja2 `{{ parameters.* }}` and `{{ credentials.* }}` expressions
- Make the HTTP call with the resolved method, URL, headers, and body
- Map the response to output `FlowItem` objects via `response_jmespath`

#### 12.4 Credential storage

Completely absent. No org-level credential store, no `credential_slots` binding, and no injection into the execution context. Most ported SaaS nodes are non-functional without this. Three layers are needed:

| Layer | What is needed |
|---|---|
| Storage | Org-scoped encrypted key-value store (e.g. `org_credentials` MongoDB collection, values encrypted at rest) |
| API | CRUD endpoints per org (`POST /orgs/{org}/credentials`, `GET`, `DELETE`) |
| Runtime | At execution time, resolve `credential_slots` for the current node and inject as `credentials.*` into the Jinja2 / expression context |

### Important — most nodes degrade without these

#### 12.5 Frontend parameter rendering gaps

The current frontend handles `string`, `number`, `boolean`, `enum` (select dropdown), `object`/`array` (Monaco editor), and code editors. Missing for n8n parity:

| n8n type | Gap | Interim fallback |
|---|---|---|
| `multiOptions` | Multi-select / checkbox list | Monaco JSON array editor |
| `collection` | Sub-form with add/remove rows | Monaco JSON object editor |
| `fixedCollection` | Keyed sub-object builder | Monaco JSON object editor |
| `notice` | Inline info/warning banner (display-only) | Omit |
| Conditional visibility | Fields shown/hidden based on another field's value | Show all fields unconditionally |

`multiOptions` → `array` of `enum` is the most common case and should be prioritized; the others can fall back to Monaco JSON initially.

#### 12.6 JSON Schema `default` propagation

The engine validates parameters against `parameter_schema` but does not apply `default` values when a parameter is omitted. n8n nodes rely heavily on defaults, particularly `hidden` parameters that carry routing metadata. The engine should apply JSON Schema defaults before calling `execute()`.

### Toolchain — needed to generate the packages

#### 12.7 `tools/dump_n8n_nodes.js`

The Node.js shim that requires compiled n8n dist and dumps `.description` as JSONL (see §2). Does not exist yet; without it the converter has no input.

#### 12.8 `tools/port_n8n_nodes.py`

The Python converter that reads the JSONL dump and emits node packages under `nodes/` (see §3–§8). Does not exist yet.

### Recommended build order

```
1. $content_ref resolver utility          (small; needed by everything below)
2. Node manifest loader                   (foundation for the whole system)
3. http_request_v1 runtime               (enables declarative track)
4. Credential storage + API              (enables real integrations)
5. Credential injection in execution     (connects storage to runtime)
6. dump_n8n_nodes.js + port_n8n_nodes.py (the porting toolchain)
7. Frontend: multiOptions rendering      (most common missing UI type)
8. JSON Schema default propagation       (correctness for many nodes)
```

Items 1–3 are pure backend and can proceed in parallel with 4–5. The toolchain (6) can start as soon as the loader (2) works end to end with a single manually authored example node.
