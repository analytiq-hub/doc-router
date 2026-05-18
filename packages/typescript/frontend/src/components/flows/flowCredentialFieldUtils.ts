import type { FlowCredentialKindSummary } from '@docrouter/sdk';

export type CredentialFieldRow = {
  name: string;
  title?: string;
  description?: string;
  type?: string;
  is_secret?: boolean;
};

/** Mask shown for stored secrets (value is not sent on save while unchanged). */
export const CREDENTIAL_SECRET_MASK = '••••••••';

export function credentialFieldRows(kind: FlowCredentialKindSummary | null): CredentialFieldRow[] {
  if (!kind?.fields?.length) return [];
  return kind.fields.map((f) => {
    const name = typeof f.name === 'string' ? f.name : '';
    const title = typeof f.title === 'string' ? f.title : undefined;
    const description = typeof f.description === 'string' ? f.description : undefined;
    const type = typeof f.type === 'string' ? f.type : undefined;
    const is_secret = f.is_secret === true;
    return { name, title, description, type, is_secret };
  });
}

export function credentialFieldValueForSubmit(
  f: CredentialFieldRow,
  raw: string,
  options?: { omitSecret?: boolean },
): unknown | undefined {
  if (options?.omitSecret && f.is_secret) return undefined;
  const v = raw ?? '';
  if (f.type === 'boolean') {
    const s = v.trim().toLowerCase();
    if (s === '' || s === 'false' || s === '0' || s === 'no' || s === 'off') return false;
    if (s === 'true' || s === '1' || s === 'yes' || s === 'on') return true;
    return Boolean(v);
  }
  if (f.type === 'integer') {
    const s = v.trim();
    if (!s) return 0;
    const n = Number(s);
    return Number.isFinite(n) ? Math.trunc(n) : v;
  }
  if (f.type === 'number') {
    const s = v.trim();
    if (!s) return 0;
    const n = Number(s);
    return Number.isFinite(n) ? n : v;
  }
  return v;
}

export function credentialFieldDisplayValue(f: CredentialFieldRow, pub: unknown): string {
  if (pub === undefined || pub === null) return '';
  if (f.type === 'boolean') return pub === true ? 'true' : pub === false ? 'false' : String(pub);
  return String(pub);
}

export function isCredentialSecretMaskValue(value: string): boolean {
  return value === CREDENTIAL_SECRET_MASK || value === '********';
}
