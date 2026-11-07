import { Outlet } from 'react-router-dom';

import Layout from '@/components/Layout';
import FormioProvider from '@/components/FormioProvider';

/** Org chrome; Formio only under org routes (not settings/home). */
export function OrgLayout() {
  return (
    <FormioProvider>
      <Layout>
        <Outlet />
      </Layout>
    </FormioProvider>
  );
}
