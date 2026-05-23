'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { flowInputClass, flowLabelClass } from './flowUiClasses';
import {
  buildFlowTimezoneOptions,
  browserTimezone,
  filterFlowTimezoneOptions,
  FLOW_TIMEZONE_DEFAULT,
  flowTimezoneForPersist,
  flowTimezoneLabel,
  storedFlowTimezone,
} from './flowTimezone';

const btnSecondary =
  'rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';
const btnPrimary =
  'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50';

export type FlowSettingsValue = {
  timezone?: string;
};

type FlowSettingsModalProps = {
  open: boolean;
  settings: FlowSettingsValue;
  readOnly?: boolean;
  onClose: () => void;
  onSave: (next: FlowSettingsValue) => void;
};

const FlowSettingsModal: React.FC<FlowSettingsModalProps> = ({
  open,
  settings,
  readOnly = false,
  onClose,
  onSave,
}) => {
  const [draftTimezone, setDraftTimezone] = useState(FLOW_TIMEZONE_DEFAULT);
  const [query, setQuery] = useState('');
  const [listOpen, setListOpen] = useState(false);

  const browserDefault = useMemo(() => browserTimezone(), [open]);

  useEffect(() => {
    if (!open) return;
    setDraftTimezone(storedFlowTimezone(settings, browserDefault));
    setQuery('');
    setListOpen(false);
  }, [open, settings, browserDefault]);

  const options = useMemo(() => buildFlowTimezoneOptions(browserDefault), [browserDefault]);
  const filtered = useMemo(() => filterFlowTimezoneOptions(options, query), [options, query]);
  const selectedLabel = flowTimezoneLabel(draftTimezone, browserDefault);

  const applySave = () => {
    onSave({ timezone: flowTimezoneForPersist(draftTimezone, browserDefault) });
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} className="relative z-[120]">
      <DialogBackdrop className="fixed inset-0 bg-black/30" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel className="flex w-full max-w-lg flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
            <DialogTitle className="text-base font-semibold text-gray-900">Flow settings</DialogTitle>
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
              Schedule triggers run in this timezone. Default uses your browser timezone (
              {flowTimezoneLabel(browserDefault, browserDefault)}). Cron and interval rules are interpreted in local
              wall time for the selected zone.
            </p>

            <div className="relative">
              <label className={flowLabelClass} htmlFor="flow-settings-timezone">
                Timezone
              </label>
              <input
                id="flow-settings-timezone"
                className={flowInputClass}
                value={listOpen ? query : selectedLabel}
                readOnly={readOnly}
                placeholder={flowTimezoneLabel(FLOW_TIMEZONE_DEFAULT, browserDefault)}
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
                aria-controls="flow-settings-timezone-list"
              />
              {listOpen && !readOnly ? (
                <ul
                  id="flow-settings-timezone-list"
                  className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-md border border-gray-200 bg-white py-1 text-sm shadow-lg"
                  role="listbox"
                >
                  {filtered.length === 0 ? (
                    <li className="px-3 py-2 text-gray-500">No matching timezones</li>
                  ) : (
                    filtered.map((opt) => (
                      <li key={opt.key}>
                        <button
                          type="button"
                          className={`block w-full px-3 py-2 text-left hover:bg-gray-100 ${
                            opt.key === draftTimezone ? 'bg-blue-50 font-medium text-blue-900' : 'text-gray-900'
                          }`}
                          role="option"
                          aria-selected={opt.key === draftTimezone}
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => {
                            setDraftTimezone(opt.key);
                            setQuery('');
                            setListOpen(false);
                          }}
                        >
                          {opt.label}
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              ) : null}
            </div>
          </div>

          <div className="flex justify-end gap-2 border-t border-gray-200 px-4 py-3">
            <button type="button" className={btnSecondary} onClick={onClose}>
              Cancel
            </button>
            {!readOnly ? (
              <button type="button" className={btnPrimary} onClick={applySave}>
                Save
              </button>
            ) : null}
          </div>
        </DialogPanel>
      </div>
    </Dialog>
  );
};

export default FlowSettingsModal;
