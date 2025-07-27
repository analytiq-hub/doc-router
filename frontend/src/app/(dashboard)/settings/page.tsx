'use client'

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import SettingsLayout from '@/components/SettingsLayout';

const SettingsPage = () => {
  const router = useRouter();

  useEffect(() => {
    router.replace('/settings/user/developer');
  }, [router]);

  return (
    <SettingsLayout selectedMenu="user_developer">
      <div className="flex justify-center items-center h-64">
        <div className="animate-pulse text-gray-500">
          Loading settings...
        </div>
      </div>
    </SettingsLayout>
  );
};

export default SettingsPage;
