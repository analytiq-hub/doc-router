'use client'

import React from 'react';
import { Link } from 'react-router-dom';
import { List } from 'lucide-react';

import LLMManager from '@/components/LLMManager';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import { Button } from '@/components/ui/button';

const LLMManagerPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader
        title="LLM"
        subtitle="Enable providers and manage API keys."
        actions={
          <Button variant="secondary" render={<Link to="/settings/account/development/llm-manager/models" />}>
            <List data-icon="inline-start" />
            View all models
          </Button>
        }
      />
      <LLMManager />
    </div>
  );
};

export default LLMManagerPage;