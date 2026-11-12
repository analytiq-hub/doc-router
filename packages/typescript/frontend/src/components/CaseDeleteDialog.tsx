'use client'

import { useEffect, useMemo, useState } from 'react'
import type { Case } from '@docrouter/sdk'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DocRouterOrgApi } from '@/utils/api'
import { toastActionError } from '@/utils/toastActionError'
import { toast } from 'sonner'
import { caseDisplayName } from '@/utils/caseDisplayName'
import { deleteCaseAndWait, type CaseDeleteMode } from '@/utils/caseDelete'

type CaseDeleteDialogProps = {
  open: boolean
  organizationId: string
  caseRow: Case | null
  /** Same as documents.write — required for cascade delete per API. */
  canCascadeDelete: boolean
  onClose: () => void
  onDeleted: () => void | Promise<void>
}

export default function CaseDeleteDialog({
  open,
  organizationId,
  caseRow,
  canCascadeDelete,
  onClose,
  onDeleted,
}: CaseDeleteDialogProps) {
  const [mode, setMode] = useState<CaseDeleteMode>('unassign')
  const [confirmId, setConfirmId] = useState('')
  const [busy, setBusy] = useState(false)

  const docCount = caseRow?.document_count ?? 0
  const caseId = caseRow?.case_id ?? ''

  const cascadeConfirmOk = confirmId.trim() === caseId
  const canSubmit = useMemo(() => {
    if (!caseRow || busy) return false
    if (mode === 'cascade') {
      return canCascadeDelete && cascadeConfirmOk
    }
    return true
  }, [busy, canCascadeDelete, cascadeConfirmOk, caseRow, mode])

  const resetForm = () => {
    setMode('unassign')
    setConfirmId('')
    setBusy(false)
  }

  useEffect(() => {
    if (open) resetForm()
  }, [open, caseRow?.case_id])

  const handleClose = () => {
    if (busy) return
    resetForm()
    onClose()
  }

  const handleSubmit = async () => {
    if (!caseRow || !canSubmit) return
    const api = new DocRouterOrgApi(organizationId)
    setBusy(true)
    try {
      if (mode === 'cascade') {
        toast.info('Deleting case and documents…', { duration: 3000 })
      }
      const result = await deleteCaseAndWait(api, caseRow.case_id, mode)
      if (result.cascade && result.polled) {
        toast.success(
          docCount > 0 ? `Case and ${docCount} document(s) deleted.` : 'Case deleted.',
        )
      } else {
        toast.success(
          docCount > 0
            ? `Case deleted. ${docCount} document(s) were unassigned and kept.`
            : 'Case deleted.',
        )
      }
      resetForm()
      onClose()
      await onDeleted()
    } catch (error) {
      toastActionError('Failed to delete case', error)
    } finally {
      setBusy(false)
    }
  }

  if (!caseRow) {
    return null
  }

  const title = caseDisplayName(caseRow)

  return (
    <Dialog open={open} onOpenChange={(next) => !next && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete case</DialogTitle>
          <DialogDescription className="text-left">
            <span className="font-medium text-foreground">{title}</span>
            {title !== caseRow.case_id ? (
              <span className="mt-1 block font-mono text-xs">{caseRow.case_id}</span>
            ) : null}
            <span className="mt-2 block">
              This case contains <strong>{docCount}</strong> document{docCount === 1 ? '' : 's'}.
            </span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3" role="radiogroup" aria-label="Delete mode">
          <label
            className={`flex cursor-pointer gap-2 rounded-lg border p-3 ${
              mode === 'unassign' ? 'border-primary' : 'border-border'
            }`}
          >
            <input
              type="radio"
              name="case-delete-mode"
              className="mt-0.5"
              checked={mode === 'unassign'}
              disabled={busy}
              onChange={() => {
                setMode('unassign')
                setConfirmId('')
              }}
            />
            <span className="text-sm">
              Remove case only — documents stay in the org and are unassigned from this case.
            </span>
          </label>
          {canCascadeDelete ? (
            <label
              className={`flex cursor-pointer gap-2 rounded-lg border p-3 ${
                mode === 'cascade' ? 'border-primary' : 'border-border'
              }`}
            >
              <input
                type="radio"
                name="case-delete-mode"
                className="mt-0.5"
                checked={mode === 'cascade'}
                disabled={busy}
                onChange={() => setMode('cascade')}
              />
              <span className="text-sm">Delete case and all member documents</span>
            </label>
          ) : null}
        </div>

        {mode === 'cascade' ? (
          <div className="space-y-3">
            <Alert variant="destructive">
              <AlertDescription>
                This permanently deletes every document in the case (files, OCR, extractions, and
                related data). This cannot be undone.
              </AlertDescription>
            </Alert>
            <div className="space-y-2">
              <Label htmlFor="case-delete-confirm">Type case id to confirm</Label>
              <Input
                id="case-delete-confirm"
                value={confirmId}
                onChange={(e) => setConfirmId(e.target.value)}
                disabled={busy}
                autoComplete="off"
                className="font-mono"
                placeholder={caseRow.case_id}
              />
            </div>
          </div>
        ) : null}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={handleClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={!canSubmit}
            onClick={() => void handleSubmit()}
          >
            {busy ? 'Deleting…' : mode === 'cascade' ? 'Delete case and documents' : 'Delete case'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
