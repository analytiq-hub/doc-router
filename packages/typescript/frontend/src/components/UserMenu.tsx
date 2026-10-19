'use client'

import React, { useState } from 'react';
import { Settings as SettingsIcon, ExitToApp as SignoutIcon, Help as HelpIcon, Info as InfoIcon, Feedback as FeedbackIcon, Payment as PaymentIcon } from '@mui/icons-material';
import { signOut } from '@/utils/signOut';
import { useAppSession } from '@/contexts/AppSessionContext';
import Link from 'next/link';
import Image from 'next/image';
import { useOrganization } from '@/contexts/OrganizationContext';
import { isSysAdmin, isOrgAdmin } from '@/utils/roles';
// Add this interface at the top of your file
declare global {
  interface Window {
    startTourGuide?: () => void;
  }
}

interface UserMenuProps {
  user: {
    name?: string | null;
    email?: string | null;
    image?: string | null;
  } | undefined;
}

const UserMenu: React.FC<UserMenuProps> = ({ user }) => {
  const [isOpen, setIsOpen] = useState(false);
  const { session } = useAppSession();
  const { currentOrganization } = useOrganization();

  const handleLogout = () => {
    void signOut();
    setIsOpen(false);
  };

  const startTour = () => {
    // Reset the tour flag
    localStorage.removeItem('hasSeenTour');
    
    // If the startTourGuide function is available, use it directly
    if (window.startTourGuide) {
      window.startTourGuide();
    } else {
      // Otherwise reload the page to trigger the tour
      window.location.reload();
    }
    
    setIsOpen(false);
  };

  const getInitials = (name: string | null | undefined): string => {
    if (!name) return 'U';
    return name.split(' ')
      .map(word => word[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  // Check if user is admin (system admin or organization admin)
  const isAdmin = () => {
    if (!session?.user || !currentOrganization) return false;
    
    return isSysAdmin(session) || isOrgAdmin(currentOrganization, session);
  };

  return (
    <div className="relative">
      {/* Avatar Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center ml-2 rounded-full hover:ring-2 hover:ring-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400"
        title={user?.name || 'User'}
      >
        {user?.image ? (
          <Image
            src={user.image}
            alt={user.name || 'User'}
            width={32}
            height={32}
            className="rounded-full"
          />
        ) : (
          <div className="h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium">
            {getInitials(user?.name)}
          </div>
        )}
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-30"
            onClick={() => setIsOpen(false)}
          />

          <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-40">
            {/* User Info */}
            <div className="px-4 py-3">
              <p className="text-sm font-medium text-gray-900">
                {user?.name || 'User'}
              </p>
              <p className="text-sm text-gray-500 truncate">
                {user?.email || ''}
              </p>
            </div>

            <div className="border-t border-gray-200" />

            {/* Billing Link - Only show for admins */}
            {isAdmin() && currentOrganization && (
              <Link
                href={`/settings/organizations/${currentOrganization.id}/subscription`}
                className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                onClick={() => setIsOpen(false)}
              >
                <PaymentIcon className="h-4 w-4 mr-2" />
                <span className="pt-[3px]">Billing</span>
              </Link>
            )}

            {/* Settings Link */}
            <Link
              href="/settings"
              className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
              onClick={() => setIsOpen(false)}
            >
              <SettingsIcon className="h-4 w-4 mr-2" />
              <span className="pt-[3px]">Settings</span>
            </Link>

            {/* Tour Guide Option */}
            <button
              onClick={startTour}
              className="flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              <HelpIcon className="h-4 w-4 mr-2" />
              <span className="pt-[3px]">Start Tour Guide</span>
            </button>

            {/* Feedback Link */}
            <Link
              href="/feedback"
              className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
              onClick={() => setIsOpen(false)}
            >
              <FeedbackIcon className="h-4 w-4 mr-2" />
              <span className="pt-[3px]">Provide Feedback</span>
            </Link>

            {/* About Link */}
            <Link
              href="/"
              className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
              onClick={() => setIsOpen(false)}
            >
              <InfoIcon className="h-4 w-4 mr-2" />
              <span className="pt-[3px]">About</span>
            </Link>

            <div className="border-t border-gray-200" />

            {/* Sign Out Button */}
            <button
              onClick={handleLogout}
              className="flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              <SignoutIcon className="h-4 w-4 mr-2" />
              <span className="pt-[3px]">Sign out</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default UserMenu;