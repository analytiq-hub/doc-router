import React, { useMemo } from 'react';
import { Switch } from '@headlessui/react';
import Editor from '@monaco-editor/react';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import { flowInputClass, flowLabelClass, flowSelectClass } from './flowUiClasses';
import { FLOW_VALUE_MIME, type FlowValueDragPayload } from './IoViewer';

function safeJsonStringify(value: unknown, fallback: string): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return fallback;
  }
}

function getSchemaProps(schema: unknown): Record<string, unknown> {
  const props = (schema as { properties?: unknown } | null | undefined)?.properties;
  return props && typeof props === 'object' ? (props as Record<string, unknown>) : {};
}

const switchTrackClass =
  'group relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent bg-gray-200 transition-colors data-[checked]:bg-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-1';
const switchThumbClass =
  'inline-block h-3.5 w-3.5 translate-x-0.5 rounded-full bg-white shadow transition group-data-[checked]:translate-x-4';

function payloadToExpression(p: FlowValueDragPayload): string {
  let expr = `_node["${p.nodeId}"]["json"]`;
  for (const seg of p.path) {
    expr += typeof seg === 'number' ? `[${seg}]` : `["${String(seg)}"]`;
  }
  return `=${expr}`;
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
          className={switchTrackClass}
        >
          <span className={switchThumbClass} aria-hidden />
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
}> = ({ node, nodeType, onChange, readOnly = false }) => {
  const schemaProps = useMemo(() => getSchemaProps(nodeType?.parameter_schema), [nodeType]);
  const params = node.parameters || {};

  const renderParamField = (key: string, subschema: { type?: string; enum?: unknown[] } & Record<string, unknown>) => {
    const t = subschema?.type;
    const v = (params as Record<string, unknown>)[key];
    const isCode = key === 'python_code' || key === 'js_code' || key === 'ts_code';

    if (isCode || t === 'object' || t === 'array') {
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
          <div className="text-xs font-semibold text-gray-600 mb-1">{key}</div>
          <Editor
            height="400px"
            language={lang}
            value={textValue}
            onChange={(val) => {
              if (readOnly) return;
              if (isCode) {
                onChange({ parameters: { ...params, [key]: val ?? '' } });
                return;
              }
              try {
                const parsed = JSON.parse(val ?? 'null');
                onChange({ parameters: { ...params, [key]: parsed } });
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
                  isCode
                    ? payloadToExpression(parsed).replace(/^=/, '') // code nodes want the snippet, not `=...`
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
            onChange={(checked) => onChange({ parameters: { ...params, [key]: checked } })}
            className={switchTrackClass}
          >
            <span className={switchThumbClass} aria-hidden />
          </Switch>
        </div>
      );
    }

    if (t === 'number' || t === 'integer') {
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
            className={flowInputClass}
            value={typeof v === 'number' ? v : (v as number | '') ?? ''}
            onChange={(e) => onChange({ parameters: { ...params, [key]: Number(e.target.value) } })}
          />
        </div>
      );
    }

    if (subschema?.enum && Array.isArray(subschema.enum)) {
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
            onChange={(e) => onChange({ parameters: { ...params, [key]: e.target.value } })}
          >
            {subschema.enum.map((opt: unknown) => (
              <option key={String(opt)} value={String(opt)}>
                {String(opt)}
              </option>
            ))}
          </select>
        </div>
      );
    }

    return (
      <div key={key} className="mb-3">
        <label className={flowLabelClass} htmlFor={`param-str-${key}`}>
          {key}
        </label>
        <input
          id={`param-str-${key}`}
          className={flowInputClass}
          value={typeof v === 'string' ? v : (v as string) ?? ''}
          onChange={(e) => onChange({ parameters: { ...params, [key]: e.target.value } })}
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
            onChange({ parameters: { ...params, [key]: payloadToExpression(p) } });
          }}
        />
      </div>
    );
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1">
      {Object.entries(schemaProps).map(([k, subschema]) => renderParamField(k, subschema as { type?: string; enum?: unknown[] }))}
      {Object.keys(schemaProps).length === 0 && <div className="text-sm text-[#6b7280]">No parameters for this node type.</div>}
    </div>
  );
};
