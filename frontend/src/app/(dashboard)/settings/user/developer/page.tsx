'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import Link from 'next/link';
import { Button } from '@mui/material';

const DeveloperPage: React.FC = () => {
  const apiUrl = `${process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL || 'http://localhost:8000'}/docs`;
  
  return (
    <SettingsLayout selectedMenu="user_developer">
      <div className="space-y-6">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-xl font-semibold">Account Tokens</h2>
            <p className="text-gray-600 mb-2">
              Use Acccess Tokens to authenticate with our account API.
            </p>
          </div>
          <Link href="/settings/user/developer/account-access-tokens" passHref>
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-xl font-semibold">Organization Tokens</h2>
            <p className="text-gray-600 mb-2">
              Use Organization Tokens to authenticate with our organization API.
            </p>
          </div>
          <Link href="/settings/user/developer/organization-access-tokens" passHref>
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <div className="bg-blue-50 rounded-lg shadow p-4">
          <div className="space-y-2 text-blue-900">
            <p>
              The complete API documentation is available at:
            </p>
            <p>
              <a 
                href={apiUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-blue-700"
              >
                <code className="bg-blue-100 px-1.5 py-0.5 rounded font-mono text-sm">
                  {apiUrl}
                </code>
              </a>
            </p>
          </div>
        </div>
      </div>
    </SettingsLayout>
  );
};

export default DeveloperPage;
