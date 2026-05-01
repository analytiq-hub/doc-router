# DocRouter node format: JSON manifest + sidecars

This document specifies a **file-based** description of flow node types that DocRouter (and tooling such as codegen or import from n8n) can consume. Goals:

- Keep a **canonical JSON** artifact that is strict, diff-friendly, and easy to validate in CI.
- Avoid huge inline strings (templates, payloads, JMESPath, SQL) inside that JSON by using **sidecar files**.
- Align with the runtime **`NodeType` protocol** ([`packages/python/analytiq_data/flows/node_registry.py`](../packages/python/analytiq_data/flows/node_registry.py)): palette metadata, **`parameter_schema`** (JSON Schema), ports, **`execute`** behavior binding.

Relationship to broader interop goals: see [`flows_workflow_interop.md`](./flows_workflow_interop.md). For n8n’s `*.node.ts` shape contrast, see the appendix in [`n8n_nodes.md`](./n8n_nodes.md).

---

## 1. Packaging model

A **node package** is a **directory** whose name SHOULD be `snake_case` and equal to the node’s **`key`** segment after the dot (see **identity** below), or another stable folder slug with `key` set explicitly in the manifest.

Suggested layout:

```text
nodes/
└── my_integration/
    ├── node.manifest.json      # required: canonical descriptor
    ├── parameter.schema.json    # optional: sidecar JSON Schema for parameters
    ├── templates/               # optional: opaque text blobs referenced by manifest
    │   └── request_body.tpl.txt
    ├── fixtures/                # optional: example parameter sets for tests/docs (not loaded at runtime)
    │   └── example_minimal.json
    └── README.md                # optional: human prose (ignored by loaders)
```

**Rules:**

- **`node.manifest.json`** is the only file the loader MUST open first.
- Every other file is referenced **by relative path from the manifest’s directory** (the package root). Paths use POSIX `/` separators in JSON strings.
- No path may escape the package root (`..` segments are forbidden in references).

---

## 2. Identity and versioning

| Field | Meaning |
|--------|--------|
| **`schema`** | URI of the manifest JSON Schema (`docrouter.ai/flow-node-manifest/v1` or similar pegged revision). Loaded by validators only. |
| **`key`** | Stable string identifier registered in the engine, e.g. `docrouter.llm_extract`, `flows.http_request`. Matches Python `NodeType.key`. |
| **`manifest_version`** | Integer for **this file format**. Bump when mandatory fields or semantics change. |
| **`type_version`** | Integer for **parameter / behavior contract** of this node definition. Equivalent in spirit to n8n **`typeVersion`**. Workflow instances store **`type`** + **`parameters`** only; **`type_version`** is resolved via the manifest at registration/import time unless you duplicate it per instance in the revision (product choice). |

**Recommended `key` pattern:** dotted namespace (`product.area.name`), lowercase, ASCII alphanumerics and dots/hyphens/underscores.

---

## 3. Palette and port metadata (maps to `NodeType`)

These fields mirror today’s registry surface so a loader can synthesize **`NodeType`** metadata or populate `GET …/flows/node-types` payloads without importing Python:

| Manifest field | `NodeType` field |
|----------------|------------------|
| `label` | `label` |
| `description` | `description` |
| `category` | `category` |
| `is_trigger` | `is_trigger` |
| `is_merge` | `is_merge` |
| `min_inputs`, `max_inputs` | same |
| `outputs` | same |
| `output_labels` | same |
| `icon_key` | `icon_key` (nullable string) |

**Execution hint** (today often a class attribute in Python):

| Field | Meaning |
|--------|--------|
| `batch_execute_inputs` | Boolean; when true, runtime invokes `execute` once per schedule step with full item lists per slot (matches `FlowsCodeNode`). Default `false`. |

---

## 4. Parameter schema: inline vs sidecar

Runtime validation uses **`parameter_schema`** as a **`dict`** compatible with **`jsonschema`** (currently Draft 7 in [`packages/python/analytiq_data/flows/engine.py`](../packages/python/analytiq_data/flows/engine.py)).

### 4.1 Inline

```json
{
  "parameter_schema": {
    "type": "object",
    "properties": {
      "prompt_id": { "type": "string", "minLength": 1 }
    },
    "required": ["prompt_id"],
    "additionalProperties": false
  }
}
```

### 4.2 Sidecar by reference

Prefer a separate file for large schemas, generated schemas, or shared fragments:

```json
{
  "parameter_schema_ref": "parameter.schema.json"
}
```

**Resolution:** Resolve `parameter_schema_ref` relative to the package root and load JSON. The resolved document MUST be a valid JSON Schema object. Loaders SHOULD reject documents that declare **both** `parameter_schema` and `parameter_schema_ref`.

### 4.3 Content references inside the schema (`$content_ref`)

Parameters holding **large or line-sensitive** content (templates, scripts, SQL, HTML, JSON payloads) can reference a sidecar file directly from the schema node using the `$content_ref` extension keyword. JSON Schema validators (Draft 7) skip unknown `$`-prefixed keywords, so no pre-processing step is needed before validation.

```json
{
  “type”: “object”,
  “properties”: {
    “body_template”: {
      “type”: “string”,
      “$content_ref”: “templates/request_body.tpl.txt”
    },
    “processor_code”: {
      “type”: “string”,
      “$content_ref”: “scripts/processor.py”
    },
    “config”: {
      “type”: “object”,
      “$content_ref”: “defaults/config.json”
    },
    “allowed_tags”: {
      “type”: “array”,
      “$content_ref”: “defaults/tags.json”
    }
  }
}
```

**Rules:**

- Valid on nodes whose `type` is `string`, `object`, or `array`. Has no meaning on `number`, `integer`, or `boolean` nodes.
- Path is **package-relative** from the manifest directory. `..` segments are forbidden (same root confinement rule as `parameter_schema_ref`).
- When the file extension is ambiguous, add **`$content_media_type`** on the same node:

```json
{
  “type”: “string”,
  “$content_ref”: “scripts/processor”,
  “$content_media_type”: “text/x-python”
}
```

- May appear at **any depth** in the schema tree, including nested object properties.
- **Authoring/tooling only:** tells editors and import tooling (e.g. n8n → DocRouter) where to find a default value. Does **not** affect the runtime parameter contract — parameters are always plain strings/objects/arrays in the saved workflow.
- Do **not** place `$content_ref` on a node that also carries a JSON Schema `$ref` (schema composition reference) — the semantics conflict.

**Schema `$ref` composition** (distinct from `$content_ref`): `parameter.schema.json` MAY use standard JSON Schema `$ref` to reference sibling schema fragments under the package (e.g. `”$ref”: “defs/common.json”`). Loaders that only support inlined schemas can run a `$ref`-flattening step in CI to emit a single bundle.

---

## 5. Sidecar file references

Sidecar file references for parameter defaults and fixtures are declared using **`$content_ref`** (and optionally **`$content_media_type`**) directly on schema nodes in **`parameter.schema.json`** — see §4.3.

The manifest-level `sidecars` block described in earlier drafts of this spec is superseded by the `$content_ref` mechanism and MUST NOT be used in new packages.

---

## 6. Behavior binding (`executor`)

The manifest describes **what runs** without embedding Python or TypeScript. Two complementary strategies:

### 6.1 `executor_kind: "python_class"`

Points at an implementation already shipped in **`analytiq_data`**:

```json
{
  "executor": {
    "kind": "python_class",
    "import": "analytiq_data.docrouter_flows.nodes.llm_node",
    "class": "DocRouterLlmExtractNode"
  }
}
```

Registration (at app startup or via a discovery plugin) **`import`**s the module and **`register()`**s an instance of **`class`**. The manifest then serves as **documentation + validation** that the Python class stays in sync with **`parameter_schema`**; CI checks can assert parity.

### 6.2 `executor_kind: "declarative"`

For nodes where behavior is entirely data-driven — HTTP integrations, transforms, static outputs — without a new Python class per vendor.

#### How it works

Two JSON documents govern a declarative node at execution time:

| Document | Purpose | Who reads it |
|---|---|---|
| `parameter.schema.json` | What the user configures in the UI | Form renderer, runtime validator |
| spec (`spec_ref` target) | How the runtime executes, using those parameters | The runtime interpreter (Python) |

The spec may reference `parameters.*` and `credentials.*` via Jinja2 `{{ }}` expressions (e.g. `"{{ parameters.channel }}"`). The interpreter resolves these before executing.

#### Runtime registry

Keep the set small. Each runtime is one Python class implementing a fixed interpreter contract:

| `runtime` | Behavior |
|---|---|
| `http_request_v1` | Makes an HTTP request; maps the response to output items |
| `jq_transform_v1` | Applies a jq expression to input items |
| `template_render_v1` | Renders a Jinja2 template over item data; emits strings |
| `static_output_v1` | Emits a fixed JSON payload (constants, seed data, stubs) |

Per-runtime JSON Schemas live under `schemas/runtimes/` (e.g. `schemas/runtimes/http_request_v1.schema.json`) and are used by the §8 validation pipeline.

#### `$content_ref` inside specs

`$content_ref` works inside spec files by the same package-relative rules as inside parameter schemas — the runtime loader resolves them before executing. This keeps large bodies, scripts, and templates out of JSON strings.

#### Example 1 — HTTP integration (`http_request_v1`)

**`node.manifest.json`:**
```json
{
  "key": "integrations.slack_post_message",
  "label": "Slack: Post Message",
  "executor": {
    "kind": "declarative",
    "runtime": "http_request_v1",
    "spec_ref": "http.spec.json"
  },
  "parameter_schema_ref": "parameter.schema.json",
  "credential_slots": [
    { "slot": "slackToken", "label": "Slack Bot Token", "required": true }
  ]
}
```

**`parameter.schema.json`:**
```json
{
  "type": "object",
  "properties": {
    "channel": { "type": "string" },
    "message": { "type": "string" }
  },
  "required": ["channel", "message"],
  "additionalProperties": false
}
```

**`http.spec.json`:**
```json
{
  "method": "POST",
  "url": "https://slack.com/api/chat.postMessage",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer {{ credentials.slackToken }}"
  },
  "body": {
    "$content_ref": "templates/post_message.json.tpl",
    "$content_media_type": "application/json"
  },
  "response_jmespath": "ok"
}
```

**`templates/post_message.json.tpl`:**
```
{
  "channel": "{{ parameters.channel }}",
  "text":    "{{ parameters.message }}"
}
```

#### Example 2 — Data transform (`jq_transform_v1`)

**`node.manifest.json`:**
```json
{
  "key": "flows.extract_line_items",
  "label": "Extract Line Items",
  "executor": {
    "kind": "declarative",
    "runtime": "jq_transform_v1",
    "spec_ref": "transform.spec.json"
  },
  "parameter_schema_ref": "parameter.schema.json"
}
```

**`parameter.schema.json`:**
```json
{
  "type": "object",
  "properties": {
    "include_tax": { "type": "boolean", "default": false }
  },
  "additionalProperties": false
}
```

**`transform.spec.json`:**
```json
{
  "expression": { "$content_ref": "transform.jq" },
  "input_slot": 0
}
```

**`transform.jq`:**
```
.items[] | {
  id:    .id,
  name:  .name,
  total: (if $parameters.include_tax then .price * .qty * 1.2 else .price * .qty end)
}
```

#### Example 3 — Static output (`static_output_v1`)

Useful for injecting constants or seed data into a flow without any Python:

**`node.manifest.json`:**
```json
{
  "key": "flows.seed_config",
  "label": "Seed Config",
  "is_trigger": true,
  "min_inputs": 0,
  "max_inputs": 0,
  "outputs": 1,
  "output_labels": ["output"],
  "executor": {
    "kind": "declarative",
    "runtime": "static_output_v1",
    "spec_ref": "output.spec.json"
  }
}
```

**`output.spec.json`:**
```json
{
  "items": { "$content_ref": "defaults/config.json" }
}
```

### 6.3 `executor_kind: "composite"`

(Optional) **`steps`** array referencing other declarative specs or builtins—only worth defining once you need it;otherwise start with **`python_class`** + one **`declarative`** runner.

---

## 7. Credentials and secrets

Do **not** put secrets in the manifest. Prefer:

```json
{
  "credential_slots": [
    {
      "slot": "apiCredential",
      "label": "API connection",
      "required": true,
      "docrouter_binding": "organization_credential_kind:slack_api"
    }
  ]
}
```

**`credential_slots`** are **declarative** hints for UX and migration. Wiring to DocRouter’s real credential storage is product-specific until a single org-level credential type exists; until then loaders MAY ignore **`docrouter_binding`** or map it in an import adapter.

---

## 8. Validation pipeline (recommended)

1. **Structural:** Validate **`node.manifest.json`** against **`schemas/flow-node-manifest-v1.json`** (committed in-repo beside the loader).
2. **References:** Resolve **`parameter_schema_ref`**, **`spec_ref`**, and all **`$content_ref`** paths (in both the parameter schema and any spec files); ensure no traversal outside the package root.
3. **`parameter.schema.json`:** Valid JSON Schema; optional CI step to **`jsonschema` validate** **`fixtures/**/*.json`**.
4. **`executor`**:
   - For **`python_class`**, optionally **`python -c`** import smoke test or static analysis listing.
   - For **`declarative`**, validate **`spec_ref`** against the matching per-runtime schema under **`schemas/runtimes/`** (e.g. `schemas/runtimes/http_request_v1.schema.json`).

---

## 9. Manifest JSON Schema (informal outline)

The formal schema should be committed as **`schemas/flow-node-manifest-v1.json`**. Informally, top-level properties are:

| Property | Required | Notes |
|----------|----------|--------|
| `schema` | yes | Manifest schema URI. |
| `manifest_version` | yes | Integer. |
| `key` | yes | Engine registration key. |
| `type_version` | yes | Integer. |
| `label`, `description`, `category` | yes | Strings. |
| `is_trigger`, `is_merge` | yes | Booleans. |
| `min_inputs`, `max_inputs`, `outputs` | yes | Integers; `max_inputs` null = unlimited (encode as JSON `null` if you support it, or use `-1` with explicit convention). |
| `output_labels` | yes | Array of strings, length = `outputs`. |
| `icon_key` | no | String or null. |
| `batch_execute_inputs` | no | Boolean, default false. |
| `parameter_schema` | one of | Object; mutually exclusive with `parameter_schema_ref`. |
| `parameter_schema_ref` | one of | String path. |
| `executor` | yes | Object with `kind` discriminator. |
| `credential_slots` | no | Array. |

---

## 10. Minimal example (`node.manifest.json`)

```json
{
  "schema": "https://docrouter.example/schemas/flow-node-manifest/v1.json",
  "manifest_version": 1,
  "key": "example.echo",
  "type_version": 1,
  "label": "Echo",
  "description": "Passes input through with optional prefix.",
  "category": "Example",
  "is_trigger": false,
  "is_merge": false,
  "min_inputs": 1,
  "max_inputs": 1,
  "outputs": 1,
  "output_labels": ["output"],
  "icon_key": null,
  "parameter_schema_ref": "parameter.schema.json",
  "executor": {
    "kind": "python_class",
    "import": "analytiq_data.flows.nodes.example_echo",
    "class": "ExampleEchoNode"
  }
}
```

**`parameter.schema.json`:**

```json
{
  "type": "object",
  "properties": {
    "prefix": { "type": "string", "default": "" }
  },
  "additionalProperties": false
}
```

---

## 11. Evolution

- Bump **`manifest_version`** when loaders must understand new mandatory keys or incompatible reference rules.
- Bump **`type_version`** when **`parameter_schema`** or **`executor`** semantics change for the same **`key`**; workflows may pin **`type_version`** on instances if you add that field to [`FlowRevision`](../packages/python/app/routes/flows.py) semantics later.
- Prefer adding **optional** manifest keys and **new `executor.kind` / `declarative.runtime`** values before breaking existing packages.

---

## 12. Summary

| Artifact | Role |
|----------|------|
| **`node.manifest.json`** | Canonical node descriptor: identity, ports, **`parameter_schema`** pointer or inline, **`executor`** binding. |
| **`parameter.schema.json`** | Optional sidecar JSON Schema for parameters. MAY use `$content_ref` / `$content_media_type` on any `string`, `object`, or `array` node to point at a sidecar file, and MAY use JSON Schema `$ref` for schema fragment composition. |
| **`templates/*`, scripts, declarative specs** | Sidecar blobs or structured specs referenced by `$content_ref` (in the schema) or `spec_ref` (in the executor) instead of inlined strings. |

This split keeps CI validation simple (**everything is JSON on the wire**) while preserving **human-friendly** authoring for large payloads and a clear bridge to **`NodeType`** at runtime.

