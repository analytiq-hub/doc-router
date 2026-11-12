'use client'

import {
  Building2,
  Code2,
  KeyRound,
  Settings,
  User,
  Users,
  type LucideIcon,
} from 'lucide-react'
import React from 'react'
import { Link } from 'react-router-dom'

import SidebarNavTooltip from '@/components/SidebarNavTooltip'
import { cn } from '@/lib/utils'
import { useAppSession } from '@/contexts/AppSessionContext'
import { isSysAdmin } from '@/utils/roles'

export const settingsPageTitleClass = 'text-lg font-semibold text-foreground'
export const settingsSectionTitleClass = 'text-lg font-semibold text-foreground'
export const settingsDescriptionClass = 'text-sm text-muted-foreground'

const settingsNavGridClass = 'md:grid md:w-full md:grid-cols-[1.25rem_1fr] md:gap-x-2 md:px-4'
const settingsNavLinkClass =
  'col-span-2 flex h-10 w-full items-center rounded-md pl-[calc(1.25rem+0.5rem)] pr-4'

interface SettingsLayoutProps {
  selectedMenu?: string
  children?: React.ReactNode
}

interface MenuItem {
  name: string
  href: string
  id: string
  adminOnly?: boolean
}

const SectionIcons: Record<string, LucideIcon> = {
  User: User,
  Organizations: Building2,
  System: Settings,
}

const ItemIcons: Record<string, LucideIcon> = {
  user_profile: User,
  user_developer: Code2,
  organizations: Building2,
  system_users: Users,
  system_license: KeyRound,
  system_development: Code2,
}

const SettingsLayout: React.FC<SettingsLayoutProps> = ({ selectedMenu = 'user_developer', children }) => {
  const { session } = useAppSession()
  const isAdmin = isSysAdmin(session)

  const menuItems: Array<{
    title: string
    items: Array<MenuItem>
  }> = [
    {
      title: 'User',
      items: [
        { name: 'Profile', href: '/settings/user/profile', id: 'user_profile' },
        { name: 'Developer', href: '/settings/user/developer', id: 'user_developer' },
      ],
    },
    {
      title: 'Organizations',
      items: [{ name: 'Organizations', href: '/settings/organizations', id: 'organizations' }],
    },
    {
      title: 'System',
      items: [
        { name: 'Users', href: '/settings/account/users', id: 'system_users', adminOnly: true },
        { name: 'License', href: '/settings/account/license', id: 'system_license', adminOnly: true },
        { name: 'Development', href: '/settings/account/development', id: 'system_development', adminOnly: true },
      ],
    },
  ]

  return (
    <div className="flex min-h-screen bg-muted/40">
      <aside className="w-16 shrink-0 border-r border-border bg-card transition-all duration-200 md:w-fit max-md:overflow-visible">
        <nav className="h-full py-4 md:flex md:w-max md:flex-col md:py-6">
          {menuItems.map((section) => {
            const visibleItems = section.items.filter((item) => !item.adminOnly || isAdmin)
            if (visibleItems.length === 0) return null

            const SectionIcon = SectionIcons[section.title] ?? Settings

            return (
              <div key={section.title} className="mb-4 last:mb-0 md:mb-5 md:w-full">
                <div className="md:hidden">
                  {visibleItems.map((item) => {
                    const ItemIcon = ItemIcons[item.id] ?? Settings
                    const isSelected = selectedMenu === item.id

                    return (
                      <SidebarNavTooltip key={item.id} label={item.name} className="mx-1">
                        <Link
                          to={item.href}
                          className={cn(
                            'flex h-10 items-center justify-center rounded-md text-sm font-medium transition-colors',
                            isSelected
                              ? 'bg-primary-soft text-primary'
                              : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                          )}
                        >
                          <ItemIcon className="size-5 shrink-0" aria-hidden />
                        </Link>
                      </SidebarNavTooltip>
                    )
                  })}
                </div>

                <div className={cn('hidden md:w-full', settingsNavGridClass)}>
                  <SectionIcon className="size-5 shrink-0 self-center text-muted-foreground" aria-hidden />
                  <h2 className="min-w-0 self-center text-sm font-medium whitespace-nowrap text-muted-foreground">
                    {section.title}
                  </h2>
                  {visibleItems.map((item) => {
                    const isSelected = selectedMenu === item.id

                    return (
                      <Link
                        key={item.id}
                        to={item.href}
                        className={cn(
                          settingsNavLinkClass,
                          'text-sm font-medium whitespace-nowrap transition-colors',
                          isSelected
                            ? 'bg-primary-soft text-primary'
                            : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                        )}
                      >
                        {item.name}
                      </Link>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </nav>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl px-2 py-8 text-sm text-foreground md:px-6">{children}</div>
      </main>
    </div>
  )
}

export default SettingsLayout
