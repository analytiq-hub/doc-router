'use client'

import { use } from 'react';
import Dashboard from '@/components/Dashboard';

const DashboardPage: React.FC<{ params: Promise<{ organizationId: string }> }> = ({ params }) => {
  const { organizationId } = use(params);
  return (
    <div className="container mx-auto p-4">
      <Dashboard organizationId={organizationId} />
    </div>
  );
};

export default DashboardPage;
