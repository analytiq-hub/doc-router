import { GripVertical, X } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from 'react'
import { cn } from 'cn'

import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'

export interface Property {
  label: string
  value: ReactNode
}

interface Position {
  left: number
  top: number
}

const KEEP_VISIBLE = 48

export function PropertiesDialog({
  title,
  description,
  properties,
  columns = 1,
  footer,
  onClose,
}: {
  title: string
  description?: string
  properties: Property[]
  columns?: 1 | 2
  footer?: ReactNode
  onClose: () => void
}) {
  const popup = useRef<HTMLDivElement>(null)
  const drag = useRef<{ startX: number; startY: number; left: number; top: number; width: number } | null>(null)
  const offset = useRef({ x: 0, y: 0 })
  const [position, setPosition] = useState<Position | null>(null)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return
      if (document.querySelector('[role="menu"][data-open], [role="alertdialog"], [data-slot="dialog-overlay"]')) return
      onClose()
    }
    document.addEventListener('keydown', onKeyDown, true)
    return () => document.removeEventListener('keydown', onKeyDown, true)
  }, [onClose])

  const startDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !popup.current || (event.target as HTMLElement).closest('button')) return
    const rect = popup.current.getBoundingClientRect()
    drag.current = { startX: event.clientX, startY: event.clientY, left: rect.left, top: rect.top, width: rect.width }
    offset.current = { x: 0, y: 0 }
    setPosition({ left: rect.left, top: rect.top })
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const moveDrag = (event: PointerEvent<HTMLDivElement>) => {
    const start = drag.current
    if (!start || !popup.current) return
    const left = Math.min(Math.max(start.left + event.clientX - start.startX, KEEP_VISIBLE - start.width), window.innerWidth - KEEP_VISIBLE)
    const top = Math.min(Math.max(start.top + event.clientY - start.startY, 0), window.innerHeight - KEEP_VISIBLE)
    offset.current = { x: left - start.left, y: top - start.top }
    popup.current.style.transform = `translate3d(${offset.current.x}px, ${offset.current.y}px, 0)`
  }
  const endDrag = () => {
    const start = drag.current
    if (!start) return
    drag.current = null
    setPosition({ left: start.left + offset.current.x, top: start.top + offset.current.y })
    if (popup.current) popup.current.style.transform = ''
  }

  const rows: Property[][] = []
  for (let i = 0; i < properties.length; i += columns) rows.push(properties.slice(i, i + columns))

  const placement: CSSProperties | undefined = position
    ? { left: position.left, top: position.top, translate: 'none' }
    : undefined

  return (
    <Dialog open modal={false} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        ref={popup}
        overlay={false}
        showCloseButton={false}
        style={placement}
        className={cn(
          'flex max-h-11/12 flex-col gap-0 overflow-hidden p-0 shadow-xl ring-foreground/20',
          columns === 2 && 'sm:max-w-2xl',
        )}
      >
        <div
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          className="flex shrink-0 cursor-grab touch-none items-start gap-2 bg-primary px-4 py-3 text-primary-foreground select-none active:cursor-grabbing"
        >
          <GripVertical className="mt-0.5 size-5 shrink-0 opacity-70" aria-hidden />
          <div className="min-w-0 flex-1">
            <DialogTitle className="truncate text-base font-semibold">{title}</DialogTitle>
            {description ? (
              <DialogDescription className="text-primary-foreground/80">{description}</DialogDescription>
            ) : null}
          </div>
          <DialogClose
            render={
              <Button
                variant="ghost"
                size="icon-sm"
                className="-mt-0.5 -mr-1.5 text-primary-foreground hover:bg-white/20 hover:text-primary-foreground"
              />
            }
          >
            <X />
            <span className="sr-only">Close</span>
          </DialogClose>
        </div>
        <dl className="min-h-0 flex-1 overflow-y-auto">
          {rows.map((row, index) => (
            <div
              key={row[0].label}
              className={cn('grid gap-x-6 px-4 py-2 text-sm', columns === 2 && 'grid-cols-2', index % 2 === 1 && 'bg-muted')}
            >
              {row.map((property) => (
                <div key={property.label} className="grid grid-cols-[7rem_1fr] gap-x-3">
                  <dt className="text-muted-foreground">{property.label}</dt>
                  <dd className="min-w-0 break-words">{property.value ?? '—'}</dd>
                </div>
              ))}
            </div>
          ))}
        </dl>
        {footer ?? (
          <div className="flex shrink-0 justify-end border-t bg-muted/40 px-4 py-3">
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
