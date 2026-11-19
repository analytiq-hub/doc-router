import type { ReactNode } from 'react'

import { settingsDescriptionClass, settingsPageTitleClass } from '@/components/settingsTypography'

/** Settings-only page title row: compact type (lg), not the org work `PageHeader` (2xl). */
export function SettingsPageHeader({
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
    <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className={settingsPageTitleClass}>{title}</h1>
          {titleAdornment}
        </div>
        {subtitle ? <p className={settingsDescriptionClass}>{subtitle}</p> : null}
        {meta}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </div>
  )
}