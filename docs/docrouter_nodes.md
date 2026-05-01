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

### 4.3 Optional future: `$ref` inside schema

Sidecar **`parameter.schema.json`** MAY use **`$ref`** to sibling files under the package (e.g. `defs/common.json`). Loaders that only support inlined schemas can run a **`$ref` flattening** step in CI to emit a single bundle.

---

## 5. Sidecar text blobs (`content_ref`)

Some parameters are meant to hold **large or line-sensitive** text (HTTP body templates, scripts, SQL). Embedded JSON strings are valid but painful to diff and edit.

**Convention:** in **`parameter.schema.json`**, such properties stay typed as **`{ "type": "string" }`** (or `string` with `contentEncoding` hints if you adopt a stricter convention). At **authoring time**, optional metadata in the **manifest** (not inside the JSON Schema draft spec) describes **defaults** or **fixtures** pointing at files:

```json
{
  "sidecars": {
    "parameters": {
      "body_template": {
        "content_ref": "templates/request_body.tpl.txt",
        "media_type": "text/plain"
      }
    }
  }
}
```

Semantics:

- **`sidecars`** is **documentation / tooling only** unless the product explicitly adds a “load fixture into editor” feature. It does **not** change runtime JSON: run parameters are still plain strings once the workflow is saved.
- **`content_ref`** is a package-relative path; same root confinement rules as **`parameter_schema_ref`**.
- **`media_type`** is optional (e.g. `application/json` for pretty-printed JSON templates).

**Import tooling** (e.g. n8n → DocRouter) can use **`content_ref`** to map n8n multiline defaults into files and set workflow defaults to either the inlined string or a placeholder that tells the UI to open the sidecar path (product-specific).

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

For nodes where behavior is entirely data-driven (HTTP, JMESPath, static routing):

```json
{
  "executor": {
    "kind": "declarative",
    "runtime": "http_request_v1",
    "spec_ref": "http.spec.json"
  }
}
```

- **`runtime`** names a **small set** of interpreters implemented once in Python (e.g. `http_request_v1`, `jq_transform_v1`).
- **`spec_ref`** resolves to JSON consumed by that runtime. Large bodies again MAY use **`content_ref`** inside that spec pointing to **`templates/`**.

This path is ideal for translating **n8n-style declarative routing** into DocRouter without a new Python class per vendor.

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

1. **Structural:** Validate **`node.manifest.json`** against **`docrouter-flow-node-manifest-v1.json`** (publish this schema beside the loader or under `schemas/` in-repo).
2. **References:** Resolve **`parameter_schema_ref`**, **`spec_ref`**, and all **`content_ref`** paths; ensure no traversal outside the package root.
3. **`parameter.schema.json`:** Valid JSON Schema; optional CI step to **`jsonschema` validate** **`fixtures/**/*.json`**.
4. **`executor`**:
   - For **`python_class`**, optionally **`python -c`** import smoke test or static analysis listing.
   - For **`declarative`**, validate **`spec_ref`** against a per-runtime schema (e.g. `http_request_v1.schema.json`).

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
| `sidecars` | no | Object (see §5). |
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
| **`parameter.schema.json`** | Optional sidecar JSON Schema for parameters (and optional **`$ref` graph inside the package). |
| **`templates/*`, declarative specs** | Sidecar blobs or structured specs referenced by **`_ref`** fields instead of inlined strings. |

This split keeps CI validation simple (**everything is JSON on the wire**) while preserving **human-friendly** authoring for large payloads and a clear bridge to **`NodeType`** at runtime.

