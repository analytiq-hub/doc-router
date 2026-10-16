import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();

vi.mock('@/utils/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => getMock(...args),
  },
}));

describe('fetchOrgPermissionsMe', () => {
  beforeEach(() => {
    getMock.mockReset();
    vi.resetModules();
  });

  afterEach(() => {
    vi.resetModules();
  });

  it('calls permissions/me with Bearer token', async () => {
    getMock.mockResolvedValue({
      data: {
        capabilities: ['config.read'],
        permission_group_ids: ['viewer'],
        persona: 'viewer',
      },
    });
    const { fetchOrgPermissionsMe } = await import('./orgPermissionsMe');
    const data = await fetchOrgPermissionsMe('org-1', 'token-abc');
    expect(data.capabilities).toEqual(['config.read']);
    expect(getMock).toHaveBeenCalledWith('/v0/orgs/org-1/permissions/me', {
      headers: { Authorization: 'Bearer token-abc' },
    });
  });

  it('dedupes in-flight requests for the same org and token', async () => {
    let resolveGet: (value: unknown) => void = () => {};
    const pending = new Promise((resolve) => {
      resolveGet = resolve;
    });
    getMock.mockReturnValue(
      pending.then(() => ({
        data: {
          capabilities: ['documents.read'],
          permission_group_ids: ['viewer'],
          persona: 'viewer',
        },
      })),
    );

    const { fetchOrgPermissionsMe } = await import('./orgPermissionsMe');
    const first = fetchOrgPermissionsMe('org-2', 'same-token');
    const second = fetchOrgPermissionsMe('org-2', 'same-token');
    resolveGet(undefined);
    const [a, b] = await Promise.all([first, second]);
    expect(a).toEqual(b);
    expect(getMock).toHaveBeenCalledTimes(1);
  });

  it('does not dedupe when the access token differs', async () => {
    getMock.mockResolvedValue({
      data: { capabilities: [], permission_group_ids: [], persona: null },
    });
    const { fetchOrgPermissionsMe } = await import('./orgPermissionsMe');
    await fetchOrgPermissionsMe('org-3', 'token-a');
    await fetchOrgPermissionsMe('org-3', 'token-b');
    expect(getMock).toHaveBeenCalledTimes(2);
  });
});
