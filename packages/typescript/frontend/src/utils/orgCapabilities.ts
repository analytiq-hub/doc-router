/** Org capability names (phase 3) — aligned with backend `analytiq_data.org_permissions`. */

export const CAP_DOCUMENTS_READ = 'documents.read';
export const CAP_DOCUMENTS_WRITE = 'documents.write';
export const CAP_RUNS_EXECUTE = 'runs.execute';
export const CAP_CONFIG_READ = 'config.read';
export const CAP_CONFIG_WRITE = 'config.write';
export const CAP_ORG_ADMIN = 'org.admin';

export type OrgCapability =
  | typeof CAP_DOCUMENTS_READ
  | typeof CAP_DOCUMENTS_WRITE
  | typeof CAP_RUNS_EXECUTE
  | typeof CAP_CONFIG_READ
  | typeof CAP_CONFIG_WRITE
  | typeof CAP_ORG_ADMIN;

export function hasOrgCapability(
  capabilities: readonly string[] | null | undefined,
  capability: OrgCapability,
): boolean {
  return (capabilities ?? []).includes(capability);
}
