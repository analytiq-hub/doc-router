'use client'

import React from 'react';
import Dashboard from '@/components/Dashboard';

const DashboardPage: React.FC<{ params: { organizationId: string } }> = ({ params }) => {
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-xl font-bold mb-4">File Dashboard</h1>
      <Dashboard organizationId={params.organizationId} />
    </div>
  );
};

export default DashboardPage;
