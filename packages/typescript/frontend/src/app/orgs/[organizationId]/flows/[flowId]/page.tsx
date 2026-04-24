'use client'

import { use } from 'react';
import Link from 'next/link';

export default function FlowDetailPage({
  params,
}: {
  params: Promise<{ organizationId: string; flowId: string }>;
}) {
  const { organizationId, flowId } = use(params);

  return (
    <div className="p-4">
      <div className="max-w-4xl mx-auto">
        <div className="mb-4">
          <Link
            href={`/orgs/${organizationId}/flows`}
            className="text-sm text-blue-600 hover:text-blue-700"
            prefetch={false}
          >
            ← Back to flows
          </Link>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="text-lg font-semibold">Flow</div>
          <div className="text-sm text-gray-600 mt-1">
            This page is the editor shell. Phase 2 will add the canvas + executions tabs.
          </div>
          <div className="mt-4 text-sm">
            <div>
              <span className="font-medium">Flow ID:</span> {flowId}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

