import type { FormEvent, ReactNode } from 'react'

import { ErrorAlert } from '@/components/ErrorAlert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { FieldGroup } from '@/components/ui/field'

interface FormDialogProps {
  title: string
  description?: string
  submitLabel: string
  submitDisabled?: boolean
  busy?: boolean
  error?: unknown
  onSubmit: () => void
  onClose: () => void
  size?: 'default' | 'wide'
  children: ReactNode
}

export function FormDialog({
  title,
  description,
  submitLabel,
  submitDisabled = false,
  busy = false,
  error,
  onSubmit,
  onClose,
  size = 'default',
  children,
}: FormDialogProps) {
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit()
  }
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className={size === 'wide' ? 'sm:max-w-2xl' : undefined}>
        <form onSubmit={submit} className="flex min-w-0 flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description ? (
              <DialogDescription className="[overflow-wrap:anywhere]">{description}</DialogDescription>
            ) : null}
          </DialogHeader>
          <FieldGroup>{children}</FieldGroup>
          <ErrorAlert error={error} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy || submitDisabled}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
