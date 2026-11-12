import { MoreHorizontal, type LucideIcon } from 'lucide-react'
import type { SyntheticEvent } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const keepFromGrid = (event: SyntheticEvent) => event.stopPropagation()

export interface RowAction {
  label: string
  icon?: LucideIcon
  onSelect?: () => void
  to?: string
  destructive?: boolean
  disabled?: boolean
}

interface RowActionsMenuProps {
  label: string
  actions: (RowAction | false | null | undefined)[]
}

export function RowActionsMenu({ label, actions }: RowActionsMenuProps) {
  const items = actions.filter((action): action is RowAction => Boolean(action))
  if (items.length === 0) return null
  const regular = items.filter((action) => !action.destructive)
  const destructive = items.filter((action) => action.destructive)

  const renderItem = (action: RowAction) => {
    const Icon = action.icon
    return (
      <DropdownMenuItem
        key={action.label}
        variant={action.destructive ? 'destructive' : 'default'}
        disabled={action.disabled}
        onClick={action.onSelect}
        render={action.to && !action.disabled ? <Link to={action.to} /> : undefined}
      >
        {Icon ? <Icon /> : null}
        {action.label}
      </DropdownMenuItem>
    )
  }

  return (
    <span
      className="contents"
      onClick={keepFromGrid}
      onDoubleClick={keepFromGrid}
      onMouseDown={keepFromGrid}
      onKeyDown={keepFromGrid}
    >
      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button variant="ghost" size="icon-sm" className="-ml-2" aria-label={`Actions for ${label}`} />}
        >
          <MoreHorizontal />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {regular.map(renderItem)}
          {regular.length > 0 && destructive.length > 0 ? <DropdownMenuSeparator /> : null}
          {destructive.map(renderItem)}
        </DropdownMenuContent>
      </DropdownMenu>
    </span>
  )
}
