# Node parameter validation

## Current behavior

`FlowNodeParameterFields` (in `flowNodeConfigFields.tsx`) validates merged parameters on every edit and surfaces errors under controls. Invalid parameters also **disable the flow Save** in the editor toolbar (state is lifted from the node config modal through `FlowEditor` to the flow detail page).

Authoritative server-side validation remains **`Draft7Validator`** on `node.parameters` in `engine.py` (flow save + execution). The same JSON Schema is returned from `GET …/node-types` and compiled in the browser with **AJV** (`allErrors: true`, `strict: false` so `x-ui-*` is ignored by AJV).

**Primary implementation file:** `packages/typescript/frontend/src/components/flows/flowParameterValidation.ts` (`validateFlowParameters`).

**Docs:** `docs/flow_parameter_schema_ui_plan.md` (`x-ui-regex`, `allOf`/`if`/`then` visibility, progress snapshot).

## Why JSON Schema helps

DocRouter uses one schema for both backend and UI. Node authors avoid maintaining a separate INodeProperties-style validation layer for the editor.

## Pipeline (frontend)

1. **Merge defaults** — `mergeParameterDefaults` / `applyParameterPatch` (hidden fields cleared to defaults when not **visible**).
2. **Visibility** — `flowSchemaParameterUtils.isPropertyVisible`: prefers root **`allOf`** entries whose **`then.properties`** includes the field key (evaluate **`if`** against full merged params with AJV); falls back to legacy **`x-ui-show-when`** on the property (port converter).
3. **Expression substitution** — Before AJV, string values starting with `=` are replaced with type-compatible **sentinels** recursively through objects and arrays. AJV then validates **literal** edits.
4. **AJV** — Compile once per `parameter_schema`; run on the substituted snapshot (includes standard **`if`/`then`** from `allOf` at save time).
5. **UI-only rules** (after AJV):
   - **`x-ui-regex` / `x-ui-regex-message`** — non-expression string literals.
   Conditional non-empty fields (e.g. HTTP body in JSON mode) use standard schema in **`allOf`/`then`** (`minLength`, `required`) so AJV and **`Draft7Validator`** agree — no separate UI keyword.
6. **Errors** — Top-level field messages plus **`listRowErrorsByField`** for nested list paths.

## Backend

`Draft7Validator` in `engine.py` validates saved parameters. Optional **`validate_parameters`** on node classes adds extra checks.

## Unit tests

- `packages/typescript/frontend/src/components/flows/flowParameterValidation.spec.ts`
- `packages/typescript/frontend/src/components/flows/flowSchemaParameterUtils.spec.ts`

## Out of scope

- **Async checks** (URL reachable, etc.) — execution time.
- **Importer** emitting **`allOf`** instead of **`x-ui-show-when`** — optional follow-up (see plan §9).
