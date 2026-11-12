import { Progress } from '@/components/ui/progress'

type DocumentBulkProgressProps = {
  done: number
  total: number
  label?: string
}

export function DocumentBulkProgress({ done, total, label = 'Progress' }: DocumentBulkProgressProps) {
  const max = Math.max(total, 1)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="tabular-nums">
          {done} / {total}
        </span>
      </div>
      <Progress
        value={done}
        max={max}
        aria-label={label}
        className="w-full [&_[data-slot=progress-track]]:h-2 [&_[data-slot=progress-indicator]]:h-2"
      />
    </div>
  )
}
