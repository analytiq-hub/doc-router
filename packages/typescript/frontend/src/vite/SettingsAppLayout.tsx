import { Outlet } from 'react-router-dom';

import Layout from '@/components/Layout';
import { SettingsApiDocsCallout } from '@/components/SettingsApiDocsCallout';

/** Settings uses the main shell. `Layout` swaps in the settings menu, so pages keep the content width. */
export function SettingsAppLayout() {
  return (
    <Layout>
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-8">
        <Outlet />
        <SettingsApiDocsCallout />
      </div>
    </Layout>
  );
}
