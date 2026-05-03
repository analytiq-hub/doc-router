# Plan: Schema-driven flow node parameters (UI)

This document describes how to move **all** node parameter editors—including `flows.http_request`—onto a **single schema-driven rendering layer**, while keeping **one authoritative JSON Schema per node** on the backend (already validated at execution time via `Draft7Validator`).

**Related:** `docs/flows2.md` (architecture), `docs/node_param_validation.md` (AJV + UI validation pipeline), `flowNodeConfigFields.tsx` (`FlowNodeParameterFields`), `flowParameterValidation.ts`, `FlowNameValueListField.tsx`, `flowSchemaParameterUtils.ts`.

---

## Progress snapshot (2026)

| Area | Status |
|------|--------|
| Schema-driven parameters + `x-ui-show-when` / groups / widgets | Done |
| Inline validation (AJV + expression sentinels + `x-ui-regex` + `x-ui-require-when`) | Done (`flowParameterValidation.ts`, `flowNodeConfigFields.tsx`) |
| Save disabled when parameters invalid | Done (`FlowToolbar` ← `FlowEditor` ← modal) |
| `flows.http_request` URL literals via `x-ui-regex`; backend `minLength` / Draft7 only | Done (`http_request.py`) |
| Body JSON/raw empty when mode active | `x-ui-require-when` on `body_json` / `body_raw` |
| List row errors (`name_value_list`) | Per-row messages via `listRowErrorsByField` + `FlowNameValueListField.rowErrors` |
| Phase D read-only audit | Partial (textarea read-only branch aligned; full audit still optional) |
| Flow credentials API | `get_async_db()` is synchronous — callers must not `await` it (`flows_credentials.py`, `docs/docrouter_credentials.md` examples) |

---

## 1. Goals

1. **One code path** in the node config modal for parameters: no `nodeType.key === 'flows.http_request'` branch in `FlowNodeConfigModal`.
2. **Visual and behavioral consistency**: booleans, enums, strings with drag-from-IO, and structured fields use shared components.
3. **Backend remains source of truth**: `NodeType.parameter_schema` continues to drive validation in `engine.py`; the UI consumes the **same** schema (via `GET …/node-types`).
4. **Extensible without forked node files**: new widget types register once; nodes only extend JSON Schema (plus optional UI hints).

Non-goals for v1 of this plan: replacing Monaco for code nodes with a different editor; building a full visual "expression builder" beyond existing `=expression` strings.

---

## 2. Current state

### 2.1 Backend

- Each registered node exposes `parameter_schema: dict` (JSON Schema draft-07 style object with `properties`, `required`, etc.).
- `flows.http_request` carries full `x-ui-*` annotations (see §4) — groups, conditional visibility, widget hints, regex, require-when — on each field. Other built-ins use the same vocabulary where it applies: **`flows.code`** (`x-ui-widget: code`, groups), **`flows.branch`** (condition group, placeholders), **`flows.merge`** / **`flows.trigger.manual`** (schema `title` / `description` for empty parameter UIs and API consumers).
- The n8n port converter (`analytiq_data/flows/port/schema.py`) maps `INodeProperty` UI hints to `x-ui-*` keys: `placeholder` → `x-ui-placeholder`, `type: "code"` → `x-ui-widget: "code"`, single-field `displayOptions.show` → `x-ui-show-when`.

### 2.2 Frontend

- **`FlowNodeParameterFields`** reads `nodeType.parameter_schema`, walks properties in declaration order, evaluates `x-ui-show-when`, merges defaults, clears hidden fields via schema defaults, and picks widgets: `x-ui-widget` drives the widget (`name_value_list`, `textarea`, `code`); booleans → Headless `Switch`; enums with `x-ui-enum-names`; structured `oneOf` on **`type: string`** stays a plain text field (not Monaco); object/array/code → Monaco when applicable.
- **`flowParameterValidation.ts`**: compiles AJV once per schema; **substitutes** `=…` expression leaves with type-compatible sentinels before AJV; then applies **`x-ui-regex` / `x-ui-regex-message`** (literals only) and **`x-ui-require-when` / `x-ui-require-message`** for visible fields; maps nested/list paths to **row-level** errors for pair lists. Covered by `flowParameterValidation.spec.ts`.
- **`flowSchemaParameterUtils.ts`** provides pure helpers: `evalShowWhen`, `getVisiblePropertyKeys`, `clearHiddenFieldsToDefaults`, `applyParameterPatch`, `mergeParameterDefaults`. Unit-tested in `flowSchemaParameterUtils.spec.ts`.
- **`FlowNameValueListField.tsx`** — pair editor + optional **`rowErrors`** for validation messages under a row.
- **`flows.http_request`** uses the generic path; no special-case branch remains in `FlowNodeConfigModal`.

### 2.3 What was special-cased (now resolved)

The following gaps existed in the generic renderer when `flows.http_request` had its own `FlowHttpRequestParameterFields` component. All are now handled:

| Was missing | How it is handled now |
|-------------|-----------------------|
| Array of `{name, value}` objects | `x-ui-widget: "name_value_list"` → `FlowNameValueListField` |
| Conditional field visibility | `x-ui-show-when` evaluated by `flowSchemaParameterUtils.ts` |
| `x-ui-enum-names` display labels | Read in `renderParamField` enum branch |
| Display order | `properties` declaration order (Python insertion order, JSON key order) |
| Section labels | `x-ui-group` renders a non-collapsible divider above first field in each group |

---

## 3. Architecture

### 3.1 Single entry: `FlowNodeParameterFields`

- Always renders parameters from `nodeType.parameter_schema` + current `node.parameters`.
- **Widget selection** pipeline:
  1. If property schema has `x-ui-widget`, use the registered widget for that hint.
  2. Else infer from JSON Schema: `type`, `enum`, `oneOf`, array `items` shape.
  3. Fallback: string input with drag-drop for expressions.

### 3.2 Widget registry

Built-in widgets:

| Widget id | Activated by | Notes |
|-----------|-------------|-------|
| `name_value_list` | `x-ui-widget: "name_value_list"` | Pair editor; explicit only — not inferred from item shape |
| `textarea` | `x-ui-widget: "textarea"` | Monospace textarea |
| `code` | `x-ui-widget: "code"` or `python_code` / `js_code` / `ts_code` key | Monaco |
| `boolean` | `type: "boolean"` | Headless Switch |
| `enum` | `enum` array present | `<select>` with `x-ui-enum-names` labels |
| `number` | `type: "number"` or `"integer"` | `<input type="number">` with `minimum` |
| `string` | default | Text input with drag-drop |

Credential slots remain separate (`FlowNodeCredentialSlots`) and are not part of `parameter_schema`.

### 3.3 State updates and hidden field clearing

`applyParameterPatch(schema, currentMerged, patch)` merges the patch then calls `clearHiddenFieldsToDefaults`, which resets any field whose `x-ui-show-when` condition is false to its schema `default` (or type fallback). This ensures stale body content from a previous mode does not accumulate in saved flow JSON.

---

## 4. Schema extensions (`x-ui-*` vendor keywords)

All extensions are **optional**; schemas without them use inferred behavior.

**Field order:** The UI walks `properties` in **declaration order** — Python 3.7+ dict insertion order, preserved through JSON serialization. There is no separate order list.

| Keyword | Level | Purpose |
|---------|-------|---------|
| `x-ui-widget` | property | Widget id: `"name_value_list"`, `"textarea"`, `"code"`, `"monospace"`. Required for pair-list arrays (not inferred). |
| `x-ui-group` | property | Short string rendered as a non-collapsible section divider. Adjacent fields with the same group string are visually grouped. |
| `x-ui-show-when` | property | `{ "field": "body_mode", "in": ["json"] }` or `{ "field": "body_mode", "equals": "raw" }`. Hidden field values are cleared to schema defaults. |
| `x-ui-placeholder` | property | Placeholder text for string inputs. |
| `x-ui-enum-names` | property | Human-readable labels for `enum` values; rendered as `<option>` text. |
| `x-ui-regex` | property | ECMAScript regex string (checked **only in the UI**). Literal values are tested after AJV; strings starting with `=` are skipped (expressions). Use with standard JSON Schema (`minLength`, etc.) on the backend so Draft7 stays expression-safe. |
| `x-ui-regex-message` | property | Message when `x-ui-regex` fails. |
| `x-ui-require-when` | property | Same predicate shape as `x-ui-show-when`. When true **and** the field is visible, the control must be non-empty (string trimmed, non-empty array, etc.). Enforced **only in the UI** (cross-field rules stay out of Draft7 unless expressed as JSON Schema `if`/`then`). |
| `x-ui-require-message` | property | Message when `x-ui-require-when` fails. |

The port converter (`port/schema.py`) maps n8n `INodeProperty` fields to these keys automatically: `placeholder` → `x-ui-placeholder`, `type: "code"` → `x-ui-widget: "code"`, single-field `displayOptions.show` → `x-ui-show-when`. Multi-field `displayOptions` and `hide` are left unmapped until the UI supports richer predicates.

---

## 5. Backend

- `Draft7Validator` ignores unknown `x-*` keywords (standard JSON Schema behaviour).
- `GET …/node-types` returns the enriched schema as-is.
- The Python test `test_http_request_parameter_schema_display_extensions` (in `tests/flows/test_flow_http_request_node.py`) asserts that `x-ui-widget` and `x-ui-show-when` are present on the expected fields, and that `list(props.keys())` matches the declared field order.
- The Python test `test_flow_port_schema_display.py` asserts that `port/schema.py` maps n8n hints to `x-ui-*` keys correctly.

---

## 6. Remaining work

Phases A–C (generic renderer, HTTP on schema path) are complete. **Phase E** (inline validation, sentinels, `x-ui-regex`, `x-ui-require-when`, save blocking, list row errors) is **implemented** — see §Progress snapshot and `docs/node_param_validation.md`.

### Phase D — Hardening (optional follow-ups)

- **Read-only mode:** spot-check any new widget branches for consistent disabled/read-only styling (`flowUiClasses.ts` shared inputs).
- **Empty schema:** keep current “No parameters for this node type.” message when `properties` is empty.

---

## 7. Testing

| Layer | What | Status |
|-------|------|--------|
| Unit (TS) | `getVisiblePropertyKeys`, `clearHiddenFieldsToDefaults`, `applyParameterPatch`, `evalShowWhen` | Done (`flowSchemaParameterUtils.spec.ts`) |
| Unit (TS) | `x-ui-enum-names` option labels | Done (enum branch in `flowNodeConfigFields.tsx`) |
| Python | `x-ui-*` keys present on HTTP node schema; `list(props.keys())` order | Done (`test_flow_http_request_node.py`) |
| Python | Port converter maps `placeholder`, `code` type, `displayOptions.show` to `x-ui-*` | Done (`test_flow_port_schema_display.py`) |
| Manual | Phase C QA checklist (below) | Due before merge |
| Unit (TS) | AJV + sentinels + `x-ui-regex` + `x-ui-require-when` + list row mapping | Done (`flowParameterValidation.spec.ts`) |

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
| `show-when` too weak | Start with `field` + `in` / `equals`; extend later (`not`, nested paths). |
| Drag-drop regression in pair lists | `FlowNameValueListField` handles both name and value cells; Phase C checklist covers each. |
| Expression strings vs schema types | UI substitutes expression leaves with sentinels before AJV; literals use full schema; URL shape for literals via `x-ui-regex`. |

---

## 9. Open decisions

- Whether to adopt JSON Schema `if`/`then` for visibility instead of `x-ui-show-when` (more standard, harder for node authors to read).
- Freeze the `x-ui-*` keyword set before widespread use in ported node schemas.
