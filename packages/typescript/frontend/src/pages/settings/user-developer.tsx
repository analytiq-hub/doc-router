'use client'

import React from 'react'
import { Link } from 'react-router-dom'

import SettingsLayout, { settingsDescriptionClass, settingsSectionTitleClass } from '@/components/SettingsLayout'
import { Button } from '@/components/ui/button'
import { fastApiBrowserBase } from '@/utils/api'

const DeveloperPage: React.FC = () => {
  const apiUrl = `${fastApiBrowserBase()}/docs`

  const sections = [
    {
      title: 'Account tokens',
      description: 'Use access tokens to authenticate with our account API.',
      href: '/settings/user/developer/account-access-tokens',
    },
    {
      title: 'Organization tokens',
      description: 'Use organization tokens to authenticate with our organization API.',
      href: '/settings/user/developer/organization-access-tokens',
    },
    {
      title: 'Webhook',
      description: 'Configure a per-organization webhook and view delivery history.',
      href: '/settings/user/developer/organization-webhooks',
    },
  ]

  return (
    <SettingsLayout selectedMenu="user_developer">
      <div className="space-y-6">
        {sections.map((section) => (
          <div key={section.href} className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className={settingsSectionTitleClass}>{section.title}</h2>
              <p className={`${settingsDescriptionClass} mb-0`}>{section.description}</p>
            </div>
            <Button type="button" render={<Link to={section.href} />}>
              Manage
            </Button>
          </div>
        ))}

        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 shadow-sm">
          <p className="text-sm text-foreground">The complete API documentation is available at:</p>
          <a
            href={apiUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-primary hover:underline"
          >
            <code className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-sm">{apiUrl}</code>
          </a>
        </div>
      </div>
    </SettingsLayout>
  )
}

export default DeveloperPage
