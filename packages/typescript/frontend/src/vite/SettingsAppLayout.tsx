import { Outlet } from 'react-router-dom';

import Layout from '@/components/Layout';

/** Settings uses the main shell. `Layout` swaps in the settings menu, so pages keep the content width. */
export function SettingsAppLayout() {
  return (
    <Layout>
      <div className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </div>
    </Layout>
  );
}
