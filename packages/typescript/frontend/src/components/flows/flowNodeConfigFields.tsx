import React, { useCallback, useEffect, useMemo } from 'react';
import { Switch } from '@headlessui/react';
import Editor from '@monaco-editor/react';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import {
  flowInputClass,
  flowLabelClass,
  flowSelectClass,
  flowSwitchThumbClass,
  flowSwitchTrackClass,
} from './flowUiClasses';
import { FlowNameValueListField, payloadToExpression, type NameValuePair } from './FlowNameValueListField';
import { FLOW_VALUE_MIME, type FlowValueDragPayload } from './IoViewer';
import {
  applyParameterPatch,
  getOrderedKeys,
  getSchemaProperties,
  isPropertyVisible,
  mergeParameterDefaults,
} from './flowSchemaParameterUtils';
import { compileParameterValidator, validateFlowParameters } from './flowParameterValidation';

function safeJsonStringify(value: unknown, fallback: string): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return fallback;
  }
}

function parseDropPayload(e: React.DragEvent): FlowValueDragPayload | null {
  const raw = e.dataTransfer.getData(FLOW_VALUE_MIME);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as FlowValueDragPayload;
    if (!parsed || parsed.kind !== 'jsonPath' || typeof parsed.nodeId !== 'string' || !Array.isArray(parsed.path)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function ParamFieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-red-600">{message}</p>;
}

export const FlowNodeSettingsFields: React.FC<{
  node: FlowNode;
  onChange: (patch: Partial<FlowNode>) => void;
  readOnly?: boolean;
}> = ({ node, onChange, readOnly = false }) => {
  if (readOnly) {
    return (
      <div className="space-y-3">
        <div>
          <span className={flowLabelClass}>Name</span>
          <input readOnly className={flowInputClass} value={node.name} />
        </div>
        <div>
          <span className={flowLabelClass}>Disabled</span>
          <input readOnly className={flowInputClass} value={node.disabled ? 'yes' : 'no'} />
        </div>
        <div>
          <span className={flowLabelClass}>On error</span>
          <input readOnly className={flowInputClass} value={node.on_error ?? 'stop'} />
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div>
        <label className={flowLabelClass} htmlFor="flow-node-settings-name">
          Name
        </label>
        <input
          id="flow-node-settings-name"
          className={flowInputClass}
          value={node.name}
          onChange={(e) => onChange({ name: e.target.value })}
        />
      </div>
      <div className="flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
        <span className="text-sm text-gray-800">Disabled</span>
        <Switch
          checked={Boolean(node.disabled)}
          onChange={(checked) => onChange({ disabled: checked })}
          className={flowSwitchTrackClass}
        >
          <span className={flowSwitchThumbClass} aria-hidden />
        </Switch>
      </div>
      <div>
        <label className={flowLabelClass} htmlFor="flow-node-on-error">
          On error
        </label>
        <select
          id="flow-node-on-error"
          className={flowSelectClass}
          value={node.on_error ?? 'stop'}
          onChange={(e) => onChange({ on_error: e.target.value as 'stop' | 'continue' })}
        >
          <option value="stop">stop</option>
          <option value="continue">continue</option>
        </select>
      </div>
    </div>
  );
};

export const FlowNodeParameterFields: React.FC<{
  node: FlowNode;
  nodeType: FlowNodeType | null;
  onChange: (patch: Partial<FlowNode>) => void;
  readOnly?: boolean;
  onParametersValidityChange?: (valid: boolean) => void;
}> = ({ node, nodeType, onChange, readOnly = false, onParametersValidityChange }) => {
  const rootSchema = nodeType?.parameter_schema;
  const schemaProps = useMemo(() => getSchemaProperties(rootSchema), [rootSchema]);
  const mergedParams = useMemo(
    () => mergeParameterDefaults(rootSchema, (node.parameters || {}) as Record<string, unknown>),
    [rootSchema, node.parameters],
  );

  const paramValidator = useMemo(
    () => compileParameterValidator(rootSchema as Record<string, unknown> | undefined),
    [rootSchema],
  );

  const parameterValidation = useMemo(() => {
    if (!rootSchema || nodeType?.is_trigger) {
      return {
        valid: true as const,
        errorsByField: {} as Record<string, string>,
        listRowErrorsByField: {} as Record<string, Record<number, string>>,
      };
    }
    return validateFlowParameters(
      paramValidator,
      rootSchema as Record<string, unknown>,
      mergedParams,
    );
  }, [rootSchema, nodeType?.is_trigger, paramValidator, mergedParams]);

  useEffect(() => {
    if (readOnly || nodeType?.is_trigger) {
      onParametersValidityChange?.(true);
      return;
    }
    onParametersValidityChange?.(parameterValidation.valid);
  }, [readOnly, nodeType?.is_trigger, parameterValidation.valid, onParametersValidityChange]);

  const fieldErr = useCallback(
    (key: string) => (readOnly ? undefined : parameterValidation.errorsByField[key]),
    [readOnly, parameterValidation.errorsByField],
  );

  const listRowErr = useCallback(
    (key: string) => (readOnly ? undefined : parameterValidation.listRowErrorsByField[key]),
    [readOnly, parameterValidation.listRowErrorsByField],
  );

  const applyPatch = useCallback(
    (patch: Record<string, unknown>) => {
      if (!rootSchema) {
        onChange({ parameters: { ...mergedParams, ...patch } });
        return;
      }
      onChange({ parameters: applyParameterPatch(rootSchema, mergedParams, patch) });
    },
    [rootSchema, mergedParams, onChange],
  );

  const orderedKeys = useMemo(() => getOrderedKeys(rootSchema), [rootSchema]);

  if (nodeType?.is_trigger) {
    return (
      <div className="rounded-md border border-gray-200 bg-gray-50/80 px-3 py-3 text-sm text-gray-700">
        <p>This trigger has no editable parameters.</p>
        {!readOnly && (
          <p className="mt-2 text-gray-600">
            Add a Code node after the trigger to emit rows, mock data, or reshape what downstream nodes receive.
          </p>
        )}
      </div>
    );
  }

  const renderParamField = (key: string, subschema: { type?: string; enum?: unknown[] } & Record<string, unknown>) => {
    const t = subschema?.type;
    const uiHint = typeof subschema['x-ui-widget'] === 'string' ? (subschema['x-ui-widget'] as string) : '';
    const params = mergedParams;
    const v = params[key];
    const isCode =
      key === 'python_code' || key === 'js_code' || key === 'ts_code' || uiHint === 'code';
    /** `oneOf` used only for string alternate patterns (e.g. URL vs expression) still renders as a text field. */
    const monacoOneOf =
      Array.isArray((subschema as { oneOf?: unknown }).oneOf) && t !== 'string';
    const rawPlaceholder =
      typeof subschema['x-ui-placeholder'] === 'string' ? (subschema['x-ui-placeholder'] as string) : '';

    if (uiHint === 'name_value_list') {
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <span className={flowLabelClass}>{key}</span>
            <input readOnly className={flowInputClass} value={safeJsonStringify(v, '[]')} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <FlowNameValueListField
            label={key}
            value={v}
            readOnly={readOnly}
            rowErrors={listRowErr(key)}
            onChange={(pairs: NameValuePair[]) => applyPatch({ [key]: pairs })}
          />
          <ParamFieldError message={fieldErr(key)} />
        </div>
      );
    }

    if (t === 'boolean') {
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <span className={flowLabelClass}>{key}</span>
            <input readOnly className={flowInputClass} value={Boolean(v) ? 'true' : 'false'} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3 flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
          <span className="text-sm text-gray-800">{key}</span>
          <Switch
            checked={Boolean(v)}
            onChange={(checked) => applyPatch({ [key]: checked })}
            className={flowSwitchTrackClass}
          >
            <span className={flowSwitchThumbClass} aria-hidden />
          </Switch>
          <ParamFieldError message={fieldErr(key)} />
        </div>
      );
    }

    if (t === 'number' || t === 'integer') {
      const minVal = (subschema as { minimum?: number }).minimum;
      const inputMin = typeof minVal === 'number' ? minVal : undefined;
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <span className={flowLabelClass}>{key}</span>
            <input readOnly className={flowInputClass} value={v == null || v === '' ? '' : String(v)} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <label className={flowLabelClass} htmlFor={`param-${key}`}>
            {key}
          </label>
          <input
            id={`param-${key}`}
            type="number"
            min={inputMin}
            className={flowInputClass}
            value={typeof v === 'number' ? v : (v as number | '') ?? ''}
            onChange={(e) => applyPatch({ [key]: Number(e.target.value) })}
          />
          <ParamFieldError message={fieldErr(key)} />
        </div>
      );
    }

    if (subschema?.enum && Array.isArray(subschema.enum)) {
      const enumNames = (subschema['x-ui-enum-names'] as unknown[] | undefined) ?? undefined;
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <span className={flowLabelClass}>{key}</span>
            <input readOnly className={flowInputClass} value={v == null ? '' : String(v)} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <label className={flowLabelClass} htmlFor={`param-enum-${key}`}>
            {key}
          </label>
          <select
            id={`param-enum-${key}`}
            className={flowSelectClass}
            value={v == null || typeof v === 'object' ? '' : String(v)}
            onChange={(e) => applyPatch({ [key]: e.target.value })}
          >
            {subschema.enum.map((opt: unknown, idx: number) => (
              <option key={String(opt)} value={String(opt)}>
                {enumNames != null && enumNames[idx] != null ? String(enumNames[idx]) : String(opt)}
              </option>
            ))}
          </select>
          <ParamFieldError message={fieldErr(key)} />
        </div>
      );
    }

    if (t === 'string' && uiHint === 'textarea') {
      const placeholder =
        rawPlaceholder || (typeof subschema.description === 'string' ? subschema.description : '') || undefined;
      const tv = typeof v === 'string' ? v : (v as string) ?? '';
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <span className={flowLabelClass}>{key}</span>
            <textarea
              readOnly
              className={flowInputClass + ' min-h-[120px] cursor-default font-mono text-[11px]'}
              value={tv}
            />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <label className={flowLabelClass} htmlFor={`param-textarea-${key}`}>
            {key}
          </label>
          <textarea
            id={`param-textarea-${key}`}
            className={flowInputClass + ' min-h-[120px] font-mono text-[11px]'}
            placeholder={placeholder}
            value={tv}
            onChange={(e) => applyPatch({ [key]: e.target.value })}
          />
          <ParamFieldError message={fieldErr(key)} />
        </div>
      );
    }

    if (isCode || monacoOneOf || t === 'object' || (t === 'array' && uiHint !== 'name_value_list')) {
      const lang = key === 'python_code' ? 'python' : key === 'ts_code' ? 'typescript' : key === 'js_code' ? 'javascript' : 'json';
      const textValue =
        typeof v === 'string'
          ? v
          : v == null
            ? t === 'object' || t === 'array'
              ? safeJsonStringify(v ?? (t === 'array' ? [] : {}), t === 'array' ? '[]' : '{}')
              : ''
            : safeJsonStringify(v, '');
      return (
        <div key={key} className="min-h-0 flex-1">
          <div className="mb-1 text-xs font-semibold text-gray-600">{key}</div>
          <Editor
            height="400px"
            language={lang}
            value={textValue}
            onChange={(val) => {
              if (readOnly) return;
              if (isCode || uiHint === 'code') {
                applyPatch({ [key]: val ?? '' });
                return;
              }
              try {
                const parsed = JSON.parse(val ?? 'null');
                applyPatch({ [key]: parsed });
              } catch {
                // ignore until valid
              }
            }}
            onMount={(editor) => {
              const dom = editor.getDomNode();
              if (!dom) return;
              if ((dom as HTMLElement).dataset.flowDropInstalled === '1') return;
              (dom as HTMLElement).dataset.flowDropInstalled = '1';
              const onDragOver = (ev: DragEvent) => {
                if (readOnly) return;
                if (ev.dataTransfer?.types?.includes(FLOW_VALUE_MIME)) {
                  ev.preventDefault();
                  ev.dataTransfer.dropEffect = 'copy';
                }
              };
              const onDrop = (ev: DragEvent) => {
                if (readOnly) return;
                if (!ev.dataTransfer) return;
                const raw = ev.dataTransfer.getData(FLOW_VALUE_MIME);
                if (!raw) return;
                ev.preventDefault();
                let parsed: FlowValueDragPayload | null = null;
                try {
                  parsed = JSON.parse(raw) as FlowValueDragPayload;
                } catch {
                  parsed = null;
                }
                if (!parsed || parsed.kind !== 'jsonPath') return;
                const insert =
                  isCode || uiHint === 'code'
                    ? payloadToExpression(parsed).replace(/^=/, '')
                    : JSON.stringify(parsed.exampleValue ?? null, null, 2);
                const pos = editor.getTargetAtClientPoint(ev.clientX, ev.clientY)?.position ?? editor.getPosition();
                if (!pos) return;
                const model = editor.getModel();
                if (!model) return;
                editor.executeEdits('flow-drop', [
                  {
                    range: {
                      startLineNumber: pos.lineNumber,
                      startColumn: pos.column,
                      endLineNumber: pos.lineNumber,
                      endColumn: pos.column,
                    },
                    text: insert,
                    forceMoveMarkers: true,
                  },
                ]);
              };
              dom.addEventListener('dragover', onDragOver);
              dom.addEventListener('drop', onDrop);
            }}
            options={{
              minimap: { enabled: false },
              fontSize: 12,
              scrollBeyondLastLine: false,
              readOnly,
              folding: true,
              showFoldingControls: 'always',
              foldingHighlight: true,
              renderLineHighlight: 'none',
            }}
          />
          {!readOnly ? <ParamFieldError message={fieldErr(key)} /> : null}
        </div>
      );
    }

    const monoClass = uiHint === 'monospace' ? ' font-mono text-[11px]' : '';
    const placeholder = rawPlaceholder || undefined;

    return (
      <div key={key} className="mb-3">
        <label className={flowLabelClass} htmlFor={`param-str-${key}`}>
          {key}
        </label>
        <input
          id={`param-str-${key}`}
          className={flowInputClass + monoClass}
          value={typeof v === 'string' ? v : (v as string) ?? ''}
          placeholder={placeholder}
          onChange={(e) => applyPatch({ [key]: e.target.value })}
          readOnly={readOnly}
          onDragOver={(e) => {
            if (readOnly) return;
            if (e.dataTransfer.types.includes(FLOW_VALUE_MIME)) e.preventDefault();
          }}
          onDrop={(e) => {
            if (readOnly) return;
            const p = parseDropPayload(e);
            if (!p) return;
            e.preventDefault();
            applyPatch({ [key]: payloadToExpression(p) });
          }}
        />
        <ParamFieldError message={fieldErr(key)} />
      </div>
    );
  };

  const blocks: React.ReactNode[] = [];
  let lastGroupLabel: string | null | undefined;

  for (const key of orderedKeys) {
    if (!isPropertyVisible(key, rootSchema, mergedParams)) continue;
    const sub = schemaProps[key];
    const groupRaw = sub['x-ui-group'];
    const group = typeof groupRaw === 'string' ? groupRaw.trim() || undefined : undefined;

    if (group) {
      if (group !== lastGroupLabel) {
        blocks.push(
          <div
            key={`group-${group}-${key}`}
            className="pt-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500 first:pt-0"
          >
            {group}
          </div>,
        );
        lastGroupLabel = group;
      }
    } else {
      lastGroupLabel = undefined;
    }

    blocks.push(renderParamField(key, sub as { type?: string; enum?: unknown[] } & Record<string, unknown>));
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1">
      {blocks}
      {Object.keys(schemaProps).length === 0 && <div className="text-sm text-[#6b7280]">No parameters for this node type.</div>}
    </div>
  );
};
