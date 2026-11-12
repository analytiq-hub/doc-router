'use client'

import React from 'react'
import { Link } from 'react-router-dom'

import SettingsLayout, { settingsDescriptionClass, settingsSectionTitleClass } from '@/components/SettingsLayout'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

const DevelopmentSettingsPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div className="space-y-6">
        {[
          {
            title: 'LLM configuration',
            description: 'Manage your Large Language Models and their API tokens.',
            href: '/settings/account/development/llm-manager',
          },
          {
            title: 'AWS setup',
            description: 'Configure AWS access key ID, secret access key, and S3 bucket name.',
            href: '/settings/account/development/aws-config',
          },
          {
            title: 'GCP setup',
            description: 'Upload the Google Cloud service account JSON key for Vertex AI.',
            href: '/settings/account/development/gcp-config',
          },
          {
            title: 'Azure setup',
            description:
              'Configure Microsoft Entra service principal and Microsoft Foundry service API base.',
            href: '/settings/account/development/azure-config',
          },
          {
            title: 'Worker settings',
            description: 'Configure deployment-wide OCR concurrency limits for queue workers.',
            href: '/settings/account/development/worker-settings',
          },
        ].map((section, index) => (
          <React.Fragment key={section.href}>
            {index > 0 ? <Separator /> : null}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className={settingsSectionTitleClass}>{section.title}</h2>
                <p className={`${settingsDescriptionClass} mb-0`}>{section.description}</p>
              </div>
              <Button type="button" render={<Link to={section.href} />}>
                Manage
              </Button>
            </div>
          </React.Fragment>
        ))}
      </div>
    </SettingsLayout>
  )
}

export default DevelopmentSettingsPage
