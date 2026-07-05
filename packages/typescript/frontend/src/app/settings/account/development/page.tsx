'use client'

import React from 'react';
import Link from 'next/link';
import { Button, Divider } from '@mui/material';
import SettingsLayout, { settingsSectionTitleClass, settingsDescriptionClass } from '@/components/SettingsLayout';

const DevelopmentSettingsPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div className="space-y-6">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className={settingsSectionTitleClass}>LLM Configuration</h2>
            <p className={`${settingsDescriptionClass} mb-2`}>
              Manage your Large Language Models and their API tokens.
            </p>
          </div>
          <Link href="/settings/account/development/llm-manager" passHref>
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <Divider />

        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className={settingsSectionTitleClass}>AWS Setup</h2>
            <p className={`${settingsDescriptionClass} mb-2`}>
              Configure AWS access key ID, secret access key, and S3 bucket name.
            </p>
          </div>
          <Link href="/settings/account/development/aws-config" passHref>
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <Divider />

        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className={settingsSectionTitleClass}>GCP Setup</h2>
            <p className={`${settingsDescriptionClass} mb-2`}>
              Upload the Google Cloud service account JSON key for Vertex AI.
            </p>
          </div>
          <Link href="/settings/account/development/gcp-config" passHref>
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <Divider />

        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className={settingsSectionTitleClass}>Azure Setup</h2>
            <p className={`${settingsDescriptionClass} mb-2`}>
              Configure Microsoft Entra service principal (tenant, client ID, client secret) and Microsoft Foundry service API base.
            </p>
          </div>
          <Link href="/settings/account/development/azure-config" passHref>
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <Divider />

        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className={settingsSectionTitleClass}>Worker Settings</h2>
            <p className={`${settingsDescriptionClass} mb-2`}>
              Configure deployment-wide OCR concurrency limits for queue workers.
            </p>
          </div>
          <Link href="/settings/account/development/worker-settings" passHref>
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
