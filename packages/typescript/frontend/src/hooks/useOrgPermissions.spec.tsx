/** @vitest-environment jsdom */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CAP_CONFIG_WRITE, CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities';

const replaceMock = vi.fn();
const fetchOrgPermissionsMeMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: vi.fn(),
  }),
}));

vi.mock('@/utils/orgPermissionsMe', () => ({
  fetchOrgPermissionsMe: (...args: unknown[]) => fetchOrgPermissionsMeMock(...args),
}));

const useAppSessionMock = vi.fn();
vi.mock('@/contexts/AppSessionContext', () => ({
  useAppSession: () => useAppSessionMock(),
}));

function sessionFixture(apiAccessToken = 'jwt-token') {
  return {
    session: { user: { id: 'user-1' } },
    status: 'authenticated' as const,
    apiAccessToken,
  };
}

describe('useOrgPermissions', () => {
  beforeEach(() => {
    replaceMock.mockReset();
    fetchOrgPermissionsMeMock.mockReset();
    useAppSessionMock.mockReturnValue(sessionFixture());
  });

  it('is not ready without organizationId', async () => {
    const { useOrgPermissions } = await import('./useOrgPermissions');
    const { result } = renderHook(() => useOrgPermissions(undefined));
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.ready).toBe(false);
    expect(result.current.hasCapability(CAP_CONFIG_WRITE)).toBe(false);
    expect(fetchOrgPermissionsMeMock).not.toHaveBeenCalled();
  });

  it('loads capabilities and exposes hasCapability when ready', async () => {
    fetchOrgPermissionsMeMock.mockResolvedValue({
      capabilities: ['config.read', 'config.write'],
      permission_group_ids: ['builder'],
      persona: 'builder',
    });
    const { useOrgPermissions } = await import('./useOrgPermissions');
    const { result } = renderHook(() => useOrgPermissions('org-abc'));

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });
    expect(result.current.hasCapability(CAP_CONFIG_WRITE)).toBe(true);
    expect(result.current.hasCapability(CAP_DOCUMENTS_WRITE)).toBe(false);
    expect(fetchOrgPermissionsMeMock).toHaveBeenCalledWith('org-abc', 'jwt-token');
  });

  it('hasCapability is false while loading', async () => {
    let resolveFetch: (value: unknown) => void = () => {};
    fetchOrgPermissionsMeMock.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );
    const { useOrgPermissions } = await import('./useOrgPermissions');
    const { result } = renderHook(() => useOrgPermissions('org-abc'));

    expect(result.current.loading).toBe(true);
    expect(result.current.hasCapability(CAP_CONFIG_WRITE)).toBe(false);

    await act(async () => {
      resolveFetch({
        capabilities: ['config.write'],
        permission_group_ids: ['builder'],
        persona: 'builder',
      });
    });
    await waitFor(() => {
      expect(result.current.hasCapability(CAP_CONFIG_WRITE)).toBe(true);
    });
  });
});

describe('useOrgCapabilityRouteGuard', () => {
  beforeEach(() => {
    replaceMock.mockReset();
    fetchOrgPermissionsMeMock.mockReset();
    useAppSessionMock.mockReturnValue(sessionFixture());
  });

  it('redirects when the user lacks the capability', async () => {
    fetchOrgPermissionsMeMock.mockResolvedValue({
      capabilities: ['config.read'],
      permission_group_ids: ['viewer'],
      persona: 'viewer',
    });
    const { useOrgCapabilityRouteGuard } = await import('./useOrgPermissions');
    renderHook(() =>
      useOrgCapabilityRouteGuard('/orgs/org-abc/schemas', 'org-abc', CAP_CONFIG_WRITE),
    );

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/orgs/org-abc/schemas');
    });
  });

  it('does not redirect when the user has the capability', async () => {
    fetchOrgPermissionsMeMock.mockResolvedValue({
      capabilities: ['config.read', 'config.write'],
      permission_group_ids: ['builder'],
      persona: 'builder',
    });
    const { useOrgCapabilityRouteGuard } = await import('./useOrgPermissions');
    renderHook(() =>
      useOrgCapabilityRouteGuard('/orgs/org-abc/schemas', 'org-abc', CAP_CONFIG_WRITE),
    );

    await waitFor(() => {
      expect(fetchOrgPermissionsMeMock).toHaveBeenCalled();
    });
    expect(replaceMock).not.toHaveBeenCalled();
  });
});

describe('useOrgCapabilityTabGuard', () => {
  beforeEach(() => {
    replaceMock.mockReset();
    fetchOrgPermissionsMeMock.mockReset();
    useAppSessionMock.mockReturnValue(sessionFixture());
  });

  it('redirects off a guarded tab when the user lacks write', async () => {
    fetchOrgPermissionsMeMock.mockResolvedValue({
      capabilities: ['documents.read', 'config.read'],
      permission_group_ids: ['viewer'],
      persona: 'viewer',
    });
    const { useOrgCapabilityTabGuard } = await import('./useOrgPermissions');
    renderHook(() =>
      useOrgCapabilityTabGuard(
        'org-abc',
        'case-create',
        'case-create',
        '/orgs/org-abc/cases',
        CAP_DOCUMENTS_WRITE,
      ),
    );

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/orgs/org-abc/cases');
    });
  });

  it('does not redirect when tab is not guarded', async () => {
    fetchOrgPermissionsMeMock.mockResolvedValue({
      capabilities: ['documents.read'],
      permission_group_ids: ['viewer'],
      persona: 'viewer',
    });
    const { useOrgCapabilityTabGuard } = await import('./useOrgPermissions');
    renderHook(() =>
      useOrgCapabilityTabGuard(
        'org-abc',
        'cases',
        'case-create',
        '/orgs/org-abc/cases',
        CAP_DOCUMENTS_WRITE,
      ),
    );

    await waitFor(() => {
      expect(fetchOrgPermissionsMeMock).toHaveBeenCalled();
    });
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
