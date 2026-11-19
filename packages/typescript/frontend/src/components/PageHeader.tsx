import type { ReactNode } from 'react'

/** Org work pages (Documents, Tags, …). Settings routes use `SettingsPageHeader` instead. */
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
    <div className="mb-6 flex items-start gap-4">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">{title}</h1>
          {titleAdornment}
        </div>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
        {meta}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap justify-end gap-2">{actions}</div> : null}
    </div>
  )
}
