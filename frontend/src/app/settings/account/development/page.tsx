'use client'

import React from 'react';
import Link from 'next/link';
import { Button, Divider } from '@mui/material';
import SettingsLayout from '@/components/SettingsLayout';

const DevelopmentSettingsPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div className="space-y-6">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-xl font-semibold">LLM tokens</h2>
            <p className="text-gray-600 mb-2">
              Manage your Large Language Model (LLM) API tokens.
            </p>
          </div>
          <Link href="/settings/account/development/llm-tokens" passHref>
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <Divider />

        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-xl font-semibold">AWS Credentials</h2>
            <p className="text-gray-600 mb-2">
              Configure your AWS access keys.
            </p>
          </div>
          <Link href="/settings/account/development/aws-credentials" passHref>
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>
      </div>
    </SettingsLayout>
  );
};

export default DevelopmentSettingsPage;
