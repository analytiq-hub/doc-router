import { useParams } from 'react-router-dom'

import Dashboard from '@/components/Dashboard'
import { OrgPageContainer } from '@/components/OrgPageContainer'

export function OrgDashboard() {
  const { organizationId } = useParams()
  if (!organizationId) return null
  return (
    <OrgPageContainer>
      <Dashboard organizationId={organizationId} />
    </OrgPageContainer>
  )
}
