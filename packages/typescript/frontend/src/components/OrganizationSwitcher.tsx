'use client';

import { ChevronDownIcon } from 'lucide-react';
import { useOrganization } from '@/contexts/OrganizationContext';
import { useAppSession } from '@/contexts/AppSessionContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';

const typeBadgeVariant = {
  individual: 'secondary',
  team: 'default',
  enterprise: 'outline',
} as const;

export default function OrganizationSwitcher() {
  const { currentOrganization, switchOrganization, organizations, isLoading } = useOrganization();
  const { status } = useAppSession();

  if (status === 'loading' || isLoading || !organizations) {
    return (
      <div className="mr-2 flex items-center gap-2 px-2 text-sm text-brand-foreground/90">
        <Spinner className="size-4 text-brand-foreground" />
        Loading…
      </div>
    );
  }

  if (!currentOrganization || organizations.length === 0) {
    return (
      <span className="mr-2 px-2 text-sm text-brand-foreground/90">No organization available</span>
    );
  }

  if (organizations.length === 1) {
    return (
      <span className="mr-2 max-w-48 truncate px-2 text-sm font-medium text-brand-foreground">
        {currentOrganization.name}
      </span>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mr-2 max-w-56 bg-card text-foreground"
            aria-label="Switch organization"
          />
        }
      >
        <span className="truncate">{currentOrganization.name}</span>
        <ChevronDownIcon className="size-4 shrink-0 opacity-60" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-80 w-64">
        {organizations.map((organization) => (
          <DropdownMenuItem
            key={organization.id}
            className="flex cursor-pointer items-center justify-between gap-2"
            onClick={() => switchOrganization(organization.id)}
          >
            <span className="truncate">{organization.name}</span>
            <Badge
              variant={typeBadgeVariant[organization.type] ?? 'secondary'}
              className={cn('shrink-0 text-xs capitalize')}
            >
              {organization.type}
            </Badge>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
