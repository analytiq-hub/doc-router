'use client';

import React, { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { XMarkIcon } from '@heroicons/react/24/outline';
import type { FlowHeader } from '@docrouter/sdk';
import { flowInputClass, flowLabelClass } from './flowUiClasses';

const btnSecondary =
  'rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';
const btnPrimary =
  'rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50';

export type FlowToolSettingsValue = {
  callable_as_tool: boolean;
  tool_description: string;
};

type FlowToolSettingsModalProps = {
  open: boolean;
  flow: Pick<FlowHeader, 'callable_as_tool' | 'tool_description'>;
  readOnly?: boolean;
  busy?: boolean;
  onClose: () => void;
  onSave: (next: FlowToolSettingsValue) => void | Promise<void>;
};

const FlowToolSettingsModal: React.FC<FlowToolSettingsModalProps> = ({
  open,
  flow,
  readOnly = false,
  busy = false,
  onClose,
  onSave,
}) => {
  const [callable, setCallable] = useState(false);
  const [toolDescription, setToolDescription] = useState('');

  useEffect(() => {
    if (!open) return;
    setCallable(Boolean(flow.callable_as_tool));
    setToolDescription(flow.tool_description ?? '');
  }, [flow.callable_as_tool, flow.tool_description, open]);

  const applySave = () => {
    void onSave({
      callable_as_tool: callable,
      tool_description: toolDescription.trim(),
    });
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent showCloseButton={false} className="z-[120] gap-0 overflow-hidden p-0 sm:max-w-lg">
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
            <DialogTitle className="text-base font-semibold text-gray-900">Tool flow settings</DialogTitle>
            <button
              type="button"
              className="rounded-md p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              aria-label="Close"
              onClick={onClose}
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>

          <div className="space-y-4 px-4 py-4">
            <p className="text-sm text-gray-600">
              Callable flows can be invoked from a Flow Tool node in another workflow. They must include a Sub-flow
              entry trigger; the last executed node&apos;s output is returned to the caller.
            </p>

            <div className="flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
              <span className="text-sm text-gray-800">Callable as tool</span>
              <Switch
                checked={callable}
                onCheckedChange={setCallable}
                disabled={readOnly || busy}
              />
            </div>

            <div>
              <label className={flowLabelClass} htmlFor="flow-tool-description">
                Tool description
              </label>
              <textarea
                id="flow-tool-description"
                className={`${flowInputClass} min-h-[96px] resize-y`}
                value={toolDescription}
                readOnly={readOnly || busy}
                placeholder="Describe what this flow does when used as a tool"
                onChange={(e) => setToolDescription(e.target.value)}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 border-t border-gray-200 px-4 py-3">
            <button type="button" className={btnSecondary} onClick={onClose} disabled={busy}>
              Cancel
            </button>
            {!readOnly ? (
              <button type="button" className={btnPrimary} onClick={applySave} disabled={busy}>
                {busy ? 'Saving…' : 'Save'}
              </button>
            ) : null}
          </div>
      </DialogContent>
    </Dialog>
  );
};

export default FlowToolSettingsModal;
