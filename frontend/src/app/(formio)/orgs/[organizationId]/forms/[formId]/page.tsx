'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import FormCreate from '@/components/FormCreate';

export default function FormEditPage() {
  const { organizationId, formId } = useParams();
  const router = useRouter();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => router.push(`/orgs/${organizationId}/forms`)}
              className="px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-md"
            >
              ← Back to Forms
            </button>
            <h1 className="text-lg font-semibold text-gray-900">
              Edit Form
            </h1>
          </div>
        </div>
      </div>

      {/* Form Edit Content */}
      <div className="p-4">
        <FormCreate organizationId={organizationId as string} formId={formId as string} />
      </div>
    </div>
  );
} 