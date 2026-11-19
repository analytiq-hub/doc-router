import type { LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export interface NavItem {
  text: string
  icon: LucideIcon
  href: string
  tooltip: string
}

/** An item of the left navigation: an icon and its name, or the icon alone (with a tooltip) when closed. */
export function NavLinkItem({
  item,
  open,
  active,
  disabled,
}: {
  item: NavItem
  open: boolean
  active: boolean
  disabled?: boolean
}) {
  const Icon = item.icon
  const link = (
    <Link
      to={item.href}
      aria-current={active ? 'page' : undefined}
      aria-disabled={disabled || undefined}
      className={cn(
        'flex h-10 w-full items-center gap-3.5 rounded-md px-3 text-sm font-medium outline-none transition-colors hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring',
        active && 'bg-primary-soft text-primary',
        !active && !disabled && 'text-foreground',
        disabled && 'pointer-events-none cursor-not-allowed opacity-60',
      )}
      onClick={disabled ? (event) => event.preventDefault() : undefined}
    >
      <Icon className="size-5 shrink-0" aria-hidden />
      <span className={cn('truncate', !open && 'sr-only')}>{item.text}</span>
    </Link>
  )

  if (open) {
    return link
  }

  return (
    <Tooltip>
      <TooltipTrigger render={link} />
      <TooltipContent side="right">{disabled ? 'Select an organization' : item.tooltip}</TooltipContent>
    </Tooltip>
  )
}
