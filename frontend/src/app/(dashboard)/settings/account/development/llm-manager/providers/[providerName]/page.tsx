'use client'

import React from 'react';
import { useParams } from 'next/navigation';
import SettingsLayout from '@/components/SettingsLayout';
import LLMProviderConfig from '@/components/LLMProviderConfig';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

const ProviderConfigPage: React.FC = () => {
  const params = useParams();
  const providerName = params.providerName as string;

  return (
    <SettingsLayout selectedMenu="system_development">
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <Link 
            href="/settings/account/development/llm-manager"
            className="text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            <ArrowBackIcon className="w-5 h-5" />
            Back to Providers
          </Link>
        </div>
        
        <div>
          <LLMProviderConfig providerName={providerName} />
        </div>
      </div>
    </SettingsLayout>
  );
};

export default ProviderConfigPage;
