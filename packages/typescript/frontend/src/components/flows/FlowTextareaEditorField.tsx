'use client';

import React, { useState } from 'react';
import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react';
import { ArrowsPointingOutIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { flowInputClass } from './flowUiClasses';

const expandButtonClass =
  'absolute bottom-px right-px z-10 cursor-pointer rounded-tl border border-b-0 border-r-0 border-gray-300 bg-white p-1 text-gray-500 hover:text-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-400/30';

type FlowTextareaEditorFieldProps = {
  value: string;
  label: string;
  placeholder?: string;
  readOnly?: boolean;
  minHeightClass?: string;
  onChange: (value: string) => void;
};

/** Multiline text field with an expanded editor dialog (same affordance as the code editor). */
export function FlowTextareaEditorField({
  value,
  label,
  placeholder,
  readOnly = false,
  minHeightClass = 'min-h-[120px]',
  onChange,
}: FlowTextareaEditorFieldProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const textareaClass = `${flowInputClass} ${minHeightClass} resize-y font-mono text-[11px]`;

  const renderTextarea = (rows?: number, className?: string) => (
    <textarea
      className={className ?? textareaClass}
      placeholder={placeholder}
      value={value}
      readOnly={readOnly}
      rows={rows}
      onChange={(e) => {
        if (readOnly) return;
        onChange(e.target.value);
      }}
    />
  );

  return (
    <>
      <div className="relative">
        {!modalOpen ? (
          renderTextarea()
        ) : (
          <div
            className={`${textareaClass} flex cursor-default items-center justify-center text-xs text-gray-500`}
          >
            Editing in expanded window…
          </div>
        )}
        <button
          type="button"
          className={expandButtonClass}
          aria-label={`Open expanded editor for ${label}`}
          title="Open expanded editor"
          data-testid="textarea-editor-fullscreen-button"
          onClick={() => setModalOpen(true)}
        >
          <ArrowsPointingOutIcon className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      <Dialog open={modalOpen} onClose={() => setModalOpen(false)} className="relative z-[250]">
        <DialogBackdrop className="fixed inset-0 bg-black/30" />
        <div className="fixed inset-0 flex items-center justify-center p-3 sm:p-6">
          <DialogPanel
            className="flex w-[min(720px,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-2xl"
            data-testid="textarea-editor-fullscreen"
          >
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <DialogTitle className="text-sm font-semibold text-gray-900">Edit {label}</DialogTitle>
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
              {renderTextarea(16, `${textareaClass} min-h-[min(480px,calc(100vh-12rem))] w-full`)}
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </>
  );
}
