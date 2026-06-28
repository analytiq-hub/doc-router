import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Switch } from '@headlessui/react';
import Editor from '@monaco-editor/react';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import type { DocRouterOrgApi } from '@/utils/api';
import {
  flowInputClass,
  flowLabelClass,
  flowMonacoParamShellClass,
  flowSelectClass,
  flowSwitchThumbClass,
  flowSwitchTrackClass,
} from './flowUiClasses';
import {
  FLOW_NODE_BATCH_SIZE_DEFAULT,
  FLOW_NODE_BATCH_SIZE_MAX,
  FLOW_NODE_BATCH_SIZE_MIN,
  nodeTypeSupportsBatchSize,
  resolveFlowNodeBatchSize,
} from './flowNodeSettings';
import { FlowNameValueListField, type NameValuePair } from './FlowNameValueListField';
import { FLOW_VALUE_MIME, parseFlowValueDragPayload, payloadToExpression, type FlowValueDragPayload } from './IoViewer';
import { FlowExpressionPreviewLine, type ExpressionPreviewContext } from './FlowExpressionPreviewLine';
import {
  applyParameterPatch,
  companionUiPrimaryKey,
  getOrderedKeys,
  getSchemaProperties,
  isCompanionUiProperty,
  isPropertyVisible,
  mergeParameterDefaults,
  mergeObjectFieldDefaults,
  mergeCollectionFieldDefaults,
  resolveEnumSchemaForParams,
} from './flowSchemaParameterUtils';
import { FlowCredentialAuthenticationField } from './FlowCredentialAuthenticationField';
import { FlowOrgEntityPickerField } from './FlowOrgEntityPickerField';
import { FlowOrgTagMultiPickerField } from './FlowOrgTagMultiPickerField';
import { FlowEnumMultiCheckboxField } from './FlowEnumMultiCheckboxField';
import { FlowCollectionFieldsField } from './FlowCollectionFieldsField';
import { FlowCodeEditorField, type FlowCodeEditorLanguage } from './FlowCodeEditorField';
import { FlowParamLabel } from './FlowParamLabel';
import { FlowTextareaEditorField } from './FlowTextareaEditorField';
import { wiredToolNamesForConsumer } from './toolTestUtils';
import {
  FlowScheduleTriggerRulesField,
  type ScheduleRuleValue,
} from './FlowScheduleTriggerRulesField';
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

function schemaDescription(subschema: Record<string, unknown>): string | undefined {
  const d = subschema.description;
  return typeof d === 'string' && d.trim().length > 0 ? d.trim() : undefined;
}

function FlowFlowPickerField({
  label,
  description,
  value,
  readOnly,
  flowOrgApi,
  currentFlowId,
  pickerMode = 'callable',
  onChange,
}: {
  label: string;
  description?: string;
  value: string;
  readOnly: boolean;
  flowOrgApi: DocRouterOrgApi | null | undefined;
  currentFlowId?: string | null;
  /** ``callable`` = Flow Tool targets; ``subflow`` = active flows for Execute Flow. */
  pickerMode?: 'callable' | 'subflow';
  onChange: (flowId: string) => void;
}) {
  const [items, setItems] = useState<Array<{ flow_id: string; name: string; active: boolean }>>([]);
  const [query, setQuery] = useState('');
  const [listOpen, setListOpen] = useState(false);

  useEffect(() => {
    if (!flowOrgApi) return;
    let cancelled = false;
    void (async () => {
      try {
        const collected: Array<{ flow_id: string; name: string; active: boolean }> = [];
        let offset = 0;
        const limit = 200;
        for (;;) {
          const res = await flowOrgApi.listFlows({
            limit,
            offset,
            ...(pickerMode === 'callable' ? { callableAsTool: true } : { activeOnly: true }),
          });
          for (const row of res.items) {
            const fid = row.flow?.flow_id ?? '';
            if (!fid || fid === currentFlowId) continue;
            collected.push({
              flow_id: fid,
              name: row.flow?.name?.trim() || fid,
              active: Boolean(row.flow?.active),
            });
          }
          offset += res.items.length;
          if (res.items.length === 0 || offset >= res.total) break;
        }
        collected.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
        if (!cancelled) setItems(collected);
      } catch {
        if (!cancelled) setItems([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [currentFlowId, flowOrgApi, pickerMode]);

  const selected = items.find((x) => x.flow_id === value);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) => x.name.toLowerCase().includes(q) || x.flow_id.toLowerCase().includes(q));
  }, [items, query]);

  return (
    <div className="relative">
      <FlowParamLabel label={label} description={description} />
      <input
        className={flowInputClass}
        value={listOpen ? query : selected ? `${selected.name}${selected.active ? '' : ' (inactive)'}` : value}
        readOnly={readOnly}
        placeholder={pickerMode === 'subflow' ? 'Search active flows…' : 'Search callable flows…'}
        onChange={(e) => {
          setQuery(e.target.value);
          setListOpen(true);
        }}
        onFocus={() => {
          if (readOnly) return;
          setQuery('');
          setListOpen(true);
        }}
        onBlur={() => {
          window.setTimeout(() => setListOpen(false), 150);
        }}
        autoComplete="off"
        role="combobox"
        aria-expanded={listOpen}
      />
      {listOpen && !readOnly ? (
        <ul
          className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-md border border-gray-200 bg-white py-1 text-sm shadow-lg"
          role="listbox"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-gray-500">No callable flows found</li>
          ) : (
            filtered.map((flow) => (
              <li key={flow.flow_id}>
                <button
                  type="button"
                  className={`block w-full px-3 py-2 text-left hover:bg-gray-100 ${
                    flow.flow_id === value ? 'bg-blue-50 font-medium text-blue-900' : 'text-gray-900'
                  }`}
                  role="option"
                  aria-selected={flow.flow_id === value}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onChange(flow.flow_id);
                    setQuery('');
                    setListOpen(false);
                  }}
                >
                  {flow.name}
                  {!flow.active ? <span className="ml-1 text-xs text-amber-700">(inactive)</span> : null}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}


function FlowLlmModelPickerField({
  label,
  description,
  value,
  readOnly,
  flowOrgApi,
  onChange,
}: {
  label: string;
  description?: string;
  value: string;
  readOnly: boolean;
  flowOrgApi: DocRouterOrgApi | null | undefined;
  onChange: (model: string) => void;
}) {
  const [models, setModels] = useState<string[]>([]);
  useEffect(() => {
    if (!flowOrgApi) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await flowOrgApi.listLLMModels({ excludeEmbeddings: true });
        if (!cancelled) setModels(Array.isArray(res.models) ? res.models : []);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [flowOrgApi]);

  return (
    <div>
      <FlowParamLabel label={label} description={description} />
      <select
        className={flowSelectClass}
        disabled={readOnly}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Select model…</option>
        {models.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
    </div>
  );
}

function FlowKnowledgeBasePickerField({
  label,
  description,
  value,
  readOnly,
  flowOrgApi,
  onChange,
}: {
  label: string;
  description?: string;
  value: string;
  readOnly: boolean;
  flowOrgApi: DocRouterOrgApi | null | undefined;
  onChange: (kbId: string) => void;
}) {
  const [items, setItems] = useState<Array<{ kb_id: string; name: string }>>([]);
  useEffect(() => {
    if (!flowOrgApi) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await flowOrgApi.listKnowledgeBases({ limit: 200 });
        const rows = (res.knowledge_bases ?? []).filter((kb) => kb.status === 'active');
        if (!cancelled) setItems(rows.map((kb) => ({ kb_id: kb.kb_id, name: kb.name })));
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [flowOrgApi]);

  return (
    <div>
      <FlowParamLabel label={label} description={description} />
      <select
        className={flowSelectClass}
        disabled={readOnly}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Select knowledge base…</option>
        {items.map((kb) => (
          <option key={kb.kb_id} value={kb.kb_id}>
            {kb.name}
          </option>
        ))}
      </select>
    </div>
  );
}


export const FlowNodeSettingsFields: React.FC<{
  node: FlowNode;
  nodeType: FlowNodeType | null;
  onChange: (patch: Partial<FlowNode>) => void;
  readOnly?: boolean;
}> = ({ node, nodeType, onChange, readOnly = false }) => {
  const isWebhookTrigger = node.type === 'flows.trigger.webhook';
  const multipleMethods = Boolean((node.parameters as Record<string, unknown> | undefined)?.multiple_methods);
  const supportsBatchSize = nodeTypeSupportsBatchSize(nodeType);
  const batchSize = resolveFlowNodeBatchSize(node);

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
        {supportsBatchSize ? (
          <div>
            <span className={flowLabelClass}>Batch size</span>
            <input readOnly className={flowInputClass} value={String(batchSize)} />
          </div>
        ) : null}
        {isWebhookTrigger ? (
          <div>
            <span className={flowLabelClass}>Allow multiple HTTP methods</span>
            <input readOnly className={flowInputClass} value={multipleMethods ? 'yes' : 'no'} />
          </div>
        ) : null}
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
      {supportsBatchSize ? (
        <div>
          <label className={flowLabelClass} htmlFor="flow-node-batch-size">
            Batch size
          </label>
          <input
            id="flow-node-batch-size"
            type="number"
            className={flowInputClass}
            min={FLOW_NODE_BATCH_SIZE_MIN}
            max={FLOW_NODE_BATCH_SIZE_MAX}
            step={1}
            value={batchSize}
            onChange={(e) => {
              const parsed = Number.parseInt(e.target.value, 10);
              if (!Number.isFinite(parsed)) {
                onChange({ batch_size: undefined });
                return;
              }
              const next = Math.min(
                FLOW_NODE_BATCH_SIZE_MAX,
                Math.max(FLOW_NODE_BATCH_SIZE_MIN, parsed),
              );
              onChange({
                batch_size: next === FLOW_NODE_BATCH_SIZE_DEFAULT ? undefined : next,
              });
            }}
          />
          <p className="mt-1 text-[11px] text-gray-500">
            Max input items in flight at once ({FLOW_NODE_BATCH_SIZE_MIN}–{FLOW_NODE_BATCH_SIZE_MAX},
            default {FLOW_NODE_BATCH_SIZE_DEFAULT} = sequential).
          </p>
        </div>
      ) : null}
      {isWebhookTrigger ? (
        <div className="flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
          <span className="text-sm text-gray-800">Allow multiple HTTP methods</span>
          <Switch
            checked={multipleMethods}
            onChange={(checked) =>
              onChange({
                parameters: { ...(node.parameters ?? {}), multiple_methods: checked },
              })
            }
            className={flowSwitchTrackClass}
          >
            <span className={flowSwitchThumbClass} aria-hidden />
          </Switch>
        </div>
      ) : null}
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
  /** Org API for credential pickers (e.g. ``credential_authentication`` widget). */
  flowOrgApi?: DocRouterOrgApi | null;
  /** Canvas edges — used by tool_name picker on tool_consumer nodes. */
  edges?: readonly { source: string; target: string; targetHandle?: string | null; data?: { connectionType?: string } }[];
  /** All flow nodes — used to resolve wired tool names for tool_executor / agent. */
  allNodes?: readonly FlowNode[];
  /** Current flow id — excludes self from flow_picker targets. */
  currentFlowId?: string | null;
}> = ({
  node,
  nodeType,
  onChange,
  readOnly = false,
  expressionPreview = null,
  soleInboundParentNodeId = null,
  flowOrgApi = null,
  edges = [],
  allNodes = [],
  currentFlowId = null,
}) => {
  const [fieldRegexErrors, setFieldRegexErrors] = useState<Record<string, string>>({});
  const rootSchema = nodeType?.parameter_schema;
  const schemaProps = useMemo(() => getSchemaProperties(rootSchema), [rootSchema]);
  const mergedParams = useMemo(
    () => mergeParameterDefaults(rootSchema, (node.parameters || {}) as Record<string, unknown>),
    [rootSchema, node.parameters],
  );

  const applyPatch = useCallback(
    (patch: Record<string, unknown>) => {
      let nextPatch = { ...patch };
      if (rootSchema) {
        const props = getSchemaProperties(rootSchema);
        const opSub = props.operation;
        if (
          opSub &&
          Object.prototype.hasOwnProperty.call(patch, 'resource') &&
          !Object.prototype.hasOwnProperty.call(patch, 'operation')
        ) {
          const afterResource = { ...mergedParams, ...patch };
          const resolved = resolveEnumSchemaForParams(opSub, afterResource);
          const allowed = resolved.enum?.map(String) ?? [];
          const currentOp = String(afterResource.operation ?? '');
          if (allowed.length > 0 && !allowed.includes(currentOp)) {
            nextPatch = { ...nextPatch, operation: allowed[0] };
          }
        }
        if (opSub && Object.prototype.hasOwnProperty.call(patch, 'operation')) {
          const afterOperation = { ...mergedParams, ...nextPatch };
          const resolved = resolveEnumSchemaForParams(opSub, afterOperation);
          const allowed = resolved.enum?.map(String) ?? [];
          const currentOp = String(afterOperation.operation ?? '');
          if (allowed.length > 0 && !allowed.includes(currentOp)) {
            nextPatch = { ...nextPatch, operation: allowed[0] };
          }
        }
      }
      if (!rootSchema) {
        onChange({ parameters: { ...mergedParams, ...nextPatch } });
        return;
      }
      onChange({ parameters: applyParameterPatch(rootSchema, mergedParams, nextPatch) });
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

  const renderParamField = (
    key: string,
    subschema: { type?: string; enum?: unknown[]; title?: string } & Record<string, unknown>,
    ctx?: {
      params: Record<string, unknown>;
      setField: (fieldKey: string, value: unknown) => void;
      idPrefix: string;
      suppressLabel?: boolean;
    },
  ) => {
    const titleRaw = subschema?.title;
    const propLabel = typeof titleRaw === 'string' && titleRaw.trim().length > 0 ? titleRaw.trim() : key;
    const suppressLabel = Boolean(ctx?.suppressLabel);
    const t = subschema?.type;
    const uiHint = typeof subschema['x-ui-widget'] === 'string' ? (subschema['x-ui-widget'] as string) : '';
    if (uiHint === 'credential_authentication') {
      const companionKeys = Object.keys(schemaProps).filter(
        (k) => companionUiPrimaryKey(schemaProps[k] as Record<string, unknown>) === key,
      );
      return (
        <div key={key} className="mb-3">
          <FlowCredentialAuthenticationField
            node={node}
            nodeType={nodeType}
            rootSchema={rootSchema}
            mergedParams={mergedParams}
            rawParams={(node.parameters || {}) as Record<string, unknown>}
            parameterKey={key}
            companionKeys={companionKeys}
            title={propLabel}
            onChange={onChange}
            flowOrgApi={flowOrgApi}
            readOnly={readOnly}
          />
        </div>
      );
    }
    const params = ctx?.params ?? mergedParams;
    const idPrefix = ctx?.idPrefix ?? '';
    const setField = (fieldKey: string, value: unknown) => {
      if (ctx) ctx.setField(fieldKey, value);
      else applyPatch({ [fieldKey]: value });
    };
    const v = params[key];
    const isCode =
      key === 'python_code' || key === 'js_code' || key === 'ts_code' || uiHint === 'code';
    /** `oneOf` used only for string alternate patterns (e.g. URL vs expression) still renders as a text field. */
    const monacoOneOf =
      Array.isArray((subschema as { oneOf?: unknown }).oneOf) && t !== 'string';
    const rawPlaceholder =
      typeof subschema['x-ui-placeholder'] === 'string' ? (subschema['x-ui-placeholder'] as string) : '';

    if (uiHint === 'org_tag_picker') {
      return (
        <div key={key} className="mb-3">
          <FlowOrgTagMultiPickerField
            label={propLabel}
            description={schemaDescription(subschema)}
            value={v}
            readOnly={readOnly}
            flowOrgApi={flowOrgApi}
            onChange={(ids) => setField(key, ids)}
          />
        </div>
      );
    }

    if (uiHint === 'org_prompt_picker') {
      return (
        <div key={key} className="mb-3">
          <FlowOrgEntityPickerField
            kind="prompt"
            label={propLabel}
            description={schemaDescription(subschema)}
            value={v}
            readOnly={readOnly}
            flowOrgApi={flowOrgApi}
            onChange={(id) => setField(key, id)}
          />
        </div>
      );
    }

    if (uiHint === 'llm_model_picker') {
      return (
        <div key={key} className="mb-3">
          <FlowLlmModelPickerField
            label={propLabel}
            description={schemaDescription(subschema)}
            value={typeof v === 'string' ? v : ''}
            readOnly={readOnly}
            flowOrgApi={flowOrgApi}
            onChange={(id) => setField(key, id)}
          />
        </div>
      );
    }

    if (uiHint === 'knowledge_base_picker') {
      return (
        <div key={key} className="mb-3">
          <FlowKnowledgeBasePickerField
            label={propLabel}
            description={schemaDescription(subschema)}
            value={typeof v === 'string' ? v : ''}
            readOnly={readOnly}
            flowOrgApi={flowOrgApi}
            onChange={(id) => setField(key, id)}
          />
        </div>
      );
    }

    if (uiHint === 'flow_picker') {
      const pickerModeRaw = subschema['x-ui-flow-picker-mode'];
      const pickerMode =
        pickerModeRaw === 'subflow' || pickerModeRaw === 'callable' ? pickerModeRaw : 'callable';
      return (
        <div key={key} className="mb-3">
          <FlowFlowPickerField
            label={propLabel}
            description={schemaDescription(subschema)}
            value={typeof v === 'string' ? v : ''}
            readOnly={readOnly}
            flowOrgApi={flowOrgApi}
            currentFlowId={currentFlowId}
            pickerMode={pickerMode}
            onChange={(id) => setField(key, id)}
          />
        </div>
      );
    }

    if (uiHint === 'tool_name_input' || uiHint === 'wired_tool_picker') {
      const wiredNames = nodeType?.tool_consumer
        ? wiredToolNamesForConsumer(node.id, edges, allNodes.length ? allNodes : [node])
        : [];
      const current = typeof v === 'string' ? v : '';
      if (wiredNames.length > 0) {
        return (
          <div key={key} className="mb-3">
            <FlowParamLabel label={propLabel} htmlFor={`param-tool-name-${key}`} description={schemaDescription(subschema)} />
            <select
              id={`param-tool-name-${key}`}
              className={flowSelectClass}
              disabled={readOnly}
              value={wiredNames.includes(current) ? current : wiredNames[0] ?? ''}
              onChange={(e) => setField(key, e.target.value)}
            >
              {wiredNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <FlowParamLabel label={propLabel} description={schemaDescription(subschema)} />
          <input
            className={flowInputClass}
            readOnly={readOnly}
            value={current}
            placeholder="Wire a tool node, or type tool_name to match"
            onChange={(e) => setField(key, e.target.value)}
          />
        </div>
      );
    }

    if (uiHint === 'enum_multi_checkbox') {
      const itemsSchema = (subschema.items ?? {}) as Record<string, unknown>;
      const enumValues = Array.isArray(itemsSchema.enum)
        ? itemsSchema.enum.filter((entry): entry is string => typeof entry === 'string')
        : [];
      const enumNamesRaw = subschema['x-ui-enum-names'] ?? itemsSchema['x-ui-enum-names'];
      const enumNames = Array.isArray(enumNamesRaw)
        ? enumNamesRaw.map((entry) => (entry == null ? '' : String(entry)))
        : undefined;
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <FlowParamLabel label={propLabel} description={schemaDescription(subschema)} />
            <input
              readOnly
              className={flowInputClass}
              value={Array.isArray(v) ? v.join(', ') : ''}
            />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <FlowEnumMultiCheckboxField
            label={propLabel}
            description={schemaDescription(subschema)}
            value={v}
            options={enumValues}
            enumNames={enumNames}
            readOnly={readOnly}
            onChange={(next) => setField(key, next)}
          />
        </div>
      );
    }

    if (uiHint === 'schedule_trigger_rules') {
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <FlowParamLabel label={propLabel} description={schemaDescription(subschema)} />
            <input readOnly className={flowInputClass} value={safeJsonStringify(v, '{}')} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <FlowScheduleTriggerRulesField
            label={propLabel}
            value={v}
            readOnly={readOnly}
            onChange={(next: ScheduleRuleValue) => setField(key, next)}
          />
        </div>
      );
    }

    if (uiHint === 'name_value_list') {
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <FlowParamLabel label={propLabel} description={schemaDescription(subschema)} />
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
            onChange={(pairs: NameValuePair[]) => setField(key, pairs)}
          />
        </div>
      );
    }

    if (t === 'boolean') {
      const hint = schemaDescription(subschema);
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            {!suppressLabel ? <FlowParamLabel label={propLabel} description={hint} /> : null}
            <input readOnly className={flowInputClass} value={Boolean(v) ? 'true' : 'false'} />
          </div>
        );
      }
      return (
        <div key={key} className={suppressLabel ? 'mb-1' : 'group/field mb-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2'}>
          <div className={`flex items-center gap-3 ${suppressLabel ? 'justify-end' : 'justify-between'}`}>
            {!suppressLabel ? (
              <FlowParamLabel
                label={propLabel}
                description={hint}
                useParentGroup
                wrapperClassName="mb-0"
                className="mb-0 text-sm font-normal leading-none text-gray-800"
              />
            ) : null}
            <Switch
              checked={Boolean(v)}
              onChange={(checked) => setField(key, checked)}
              className={flowSwitchTrackClass}
            >
              <span className={flowSwitchThumbClass} aria-hidden />
            </Switch>
          </div>
        </div>
      );
    }

    if (t === 'number' || t === 'integer') {
      const minVal = (subschema as { minimum?: number }).minimum;
      const inputMin = typeof minVal === 'number' ? minVal : undefined;
      const hint = schemaDescription(subschema);
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <FlowParamLabel label={propLabel} description={hint} />
            <input readOnly className={flowInputClass} value={v == null || v === '' ? '' : String(v)} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          <FlowParamLabel label={propLabel} htmlFor={`param-${key}`} description={hint} />
          <input
            id={`param-${key}`}
            type="number"
            min={inputMin}
            className={flowInputClass}
            value={typeof v === 'number' ? v : (v as number | '') ?? ''}
            onChange={(e) => setField(key, Number(e.target.value))}
          />
        </div>
      );
    }

    const resolvedEnum = resolveEnumSchemaForParams(
      subschema as Record<string, unknown>,
      params,
    );
    if (resolvedEnum.enum && Array.isArray(resolvedEnum.enum)) {
      const enumNames = resolvedEnum['x-ui-enum-names'] ?? undefined;
      const hint = schemaDescription(subschema);
      if (readOnly) {
        return (
          <div key={key} className="mb-3">
            <FlowParamLabel label={propLabel} description={hint} />
            <input readOnly className={flowInputClass} value={v == null ? '' : String(v)} />
          </div>
        );
      }
      return (
        <div key={key} className="mb-3">
          {!suppressLabel ? (
            <FlowParamLabel label={propLabel} htmlFor={`param-enum-${idPrefix}${key}`} description={hint} />
          ) : null}
          <select
            id={`param-enum-${idPrefix}${key}`}
            className={flowSelectClass}
            value={v == null || typeof v === 'object' ? '' : String(v)}
            onChange={(e) => setField(key, e.target.value)}
          >
            {resolvedEnum.enum.map((opt: unknown, idx: number) => (
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
            <FlowParamLabel label={propLabel} htmlFor={`param-json-${key}`} description={schemaDescription(subschema)} />
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
          <FlowParamLabel
            label={propLabel}
            htmlFor={`param-json-${key}`}
            description={schemaDescription(subschema) ?? title}
          />
          <div className={flowMonacoParamShellClass}>
            <Editor
              width="100%"
              height="200px"
              language={monacoLang}
              theme="vs"
              value={tv}
              onChange={(val) => setField(key, val ?? '')}
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
      const placeholder = rawPlaceholder || undefined;
      const tv = typeof v === 'string' ? v : (v as string) ?? '';
      const hint = schemaDescription(subschema);
      return (
        <div key={key} className="mb-3">
          <FlowParamLabel label={propLabel} description={hint} />
          <FlowTextareaEditorField
            value={tv}
            label={propLabel}
            placeholder={placeholder}
            readOnly={readOnly}
            onChange={(next) => setField(key, next)}
          />
          {expressionPreview ? <FlowExpressionPreviewLine expression={tv} preview={expressionPreview} /> : null}
        </div>
      );
    }

    if (t === 'object' && uiHint === 'collection_fields') {
      const nestedProps = (subschema.properties ?? {}) as Record<string, Record<string, unknown>>;
      if (Object.keys(nestedProps).length > 0) {
        const addLabel =
          typeof subschema['x-ui-collection-add-label'] === 'string'
            ? (subschema['x-ui-collection-add-label'] as string)
            : 'Add option';
        const hint = schemaDescription(subschema);
        return (
          <div key={key} className="mb-3 space-y-1">
            <FlowCollectionFieldsField
              label={propLabel}
              description={hint}
              addLabel={addLabel}
              subschema={subschema as Record<string, unknown>}
              value={v}
              readOnly={readOnly}
              idPrefix={`${idPrefix}${key}-`}
              onChange={(next) => setField(key, next)}
              renderProperty={(nestedKey, nestedSchema, nestedCtx) =>
                renderParamField(nestedKey, nestedSchema, nestedCtx)
              }
            />
          </div>
        );
      }
    }

    if (t === 'object' && uiHint === 'object_fields') {
      const nestedProps = (subschema.properties ?? {}) as Record<string, Record<string, unknown>>;
      const nestedKeys = Object.keys(nestedProps);
      if (nestedKeys.length > 0) {
        const obj = mergeObjectFieldDefaults(subschema as Record<string, unknown>, v);
        const hint = schemaDescription(subschema);
        const nestedCtx = {
          params: obj,
          setField: (fieldKey: string, value: unknown) => {
            const parentObj = mergeObjectFieldDefaults(
              subschema as Record<string, unknown>,
              mergedParams[key],
            );
            setField(key, { ...parentObj, [fieldKey]: value });
          },
          idPrefix: `${idPrefix}${key}-`,
        };
        return (
          <div key={key} className="mb-3 space-y-1">
            <FlowParamLabel label={propLabel} description={hint} wrapperClassName="pt-1 uppercase tracking-wide text-[11px] font-semibold text-gray-500" className="text-[11px] font-semibold uppercase tracking-wide text-gray-500" />
            {nestedKeys.map((nestedKey) =>
              renderParamField(nestedKey, nestedProps[nestedKey], nestedCtx),
            )}
          </div>
        );
      }
    }

    if (isCode) {
      const lang: FlowCodeEditorLanguage =
        key === 'python_code' ? 'python' : key === 'ts_code' ? 'typescript' : key === 'js_code' ? 'javascript' : 'python';
      const textValue = typeof v === 'string' ? v : '';
      return (
        <div key={key} className="min-h-0 flex-1">
          <FlowParamLabel label={propLabel} description={schemaDescription(subschema)} wrapperClassName="mb-1" />
          <FlowCodeEditorField
            value={textValue}
            language={lang}
            label={propLabel}
            height="400px"
            readOnly={readOnly}
            nodeId={node.id}
            soleInboundParentNodeId={soleInboundParentNodeId}
            onChange={(next) => setField(key, next)}
          />
        </div>
      );
    }

    if (monacoOneOf || (t === 'object' && uiHint !== 'object_fields' && uiHint !== 'collection_fields') || (t === 'array' && uiHint !== 'name_value_list')) {
      const lang = key === 'python_code' ? 'python' : key === 'ts_code' ? 'typescript' : key === 'js_code' ? 'javascript' : 'json';
      const textValue =
        typeof v === 'string'
          ? v
          : v == null
            ? t === 'object' || t === 'array'
              ? safeJsonStringify(v ?? (t === 'array' ? [] : {}), t === 'array' ? '[]' : '{}')
              : ''
            : safeJsonStringify(v, '');
      const objectEditorHeight =
        key === 'options' || key === 'filters' ? '160px' : '400px';
      return (
        <div key={key} className="min-h-0 flex-1">
          <FlowParamLabel label={propLabel} description={schemaDescription(subschema)} wrapperClassName="mb-1" />
          <Editor
            height={objectEditorHeight}
            language={lang}
            value={textValue}
            onChange={(val) => {
              if (readOnly) return;
              try {
                const parsed = JSON.parse(val ?? 'null');
                setField(key, parsed);
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
                  parsed.kind === 'contextVar'
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
    const hint = schemaDescription(subschema);
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
        {!suppressLabel ? (
          <FlowParamLabel label={propLabel} htmlFor={`param-str-${idPrefix}${key}`} description={hint} />
        ) : null}
        <input
          id={`param-str-${idPrefix}${key}`}
          className={flowInputClass + monoClass}
          value={strVal}
          placeholder={placeholder}
          onChange={(e) => {
            setField(key, e.target.value);
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
            setField(key, payloadToExpression(p, node.id, 0, { soleInboundParentNodeId }));
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
    const subPre = schemaProps[key];
    if (isCompanionUiProperty(subPre as Record<string, unknown>)) continue;
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
