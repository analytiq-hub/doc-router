'use client'

import React from 'react';
import Link from 'next/link';
import { useAppSession } from '@/contexts/AppSessionContext';
import {
  Person as UserIcon,
  Code as DeveloperIcon,
  Business as OrganizationsIcon,
  Group as UsersIcon,
  Build as DevelopmentIcon,
  Settings as SystemIcon,
} from '@mui/icons-material';
import type { SvgIconProps } from '@mui/material';
import SidebarNavTooltip from '@/components/SidebarNavTooltip';

export const settingsPageTitleClass = 'text-lg font-semibold text-gray-900';
export const settingsSectionTitleClass = 'text-lg font-semibold text-gray-900';
export const settingsDescriptionClass = 'text-sm text-gray-600';

const settingsNavGridClass =
  'md:grid md:w-full md:grid-cols-[1.25rem_1fr] md:gap-x-2 md:px-4';
const settingsNavLinkClass =
  'col-span-2 flex h-10 w-full items-center rounded-md pl-[calc(1.25rem+0.5rem)] pr-4';

interface SettingsLayoutProps {
  selectedMenu?: string;
  children?: React.ReactNode;
}

interface MenuItem {
  name: string;
  href: string;
  id: string;
  icon: React.ComponentType<SvgIconProps>;
  adminOnly?: boolean;
}

const SettingsLayout: React.FC<SettingsLayoutProps> = ({ 
  selectedMenu = 'user_developer',
  children
}) => {
  const { session } = useAppSession();
  const isAdmin = session?.user?.role === 'admin';

  const menuItems: Array<{
    title: string;
    icon: React.ElementType;
    items: Array<MenuItem>;
  }> = [
    {
      title: 'User',
      icon: UserIcon,
      items: [
        {
          name: 'Profile',
          href: '/settings/user/profile',
          id: 'user_profile',
          icon: UserIcon,
        },
        {
          name: 'Developer',
          href: '/settings/user/developer',
          id: 'user_developer',
          icon: DeveloperIcon,
        },
      ],
    },
    {
      title: 'Organizations',
      icon: OrganizationsIcon,
      items: [
        {
          name: 'Organizations',
          href: '/settings/organizations',
          id: 'organizations',
          icon: OrganizationsIcon,
          adminOnly: false,
        },
      ],
    },
    {
      title: 'System',
      icon: SystemIcon,
      items: [
        {
          name: 'Users',
          href: '/settings/account/users',
          id: 'system_users',
          icon: UsersIcon,
          adminOnly: true,
        },
        {
          name: 'Development',
          href: '/settings/account/development',
          id: 'system_development',
          icon: DevelopmentIcon,
          adminOnly: true,
        },
      ],
    },
  ];

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="bg-white w-16 md:w-fit shrink-0 border-r border-gray-200 transition-all duration-200 max-md:overflow-visible">
        <nav className="h-full py-4 md:py-6 md:flex md:flex-col md:w-max">
          {menuItems.map((section) => {
            const visibleItems = section.items.filter(item => 
              !item.adminOnly || isAdmin
            );

            if (visibleItems.length === 0) return null;

            const SectionIcon = section.icon;

            return (
              <div key={section.title} className="mb-4 md:mb-5 last:mb-0 md:w-full">
                {/* Mobile: icon-only */}
                <div className="md:hidden">
                  {visibleItems.map((item) => {
                    const ItemIcon = item.icon;
                    const isSelected = selectedMenu === item.id;

                    return (
                      <SidebarNavTooltip
                        key={item.id}
                        label={item.name}
                        className="mx-1"
                      >
                        <Link
                          href={item.href}
                          className={[
                            'flex items-center justify-center h-10 rounded-md',
                            'text-sm font-medium transition-colors duration-200',
                            isSelected
                              ? 'bg-blue-50 text-blue-600'
                              : 'text-gray-600 hover:bg-gray-100',
                          ].join(' ')}
                        >
                          <ItemIcon className="h-5 w-5 shrink-0" />
                        </Link>
                      </SidebarNavTooltip>
                    );
                  })}
                </div>

                {/* Desktop: shared grid aligns section labels with item labels */}
                <div className={`hidden md:w-full ${settingsNavGridClass}`}>
                  <SectionIcon className="h-5 w-5 shrink-0 self-center" />
                  <h2 className="text-sm font-medium text-gray-500 whitespace-nowrap self-center min-w-0">
                    {section.title}
                  </h2>
                  {visibleItems.map((item) => {
                    const isSelected = selectedMenu === item.id;

                    return (
                      <Link
                        key={item.id}
                        href={item.href}
                        className={[
                          settingsNavLinkClass,
                          'text-sm font-medium whitespace-nowrap transition-colors duration-200',
                          isSelected
                            ? 'bg-blue-50 text-blue-600'
                            : 'text-gray-600 hover:bg-gray-100',
                        ].join(' ')}
                      >
                        {item.name}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto py-8 px-2 md:px-6 text-sm text-gray-900">
          {children}
        </div>
      </main>
    </div>
  );
};

export default SettingsLayout;
