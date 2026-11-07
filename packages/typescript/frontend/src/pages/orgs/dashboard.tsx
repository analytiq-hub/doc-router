'use client'

import Dashboard from '@/components/Dashboard';
import { useRouteParams } from '@/utils/useRouteParams';

const DashboardPage: React.FC<{ params: Promise<{ organizationId: string }> }> = (props) => {
  const { organizationId } = useRouteParams(props);
  return (
    <div className="container mx-auto p-4">
      <Dashboard organizationId={organizationId} />
    </div>
  );
};

export default DashboardPage;
