export const BULK_FLOW_RERUN_MODE_KEY = 'docrouter.bulkFlowRerunMode';

export type BulkFlowRerunMode = 'force' | 'incomplete_only';

export function readBulkFlowRerunModeFromSession(): BulkFlowRerunMode {
  if (typeof window === 'undefined') return 'force';
  try {
    const raw = sessionStorage.getItem(BULK_FLOW_RERUN_MODE_KEY);
    return raw === 'incomplete_only' ? 'incomplete_only' : 'force';
  } catch {
    return 'force';
  }
}

export function persistBulkFlowRerunModeToSession(value: BulkFlowRerunMode): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(BULK_FLOW_RERUN_MODE_KEY, value);
  } catch {
    // ignore
  }
}
