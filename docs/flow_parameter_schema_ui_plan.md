# Plan: Schema-driven flow node parameters (UI)

This document describes how **all** node parameter editors share a **single schema-driven rendering layer**, while keeping **one authoritative JSON Schema per node** on the backend (validated at execution time via `Draft7Validator` after expression resolution).

**Related:** `docs/flows2.md` (architecture), `flowNodeConfigFields.tsx` (`FlowNodeParameterFields`), `FlowNameValueListField.tsx`, `flowSchemaParameterUtils.ts`.

---

## Progress snapshot (2026)

| Area | Status |
|------|--------|
| Schema-driven parameters + groups / widgets | Done |
| Conditional visibility (`x-ui-show-when`) | Done — **only** mechanism the frontend uses to show/hide fields |
| Port `displayOptions` → UI visibility | Done — single-field `show` maps to `x-ui-show-when` in `port/schema.py`; multi-field `show` / `hide` stays unmapped (see §4) |
| Frontend validation | **Removed** — no AJV, no sentinels, no save-blocking |
| Backend validation at save time | **Removed** — Draft7Validator no longer runs on raw (pre-resolution) params |
| Backend validation at execution time | Done — `_validate_resolved_params()` runs after `resolve_parameters()` in all three execution paths |
| Pair-list `value` schema | `{}` (any type) — expressions resolve to any Python type; node coerces to string |
| Expression preview in UI | Done (debounced `POST …/preview-expression` + `FlowExpressionPreviewLine`; request includes **`nodes`** so `_node` matches execute — §8) |
| Expression variables: `_json` / `_binary` / `_node` / … (see §8) | **Done** — name-keyed `_node['Display'].json` / `.output[slot].json` (backend); **`_items`** remains id-keyed (`materialize_node_data`); editor rewrites `_node[…]` on rename/delete (**§8.6**) |
| `flows.http_request` on generic schema path | Done |
| `x-ui-widget: credential_authentication` + companion rows (`x-ui-companion-of`) | Done — suppresses duplicate credential row rendering |

---

## 1. Goals

1. **One code path** in the node config modal for parameters: no per-node-type branch in `FlowNodeConfigModal`.
2. **Visual and behavioral consistency**: booleans, enums, strings with drag-from-IO, and structured fields use shared components.
3. **Backend remains source of truth**: `NodeType.parameter_schema` drives validation at execution time; the UI consumes the same schema (via `GET …/node-types`).
4. **Extensible without forked node files**: new widget types register once; nodes extend JSON Schema plus optional `x-ui-*` hints.

Non-goals for v1: replacing Monaco for code nodes; building a full visual expression builder beyond existing `=expression` strings.

---

## 2. Current state

### 2.1 Backend

- Each registered node exposes `parameter_schema: dict` (JSON Schema draft-07 object with `properties`, `required`, etc.).
- **Save time** (`validate_revision`): structural checks only — unique IDs, one trigger, DAG, connection bounds, credential slot names. `Draft7Validator` is **not** run here because parameters may contain unresolved `=expression` strings that would be incorrectly rejected.
- **Execution time**: `resolve_parameters()` substitutes all `=expression` strings with their runtime values (Python `eval` in a sandboxed environment). `_validate_resolved_params()` then runs `Draft7Validator` on the resolved parameters — catching type errors, missing required fields, and enum violations on actual values.
- `flows.http_request` uses `x-ui-show-when` for display hints and `allOf`/`if`/`then` for conditional backend constraints (e.g. `minLength` on `body_json` when `body_mode == "json"`). The `if`/`then` branches fire correctly post-resolution because hidden fields are cleared to their schema defaults by `clearHiddenFieldsToDefaults` before the flow is saved.
- Pair-list item schema (`query_params`, `headers`, `body_params`): `value` is `{}` (any type). Expressions resolve to arbitrary Python values; the node coerces to `str` when building the HTTP request.

### 2.2 Frontend

- **`FlowNodeParameterFields`** reads `nodeType.parameter_schema`, walks properties in declaration order (`getOrderedKeys`), skips **`x-ui-companion-of`** rows (rendered inside composite widgets), evaluates visibility **only** via `x-ui-show-when` (`isPropertyVisible` / `evalShowWhen`), merges defaults, clears hidden fields via schema defaults, and picks widgets based on `x-ui-widget` and inferred JSON Schema type.
- **No frontend validation**: `flowParameterValidation.ts` has been removed. No AJV, no sentinel substitution, no inline errors, no Save-button blocking. Parameter errors surface after the user runs the flow or executes a step.
- **`flowSchemaParameterUtils.ts`**: `evalShowWhen`, `isPropertyVisible`, `getOrderedKeys`, `getVisiblePropertyKeys`, `defaultFromSubschema`, `mergeParameterDefaults`, `clearHiddenFieldsToDefaults`, `applyParameterPatch`. The UI **does not** interpret root `allOf`/`if`/`then` for visibility — port-converted nodes rely on emitted `x-ui-show-when` where the mapper applies. Unit-tested in `flowSchemaParameterUtils.spec.ts`.
- **`FlowNameValueListField.tsx`** — pair editor with add/remove rows and drag-drop into name and value cells.
- **`flows.http_request`** uses the generic path; no special-case branch in `FlowNodeConfigModal`.

### 2.3 Why frontend validation was removed

Static validation against raw parameters (containing `=expression` strings) requires sentinel substitution — replacing expression strings with type-compatible placeholders before running AJV. Sentinels are inherently imprecise: they satisfy `type: string` but not `minLength`, they can't satisfy `pattern`, and they make `if`/`then` conditions misfire. The fundamental problem is that the schema is written for resolved values (what the backend sees), not for expression strings (what the UI stores).

Runtime evaluation — resolving expressions against actual upstream data — is the correct approach. Validation then runs on real values, not approximations.

### 2.4 What was special-cased (now resolved)

| Was missing | How it is handled now |
|-------------|-----------------------|
| Array of `{name, value}` objects | `x-ui-widget: "name_value_list"` → `FlowNameValueListField` |
| Conditional field visibility | `x-ui-show-when` on each property; port converter fills it from simple `displayOptions.show` |
| `x-ui-enum-names` display labels | Read in `renderParamField` enum branch |
| Display order | `properties` declaration order (Python insertion order, JSON key order) |
| Section labels | `x-ui-group` renders a non-collapsible section divider |
| `credential_authentication` widget | Primary property: `x-ui-widget: "credential_authentication"`. Companion properties (e.g. generic auth type enum) set `x-ui-companion-of` to the primary property key so they are not rendered twice; the widget owns both values. Default `FlowNodeCredentialSlots` is suppressed when this widget is present (schema-driven). |

---

## 3. Architecture

### 3.1 Single entry: `FlowNodeParameterFields`

- Always renders parameters from `nodeType.parameter_schema` + current `node.parameters`.
- **Widget selection** pipeline:
  1. If property schema has `x-ui-widget`, use the registered widget for that hint.
  2. Else infer from JSON Schema: `type`, `enum`, `oneOf`, array `items` shape.
  3. Fallback: string input with drag-drop for expressions.

### 3.2 Widget registry

| Widget id | Activated by | Notes |
|-----------|-------------|-------|
| `name_value_list` | `x-ui-widget: "name_value_list"` | Pair editor; explicit only — not inferred from item shape |
| `textarea` | `x-ui-widget: "textarea"` | Monospace textarea |
| `json` | `x-ui-widget: "json"` (`type: "string"`) | Monaco JSON; `plaintext` language when value starts with `=` |
| `code` | `x-ui-widget: "code"` or `python_code` / `js_code` / `ts_code` key | Monaco |
| `boolean` | `type: "boolean"` | Headless Switch |
| `enum` | `enum` array present | `<select>` with `x-ui-enum-names` labels |
| `number` | `type: "number"` or `"integer"` | `<input type="number">` with `minimum` |
| `string` | default | Text input with drag-drop |

Credential slots remain separate (`FlowNodeCredentialSlots`) and are not part of `parameter_schema`.

### 3.3 State updates and hidden field clearing

`applyParameterPatch(schema, currentMerged, patch)` merges the patch then calls `clearHiddenFieldsToDefaults`, which resets any field whose visibility condition is false to its schema `default` (or type fallback). This ensures hidden fields are cleared before save, which in turn ensures `allOf`/`if`/`then` backend constraints fire correctly post-resolution.

---

## 4. Schema extensions (`x-ui-*` vendor keywords)

All extensions are **optional**; schemas without them use inferred behavior.

**Field order:** The UI walks `properties` in **declaration order** — Python 3.7+ dict insertion order, preserved through JSON serialization. There is no separate order list.

| Keyword | Level | Purpose |
|---------|-------|---------|
| `x-ui-widget` | property | Widget id: `"name_value_list"`, `"textarea"`, `"json"`, `"code"`, `"monospace"`. Required for pair-list arrays (not inferred). |
| `x-ui-group` | property | Short string rendered as a non-collapsible section divider. Adjacent fields with the same group label are visually grouped. |
| `x-ui-show-when` | property | `{ "field": "body_mode", "in": ["json"] }` or `{ "field": "body_mode", "equals": "raw" }`. **Use whenever a field should be hidden unless its predicate matches** (frontend has no other visibility source). Hidden field values are cleared to schema defaults by `clearHiddenFieldsToDefaults`. |
| `x-ui-placeholder` | property | Placeholder text for string inputs. |
| `x-ui-enum-names` | property | Human-readable labels for `enum` values; rendered as `<option>` text. |
| `x-ui-regex` / `x-ui-regex-message` | property | Used on some hand-authored schemas (e.g. HTTP URL); **not yet read by the flows UI** — validation still runs post-resolution only. |

### Visibility: `x-ui-show-when` vs `allOf`/`if`/`then`

These two mechanisms serve different purposes and should not be conflated:

- **`x-ui-show-when`** is a **display rule** — it tells the UI whether to render a field (`isPropertyVisible`). Omitted or absent → field is shown. Ignored by `Draft7Validator`. Hand-authored and port-converted nodes should carry this wherever fields are conditionally shown.
- **`allOf`/`if`/`then`** is a **validation constraint** — it tells `Draft7Validator` whether to apply certain constraints conditionally after resolution. The **frontend does not** walk `if`/`then` branches to decide visibility.

For hand-authored nodes, use both independently:
- `x-ui-show-when` on the property for display
- `allOf`/`if`/`then` at the root for conditional backend validation (e.g. `minLength` when a field is active)

Port-converted nodes (from n8n via `port/schema.py`): `_apply_inode_ui_extensions` emits `x-ui-show-when` when `displayOptions.show` has exactly one field key and a value list. Multi-field `show`, `hide`, and other shapes are left unmapped — those properties may appear even when an n8n editor would hide them until the mapper is extended.

---

## 5. Backend

- `Draft7Validator` ignores unknown `x-*` keywords (standard JSON Schema behaviour).
- `GET …/node-types` returns the enriched schema as-is.
- **Validation timing**: `_validate_resolved_params(resolved_node)` in `engine.py` runs `Draft7Validator` on fully-resolved parameters in all three execution paths (trigger-only, batch, per-item first item). Errors raise `RuntimeError` and are caught by the node's `on_error` handler.
- The Python test `test_http_request_parameter_schema_display_extensions` (in `tests/flows/test_flow_http_request_node.py`) asserts UI-oriented keys and `list(props.keys())` field order.
- The Python test `test_flow_port_schema_display.py` asserts that `port/schema.py` maps n8n hints to `x-ui-*` keys correctly.

---

## 6. Testing

| Layer | What | Status |
|-------|------|--------|
| Unit (TS) | `getOrderedKeys`, `getVisiblePropertyKeys`, `defaultFromSubschema`, `mergeParameterDefaults`, `clearHiddenFieldsToDefaults`, `applyParameterPatch`, `evalShowWhen` | Done (`flowSchemaParameterUtils.spec.ts`) |
| Python | `x-ui-*` keys present on HTTP node schema; `list(props.keys())` order | Done (`test_flow_http_request_node.py`) |
| Python | Port converter maps `placeholder`, `code` type, `displayOptions.show` to `x-ui-*` | Done (`test_flow_port_schema_display.py`) |
| Python | E2E flow run with expressions in pair-list values | Done (`test_flows_e2e.py`) |
| Python | Expression / `_node` / preview (`revision_nodes`) | Done (`tests/flows/test_expressions.py`) |
| TS | `_node` string rewrite helpers | Done (`flowExpressionNodeRefs.spec.ts`) |

---

## 7. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Schema/UI drift | Single schema from API; `x-ui-*` only adds presentation — validation unchanged. |
| `x-ui-show-when` too weak | Supports `field` + `in` / `equals`; extend later (`not`, nested paths) if needed. |
| Drag-drop regression in pair lists | `FlowNameValueListField` handles both name and value cells; regression-test HTTP flows manually when touching drag handlers. |
| Expression errors silent until run | Mitigated where upstream **`run_data`** / INPUT preview exists — **`preview-expression`** surfaces errors; empty graph still needs a run for sample data. |
| Post-resolution validation too strict | Pair-list `value` fields use `{}` schema; node coerces to `str` internally. Other type constraints are correct post-resolution. |

---

## 8. Expression context variables (`_json`, `_binary`, `_input`, `_node`)

Parameters may contain strings starting with `=`. The remainder is evaluated as a **restricted Python expression** (`packages/python/analytiq_data/flows/expressions.py`). The engine injects a small set of **top-level names** into the eval environment. Authors and the UI use those names **verbatim** (leading underscore) — there is **no** `$json`-style alias layer; `$` tokens are not rewritten.

### 8.1 Canonical semantics

| Name | Meaning |
|------|--------|
| **`_json`** | JSON payload of the **current inbound item** (`FlowItem.json` for the item against which parameters are being resolved). |
| **`_binary`** | Binary map of the **current inbound item**, materialized for expressions (metadata / refs; raw bytes are not exposed in the eval sandbox — same rules as today’s `_binary`). |
| **`_input`** | The **entire multi-slot input structure** for the current node execution: all lanes, all items, plus `item` / `input_index` / `item_index` for the current row (see `materialize_input_context()`). |
| **`_node`** | Access to **upstream node outputs**, keyed by the node’s **canvas name** (`nodes[].name`). Each entry exposes **`output[slot_no]`** — a view of that **output handle’s lane** at the current **`item_index`** (same alignment rules as today’s per-item execution). Use **`_node['Name'].output[slot_no].json`** and **`.binary`** for that slot’s JSON / binary. **Shorthand:** **`_node['Name'].output[0]`** is the same object as **`_node['Name']`** (default first output). So **`_node['Name'].json`** / **`.binary`** mean **`_node['Name'].output[0].json`** / **`.binary`**. Other slots: **`_node['Name'].output[1].json`**, etc. If **`output[slot]`** has **fewer items** than **`item_index` + 1**, evaluation **errors** (no `None`, clamp, or last-item fallback). *(Implementation maps `output[k]` ↔ engine `data.main[k]`.)* |

**Why underscore:** these names are valid Python identifiers and match the keys injected into `eval(..., env)` (`_json`, `_binary`, `_node`, `_input`, …).

**Node names as keys:** `validate_revision` requires **unique** `nodes[].name`. That makes `_node['My HTTP Request']` unambiguous. **Stable node `id`** remains the technical key for graph edges, `run_data`, and storage (see §8.7).

### 8.2 Implementation status (backend + UI)

| Topic | Status |
|------|--------|
| Authoring / drag | **`_json`**, **`_binary`** in Context + IO drag; upstream output drags insert **`_node[JSON.stringify(displayName)].json`** (display name = trimmed canvas name, else node **`id`** — matches Python `node_name`). |
| `$` aliases | **Not supported** — expressions use injected names only. |
| **`_node` shape** | **`materialize_node_outputs_by_name`** in `expressions.py`: name-keyed proxies; **`_node['Name'].output[s].json` / `.binary`**; **`_node['Name']` ≡ slot 0**; lane shorter than **`item_index`** → **`ExpressionError`**. |
| **`_items`** | Still **`materialize_node_data(run_data)`** — **id-keyed** JSON rows (for authors who want stable id-based access). |
| **`revision_nodes` / `nodes` in preview** | **`ExecutionContext.revision_nodes`**, engine + **`http_request`** pass through **`resolve_parameters`**; preview API + SDK + modal send **`nodes`**. |

### 8.3 Implementation notes

- **Eval / UI:** Injected names only — no `$` aliases. Drag and Context use **`_json`**, **`_binary`**, **`_input`**, **`_node`**, **`_execution`**, **`_item`**, **`_items`**.
- **Backend:** `materialize_node_outputs_by_name` and related proxies in `expressions.py`; **`revision_nodes`** on **`ExecutionContext`** and all **`resolve_parameters`** call sites (**`run_flow`**, **`http_request`**). When **`item_index`** is unset (merge/batch), **`_node[…].json`** / **`.binary`** raise **`ExpressionError`** — see §8.4–§8.5.
- **Preview:** **`POST …/preview-expression`** takes **`nodes`**; org SDK and **`FlowNodeConfigModal`** pass the current revision.
- **Editor:** **`flowExpressionNodeRefs.ts`** + **`FlowEditor`**: debounced rewrites on rename, sentinel substitution on delete (**§8.6**).

### 8.4 Decided semantics (name-keyed `_node`)

- **Item alignment:** If **`_node['Name'].output[slot]`** (backed by **`main[slot]`**) has **fewer than `item_index + 1` items**, treat as **error** (deterministic failure; no `None`, clamp, or last-item fallback).
- **Output API:** Use **`_node['Name'].output[slot_no].json`** / **`.binary`**. **Equivalence:** **`_node['Name'].output[0]`** is the same as **`_node['Name']`**; therefore **`_node['Name'].json`** means **`_node['Name'].output[0].json`** (and the same for **`.binary`**). Other slots use **`_node['Name'].output[1].json`**, etc.

### 8.5 Merge / batch vs `_node` row access

For nodes that resolve parameters **once** with **`item_index` unset** (merge and other batch paths), **`_node['…'].json`** / **`.binary`** are **not** available — use **`_input['all']`**, **`_items`** (id-keyed), or expressions that do not read row-scoped prior-node output. Per-item nodes align **`item_index`** with the current row as today.

### 8.6 Editor: keep `_node[…]` strings in sync (frontend)

Expression parameters are plain text; renames would otherwise **orphan** `_node['Old Name']` references (cf. n8n `Workflow.renameNodeInParameterValue`).

| Event | Behaviour (`flowExpressionNodeRefs.ts`, `FlowEditor.tsx`) |
|------|-----------------------------------------------------------|
| **Rename** | Debounced (~350ms) after **`name`** edits: rewrite **`_node['…']` / `_node["…"]`** where the inner string equals the **anchor display name** (pre-edit **`flowCanvasDisplayName`**) to the **new** display name; replacement uses **`_node[` + `JSON.stringify(newName)` + `]`**. |
| **Delete** | Replace references to the removed node’s display name with **`_node['__docrouter_removed_node__']`** (sentinel) so evaluation fails clearly. |
| **Reconnect edges only** | **No** expression rewrite — names unchanged; topology does not alter **`_node`** spellings. |

Display name rule matches the backend: **trimmed `name`**, else **`node.id`** (unnamed nodes use **`id`** inside **`_node[…]`** in dragged hints and rewrites).

### 8.7 Why node `id` remains

**Name** is the primary handle in **`_node['…']`** for humans; **`id`** is still required as the **stable** key for **`run_data`**, connections, execution continuity across **renames**, React Flow **`source`/`target`**, and **`_items[node_id]`**. The engine joins **`run_data[id]`** to **`node_name(revision_node)`** to build name-keyed **`_node`**.

### 8.8 Worked example: `.json` vs other output slots

Imagine an upstream node whose **canvas name** is **`Parse`**. After it runs, the engine stores (conceptually) two output wires:

| Output slot | `main[slot]` (list of items for that wire) |
|---------------|--------------------------------------------|
| **0** — “data” | `[ {"sku": "A1"}, {"sku": "B2"}, {"sku": "C3"} ]` — **3 rows** |
| **1** — “errors” | `[ {"msg": "bad charset"}, {"msg": "timeout"} ]` — **2 rows** |

You are configuring a downstream node that runs **once per inbound row** on the wire coming from **slot 0**. When the engine evaluates parameters for the **third** row, **`item_index` is `2`**.

- **`_node['Parse'].json`** is sugar for “**slot 0**, **same row as me**”: the dict **`{"sku": "C3"}`** — i.e. `main[0][2]` as JSON. **`_node['Parse'].binary`** is the same cell’s binary map (same index, slot 0).
- If **`main[0]`** only had **two** items (`[0]` and `[1]`) but your current **`item_index`** were **`2`**, that shortcut would be **out of range** → **error** (by design), not a silent `None`.

The **`.json` / `.binary` shortcuts never mean slot 1**. To read the “errors” wire use **`_node['Parse'].output[1].json`** (first row of slot 1 when **`item_index == 0`**), or **`_node['Parse'].output[1]`** then **`.json`** / **`.binary`** for the current **`item_index`** row. Out-of-range indices fail with **`ExpressionError`**, same as other lane faults.

