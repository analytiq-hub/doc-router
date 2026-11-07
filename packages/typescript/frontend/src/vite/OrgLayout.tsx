import { Outlet } from 'react-router-dom'

import Layout from '@/components/Layout'

/** Org chrome with nested routes (doc-orchestrator Layout + Outlet pattern). */
export function OrgLayout() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  )
}
