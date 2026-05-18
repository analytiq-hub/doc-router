import type { DocRouterOrgApi } from '@/utils/api';

/** Dynamic route `/orgs/.../flows/[flowId]` before persistence (no `POST /flows` yet). */
export const NEW_FLOW_URL_SEGMENT = 'new';

/**
 * Default credential label (n8n-style): kind display name with common suffixes stripped + ` account`.
 * e.g. `Gmail OAuth2 API` → `Gmail account`.
 */
export function defaultCredentialAccountName(kindDisplayName: string): string {
  let base = kindDisplayName.trim();
  for (const suffix of [' OAuth2 API', ' OAuth2', ' API']) {
    if (base.endsWith(suffix)) {
      base = base.slice(0, -suffix.length).trim();
      break;
    }
  }
  const label = base || kindDisplayName.trim();
  return `${label} account`;
}

/** Case-insensitive first free display name: `base`, then `base 2`, `base 3`, … */
export function nextSequentialDisplayName(takenLower: ReadonlySet<string>, baseDisplay: string): string {
  const base = baseDisplay.trim();
  const baseLower = base.toLowerCase();
  if (!baseLower) return `Untitled ${Date.now()}`;
  if (!takenLower.has(baseLower)) return base;
  for (let i = 2; i <= 9999; i++) {
    const cand = `${base} ${i}`;
    if (!takenLower.has(cand.toLowerCase())) return cand;
  }
  return `${base} ${Date.now()}`;
}

export async function loadFlowNamesTakenLower(api: DocRouterOrgApi): Promise<Set<string>> {
  const taken = new Set<string>();
  let offset = 0;
  const limit = 200;
  for (;;) {
    const res = await api.listFlows({ limit, offset, includeUnsaved: true });
    for (const it of res.items) taken.add((it.flow?.name ?? '').trim().toLowerCase());
    offset += res.items.length;
    if (res.items.length === 0 || offset >= res.total) break;
  }
  return taken;
}

export async function loadCredentialNamesTakenLower(api: DocRouterOrgApi): Promise<Set<string>> {
  const taken = new Set<string>();
  let offset = 0;
  const limit = 200;
  for (;;) {
    const res = await api.listFlowCredentials({ limit, offset });
    for (const it of res.items) taken.add((it.name ?? '').trim().toLowerCase());
    offset += res.items.length;
    if (res.items.length === 0 || offset >= res.total) break;
  }
  return taken;
}
