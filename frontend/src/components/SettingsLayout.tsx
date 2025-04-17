'use client'

import React from 'react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { 
  Person as UserIcon,
  Business as OrganizationsIcon,
  Settings as SystemIcon,
  ApiRounded as ApiIcon
} from '@mui/icons-material';

interface SettingsLayoutProps {
  selectedMenu?: string;
  children?: React.ReactNode;
}

interface MenuItem {
  name: string;
  href: string;
  id: string;
  adminOnly?: boolean;
}

const SettingsLayout: React.FC<SettingsLayoutProps> = ({ 
  selectedMenu = 'user_developer',
  children
}) => {
  const { data: session } = useSession();
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
        },
        {
          name: 'Developer',
          href: '/settings/user/developer',
          id: 'user_developer',
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
          adminOnly: true,
        },
        {
          name: 'Development',
          href: '/settings/account/development',
          id: 'system_development',
          adminOnly: true,
        },
      ],
    },
    {
      title: 'Integrations',
      icon: ApiIcon,
      items: [
        {
          name: 'Manage Integrations',
          href: '/settings/integrations',
          id: 'integrations',
        },
        {
          name: 'API Documentation',
          href: '/settings/integrations/api-docs',
          id: 'integrations_api',
        },
      ],
    },
  ];

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white">
        <nav className="h-full py-6">
          {menuItems.map((section) => {
            const visibleItems = section.items.filter(item => 
              !item.adminOnly || isAdmin
            );

            if (visibleItems.length === 0) return null;

            const Icon = section.icon;

            return (
              <div key={section.title} className="mb-6 last:mb-0">
                <h2 className="px-6 mb-1 text-sm font-medium text-gray-500 flex items-center">
                  <Icon className="h-5 w-5 mr-2" />
                  {section.title}
                </h2>
                <div className="mt-1">
                  {visibleItems.map((item) => (
                    <Link
                      key={item.id}
                      href={item.href}
                      className={`
                        flex items-center h-10 pl-[48px] pr-4 text-sm font-medium
                        transition-colors duration-200 rounded-md mx-2
                        ${selectedMenu === item.id
                          ? 'bg-blue-50 text-blue-600'
                          : 'text-gray-600 hover:bg-gray-100'
                        }
                      `}
                    >
                      {item.name}
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto py-8 px-6">
          {children}
        </div>
      </main>
    </div>
  );
};

export default SettingsLayout; 