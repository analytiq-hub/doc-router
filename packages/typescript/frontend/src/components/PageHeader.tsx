import type { ReactNode } from 'react'

export function PageHeader({
  title,
  titleAdornment,
  subtitle,
  meta,
  actions,
}: {
  title: string
  titleAdornment?: ReactNode
  subtitle?: string
  meta?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">{title}</h1>
          {titleAdornment}
        </div>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
        {meta}
      </div>
      {actions ? <div className="flex gap-2">{actions}</div> : null}
    </div>
  )
}
