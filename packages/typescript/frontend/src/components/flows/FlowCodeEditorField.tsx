import React, { useCallback, useMemo, useState } from 'react';
import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react';
import { ArrowsPointingOutIcon, XMarkIcon } from '@heroicons/react/24/outline';
import Editor, { type OnMount } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';
import { flowMonacoParamShellClass } from './flowUiClasses';
import { FLOW_VALUE_MIME, parseFlowValueDragPayload, payloadToExpression, type FlowValueDragPayload } from './IoViewer';

const flowCodeEditorExpandButtonClass =
  'absolute bottom-px right-px z-10 cursor-pointer rounded-tl border border-b-0 border-r-0 border-gray-300 bg-white p-1 text-gray-500 hover:text-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-400/30';

const flowMonacoEditorOptions: editor.IStandaloneEditorConstructionOptions = {
  minimap: { enabled: false },
  fontSize: 12,
  scrollBeyondLastLine: false,
  folding: true,
  showFoldingControls: 'always',
  foldingHighlight: true,
  renderLineHighlight: 'none',
};

export type FlowCodeEditorLanguage = 'python' | 'javascript' | 'typescript' | 'json';

function editDialogTitle(language: FlowCodeEditorLanguage, label?: string): string {
  if (label && label.trim().length > 0) {
    return `Edit ${label.trim()}`;
  }
  switch (language) {
    case 'python':
      return 'Edit Python';
    case 'javascript':
      return 'Edit JavaScript';
    case 'typescript':
      return 'Edit TypeScript';
    default:
      return 'Edit code';
  }
}

function installFlowMonacoDropHandlers(
  editor: editor.IStandaloneCodeEditor,
  opts: {
    readOnly: boolean;
    treatAsCode: boolean;
    nodeId: string;
    soleInboundParentNodeId?: string | null;
  },
) {
  const dom = editor.getDomNode();
  if (!dom) return;
  if ((dom as HTMLElement).dataset.flowDropInstalled === '1') return;
  (dom as HTMLElement).dataset.flowDropInstalled = '1';

  const onDragOver = (ev: DragEvent) => {
    if (opts.readOnly) return;
    if (ev.dataTransfer?.types?.includes(FLOW_VALUE_MIME)) {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'copy';
    }
  };

  const onDrop = (ev: DragEvent) => {
    if (opts.readOnly) return;
    if (!ev.dataTransfer) return;
    const raw = ev.dataTransfer.getData(FLOW_VALUE_MIME);
    if (!raw) return;
    ev.preventDefault();
    const parsed = parseFlowValueDragPayload(raw);
    if (!parsed) return;
    const expr = payloadToExpression(parsed, opts.nodeId, 0, {
      soleInboundParentNodeId: opts.soleInboundParentNodeId,
    });
    const insert = opts.treatAsCode
      ? expr.replace(/^=/, '')
      : parsed.kind === 'contextVar'
        ? expr
        : JSON.stringify(parsed.exampleValue ?? null, null, 2);
    const pos =
      editor.getTargetAtClientPoint(ev.clientX, ev.clientY)?.position ?? editor.getPosition();
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
}

type FlowCodeEditorFieldProps = {
  value: string;
  language: FlowCodeEditorLanguage;
  height?: string;
  modalHeight?: string;
  label?: string;
  readOnly?: boolean;
  treatAsCode?: boolean;
  nodeId: string;
  soleInboundParentNodeId?: string | null;
  onChange: (value: string) => void;
};

export const FlowCodeEditorField: React.FC<FlowCodeEditorFieldProps> = ({
  value,
  language,
  height = '400px',
  modalHeight = 'min(480px, calc(100vh - 12rem))',
  label,
  readOnly = false,
  treatAsCode = true,
  nodeId,
  soleInboundParentNodeId = null,
  onChange,
}) => {
  const [modalOpen, setModalOpen] = useState(false);
  const dialogTitle = useMemo(() => editDialogTitle(language, label), [language, label]);

  const onMount: OnMount = useCallback(
    (editorInstance) => {
      installFlowMonacoDropHandlers(editorInstance, {
        readOnly,
        treatAsCode,
        nodeId,
        soleInboundParentNodeId,
      });
    },
    [readOnly, treatAsCode, nodeId, soleInboundParentNodeId],
  );

  const editorOptions = useMemo(
    () => ({
      ...flowMonacoEditorOptions,
      readOnly,
    }),
    [readOnly],
  );

  const renderEditor = (editorHeight: string) => (
    <Editor
      height={editorHeight}
      language={language}
      value={value}
      onChange={(val) => {
        if (readOnly) return;
        onChange(val ?? '');
      }}
      onMount={onMount}
      options={editorOptions}
    />
  );

  return (
    <>
      <div className="relative">
        {!modalOpen ? (
          <div className={flowMonacoParamShellClass}>{renderEditor(height)}</div>
        ) : (
          <div
            className={`${flowMonacoParamShellClass} flex items-center justify-center text-xs text-gray-500`}
            style={{ height }}
          >
            Editing in expanded window…
          </div>
        )}
        {!readOnly ? (
          <button
            type="button"
            className={flowCodeEditorExpandButtonClass}
            aria-label="Open expanded code editor"
            title="Open expanded editor"
            data-testid="code-editor-fullscreen-button"
            onClick={() => setModalOpen(true)}
          >
            <ArrowsPointingOutIcon className="h-3.5 w-3.5" aria-hidden />
          </button>
        ) : null}
      </div>

      <Dialog open={modalOpen} onClose={() => setModalOpen(false)} className="relative z-[250]">
        <DialogBackdrop className="fixed inset-0 bg-black/30" />
        <div className="fixed inset-0 flex items-center justify-center p-3 sm:p-6">
          <DialogPanel
            className="flex w-[min(900px,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-2xl"
            data-testid="code-editor-fullscreen"
          >
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <DialogTitle className="text-sm font-semibold text-gray-900">{dialogTitle}</DialogTitle>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="rounded-md p-1.5 text-gray-600 hover:bg-gray-100"
                aria-label="Close"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="ignore-key-press-canvas min-h-0 flex-1 p-3">
              <div className={`${flowMonacoParamShellClass} min-h-0`}>{renderEditor(modalHeight)}</div>
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </>
  );
};
