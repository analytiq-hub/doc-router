'use client'

import { isSysAdmin } from "@/utils/roles";
import { useAppSession } from "@/contexts/AppSessionContext";
import { ReactNode } from "react";

interface RoleBasedRenderProps {
  children: ReactNode;
  /** Include `"admin"` to show content for platform sysadmins only. */
  allowedRoles: string[];
}

const RoleBasedRender: React.FC<RoleBasedRenderProps> = ({
  children,
  allowedRoles,
}) => {
  const { session } = useAppSession();
  const show =
    allowedRoles.includes('admin') && isSysAdmin(session);

  if (!show) {
    return null;
  }

  return <>{children}</>;
};

export default RoleBasedRender;
