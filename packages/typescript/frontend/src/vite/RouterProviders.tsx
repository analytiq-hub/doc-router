import { Outlet } from 'react-router-dom';
import { OrganizationProvider } from '@/contexts/OrganizationContext';
import FormioProvider from '@/components/FormioProvider';

/** Must render inside `RouterProvider` (uses `next/navigation` shim → `useLocation`). */
export function RouterProviders() {
  return (
    <OrganizationProvider>
      <FormioProvider>
        <Outlet />
      </FormioProvider>
    </OrganizationProvider>
  );
}
