'use client';

import { toast } from 'sonner';
import { getApiErrorMsg } from '@/utils/api';

export function toastActionError(action: string, error: unknown) {
  const detail = getApiErrorMsg(error);
  toast.error(action, { description: detail });
}
