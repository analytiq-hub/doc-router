import { useParams } from 'react-router-dom'

import Dashboard from '@/components/Dashboard'

export function OrgDashboard() {
  const { organizationId } = useParams()
  if (!organizationId) return null
  return (
    <div className="container mx-auto p-4">
      <Dashboard organizationId={organizationId} />
    </div>
  )
}
