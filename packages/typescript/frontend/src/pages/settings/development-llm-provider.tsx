'use client'

import React from 'react';
import { useParams } from '@/utils/appRouter';
import SettingsLayout from '@/components/SettingsLayout';
import LLMProviderConfig from '@/components/LLMProviderConfig';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

const ProviderConfigPage: React.FC = () => {
  const params = useParams();
  const providerName = params.providerName as string;

  return (
    <SettingsLayout selectedMenu="system_development">
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <Link 
            to="/settings/account/development/llm-manager"
            className="text-primary-600 hover:text-primary-800 flex items-center gap-1"
          >
            <ArrowLeft className="size-5" />
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
