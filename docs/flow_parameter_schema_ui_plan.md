# Plan: Schema-driven flow node parameters (UI)

This document describes how to move **all** node parameter editors—including `flows.http_request`—onto a **single schema-driven rendering layer**, while keeping **one authoritative JSON Schema per node** on the backend (already validated at execution time via `Draft7Validator`).

**Related:** `docs/flows2.md` (architecture), `flowNodeConfigFields.tsx` (schema-driven `FlowNodeParameterFields`), `FlowNameValueListField.tsx` (pair lists + drag-drop), `flowSchemaParameterUtils.ts` (visibility and defaults).

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
- Example: `packages/python/analytiq_data/flows/nodes/http_request.py` already defines a full schema for method, url, arrays of `{name, value}`, `body_mode`, conditionally relevant body fields, booleans, and `timeout_seconds`.
- Ported / imported nodes may use `build_top_level_parameter_schema` (`analytiq_data/flows/port/schema.py`), which maps n8n-style descriptions into JSON Schema and already uses **vendor extensions** such as `x-enumNames` and `x-source-type`.

### 2.2 Frontend

- **`FlowNodeParameterFields`** reads `nodeType.parameter_schema`, walks ordered properties, evaluates `x-docrouter-showWhen`, merges defaults, clears hidden fields via schema defaults, and picks widgets (`x-docrouter-ui` includes `nameValueList`, `textarea`; booleans → Headless `Switch`; enums with `x-enumNames`; code / object / array → Monaco unless overridden).
- **`flows.http_request`** uses the same path; HTTP UX is driven by extensions on `FlowsHttpRequestNode.parameter_schema` in Python.

### 2.3 Gap (why HTTP is special-cased today)

The generic renderer does **not** yet support:

| Need | Example in HTTP node |
|------|----------------------|
| **Array of fixed-shape objects** | `query_params`, `headers`, `body_params` as `{ name, value }[]` with add/remove rows and drag-drop into value cells |
| **Conditional visibility** | Show `body_json` only when `body_mode === 'json'`, etc. |
| **`x-enumNames` display labels** | Enum `<option>` text rendered as raw value strings instead of human labels |
| **Stable ordering** | Use **`properties` declaration order** in Python/JSON; optional **`x-docrouter-group`** for section labels |

---

## 3. Target architecture

### 3.1 Single entry: `FlowNodeParameterFields`

- Always render parameters from `nodeType.parameter_schema` + current `node.parameters`.
- **Widget selection** uses a small deterministic pipeline:

  1. If property schema has **`x-docrouter-ui`** (see §4), use the registered widget for that hint.
  2. Else infer from JSON Schema: `type`, `enum`, `oneOf`, `format`, array `items` shape.
  3. Fallback: string input (with existing drag-drop for expressions).

### 3.2 Widget registry (frontend)

- Central map: `(hint: string) => React component` or `(predicate: (key, subschema) => boolean) => component`.
- Built-in widgets:
  - `boolean`, `string`, `number`/`integer`, `enum` (with `x-enumNames` for display labels — **this is a bug fix**: the current renderer ignores `x-enumNames` and renders raw enum values as option labels)
  - **`nameValueList`**: pair editor with add/remove rows and drag-drop support in value cells (see §6 Phase A). This widget is **only activated by explicit `x-docrouter-ui: "nameValueList"`** — it is not inferred from item shape, to avoid silently applying pair-list UX to future array schemas that happen to have `name` and `value` fields.
  - **`code`** / **`json`** (existing Monaco branches, keyed off property name or `x-docrouter-ui`)
  - **`conditional`** wrapper: shows child fields when a sibling matches a predicate (see §4)

- **Credential slots** stay separate (`FlowNodeCredentialSlots`)—they are not part of `parameter_schema` today; no change required for this plan.

### 3.3 State updates and hidden field clearing

- Continue merging `{ ...params, [key]: next }` through `onChange({ parameters: … })`.
- **When a `showWhen` condition becomes false, the hidden field's value is cleared** (set to its schema `default`, or omitted). Rationale: stale values from a previous mode accumulate silently in saved flow JSON and make debugging harder. The trade-off (accidental data loss on mode switch) is acceptable because body content for different modes is rarely reused, and the user can see the field disappear as a signal that the value was cleared. This matches the behavior of the current `FlowHttpRequestParameterFields`.

---

## 4. Schema extensions (vendor keywords)

All extensions are **optional**; schemas without them keep current inferred behavior.

Namespace: **`x-docrouter-*`** on property schemas (not on the root object — root carries only `type`, `properties`, `required`, etc.).

**Field order:** The UI walks **`properties` in declaration order** (Python 3.7+ dict insertion order; JSON object key order round-trips the same). There is **no** `x-docrouter-order` list — a parallel array would duplicate that order and drift out of sync.

| Keyword | Level | Purpose |
|---------|--------|---------|
| `x-docrouter-ui` | property | Widget id: e.g. `"nameValueList"`, `"monospace"`, `"textarea"`. Required for pair-list arrays (not inferred). |
| `x-docrouter-group` | property | Short string label rendered as a subtle non-collapsible section divider above the field. Adjacent fields sharing the same group string are visually grouped. |
| `x-docrouter-showWhen` | property | Object like `{ "field": "body_mode", "in": ["json"] }` or `{ "field": "body_mode", "equals": "raw" }` controlling visibility. When the condition becomes false the field value is cleared to its schema default (see §3.3). |
| `x-docrouter-placeholder` | property | Optional short placeholder on string inputs. |

**Conditional fields:** Implement `x-docrouter-showWhen` in the shared renderer only (no need to encode visibility in JSON Schema `if`/`then`/`else` for v1 unless we want one schema for both validation and UI).

**`x-enumNames`:** Already written by `build_top_level_parameter_schema`. The generic renderer must be fixed to read this and render it as `<option>` labels (Phase B).

---

## 5. Backend work (minimal)

1. **Annotate** `flows.http_request` with per-field `x-docrouter-ui`, `x-docrouter-showWhen`, and `x-docrouter-group` where the UI needs hints beyond inference.
2. **Confirm** `Draft7Validator` ignores unknown `x-*` keywords (it does for standard usage).
3. **API:** Ensure `GET …/node-types` returns the enriched schema as-is (no stripping of `x-docrouter-*`).
4. **Tests:** Add a unit test that loads the HTTP node type and asserts schema includes the expected extension keys.

No change to execution logic if parameter shapes stay identical.

---

## 6. Frontend work (phased)

### Phase A — Extract shared primitives

- Move duplicated **switch row** (and any repeated label/input chrome) into `flowUiClasses.tsx` or a tiny `FlowSchemaFieldChrome.tsx`.
- Extract **pair list** from `flowHttpRequestFields.tsx` into `FlowNameValueListField.tsx` driven by a prop schema fragment (`items`). **Drag-drop into value cells must be preserved**: the new component must accept the same `FLOW_VALUE_MIME` drag payloads that the current HTTP panel handles, injecting `=expression` strings into the value input.

### Phase B — Extend `FlowNodeParameterFields`

- Fix **`x-enumNames`** rendering: read the keyword and use its strings as `<option>` labels.
- Support **`x-docrouter-showWhen`** evaluation against current `parameters`; clear hidden field values to schema defaults on condition change.
- Support **`x-docrouter-group`** section dividers.
- Support **`nameValueList`** widget via explicit `x-docrouter-ui` hint.
- **Unit tests** (TypeScript): `getVisibleFields(schema, params) → string[]` and `clearHiddenDefaults(schema, params, visibleKeys) → params` must be covered before Phase B is considered done.

### Phase C — Remove HTTP exception

- Annotate `flows.http_request` backend schema with `x-docrouter-ui`, `x-docrouter-showWhen`, and `x-docrouter-group`.
- Delete the branch in `FlowNodeConfigModal` that selects `FlowHttpRequestParameterFields`; always use `FlowNodeParameterFields`.
- Remove or shrink `flowHttpRequestFields.tsx` (delete file if fully inlined into generic components).
- **Manual QA checklist** before merging Phase C:
  - [ ] GET request: URL field, query params add/remove, drag IO value into query param value cell
  - [ ] POST `json_keypair`: body params add/remove, drag IO value into body param value cell
  - [ ] POST `json`: `body_json` field appears; switching to another mode clears `body_json`
  - [ ] POST `raw`: `body_raw` and `body_content_type` appear; switching mode clears both
  - [ ] POST `form_urlencoded`: body params list appears
  - [ ] `none` body mode: no body fields visible
  - [ ] `full_response`, `never_error`, `follow_redirects` boolean switches render and toggle correctly
  - [ ] `timeout_seconds` number input renders and saves correctly
  - [ ] Header auth credential slot visible and bindable
  - [ ] Read-only mode: all fields non-editable, switches render as text
  - [ ] Code node unaffected: Monaco editor still renders for `python_code`

### Phase D — Hardening

- **Read-only mode:** match existing read-only patterns for booleans (text vs switch) per field type.
- **Empty schema:** keep current "No parameters" message.

---

## 7. Testing strategy

| Layer | What to test | When |
|-------|----------------|------|
| Unit (TS) | `getVisibleFields(schema, params)`, `clearHiddenDefaults(schema, params, visibleKeys)` | Required before Phase B ships |
| Unit (TS) | `x-enumNames` option label rendering | Required before Phase B ships |
| Component | Pair list add/remove, drag-drop into value cell, `showWhen` toggles body fields, hidden field cleared on mode change | Phase B |
| Python | Existing engine validation tests; schema snapshot test asserting `x-docrouter-*` keys present on HTTP node | Phase C |
| Manual | Phase C QA checklist (§6 Phase C) | Phase C |

---

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Schema/UI drift | Single schema from API; UI hints only add presentation—validation unchanged. |
| `showWhen` too weak | Start with `field` + `in` / `equals`; extend later (`not`, nested paths). |
| Drag-drop regression in pair lists | Explicit Phase A requirement; Phase C checklist covers each pair-list field. |
| Bundle size | Lazy-load Monaco only for fields that need it (already per-field). |

---

## 9. Rollout

1. Land Phase A + B behind no feature flag (internal refactor).
2. Annotate HTTP schema on backend.
3. Phase C switch modal to unified renderer; manual QA checklist must pass before merge.
4. Document extension vocabulary in this file and a short subsection in `docs/flows2.md` when the implementation lands.

---

## 10. Open decisions

- **Exact naming** of `x-docrouter-*` keys (freeze before widespread use in stored flows—note: extensions live on **node type** schema, not in saved flow JSON).
- Whether to adopt JSON Schema **`if`/`then`** for visibility instead of custom `x-docrouter-showWhen` (more standard, harder for designers to read).

Once these are decided, implement Phase A–C in order.
