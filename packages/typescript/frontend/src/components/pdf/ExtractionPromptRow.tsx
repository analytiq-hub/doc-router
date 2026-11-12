import type { ReactNode } from 'react'
import {
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
} from 'lucide-react'

import { RowActionsMenu, type RowAction } from '@/components/RowActionsMenu'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'

export type ExtractionPromptRowProps = {
  ariaLabel: string
  title: string
  versionLabel?: string
  open: boolean
  preview: string
  previewFailed?: boolean
  running?: boolean
  loading?: boolean
  failed?: boolean
  isVerified?: boolean
  isEdited?: boolean
  bodyId: string
  onToggle: () => void
  actions: (RowAction | false | null | undefined)[]
  children: ReactNode
}

export function ExtractionPromptRow({
  ariaLabel,
  title,
  versionLabel,
  open,
  preview,
  previewFailed,
  running,
  loading,
  failed,
  isVerified,
  isEdited,
  bodyId,
  onToggle,
  actions,
  children,
}: ExtractionPromptRowProps) {
  const busy = Boolean(running || loading)

  return (
    <section aria-label={ariaLabel} className="border-b border-border last:border-b-0">
      <div className="flex items-start gap-1 py-2">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-start gap-2 rounded-md px-1 text-left outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={onToggle}
        >
          {open ? (
            <ChevronDown className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          ) : (
            <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          )}
          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="flex flex-wrap items-center gap-1.5">
              <span className="truncate text-sm font-medium">{title}</span>
              {versionLabel ? (
                <span className="shrink-0 text-xs text-muted-foreground">{versionLabel}</span>
              ) : null}
              {busy ? <Spinner className="size-3.5 shrink-0 text-primary" aria-label="Running" /> : null}
              {failed ? (
                <CircleAlert className="size-4 shrink-0 text-destructive" aria-label="Failed" />
              ) : null}
              {isVerified ? (
                <CircleCheck className="size-4 shrink-0 text-success" aria-label="Verified" />
              ) : null}
              {isEdited ? <span className="shrink-0 text-xs text-muted-foreground">corrected</span> : null}
            </span>
            {!open ? (
              <span
                className={cn(
                  'truncate text-xs text-muted-foreground',
                  previewFailed && 'text-destructive',
                )}
              >
                {preview}
              </span>
            ) : null}
          </span>
        </button>
        <RowActionsMenu label={ariaLabel} actions={actions} />
      </div>
      {open ? (
        <div id={bodyId} className="flex flex-col gap-3 pb-3 pl-7 pr-1">
          {children}
        </div>
      ) : null}
    </section>
  )
}
