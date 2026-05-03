# Node parameter validation

## The gap

`FlowNodeParameterFields` renders fields from `nodeType.parameter_schema` but never validates against it. Errors only surface at backend execution time when `Draft7Validator` rejects the parameters. The user gets no inline feedback while editing.

N8n validates parameters in the UI in real time — required fields are highlighted, type mismatches shown, number ranges enforced — before the user can save or execute.

## Why JSON Schema is an advantage here

N8n uses a custom `INodeProperties[]` format that is not a standard validation format. It must maintain parallel validation logic for the UI and the backend separately.

DocRouter already returns the same JSON Schema from `GET .../node-types` that `Draft7Validator` uses on the backend. One schema serves both layers with no duplication.

## AJV

AJV (Another JSON Validator) is the standard JSON Schema validation library for JavaScript/TypeScript. It compiles a JSON Schema into a validator function:

```typescript
import Ajv from 'ajv';
const ajv = new Ajv();
const validate = ajv.compile(nodeType.parameter_schema);
const valid = validate(node.parameters);
if (!valid) console.log(validate.errors);
// [{ instancePath: '/timeout_seconds', message: 'must be >= 1' }, ...]
```

It supports Draft-04 through Draft-2020-12, runs in both Node and the browser, and compiles schemas to optimized validator functions rather than interpreting them on every call. It is the de-facto standard and is used by n8n internally. It is likely already a transitive dependency in the Next.js frontend.

## Implementation plan

### Backend (no change)

`Draft7Validator` in `engine.py` already validates parameters at flow-save time and at execution entry. No changes required.

### Frontend

**1. Compile the validator once per node type**

In `FlowNodeParameterFields`, compile the schema when `nodeType` changes:

```typescript
import Ajv from 'ajv';

const ajv = new Ajv({ allErrors: true });

const validator = useMemo(
  () => (nodeType?.parameter_schema ? ajv.compile(nodeType.parameter_schema) : null),
  [nodeType],
);
```

`allErrors: true` collects all errors rather than stopping at the first, so every invalid field is surfaced at once.

**2. Run validation after each patch**

After `applyPatch` produces the next parameter object, run the validator and collect errors keyed by field name:

```typescript
const validationErrors = useMemo(() => {
  if (!validator) return {};
  validator(mergedParams);
  const errors: Record<string, string> = {};
  for (const err of validator.errors ?? []) {
    // instancePath is e.g. '/timeout_seconds' or '' for top-level required errors
    const field = err.instancePath.replace(/^\//, '') ||
      (err.params as { missingProperty?: string }).missingProperty ?? '';
    if (field) errors[field] = err.message ?? 'invalid';
  }
  return errors;
}, [validator, mergedParams]);
```

**3. Pass errors to field renderers**

Pass `validationErrors` into `renderParamField` and show an error message below the input when `validationErrors[key]` is set:

```tsx
{validationErrors[key] && (
  <p className="mt-1 text-xs text-red-600">{validationErrors[key]}</p>
)}
```

**4. Block save when invalid**

`FlowEditor` already has a Save button. Pass a `hasParameterErrors` flag up from `FlowNodeConfigModal` and disable Save (or show a warning) when any open node has validation errors.

### Error cases covered automatically from the schema

| Schema constraint | Example | AJV error message |
|---|---|---|
| `required` field missing | `url` not set | `must have required property 'url'` |
| `enum` value not in list | `method: 'OPTIONS'` | `must be equal to one of the allowed values` |
| `minimum` violated | `timeout_seconds: 0` | `must be >= 1` |
| `type` mismatch | `timeout_seconds: 'fast'` | `must be number` |
| `additionalProperties: false` | unknown key in params | `must NOT have additional properties` |

These are all already expressed in `FlowsHttpRequestNode.parameter_schema` and every other node schema — no per-node validation code is needed in the frontend.

## What this does not cover

- **Expression strings**: a field value of `=$json['url']` will fail `type: string` validation if AJV is strict about format, but expressions are valid at runtime. The validator should skip fields whose value starts with `=` or wrap expression-bearing params before validating.
- **Cross-field constraints**: AJV handles JSON Schema `if`/`then`/`else` but DocRouter uses `x-ui-show-when` for conditional visibility instead. Hidden fields are cleared to their defaults by `applyParameterPatch`, so they will not produce spurious errors as long as clearing runs before validation.
- **Async validation** (e.g. checking that a URL is reachable): out of scope; handled at execution time.
