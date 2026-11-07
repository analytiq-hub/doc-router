import { Outlet } from 'react-router-dom';

import { OrganizationProvider } from '@/contexts/OrganizationContext';

/** Session-level providers; Formio mounts under `OrgLayout` only. */
export function RouterProviders() {
  return (
    <OrganizationProvider>
      <Outlet />
    </OrganizationProvider>
  );
}
