import React from 'react';

const FlowStatusBadge: React.FC<{ active: boolean }> = ({ active }) => {
  const cls = active ? 'bg-green-100 text-green-800 border-green-200' : 'bg-gray-100 text-gray-700 border-gray-200';
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border ${cls}`}>
      {active ? 'Active' : 'Inactive'}
    </span>
  );
};

export default FlowStatusBadge;

