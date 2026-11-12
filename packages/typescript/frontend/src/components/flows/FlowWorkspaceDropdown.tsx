'use client'

import type { ReactNode } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from 'cn'
import {
  flowWorkspaceDropdownItemClass,
  flowWorkspaceDropdownItemDestructiveClass,
  flowWorkspaceDropdownItemSimpleClass,
  flowWorkspaceDropdownDividerClass,
  flowWorkspaceMenuPanelClass,
  flowWorkspaceMenuTriggerCompactClass,
  flowWorkspaceMenuTriggerIconBtnClass,
} from './flowWorkspaceMenu'

export type FlowWorkspaceMenuItem = {
  id: string
  label: ReactNode
  icon?: ReactNode
  onSelect?: () => void
  disabled?: boolean
  destructive?: boolean
  /** Matches flow toolbar / canvas menus (no icon row layout). */
  simple?: boolean
}

type FlowWorkspaceDropdownProps = {
  trigger: ReactNode
  items: FlowWorkspaceMenuItem[]
  /** When true, use the smaller 28×28 node-toolbar trigger. */
  compactTrigger?: boolean
  /** Skip default icon-button chrome on the trigger (pass full styles via `triggerClassName`). */
  unstyledTrigger?: boolean
  triggerClassName?: string
  contentClassName?: string
  align?: 'start' | 'end' | 'center'
  side?: 'top' | 'bottom' | 'left' | 'right'
  onOpenChange?: (open: boolean) => void
  /** Insert a divider before destructive items (default true). */
  separateDestructive?: boolean
}

function itemClass(item: FlowWorkspaceMenuItem, destructive: boolean) {
  if (destructive) return flowWorkspaceDropdownItemDestructiveClass
  if (item.simple) return flowWorkspaceDropdownItemSimpleClass
  return flowWorkspaceDropdownItemClass
}

export function FlowWorkspaceDropdown({
  trigger,
  items,
  compactTrigger = false,
  unstyledTrigger = false,
  triggerClassName,
  contentClassName,
  align = 'end',
  side = 'bottom',
  onOpenChange,
  separateDestructive = true,
}: FlowWorkspaceDropdownProps) {
  const regular = items.filter((item) => !item.destructive)
  const destructive = items.filter((item) => item.destructive)

  return (
    <DropdownMenu onOpenChange={onOpenChange}>
      <DropdownMenuTrigger
        className={cn(
          !unstyledTrigger && (compactTrigger ? flowWorkspaceMenuTriggerCompactClass : flowWorkspaceMenuTriggerIconBtnClass),
          triggerClassName,
        )}
      >
        {trigger}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        side={side}
        className={cn(flowWorkspaceMenuPanelClass, 'z-[280] min-w-[11rem]', contentClassName)}
      >
        {regular.map((item) => (
          <DropdownMenuItem
            key={item.id}
            disabled={item.disabled}
            onClick={() => item.onSelect?.()}
            className={cn(itemClass(item, false), 'w-full')}
          >
            {item.icon}
            {item.label}
          </DropdownMenuItem>
        ))}
        {separateDestructive && regular.length > 0 && destructive.length > 0 ? (
          <DropdownMenuSeparator className={flowWorkspaceDropdownDividerClass} />
        ) : null}
        {destructive.map((item) => (
          <DropdownMenuItem
            key={item.id}
            variant="destructive"
            disabled={item.disabled}
            onClick={() => item.onSelect?.()}
            className={cn(itemClass(item, true), 'w-full')}
          >
            {item.icon}
            {item.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
