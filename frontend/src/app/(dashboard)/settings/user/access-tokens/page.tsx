'use client'

import AccessTokenManager from '@/components/AccessTokenManager';

export default function AccessTokensPage() {
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Access Tokens</h1>
      <AccessTokenManager />
    </div>
  );
}
