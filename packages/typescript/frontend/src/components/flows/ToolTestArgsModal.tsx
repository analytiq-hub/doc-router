'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react';
import Editor from '@monaco-editor/react';
import type { Edge } from 'reactflow';
import type { FlowNode, FlowNodeType, FlowPinData } from '@docrouter/sdk';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { flowInputClass, flowLabelClass, flowMonacoParamShellClass } from './flowUiClasses';
import { buildNodeOutputPreview } from './flowNodeIoPreview';
import {
  exampleArgumentsFromSchema,
  findToolConsumerId,
  pinArgumentsForToolTest,
  toolArgumentsSchemaForNode,
  toolNameFromNode,
} from './toolTestUtils';

const btnSecondary =
  'rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';
const btnPrimary =
  'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50';

function formatArgumentsJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

function parseArgumentsJson(text: string): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  const trimmed = text.trim();
  if (!trimmed) return { ok: true, value: {} };
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { ok: false, error: 'Arguments must be a JSON object' };
    }
    return { ok: true, value: parsed as Record<string, unknown> };
  } catch {
    return { ok: false, error: 'Invalid JSON' };
  }
}

const ToolTestArgsModal: React.FC<{
  open: boolean;
  flowNode: FlowNode | null;
  nodeType: FlowNodeType | null;
  edges: Edge[];
  pinData?: FlowPinData | null;
  runData?: Record<string, unknown> | null;
  busy?: boolean;
  onClose: () => void;
  onConfirm: (args: { tool_name: string; arguments: Record<string, unknown> }) => void | Promise<void>;
}> = ({ open, flowNode, nodeType, edges, pinData, runData, busy = false, onClose, onConfirm }) => {
  const toolName = flowNode ? toolNameFromNode(flowNode) : '';
  const schema = useMemo(
    () => (flowNode ? toolArgumentsSchemaForNode(flowNode, nodeType) : { type: 'object', properties: {} }),
    [flowNode, nodeType],
  );
  const defaultArgs = useMemo(() => exampleArgumentsFromSchema(schema), [schema]);
  const consumerId = flowNode ? findToolConsumerId(flowNode.id, edges) : null;
  const pinArgs = useMemo(
    () => pinArgumentsForToolTest(consumerId, pinData),
    [consumerId, pinData],
  );

  const [argsText, setArgsText] = useState('');
  const [parseError, setParseError] = useState('');
  const [attemptedRun, setAttemptedRun] = useState(false);

  const outputPreview = useMemo(() => {
    if (!flowNode?.id) return null;
    return buildNodeOutputPreview(flowNode.id, runData ?? {}, pinData ?? undefined);
  }, [flowNode?.id, pinData, runData]);

  useEffect(() => {
    if (!open || !flowNode) return;
    setArgsText(formatArgumentsJson(defaultArgs));
    setParseError('');
    setAttemptedRun(false);
  }, [open, flowNode, defaultArgs]);

  const loadFromPins = () => {
    if (!pinArgs) return;
    setArgsText(formatArgumentsJson(pinArgs));
    setParseError('');
  };

  const handleConfirm = async () => {
    if (!flowNode || !toolName) return;
    const parsed = parseArgumentsJson(argsText);
    if (!parsed.ok) {
      setParseError(parsed.error);
      return;
    }
    setParseError('');
    setAttemptedRun(true);
    await onConfirm({ tool_name: toolName, arguments: parsed.value });
  };

  const displayName = flowNode?.name?.trim() || nodeType?.label || 'Tool';
  const showResult = attemptedRun && !busy;
  const resultJson =
    outputPreview && outputPreview.itemsJson.length > 0
      ? JSON.stringify(outputPreview.itemsJson, null, 2)
      : outputPreview?.message
        ? null
        : showResult
          ? '[]'
          : null;

  return (
    <Dialog open={open} onClose={busy ? () => {} : onClose} className="relative z-[260]">
      <DialogBackdrop className="fixed inset-0 bg-black/30" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel className="flex max-h-[min(90vh,720px)] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-xl">
          <div className="flex shrink-0 items-center justify-between border-b border-gray-200 px-4 py-3">
            <DialogTitle className="text-base font-semibold text-gray-900">Test tool arguments</DialogTitle>
            <button
              type="button"
              className="rounded-md p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50"
              aria-label="Close"
              disabled={busy}
              onClick={onClose}
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
            <p className="text-sm text-gray-600">
              Run <span className="font-medium text-gray-900">{displayName}</span> via a synthetic Tool Executor
              (Path B). Edit the arguments object sent to the tool.
            </p>

            <div>
              <label className={flowLabelClass} htmlFor="tool-test-name">
                Tool name
              </label>
              <input
                id="tool-test-name"
                className={`${flowInputClass} bg-gray-50`}
                value={toolName}
                readOnly
              />
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between gap-2">
                <label className={flowLabelClass} htmlFor="tool-test-args">
                  Arguments (JSON)
                </label>
                {pinArgs ? (
                  <button type="button" className="text-xs font-medium text-blue-600 hover:text-blue-800" onClick={loadFromPins}>
                    Load from pin data
                  </button>
                ) : null}
              </div>
              <div className={flowMonacoParamShellClass}>
                <Editor
                  width="100%"
                  height="220px"
                  language="json"
                  value={argsText}
                  onChange={(v) => {
                    setArgsText(v ?? '');
                    setParseError('');
                  }}
                  options={{
                    minimap: { enabled: false },
                    fontSize: 12,
                    scrollBeyondLastLine: false,
                    wordWrap: 'on',
                    tabSize: 2,
                    automaticLayout: true,
                  }}
                />
              </div>
              {parseError ? <p className="mt-1 text-sm text-red-600">{parseError}</p> : null}
            </div>

            {showResult ? (
              <div>
                <label className={flowLabelClass}>Result</label>
                {resultJson != null ? (
                  <div className={flowMonacoParamShellClass}>
                    <Editor
                      width="100%"
                      height="180px"
                      language="json"
                      value={resultJson}
                      options={{
                        minimap: { enabled: false },
                        fontSize: 12,
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                        tabSize: 2,
                        readOnly: true,
                        automaticLayout: true,
                      }}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-gray-600">
                    {outputPreview?.message ?? 'No output items for this tool run.'}
                  </p>
                )}
                {outputPreview?.logs?.length ? (
                  <pre className="mt-2 max-h-32 overflow-auto rounded-md border border-gray-200 bg-gray-50 p-2 text-xs text-gray-800">
                    {outputPreview.logs.join('\n')}
                  </pre>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="flex shrink-0 justify-end gap-2 border-t border-gray-200 px-4 py-3">
            <button type="button" className={btnSecondary} disabled={busy} onClick={onClose}>
              {attemptedRun ? 'Close' : 'Cancel'}
            </button>
            <button
              type="button"
              className={btnPrimary}
              disabled={busy || !toolName}
              aria-busy={busy}
              onClick={() => void handleConfirm()}
            >
              {busy ? 'Running…' : attemptedRun ? 'Run again' : 'Run tool test'}
            </button>
          </div>
        </DialogPanel>
      </div>
    </Dialog>
  );
};

export default ToolTestArgsModal;
