'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import LLMModelsConfig from '@/components/LLMModelsConfig';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

const ModelsPage: React.FC = () => {
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
          <h2 className="text-xl font-semibold mb-4">Language Models Configuration</h2>
          <LLMModelsConfig />
        </div>
      </div>
    </SettingsLayout>
  );
};

export default ModelsPage;
