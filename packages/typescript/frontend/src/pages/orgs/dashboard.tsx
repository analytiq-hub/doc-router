'use client'

import Dashboard from '@/components/Dashboard';
import { OrgPageContainer } from '@/components/OrgPageContainer';
import { useRouteParams } from '@/utils/useRouteParams';

const DashboardPage: React.FC<{ params: Promise<{ organizationId: string }> }> = (props) => {
  const { organizationId } = useRouteParams(props);
  return (
    <OrgPageContainer>
      <Dashboard organizationId={organizationId} />
    </OrgPageContainer>
  );
};

export default DashboardPage;
