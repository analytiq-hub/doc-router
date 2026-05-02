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

Do not parse TypeScript AST — it is fragile across upstream releases. Instead **require() the compiled `*.node.js` modules** from the built repo. Implemented as **`tools/dump_nodes.js`**: mandatory **`--upstream-root`**, discovery via repeatable **`--subdir REL`** paths *or* the **`FLOW_DUMP_SUBDIRS`** environment variable (**`:`**-separated relative paths under the upstream root).

Example (paths depend on how the sibling monorepo lays out packages):

```bash
FLOW_DUMP_SUBDIRS='packages/nodes-base/dist/nodes:packages/other-vendor-ai/dist/nodes' \
  node tools/dump_nodes.js --upstream-root ../upstream_nodes > tools/flow_node_dump.jsonl
```

`make flow-node-dump` passes **`FLOW_DUMP_SUBDIRS`** to **`dump_nodes.js`**. **`UPSTREAM_NODES_ROOT`** defaults to **`../n8n`** relative to the DocRouter makefile directory (`abspath` in the makefile), so the checkout can sit beside a sibling **`n8n`** tree without exporting env vars. **`make flow-node-port`** errors if zero packages are emitted unless **`tools/port_nodes.py --allow-empty`**. **`tools/flow_node_dump.jsonl`** updates only after a successful dump (write to temp file, then **`mv`**).

### Upstream toolchain and build (required)

The sibling monorepo is **pnpm-based**. If `pnpm` is missing, install it (for example `corepack enable && corepack prepare pnpm@latest --activate`, or `npm install -g pnpm`, or an OS package). From the **upstream repository root**, run **`pnpm install`**, then **`pnpm build`** so compiled artifacts exist (including **`packages/nodes-base/dist/nodes/**/*.node.js`** and any other trees you list in **`FLOW_DUMP_SUBDIRS`**). Without that, **`make flow-node-dump`** fails (**`dump_nodes.js`** exits nonzero: missing upstream directory, zero `*.node.js` matches, etc.) and **`tools/flow_node_dump.jsonl`** is left unchanged (atomic rename from a temp file).

### Verifying the JSONL before `flow-node-port`

Open **`tools/flow_node_dump.jsonl`** and spot-check important integrations (e.g. Slack, Airtable). A **healthy** row includes a full **`description.properties`** array (dozens of fields for large SaaS nodes). A **degraded** row often has only metadata such as **`displayName`**, **`name`**, **`defaultVersion`**, **`icon`**, **`group`** — and **no** (or empty) **`properties`**.

**Why this happens — versioned nodes:** many upstream nodes use a **thin base** `description` on the class and move the real UI and routing into **`nodeVersions`**: a map of version keys to **sub-constructors**, each with a complete `description`. **`tools/dump_nodes.js`** tries **`new SubCtor()`** for each entry. If instantiation **throws** (missing context, side effects, or environment), **no** version line is emitted for that sub-class; the tool then falls back to a single JSONL record using the **base** `description` only. **`tools/port_nodes.py`** correctly turns that into **schema-valid** packages with **empty `parameter.schema.json`**, missing **`credential_slots`**, and a **`python_class`** stub — which is **not** a faithful port.

**What to do:** fix or extend **`tools/dump_nodes.js`** (more robust construction, alternative extraction from compiled metadata, logging of `tryInstantiate` failures) and **re-dump**; optionally hand-merge rows for critical nodes; then re-run **`make flow-node-port`**.

**Declarative HTTP count:** even with full descriptions, **`http.spec.json`** is emitted only when the converter can extract a usable **`routing.request`**. Expect **most** packages to remain **`python_class`** until heuristics improve or nodes are ported by hand.

**`--validate`:** `python tools/port_nodes.py … --validate` checks **JSON Schema** shape for manifests (and **`http.spec.json`** when present). It does **not** prove behavioral parity with upstream or that the dump contained full **`properties`**.

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
| `name` | `key` | Prefix with integration namespace (`ext.` in generated output, e.g. `ext.slack`) |
| `description` | `description` | |
| `group[0]` | `category` | e.g. `"output"`, `"transform"` |
| `defaultVersion` \| `version` | `type_version` | Use `defaultVersion` when present; for arrays take the max |
| `inputs` | `min_inputs`, `max_inputs` | Count `Main` entries; `0` inputs → `is_trigger: true` |
| `outputs` | `outputs`, `output_labels` | Count `Main` outputs; use `outputNames` for labels if present |
| `trigger`/`poll`/`webhook` present | `is_trigger: true` | |
| `credentials[*]` | `credential_slots` | See §7 |
| `icon` | `icon_key` | Strip `file:` prefix; store path relative to package root |
| `usableAsTool` | (future) | Skip for now |

**`key` convention:** `ext.<integration>` (generated); adjust if you rename the namespace during import wiring.

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

### 7.1 n8n credentials are separate from nodes

In n8n, integration nodes only **reference** credential types:

- **`INodeTypeDescription.credentials[]`** lists allowed types (`name`, `displayName`, `required`, optional `testedBy`, etc.). The **`name`** string (e.g. `slackApi`) keys into a **global credential type registry**.
- The **fields** for that type (API token, OAuth client id, host, …) live in **credential definition modules** (typically `packages/nodes-base/credentials/*.credentials.ts`, compiled under `dist/`), not inside the node’s `description` JSON.
- At **workflow runtime**, the workflow stores which **saved credential instance** (id) is attached to each node slot; secrets are decrypted only inside execution.

So the node dump (`flow_node_dump.jsonl`) carries **which slots exist and their labels**, but **not** the full secret schema or property list for each type unless we add a **second extraction path** from compiled credential modules (see §7.3).

### 7.2 Target DocRouter model (aligned with manifests)

DocRouter should mirror the same separation: **kind** (type) vs **instance** (org-owned secret) vs **binding** (which instance fills which slot on a flow node). This matches the declarative hints already sketched in [`docrouter_nodes.md`](./docrouter_nodes.md) §7.

| Concept | Role |
|---|---|
| **Credential kind** | Global catalog entry: stable key (see `docrouter_binding`), JSON Schema for secret fields + non-secret options, display metadata, optional auth mode (OAuth vs API key). |
| **Organization credential** | One stored instance per org: references a **kind**, user-visible name, encrypted payload validated against the kind schema. |
| **Flow node binding** | Per node, map **slot name** → saved credential id (or future inline ref), analogous to n8n’s node `credentials` map in workflow JSON. |
| **Runtime context** | Resolved secrets exposed to **`http_request_v1`** / expressions as **`credentials.*`** (flat or nested per interpreter rules — decide once and document). |

Manifest **`credential_slots`** already carries **`slot`**, **`label`**, **`required`**, and **`docrouter_binding`** (today `organization_credential_kind:<n8n_type_name>`). The **kind key** should stay **stable** and, where possible, **equal to n8n’s credential type `name`** to simplify migration.

### 7.3 Phased plan: define credentials in DocRouter and map from n8n

| Phase | Scope | Status |
|---|---|---|
| **A — Slot references from nodes** | For each dumped node, emit **`credential_slots`** from `description.credentials` ([`map_credentials`](../packages/python/analytiq_data/flows/port/converter.py)). | **Done** in port |
| **B — Kind catalog from n8n** | New tooling (parallel to `dump_nodes.js`): load compiled **`*.credentials.js`** from the sibling repo (n8n places them under e.g. `packages/nodes-base/dist/` and `packages/nodes-base/dist/credentials/` after `pnpm build` — layout can change by version; discover both). Extract each credential type’s **name**, **displayName**, and **properties** (`INodeProperties`-style). Emit a machine-readable catalog (e.g. JSONL or one JSON file per kind) and derive **JSON Schema** for the stored secret payload (reuse the same mapping ideas as §5 for parameter types). Optional: dedupe by `name` across packages. | **Not started** |
| **C — DocRouter kind registry** | Check in or generate **`schemas/credential-kinds/<key>.json`** (or a single registry index). Support **aliases** if DocRouter renames a kind. Wire **`docrouter_binding`** to this registry. | **Not started** |
| **D — Storage + API** | Org-scoped encrypted store + CRUD; see §12.4. | **Not started** |
| **E — Flow revision: bindings** | Extend stored flow nodes so each integration node can record **`credentials: { "<slot>": "<org_credential_id>" }`** (or equivalent), validated against that node type’s **`credential_slots`**. | **Not started** |
| **F — Frontend** | Per slot, credential picker filtered by **kind** from **`docrouter_binding`**. | **Not started** |
| **G — Runtime injection** | Before Jinja / HTTP: resolve bindings → decrypt → build **`credentials`** dict for the interpreter; match keys expected by **`http.spec.json`** (see §7.4). | **Not started** |

**Recommended build order:** **B → C** (so kinds exist before bulk UI), then **D**, then **E + G** with **F** in parallel. Phase **A** already unblocks listing slots on ported nodes; phases **B–G** unblock **real** SaaS calls.

### 7.4 Mapping pitfalls (information loss)

- **Without phase B**, DocRouter knows **slot ids and labels** but not the **field list** for the OAuth/API form — users cannot safely create instances without manual docs or hand-authored kind schemas.
- **Jinja keys in `http.spec.json`** (e.g. `{{ credentials.accessToken }}`) follow **n8n’s decrypted credential object shape**, which comes from the **credential type**, not from the node dump. The kind catalog (phase B) plus a small **normalization rule** (flatten nested objects vs dot keys) must align generated specs with resolved **`credentials.*`** at runtime.
- **OAuth / refresh**: n8n credential types may include **automations** DocRouter does not port automatically; treat OAuth as “manual parity” until a DocRouter token refresh story exists.

---

## 8. Output layout

One directory per ported node under `nodes/`:

```
nodes/
└── ext_slack_post_message/
    ├── node.manifest.json       ← generated
    ├── parameter.schema.json    ← generated
    ├── http.spec.json           ← generated (declarative track only)
    └── templates/
        └── body.json.tpl        ← generated if body is large
```

The CLI defaults to **`packages/python/analytiq_data/flows/port/generated_nodes/`** (`--out`) so stubs are importable as `analytiq_data.flows.port.generated_nodes.<slug>.node_impl`. Pass `--out` elsewhere if needed and adjust **`executor.import`** accordingly.

For `python_class` stubs, also emit a skeleton Python file:

```
nodes/
└── ext_postgres_query/
    ├── node.manifest.json
    ├── parameter.schema.json
    └── node_impl.py             ← stub; behavior must be ported by hand
```

**`node_impl.py` stub template:** (duck-types the **`NodeType`** protocol — do not subclass it; match fields and method signatures like existing nodes, e.g. [`packages/python/analytiq_data/flows/nodes/code.py`](../packages/python/analytiq_data/flows/nodes/code.py).)

```python
from typing import Any

import analytiq_data as ad


class ExtPostgresQueryNode:
    """Upstream Postgres node — stub."""

    key = "ext.postgres_query"
    label = "Postgres"
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
        raise NotImplementedError("ext.postgres_query: Python stub not implemented")
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
| Versioned nodes (`VersionedNodeType`, `nodeVersions`) | Multiple `typeVersion` slices; sub-constructor `description` is the source of truth | If sub-constructors fail to instantiate in **`dump_nodes.js`**, JSONL contains only the **base** shell → empty parameter schema in DocRouter. Fix the dumper / environment; re-dump per version key you need; bump **`type_version`** from **`integration_type_version_key`** when present |
| Expression URLs (`=…` prefix on `routing.request.url`) | Leading `=` is stripped in **`http_spec.py`**; remaining string may still be upstream expression syntax | Treat as manual: Jinja/templates in **`http.spec.json`** or **`python_class`** |
| Incomplete declarative extraction | Nodes with `routing` / `requestDefaults` that omit a simple `routing.request` dict fall back to **`python_class`** | Converter prints stderr warnings per slug; inspect upstream `properties` trees |

---

## 10. Validation after generation

**Schema vs semantics:** validating manifests guarantees **syntax** compatible with **`schemas/`** — not that each node matches upstream capabilities. Combine this with **JSONL spot-checks** (§2, “Verifying the JSONL before `flow-node-port`”) so versioned nodes did not collapse to empty **`properties`**.

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
    for path in sorted(glob.glob("packages/python/analytiq_data/flows/port/generated_nodes/*/node.manifest.json")):
        with open(path) as f:
            mv.validate(json.load(f))
        print(path, "ok")

main()
PY

# Parameter schemas (Draft 7 meta-schema check only)
for f in packages/python/analytiq_data/flows/port/generated_nodes/*/parameter.schema.json; do
  python -c "import jsonschema, json; jsonschema.Draft7Validator.check_schema(json.load(open('$f')))"
done

# Declarative specs (when present)
python <<'PY'
import json, glob, jsonschema
with open("schemas/runtimes/http_request_v1.schema.json") as f:
    spec_schema = json.load(f)
jsonschema.Draft7Validator.check_schema(spec_schema)
sv = jsonschema.Draft7Validator(spec_schema)
for path in sorted(glob.glob("packages/python/analytiq_data/flows/port/generated_nodes/*/http.spec.json")):
    with open(path) as f:
        sv.validate(json.load(f))
    print(path, "ok")
PY
```

Alternatively: `check-jsonschema --schemafile schemas/flow-node-manifest-v1.json packages/python/analytiq_data/flows/port/generated_nodes/*/node.manifest.json` (and similarly for **`http.spec.json`**). Add this as a CI step when the dump or converter changes.

---

## 11. Suggested implementation order

**Packaging track (mostly done — dump quality still iterative)**

1. **Upstream:** install **pnpm**, **`pnpm install`** + **`pnpm build`** in the sibling clone so **`dist/**/*.node.js`** exists (§2).
2. ~~**`make flow-node-dump`** → **`tools/flow_node_dump.jsonl`**~~ — **Done** mechanically (§2, §12.7); verify JSONL for **versioned** nodes before trusting bulk output (§2).
3. ~~**`make flow-node-port`** / **`python tools/port_nodes.py --validate`**~~ — **Done** (§12.8).
4. **Ongoing:** run **`pytest packages/python/tests/test_flow_port_converter.py`** when changing the converter or **`http_spec.py`**; re-dump when upstream **`*.node.js`** changes; tighten **`dump_nodes.js`** when **`nodeVersions` instantiation** fails for important nodes.

**To make ported nodes executable**

5. Build **§12.1 → §12.4** in order (resolver → loader → **`http_request_v1`** → credentials) — see **Status** at the **end** of this document for a checklist and recommended order.
6. Expand the generated catalogue; prioritize implementing high-value **`python_class`** stubs manually where declarative mapping is insufficient.
7. Improve declarative **`http.spec.json`** generation using real failures (multi-operation routing, **`response_set`**, templated bodies).

---

## 12. DocRouter prerequisites (runtime + product gaps)

What follows blocks **executing** flows that use generated packages. **§12.7–§12.8** are the **authoring toolchain** (already implemented).

### Blockers — nothing works without these

#### 12.1 `$content_ref` resolver utility

**Implemented.** [`analytiq_data.flows.content_ref.resolve_content_refs`](../packages/python/analytiq_data/flows/content_ref.py) walks dict/list trees, resolves **package-relative** paths (no `..`), and inlines **bare** `{"$content_ref": ...}` objects plus **JSON Schema-style** nodes with `type` in `string|object|array` and `$content_ref` (materializes `default`). JSON sidecars are parsed when unambiguous; files containing Jinja (`{{` / `{%`) stay as text for a later interpolation pass. Tests: [`packages/python/tests/test_content_ref.py`](../packages/python/tests/test_content_ref.py).

The manifest loader (§12.2) and declarative runtime (§12.3) should call this helper after loading `parameter.schema.json` / `http.spec.json` from disk (**not** wired in yet — library only).

#### 12.2 Node manifest loader

Currently all nodes are hardcoded Python classes registered at startup. There is no mechanism to scan a `nodes/` directory, read `node.manifest.json` files, and register them as `NodeType` instances. Needed:

- Walk `nodes/*/node.manifest.json`; resolve `parameter_schema_ref` and run **`analytiq_data.flows.content_ref.resolve_content_refs`** on the loaded parameter schema
- For `python_class` executors: dynamically import the specified module and class
- For `declarative` executors: instantiate the appropriate runtime interpreter with the resolved spec

#### 12.3 Declarative executor runtime (`http_request_v1`)

No generic HTTP request node exists. The declarative track emits `http.spec.json` files that have nothing to run them. The runtime interpreter must:

- Resolve `$content_ref` sidecars in the spec (**`resolve_content_refs`**, §12.1)
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

Product-facing **phasing** (kind catalog from n8n, flow bindings, UI) is spelled out in **§7.3**; implement storage/API/runtime here in tandem with those steps.

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

#### 12.7 `tools/dump_nodes.js`

**Implemented** with known limits. Walks compiled `*.node.js` modules, **`require()`**s each file, discovers constructors, **`tryInstantiate`**, and emits JSONL (`source`, `description`, optional `integration_type_version_key`). For **`nodeVersions`**, it emits one record per successfully instantiated sub-class; **failed** `new SubCtor()` attempts are skipped silently today, which can leave only the **base** `description` for that file (see §2). Run **`make flow-node-dump`** (makefile **`UPSTREAM_NODES_ROOT`** / **`FLOW_DUMP_SUBDIRS`**) or §2.

#### 12.8 `packages/python/analytiq_data/flows/port/` + `tools/port_nodes.py`

**Implemented.** Python converter reads the JSONL dump and writes packages under `analytiq_data/flows/port/generated_nodes/<slug>/` (`node.manifest.json`, `parameter.schema.json`, optional `http.spec.json`, `node_impl.py` stubs). CLI: **`python tools/port_nodes.py [jsonl] --validate`**; **`make flow-node-port`**.

### Recommended runtime build order

Shortcut list — full **Status** table and notes are at the **end** of this document §13.

```
✓ Packaging: dump_nodes.js + analytiq_data.flows.port + port_nodes.py  (DONE — §12.7–§12.8)
✓ $content_ref resolver (analytiq_data.flows.content_ref) — §12.1; wire into loader/runtime next

1. Node manifest loader
2. http_request_v1 runtime
3. Credential storage + API + injection at execute time
Then: JSON Schema defaults (§12.6), richer parameter UI (§12.5)
```

---

## 13. Status (what we built vs what runs)

| Area | State | Where |
|------|--------|--------|
| **JSONL dump** from compiled `*.node.js` | **Done** (quality depends on build + `nodeVersions` instantiation) | [`tools/dump_nodes.js`](../tools/dump_nodes.js), `make flow-node-dump` — see §2 |
| **Full `description` for versioned nodes** (`nodeVersions` sub-constructors) | **Partial / fragile** | Silent skip when **`new SubCtor()`** fails → empty **`properties`** in JSONL until dumper improves |
| **Package generator** (manifest, parameter schema, optional `http.spec.json`, `python_class` stubs) | **Done** | [`analytiq_data/flows/port/`](../packages/python/analytiq_data/flows/port/), [`tools/port_nodes.py`](../tools/port_nodes.py), `make flow-node-port` |
| **Manifest / http spec JSON Schemas (stubs)** | **Done** | [`schemas/flow-node-manifest-v1.json`](../schemas/flow-node-manifest-v1.json), [`schemas/runtimes/http_request_v1.schema.json`](../schemas/runtimes/http_request_v1.schema.json) |
| **Unit tests for the converter** | **Done** | [`packages/python/tests/test_flow_port_converter.py`](../packages/python/tests/test_flow_port_converter.py) — `pytest packages/python/tests/test_flow_port_converter.py` |
| **`$content_ref` resolution** (schema + spec) | **Done** (library; not wired into loader/runtime yet) | [`content_ref.py`](../packages/python/analytiq_data/flows/content_ref.py), [`test_content_ref.py`](../packages/python/tests/test_content_ref.py) — §12.1 |
| **Dynamic registration from `node.manifest.json`** | **Not started** | §12.2 — `NodeType`s are still hand-registered at startup |
| **`http_request_v1` executor at runtime** | **Not started** | §12.3 — emitted `http.spec.json` is inert until an interpreter exists |
| **Org credential store + runtime injection** | **Not started** | §12.4 |
| **JSON Schema `default` merge before `execute()`** | **Not started** | §12.6 |
| **Richer frontend for ported parameter shapes** | **Partial / gaps** | §12.5, §9 |

**Partial by design:** the converter classifies from **`description` only** (no inspection of imperative `execute()` in compiled JS yet). **`http.spec.json`** emission is **best-effort** (first usable `routing.request`, limited `postReceive` handling). Large catalogue output expects **review**, not guaranteed drop-in parity.

### What to build next (recommended order)

**Packaging fidelity (alongside runtime work):**

- Harden **`tools/dump_nodes.js`**: surface **`nodeVersions`** instantiation failures (stderr summary per file/version key), optionally stub dependencies or extract descriptions without constructing full upstream classes — so SaaS nodes do not degrade to empty **`properties`**.

Then **runtime**:

1. ~~**`$content_ref` resolver**~~ — **Done** (`analytiq_data.flows.content_ref`); **wire it** into the manifest loader and **`http_request_v1`** when those land.
2. **Manifest loader** — discover packages under `flows/port/generated_nodes/` (or configurable root), validate, register **`NodeType`** instances (`python_class` import + declarative wrapper); run **`resolve_content_refs`** on loaded schema and spec JSON.
3. **`http_request_v1` runtime** — HTTP client + Jinja2 for `parameters.*` / `credentials.*`, response shaping via `response_jmespath`; emit **`FlowItem`** outputs.
4. **Credentials** — persistence + API + **`credential_slots`** wiring into the execution context.
5. **Defaults + UI** — engine applies JSON Schema defaults before execute (§12.6); then **`multiOptions`** / collection editors (§12.5) as needed.

Steps **2–3** (plus wiring **`resolve_content_refs`**) unlock a **declarative** generated node end-to-end without hand-copied Python; step **4** unlocks typical SaaS integrations.

Packaging was implemented **early** so manifests accumulate under `schemas/` validation and **`test_flow_port_converter.py`**; loader + **`http_request_v1`** (**items 2–3** above) are still required before flows can execute generated declarative nodes.
