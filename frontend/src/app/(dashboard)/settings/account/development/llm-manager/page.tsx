'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import LLMManager from '@/components/LLMManager';
import Link from 'next/link';
import ViewListIcon from '@mui/icons-material/ViewList';

const LLMManagerPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold">LLM Management</h2>
          <Link 
            href="/settings/account/development/llm-manager/models"
            className="text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            <ViewListIcon className="w-5 h-5" />
            View All Models
          </Link>
        </div>
        <LLMManager />
      </div>
    </SettingsLayout>
  );
};

export default LLMManagerPage;
