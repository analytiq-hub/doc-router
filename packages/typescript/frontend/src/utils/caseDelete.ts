import { isAxiosError } from 'axios';
import type { DocRouterOrgApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_MS = 300_000;

export type CaseDeleteMode = 'unassign' | 'cascade';

export function isCaseNotFoundError(error: unknown): boolean {
  if (isAxiosError(error) && error.response?.status === 404) {
    return true;
  }
  const msg = getApiErrorMsg(error).toLowerCase();
  return msg.includes('not found') || msg.includes('case not found');
}

/** Poll GET case until 404 (cascade delete in progress on server). */
export async function pollUntilCaseDeleted(
  api: DocRouterOrgApi,
  caseId: string,
  options?: { intervalMs?: number; maxWaitMs?: number },
): Promise<void> {
  const intervalMs = options?.intervalMs ?? POLL_INTERVAL_MS;
  const maxWaitMs = options?.maxWaitMs ?? MAX_POLL_MS;
  const pollStartMs = Date.now();

  while (Date.now() - pollStartMs < maxWaitMs) {
    try {
      await api.getCase({ caseId });
    } catch (error) {
      if (isCaseNotFoundError(error)) {
        return;
      }
      throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('Timed out waiting for the case to finish deleting. Refresh the cases list or try again.');
}

export type CaseDeleteResult = {
  cascade: boolean;
  /** True when the server returned 202 and polling completed. */
  polled: boolean;
};

/** Delete a case; poll when the API returns 202 (cascade). */
export async function deleteCaseAndWait(
  api: DocRouterOrgApi,
  caseId: string,
  mode: CaseDeleteMode,
): Promise<CaseDeleteResult> {
  const cascade = mode === 'cascade';
  const { status } = await api.deleteCaseWithStatus({ caseId, cascade });

  if (cascade && status === 202) {
    await pollUntilCaseDeleted(api, caseId);
    return { cascade: true, polled: true };
  }

  return { cascade, polled: false };
}
