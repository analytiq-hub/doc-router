'use client'

import AccessTokenManager from '@/components/AccessTokenManager';

export default function AccessTokensPage() {
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-lg font-semibold text-gray-900 mb-6">Access Tokens</h1>
      <AccessTokenManager />
    </div>
  );
}
