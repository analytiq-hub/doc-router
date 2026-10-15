'use client';

import React from 'react';
import { toast, type ToastOptions } from 'react-toastify';
import { getApiErrorMsg } from '@/utils/api';

export function ActionErrorToastContent({
  action,
  error,
}: {
  action: string;
  error: unknown;
}) {
  const detail = getApiErrorMsg(error);
  return (
    <div className="flex flex-col gap-0.5 text-left leading-snug whitespace-normal">
      <span className="font-medium">{action}</span>
      <span className="text-sm italic opacity-90">{detail}</span>
    </div>
  );
}

export function toastActionError(
  action: string,
  error: unknown,
  options?: ToastOptions,
) {
  toast.error(<ActionErrorToastContent action={action} error={error} />, options);
}
