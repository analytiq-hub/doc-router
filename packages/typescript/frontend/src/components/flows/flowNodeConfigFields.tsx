import React, { useCallback, useMemo, useState } from 'react';
import { Switch } from '@headlessui/react';
import Editor from '@monaco-editor/react';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import {
  flowInputClass,
  flowLabelClass,
  flowMonacoParamShellClass,
  flowSelectClass,
  flowSwitchThumbClass,
  flowSwitchTrackClass,
} from './flowUiClasses';
import { FlowNameValueListField, type NameValuePair } from './FlowNameValueListField';
import { FLOW_VALUE_MIME, parseFlowValueDragPayload, payloadToExpression, type FlowValueDragPayload } from './IoViewer';
import { FlowExpressionPreviewLine, type ExpressionPreviewContext } from './FlowExpressionPreviewLine';
import {
  applyParameterPatch,
  getOrderedKeys,
  getSchemaProperties,
  isPropertyVisible,
  mergeParameterDefaults,
} from './flowSchemaParameterUtils';
function isExpressionValue(value: unknown): boolean {
  return typeof value === 'string' && value.startsWith('=');
}

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
  return parseFlowValueDragPayload(raw);
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
  /** Live `=` expression preview (server-evaluated Python subset). */
  expressionPreview?: ExpressionPreviewContext | null;
  /** Single inbound edge source id — upstream drops from that node use `_json` instead of `_node[…].json`. */
  soleInboundParentNodeId?: string | null;
}> = ({ node, nodeType, onChange, readOnly = false, expressionPreview = null, soleInboundParentNodeId = null }) => {
  const [fieldRegexErrors, setFieldRegexErrors] = useState<Record<string, string>>({});
  const rootSchema = nodeType?.parameter_schema;
  const schemaProps = useMemo(() => getSchemaProperties(rootSchema), [rootSchema]);
  const mergedParams = useMemo(
    () => mergeParameterDefaults(rootSchema, (node.parameters || {}) as Record<string, unknown>),
    [rootSchema, node.parameters],
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

  const triggerHasParameterSchema =
    Boolean(nodeType?.is_trigger && Object.keys(schemaProps).length > 0);

  if (nodeType?.is_trigger && !triggerHasParameterSchema) {
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

  const renderParamField = (key: string, subschema: { type?: string; enum?: unknown[]; title?: string } & Record<string, unknown>) => {
    const titleRaw = subschema?.title;
    const propLabel = typeof titleRaw === 'string' && titleRaw.trim().length > 0 ? titleRaw.trim() : key;
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
            <span className={flowLabelClass}>{propLabel}</span>
            <input readOnly className={flowInputClass} value={safeJsonStringify(v, '[]')} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
            <FlowNameValueListField
            label={propLabel}
            value={v}
            readOnly={readOnly}
            configuringNodeId={node.id}
            soleInboundParentNodeId={soleInboundParentNodeId}
            expressionPreview={expressionPreview}
            onChange={(pairs: NameValuePair[]) => applyPatch({ [key]: pairs })}
          />
        </div>
      );
    }

    if (t === 'boolean') {
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <span className={flowLabelClass}>{propLabel}</span>
            <input readOnly className={flowInputClass} value={Boolean(v) ? 'true' : 'false'} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3 flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
          <span className="text-sm text-gray-800">{propLabel}</span>
          <Switch
            checked={Boolean(v)}
            onChange={(checked) => applyPatch({ [key]: checked })}
            className={flowSwitchTrackClass}
          >
            <span className={flowSwitchThumbClass} aria-hidden />
          </Switch>
        </div>
      );
    }

    if (t === 'number' || t === 'integer') {
      const minVal = (subschema as { minimum?: number }).minimum;
      const inputMin = typeof minVal === 'number' ? minVal : undefined;
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <span className={flowLabelClass}>{propLabel}</span>
            <input readOnly className={flowInputClass} value={v == null || v === '' ? '' : String(v)} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <label className={flowLabelClass} htmlFor={`param-${key}`}>
            {propLabel}
          </label>
          <input
            id={`param-${key}`}
            type="number"
            min={inputMin}
            className={flowInputClass}
            value={typeof v === 'number' ? v : (v as number | '') ?? ''}
            onChange={(e) => applyPatch({ [key]: Number(e.target.value) })}
          />
        </div>
      );
    }

    if (subschema?.enum && Array.isArray(subschema.enum)) {
      const enumNames = (subschema['x-ui-enum-names'] as unknown[] | undefined) ?? undefined;
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <span className={flowLabelClass}>{propLabel}</span>
            <input readOnly className={flowInputClass} value={v == null ? '' : String(v)} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <label className={flowLabelClass} htmlFor={`param-enum-${key}`}>
            {propLabel}
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
        </div>
      );
    }

    if (t === 'string' && uiHint === 'json') {
      const tv = typeof v === 'string' ? v : (v as string) ?? '';
      const monacoLang = isExpressionValue(tv) ? 'plaintext' : 'json';
      const title =
        rawPlaceholder || (typeof subschema.description === 'string' ? subschema.description : '') || undefined;
      if (readOnly) {
        return (
          <div key={key} className="mb-3 w-full min-w-0">
            <label className={flowLabelClass} htmlFor={`param-json-${key}`}>
              {propLabel}
            </label>
            <div className={flowMonacoParamShellClass}>
              <Editor
                width="100%"
                height="200px"
                language={monacoLang}
                value={tv}
                onMount={(editor) => {
                  requestAnimationFrame(() => editor.layout());
                }}
                options={{
                  minimap: { enabled: false },
                  overviewRulerLanes: 0,
                  fontSize: 12,
                  scrollBeyondLastLine: false,
                  readOnly: true,
                  folding: true,
                  wordWrap: 'on',
                  tabSize: 2,
                  automaticLayout: true,
                }}
              />
            </div>
            {expressionPreview && isExpressionValue(tv) ? (
              <FlowExpressionPreviewLine expression={tv} preview={expressionPreview} />
            ) : null}
          </div>
        );
      }
      return (
        <div key={key} className="mb-3 w-full min-w-0">
          <label className={flowLabelClass} htmlFor={`param-json-${key}`} title={title}>
            {propLabel}
          </label>
          <div className={flowMonacoParamShellClass}>
            <Editor
              width="100%"
              height="200px"
              language={monacoLang}
              theme="vs"
              value={tv}
              onChange={(val) => applyPatch({ [key]: val ?? '' })}
              onMount={(editor) => {
                requestAnimationFrame(() => editor.layout());
                const dom = editor.getDomNode();
                if (!dom) return;
                if ((dom as HTMLElement).dataset.flowDropInstalled === '1') return;
                (dom as HTMLElement).dataset.flowDropInstalled = '1';
                const onDragOver = (ev: DragEvent) => {
                  if (ev.dataTransfer?.types?.includes(FLOW_VALUE_MIME)) {
                    ev.preventDefault();
                    ev.dataTransfer.dropEffect = 'copy';
                  }
                };
                const onDrop = (ev: DragEvent) => {
                  if (!ev.dataTransfer) return;
                  const raw = ev.dataTransfer.getData(FLOW_VALUE_MIME);
                  if (!raw) return;
                  ev.preventDefault();
                  const parsed = parseFlowValueDragPayload(raw);
                  if (!parsed) return;
                  const insert = payloadToExpression(parsed, node.id, 0, { soleInboundParentNodeId });
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
                overviewRulerLanes: 0,
                fontSize: 12,
                scrollBeyondLastLine: false,
                readOnly: false,
                folding: true,
                wordWrap: 'on',
                tabSize: 2,
                automaticLayout: true,
              }}
            />
          </div>
          {expressionPreview && isExpressionValue(tv) ? (
            <FlowExpressionPreviewLine expression={tv} preview={expressionPreview} />
          ) : null}
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
            <span className={flowLabelClass}>{propLabel}</span>
            <textarea
              readOnly
              className={flowInputClass + ' min-h-[120px] cursor-default font-mono text-[11px]'}
              value={tv}
            />
            {expressionPreview ? <FlowExpressionPreviewLine expression={tv} preview={expressionPreview} /> : null}
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <label className={flowLabelClass} htmlFor={`param-textarea-${key}`}>
            {propLabel}
          </label>
          <textarea
            id={`param-textarea-${key}`}
            className={flowInputClass + ' min-h-[120px] font-mono text-[11px]'}
            placeholder={placeholder}
            value={tv}
            onChange={(e) => applyPatch({ [key]: e.target.value })}
          />
          {expressionPreview ? <FlowExpressionPreviewLine expression={tv} preview={expressionPreview} /> : null}
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
          <div className="mb-1 text-xs font-semibold text-gray-600">{propLabel}</div>
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
                const parsed = parseFlowValueDragPayload(raw);
                if (!parsed) return;
                const expr = payloadToExpression(parsed, node.id, 0, { soleInboundParentNodeId });
                const insert =
                  isCode || uiHint === 'code'
                    ? expr.replace(/^=/, '')
                    : parsed.kind === 'contextVar'
                      ? expr
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
        </div>
      );
    }

    const monoClass = uiHint === 'monospace' ? ' font-mono text-[11px]' : '';
    const placeholder = rawPlaceholder || undefined;
    const regexUi = typeof subschema['x-ui-regex'] === 'string' ? (subschema['x-ui-regex'] as string) : '';
    const regexMsg =
      typeof subschema['x-ui-regex-message'] === 'string'
        ? (subschema['x-ui-regex-message'] as string)
        : 'Value does not match the required pattern';

    const strVal = typeof v === 'string' ? v : (v as string) ?? '';

    const validateRegexUi = (raw: string) => {
      if (!regexUi || readOnly) return;
      const t = raw.trim();
      if (!t || isExpressionValue(t)) {
        setFieldRegexErrors((prev) => {
          if (!(key in prev)) return prev;
          const next = { ...prev };
          delete next[key];
          return next;
        });
        return;
      }
      try {
        const re = new RegExp(regexUi);
        if (!re.test(raw)) {
          setFieldRegexErrors((prev) => ({ ...prev, [key]: regexMsg }));
        } else {
          setFieldRegexErrors((prev) => {
            if (!(key in prev)) return prev;
            const next = { ...prev };
            delete next[key];
            return next;
          });
        }
      } catch {
        setFieldRegexErrors((prev) => ({ ...prev, [key]: 'Invalid x-ui-regex pattern in schema' }));
      }
    };

    return (
      <div key={key} className="mb-3">
        <label className={flowLabelClass} htmlFor={`param-str-${key}`}>
          {propLabel}
        </label>
        <input
          id={`param-str-${key}`}
          className={flowInputClass + monoClass}
          value={strVal}
          placeholder={placeholder}
          onChange={(e) => {
            applyPatch({ [key]: e.target.value });
            if (fieldRegexErrors[key]) {
              setFieldRegexErrors((prev) => {
                const next = { ...prev };
                delete next[key];
                return next;
              });
            }
          }}
          onBlur={() => validateRegexUi(strVal)}
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
            applyPatch({ [key]: payloadToExpression(p, node.id, 0, { soleInboundParentNodeId }) });
          }}
        />
        {fieldRegexErrors[key] ? <p className="mt-0.5 text-xs text-red-600">{fieldRegexErrors[key]}</p> : null}
        {expressionPreview ? <FlowExpressionPreviewLine expression={strVal} preview={expressionPreview} /> : null}
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
    <div className="flex min-h-0 min-w-0 w-full flex-1 flex-col gap-1">
      {blocks}
      {Object.keys(schemaProps).length === 0 && <div className="text-sm text-[#6b7280]">No parameters for this node type.</div>}
    </div>
  );
};
