'use client';

import {
  CircleHelp,
  CreditCard,
  Info,
  LogOut,
  MessageSquare,
  Settings,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { signOut } from '@/utils/signOut';
import { useAppSession } from '@/contexts/AppSessionContext';
import { useOrganization } from '@/contexts/OrganizationContext';
import { isSysAdmin, isOrgAdmin } from '@/utils/roles';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

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
  const { session } = useAppSession();
  const { currentOrganization } = useOrganization();
  const navigate = useNavigate();

  const getInitials = (name: string | null | undefined): string => {
    if (!name) return 'U';
    return name
      .split(' ')
      .map((word) => word[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const isAdmin = () => {
    if (!session?.user || !currentOrganization) return false;
    return isSysAdmin(session) || isOrgAdmin(currentOrganization, session);
  };

  const startTour = () => {
    localStorage.removeItem('hasSeenTour');
    if (window.startTourGuide) {
      window.startTourGuide();
    } else {
      window.location.reload();
    }
  };

  const handleLogout = () => {
    void signOut();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-brand-foreground hover:bg-brand-foreground/10 hover:text-brand-foreground"
            aria-label="Account menu"
          />
        }
      >
        <Avatar size="sm">
          {user?.image ? (
            <AvatarImage src={user.image} alt={user.name ?? 'User'} />
          ) : null}
          <AvatarFallback className="bg-primary text-primary-foreground text-xs">
            {getInitials(user?.name)}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex flex-col gap-0.5 font-normal">
            <span className="text-sm font-medium text-foreground">{user?.name ?? 'User'}</span>
            {user?.email ? (
              <span className="truncate text-xs text-muted-foreground">{user.email}</span>
            ) : null}
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        {isAdmin() && currentOrganization ? (
          <DropdownMenuItem
            render={
              <Link
                to={`/settings/organizations/${currentOrganization.id}/subscription`}
                className="flex w-full items-center"
              />
            }
          >
            <CreditCard />
            Billing
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem
          render={<Link to="/settings" className="flex w-full items-center" />}
        >
          <Settings />
          Settings
        </DropdownMenuItem>
        <DropdownMenuItem onClick={startTour}>
          <CircleHelp />
          Start Tour Guide
        </DropdownMenuItem>
        <DropdownMenuItem
          render={<Link to="/feedback" className="flex w-full items-center" />}
        >
          <MessageSquare />
          Provide Feedback
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => navigate('/')}
        >
          <Info />
          About
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout}>
          <LogOut />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default UserMenu;
