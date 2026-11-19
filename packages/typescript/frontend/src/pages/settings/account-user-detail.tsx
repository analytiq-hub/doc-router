'use client'

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import UserEdit from '@/components/UserEdit';

const UserEditPage: React.FC<{ params: Promise<{ userId: string }> }> = (props) => {
  const { userId } = useRouteParams(props);
  return <UserEdit userId={userId} />;
};

export default UserEditPage; 