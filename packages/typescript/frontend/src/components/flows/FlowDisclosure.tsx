'use client'

import { useState, type ReactNode } from 'react'

type FlowDisclosureApi = { open: boolean; toggle: () => void }

/** Headless `Disclosure` replacement for flows panels (accordion rows). */
export function FlowDisclosure({
  defaultOpen = false,
  className,
  children,
}: {
  defaultOpen?: boolean
  className?: string
  children: (api: FlowDisclosureApi) => ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={className}>
      {children({
        open,
        toggle: () => setOpen((v) => !v),
      })}
    </div>
  )
}
