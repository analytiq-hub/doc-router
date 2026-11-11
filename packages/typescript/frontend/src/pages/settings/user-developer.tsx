'use client'

import React from 'react';
import SettingsLayout, { settingsSectionTitleClass, settingsDescriptionClass } from '@/components/SettingsLayout';
import { Link } from 'react-router-dom';
import { Button } from '@mui/material';
import { fastApiBrowserBase } from '@/utils/api';

const DeveloperPage: React.FC = () => {
  const apiUrl = `${fastApiBrowserBase()}/docs`;
  
  return (
    <SettingsLayout selectedMenu="user_developer">
      <div className="space-y-6">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className={settingsSectionTitleClass}>Account Tokens</h2>
            <p className={`${settingsDescriptionClass} mb-2`}>
              Use Acccess Tokens to authenticate with our account API.
            </p>
          </div>
          <Link to="/settings/user/developer/account-access-tokens">
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className={settingsSectionTitleClass}>Organization Tokens</h2>
            <p className={`${settingsDescriptionClass} mb-2`}>
              Use Organization Tokens to authenticate with our organization API.
            </p>
          </div>
          <Link to="/settings/user/developer/organization-access-tokens">
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className={settingsSectionTitleClass}>Webhook</h2>
            <p className={`${settingsDescriptionClass} mb-2`}>
              Configure a per-organization webhook and view delivery history.
            </p>
          </div>
          <Link to="/settings/user/developer/organization-webhooks">
            <Button variant="contained" color="primary">
              Manage
            </Button>
          </Link>
        </div>

        <div className="bg-primary-50 rounded-lg shadow p-4">
          <div className="space-y-2 text-primary-900">
            <p>
              The complete API documentation is available at:
            </p>
            <p>
              <a 
                href={apiUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary-700"
              >
                <code className="bg-primary-100 px-1.5 py-0.5 rounded font-mono text-sm">
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
