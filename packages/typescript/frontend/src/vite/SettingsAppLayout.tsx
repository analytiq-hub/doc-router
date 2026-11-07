import { Outlet } from 'react-router-dom';

import Layout from '@/components/Layout';

/** Match Next root layout: settings pages sit inside the main app chrome, then `SettingsLayout` in each page. */
export function SettingsAppLayout() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}
