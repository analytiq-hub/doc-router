# Node parameter validation

## Current behavior

`FlowNodeParameterFields` (in `flowNodeConfigFields.tsx`) validates merged parameters on every edit and surfaces errors under controls. Invalid parameters also **disable the flow Save** in the editor toolbar (state is lifted from the node config modal through `FlowEditor` to the flow detail page).

Authoritative server-side validation remains **`Draft7Validator`** on `node.parameters` in `engine.py` (flow save + execution). The same JSON Schema is returned from `GET …/node-types` and compiled in the browser with **AJV** (`allErrors: true`, `strict: false` so `x-ui-*` is ignored by AJV).

**Primary implementation file:** `packages/typescript/frontend/src/components/flows/flowParameterValidation.ts` (`validateFlowParameters`).

**Docs:** `docs/flow_parameter_schema_ui_plan.md` (`x-ui-regex`, `x-ui-require-when`, progress snapshot).

## Why JSON Schema helps

DocRouter uses one schema for both backend and UI. Node authors avoid maintaining a separate INodeProperties-style validation layer for the editor.

## Pipeline (frontend)

1. **Merge defaults** — `mergeParameterDefaults` / `applyParameterPatch` (hidden fields cleared to defaults per `x-ui-show-when`).
2. **Expression substitution** — Before AJV, string values starting with `=` are replaced with type-compatible **sentinels** (e.g. string → `__EXPR__`, number → `0`) recursively through objects and **arrays** (e.g. `name_value_list` rows). AJV then validates **literal** edits without per-field “skip expression” rules in error filtering.
3. **AJV** — Compile once per `parameter_schema`; run on the substituted snapshot.
4. **UI-only rules** (after AJV):
   - **`x-ui-regex` / `x-ui-regex-message`** — applied to non-expression string literals.
   - **`x-ui-require-when` / `x-ui-require-message`** — same predicate shape as `x-ui-show-when`; when the predicate holds and the field is visible, value must be non-empty (trimmed string, non-empty array, etc.).
5. **Errors** — Top-level field messages plus **`listRowErrorsByField`** for nested list paths (e.g. “Row 2: …”) consumed by `FlowNameValueListField`.

## Backend

`Draft7Validator` in `engine.py` validates saved parameters. Optional **`validate_parameters`** on node classes adds extra checks; HTTP URL **shape** for literals is **not** duplicated in Python — use **`minLength`** / types on the schema and **`x-ui-regex`** in the UI for http(s) literals. Expressions remain valid at save time because they satisfy base string constraints.

## Unit tests

- `packages/typescript/frontend/src/components/flows/flowParameterValidation.spec.ts` — substitution, AJV, regex, require-when, list rows.

## Out of scope

- **Async checks** (URL reachable, etc.) — execution time.
- **Duplicating every cross-field rule in JSON Schema `if`/`then`** — use `x-ui-require-when` in the UI where backend resolution validates the real payload.
