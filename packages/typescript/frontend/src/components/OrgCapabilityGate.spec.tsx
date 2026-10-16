/** @vitest-environment jsdom */
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities';

const useOrgCapabilityMock = vi.fn();
vi.mock('@/hooks/useOrgPermissions', () => ({
  useOrgCapability: (...args: unknown[]) => useOrgCapabilityMock(...args),
}));

const useAppSessionMock = vi.fn();
vi.mock('@/contexts/AppSessionContext', () => ({
  useAppSession: () => useAppSessionMock(),
}));

import { OrgCapabilityGate } from './OrgCapabilityGate';

describe('OrgCapabilityGate', () => {
  beforeEach(() => {
    useOrgCapabilityMock.mockReset();
    useAppSessionMock.mockReturnValue({ session: null });
  });

  it('renders nothing while permissions are loading', () => {
    useOrgCapabilityMock.mockReturnValue({ hasCapability: false, loading: true });
    const { container } = render(
      <OrgCapabilityGate organizationId="org-1" capability={CAP_CONFIG_WRITE}>
        <span>Secret</span>
      </OrgCapabilityGate>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders children when the user has the capability', () => {
    useOrgCapabilityMock.mockReturnValue({ hasCapability: true, loading: false });
    render(
      <OrgCapabilityGate organizationId="org-1" capability={CAP_CONFIG_WRITE}>
        <span>Allowed</span>
      </OrgCapabilityGate>,
    );
    expect(screen.getByText('Allowed')).toBeInTheDocument();
  });

  it('renders fallback when the user lacks the capability', () => {
    useOrgCapabilityMock.mockReturnValue({ hasCapability: false, loading: false });
    const { container } = render(
      <OrgCapabilityGate
        organizationId="org-1"
        capability={CAP_CONFIG_WRITE}
        fallback={<span data-testid="gate-fallback">Denied</span>}
      >
        <span data-testid="gate-child">Builder only</span>
      </OrgCapabilityGate>,
    );
    expect(screen.getByTestId('gate-fallback')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="gate-child"]')).toBeNull();
  });

  it('allows platform sysadmin when allowSysadmin is set', () => {
    useOrgCapabilityMock.mockReturnValue({ hasCapability: false, loading: false });
    useAppSessionMock.mockReturnValue({
      session: { user: { isSysadmin: true } },
    });
    render(
      <OrgCapabilityGate
        organizationId="org-1"
        capability={CAP_CONFIG_WRITE}
        allowSysadmin
        fallback={<span>Denied</span>}
      >
        <span>Support view</span>
      </OrgCapabilityGate>,
    );
    expect(screen.getByText('Support view')).toBeInTheDocument();
  });
});
