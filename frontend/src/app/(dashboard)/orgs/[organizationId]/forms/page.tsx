'use client'

import React from 'react';
import FormList from '@/components/FormList';
import { useRouter } from 'next/navigation';

export default function FormsPage({ params }: { params: { organizationId: string } }) {
  const router = useRouter();

  const handleCreateForm = () => {
    router.push(`/orgs/${params.organizationId}/forms/create`);
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Forms</h1>
        <button
          onClick={handleCreateForm}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          data-tour="form-create"
        >
          Create Form
        </button>
      </div>

      <div className="max-w-6xl mx-auto">
        <FormList organizationId={params.organizationId} />
      </div>
    </div>
  );
}
