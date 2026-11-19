'use client'

import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import LLMModelsConfig from '@/components/LLMModelsConfig';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import { Button } from '@/components/ui/button';

const ModelsPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Button variant="ghost" size="sm" render={<Link to="/settings/account/development/llm-manager" />}>
          <ArrowLeft data-icon="inline-start" />
          Back to providers
        </Button>
      </div>
      <SettingsPageHeader
        title="Language models"
        subtitle="Enable models and set per-model concurrency limits."
      />
      <LLMModelsConfig />
    </div>
  );
};

export default ModelsPage;