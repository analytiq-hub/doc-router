import { useState } from 'react'
import { ChevronDownIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'
import { formatRevisionSavedAt } from '@/utils/date'

export type VersionOption = {
  version: number
  revId: string
  createdAt: string
}

export function RevisionVersionSelector({
  versions,
  currentVersion,
  selectedVersion,
  onSelect,
  loading,
  error,
}: {
  versions: VersionOption[]
  currentVersion: number
  selectedVersion: number
  onSelect: (revId: string, version: number) => void
  loading?: boolean
  error?: string | null
}) {
  const [open, setOpen] = useState(false)

  if (loading) {
    return (
      <div className="flex h-8 items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4" />
        Loading versions…
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-1.5 text-sm text-destructive">
        {error}
      </div>
    )
  }

  if (versions.length <= 1) {
    return (
      <div className="flex h-8 items-center px-1 text-sm text-muted-foreground">
        Version {currentVersion} (only version)
      </div>
    )
  }

  const showCurrentOnTrigger = selectedVersion === currentVersion

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-auto shrink-0 justify-between gap-1.5 px-2.5 font-normal"
            aria-label="Select revision version"
          />
        }
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="font-medium">v{selectedVersion}</span>
          {showCurrentOnTrigger ? <CurrentVersionBadge /> : null}
        </span>
        <ChevronDownIcon className={cn('size-4 shrink-0 opacity-60 transition-transform', open && 'rotate-180')} />
      </PopoverTrigger>
      <PopoverContent align="start" sideOffset={4} className="w-auto max-w-[11.5rem] p-1">
        <ul className="max-h-60 w-full overflow-y-auto" role="listbox" aria-label="Versions">
          {versions.map((row) => {
            const isSelected = row.version === selectedVersion
            const isCurrent = row.version === currentVersion
            return (
              <li key={row.revId} role="none">
                <button
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={cn(
                    'flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left text-sm outline-hidden transition-colors',
                    isSelected
                      ? 'bg-accent text-accent-foreground'
                      : 'hover:bg-accent hover:text-accent-foreground',
                  )}
                  onClick={() => {
                    onSelect(row.revId, row.version)
                    setOpen(false)
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">v{row.version}</span>
                    {isCurrent ? <CurrentVersionBadge /> : null}
                  </div>
                  <span
                    className={cn(
                      'text-xs tabular-nums',
                      isSelected ? 'text-accent-foreground/80' : 'text-muted-foreground',
                    )}
                  >
                    {formatRevisionSavedAt(row.createdAt)}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </PopoverContent>
    </Popover>
  )
}

function CurrentVersionBadge() {
  return (
    <Badge variant="info" className="h-5 border-0 px-1.5 text-[10px] font-semibold">
      Current
    </Badge>
  )
}
