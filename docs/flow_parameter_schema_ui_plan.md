# Plan: Schema-driven flow node parameters (UI)

This document describes how **all** node parameter editors share a **single schema-driven rendering layer**, while keeping **one authoritative JSON Schema per node** on the backend (validated at execution time via `Draft7Validator` after expression resolution).

**Related:** `docs/flows2.md` (architecture), `flowNodeConfigFields.tsx` (`FlowNodeParameterFields`), `FlowNameValueListField.tsx`, `flowSchemaParameterUtils.ts`.

---

## Progress snapshot (2026)

| Area | Status |
|------|--------|
| Schema-driven parameters + groups / widgets | Done |
| Conditional visibility (`x-ui-show-when`) | Done — preferred for all hand-authored nodes |
| Legacy visibility (`allOf` + `if`/`then` on frontend) | Supported for port-converted nodes; hand-authored nodes use `x-ui-show-when` |
| Frontend validation | **Removed** — no AJV, no sentinels, no save-blocking |
| Backend validation at save time | **Removed** — Draft7Validator no longer runs on raw (pre-resolution) params |
| Backend validation at execution time | Done — `_validate_resolved_params()` runs after `resolve_parameters()` in all three execution paths |
| Pair-list `value` schema | `{}` (any type) — expressions resolve to any Python type; node coerces to string |
| Expression preview in UI | **Not yet implemented** — next major feature |
| `flows.http_request` on generic schema path | Done |
| Phase D read-only audit | Partial (optional) |

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

- **`FlowNodeParameterFields`** reads `nodeType.parameter_schema`, walks properties in declaration order, evaluates visibility via `x-ui-show-when` (and legacy `allOf`/`if`/`then` for port-converted schemas), merges defaults, clears hidden fields via schema defaults, and picks widgets based on `x-ui-widget` and inferred JSON Schema type.
- **No frontend validation**: `flowParameterValidation.ts` has been removed. No AJV, no sentinel substitution, no inline errors, no Save-button blocking. Parameter errors surface after the user runs the flow or executes a step.
- **`flowSchemaParameterUtils.ts`**: `evalShowWhen`, `isPropertyVisible`, `getVisiblePropertyKeys`, `clearHiddenFieldsToDefaults`, `applyParameterPatch`, `mergeParameterDefaults`. Also supports `allOf`/`if`/`then` visibility for legacy port-converted schemas (`instanceMatchesIfSchema`, `getIfBranchesForPropertyKey`). Unit-tested in `flowSchemaParameterUtils.spec.ts`.
- **`FlowNameValueListField.tsx`** — pair editor with add/remove rows and drag-drop into name and value cells.
- **`flows.http_request`** uses the generic path; no special-case branch in `FlowNodeConfigModal`.

### 2.3 Why frontend validation was removed

Static validation against raw parameters (containing `=expression` strings) requires sentinel substitution — replacing expression strings with type-compatible placeholders before running AJV. Sentinels are inherently imprecise: they satisfy `type: string` but not `minLength`, they can't satisfy `pattern`, and they make `if`/`then` conditions misfire. The fundamental problem is that the schema is written for resolved values (what the backend sees), not for expression strings (what the UI stores).

Runtime evaluation — resolving expressions against actual upstream data — is the correct approach. Validation then runs on real values, not approximations.

### 2.4 What was special-cased (now resolved)

| Was missing | How it is handled now |
|-------------|-----------------------|
| Array of `{name, value}` objects | `x-ui-widget: "name_value_list"` → `FlowNameValueListField` |
| Conditional field visibility | `x-ui-show-when` on the property (preferred), or legacy `allOf`/`if`/`then` for port-converted schemas |
| `x-ui-enum-names` display labels | Read in `renderParamField` enum branch |
| Display order | `properties` declaration order (Python insertion order, JSON key order) |
| Section labels | `x-ui-group` renders a non-collapsible section divider |

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
| `x-ui-show-when` | property | `{ "field": "body_mode", "in": ["json"] }` or `{ "field": "body_mode", "equals": "raw" }`. **Preferred for visibility in hand-authored nodes.** Hidden field values are cleared to schema defaults by `clearHiddenFieldsToDefaults`. |
| `x-ui-placeholder` | property | Placeholder text for string inputs. |
| `x-ui-enum-names` | property | Human-readable labels for `enum` values; rendered as `<option>` text. |

### Visibility: `x-ui-show-when` vs `allOf`/`if`/`then`

These two mechanisms serve different purposes and should not be conflated:

- **`x-ui-show-when`** is a **display rule** — it tells the UI whether to render a field. It is ignored by `Draft7Validator`. Hand-authored nodes should use this for all visibility.
- **`allOf`/`if`/`then`** is a **validation constraint** — it tells `Draft7Validator` whether to apply certain constraints conditionally. It says nothing about display. The frontend also reads it as a legacy visibility signal for port-converted nodes (via `getIfBranchesForPropertyKey`), but this is a secondary use.

For hand-authored nodes, use both independently:
- `x-ui-show-when` on the property for display
- `allOf`/`if`/`then` at the root for conditional backend validation (e.g. `minLength` when a field is active)

Port-converted nodes (from n8n via `port/schema.py`) emit `x-ui-show-when` for single-field `displayOptions.show`. Multi-field conditions are left unmapped.

---

## 5. Backend

- `Draft7Validator` ignores unknown `x-*` keywords (standard JSON Schema behaviour).
- `GET …/node-types` returns the enriched schema as-is.
- **Validation timing**: `_validate_resolved_params(node_id, resolved_node)` in `engine.py` runs `Draft7Validator` on fully-resolved parameters in all three execution paths (trigger-only, batch, per-item first item). Errors raise `RuntimeError` and are caught by the node's `on_error` handler.
- The Python test `test_http_request_parameter_schema_display_extensions` (in `tests/flows/test_flow_http_request_node.py`) asserts UI-oriented keys and `list(props.keys())` field order.
- The Python test `test_flow_port_schema_display.py` asserts that `port/schema.py` maps n8n hints to `x-ui-*` keys correctly.

---

## 6. Remaining work

Phases A–C (generic renderer, HTTP node on schema path) are complete. Frontend AJV validation (formerly Phase E) has been removed in favour of runtime evaluation.

### Expression preview (next major feature)

When the node config modal is open and upstream `runData` or `pinData` is available, resolve `=expression` fields against that data and show the resolved value inline below the field. This requires:

1. A backend API endpoint (e.g. `POST /orgs/{org_id}/flows/evaluate-expression`) that accepts `{ expression, run_data, item_index }` and returns `{ result } | { error }`. The backend runs `eval_expression()` from `expressions.py`.
2. Passing upstream run/pin data into `FlowNodeParameterFields` (already available in `FlowNodeConfigModal` via `runData`/`pinData` props).
3. Showing a small gray preview text below expression-valued inputs, and a red error text if `eval_expression` fails.

Expressions use Python syntax (`$json['field']`, `$node['Name']['json']`, etc.) and are evaluated server-side — a JavaScript port is not feasible for the full expression set.

### Phase D — Hardening (optional)

- **Read-only mode:** spot-check all widget branches for consistent non-editable rendering.
- **Empty schema:** keep current "No parameters for this node type." message.

---

## 7. Testing

| Layer | What | Status |
|-------|------|--------|
| Unit (TS) | `getVisiblePropertyKeys`, `clearHiddenFieldsToDefaults`, `applyParameterPatch`, `evalShowWhen` | Done (`flowSchemaParameterUtils.spec.ts`) |
| Python | `x-ui-*` keys present on HTTP node schema; `list(props.keys())` order | Done (`test_flow_http_request_node.py`) |
| Python | Port converter maps `placeholder`, `code` type, `displayOptions.show` to `x-ui-*` | Done (`test_flow_port_schema_display.py`) |
| Python | E2E flow run with expressions in pair-list values | Done (`test_flows_e2e.py`) |
| Manual | Phase C QA checklist (below) | Due before merge |

**Phase C manual QA checklist:**

- [ ] GET request: URL field, query params add/remove, drag IO value into query param value cell
- [ ] POST `json_keypair`: body params add/remove, drag IO value into body param value cell
- [ ] POST `json`: `body_json` appears; switching mode clears `body_json`
- [ ] POST `raw`: `body_raw` and `body_content_type` appear; switching mode clears both
- [ ] POST `form_urlencoded`: body params list appears
- [ ] `none` body mode: no body fields visible
- [ ] `full_response`, `never_error`, `follow_redirects` boolean switches render and toggle
- [ ] `timeout_seconds` number input renders and saves
- [ ] Header auth credential slot visible and bindable
- [ ] Read-only mode: all fields non-editable, switches render as text
- [ ] Code node unaffected: Monaco editor still renders for `python_code`

---

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Schema/UI drift | Single schema from API; `x-ui-*` only adds presentation — validation unchanged. |
| `x-ui-show-when` too weak | Supports `field` + `in` / `equals`; extend later (`not`, nested paths) if needed. |
| Drag-drop regression in pair lists | `FlowNameValueListField` handles both name and value cells; Phase C checklist covers each. |
| Expression errors silent until run | Expression preview API (planned) will surface errors at edit time when upstream data is available. |
| Post-resolution validation too strict | Pair-list `value` fields use `{}` schema; node coerces to `str` internally. Other type constraints are correct post-resolution. |

---

## 9. Open decisions

- Freeze the `x-ui-*` keyword set before widespread use in ported node schemas.
- Expression preview API design: dedicated endpoint vs. reusing the existing step-execution path.
- Whether to validate on every per-item execution or only the first item (current: first item only, to avoid redundant work when all items share the same parameter structure).
