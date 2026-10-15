import { apiClient } from '@/utils/api';

export type OrgPermissionsMeResponse = {
  capabilities: string[];
  permission_group_ids: string[];
  persona: string | null;
};

const inFlight = new Map<string, Promise<OrgPermissionsMeResponse>>();

/** GET /v0/orgs/{id}/permissions/me — deduped in-flight requests per org + token. */
export function fetchOrgPermissionsMe(
  organizationId: string,
  apiAccessToken: string,
): Promise<OrgPermissionsMeResponse> {
  const key = `${organizationId}:${apiAccessToken}`;
  let pending = inFlight.get(key);
  if (!pending) {
    pending = apiClient
      .get<OrgPermissionsMeResponse>(`/v0/orgs/${organizationId}/permissions/me`, {
        headers: { Authorization: `Bearer ${apiAccessToken}` },
      })
      .then((res) => res.data)
      .finally(() => {
        inFlight.delete(key);
      });
    inFlight.set(key, pending);
  }
  return pending;
}
