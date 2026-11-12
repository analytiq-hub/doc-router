import { Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Tag } from '@docrouter/sdk'

import { CaseAssignmentFields } from './CaseAssignmentFields'
import { TagCheckboxList } from '@/components/TagCheckboxList'
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

interface DocumentUpdateProps {
  isOpen: boolean
  onClose: () => void
  documentName: string
  currentTags: string[]
  currentMetadata?: Record<string, string>
  currentCaseId?: string | null
  availableTags: Tag[]
  onSave: (
    tagIds: string[],
    metadata: Record<string, string>,
    caseOptions?: { caseId: string | null; createCaseIfMissing: boolean },
  ) => Promise<void>
}

export function DocumentUpdate({
  isOpen,
  onClose,
  documentName,
  currentTags,
  currentMetadata = {},
  currentCaseId = null,
  availableTags,
  onSave,
}: DocumentUpdateProps) {
  const [selectedTags, setSelectedTags] = useState(currentTags)
  const [caseIdInput, setCaseIdInput] = useState('')
  const [createCaseIfMissing, setCreateCaseIfMissing] = useState(false)
  const [metadataFields, setMetadataFields] = useState<Array<{ id: string; key: string; value: string }>>([])
  const [validationError, setValidationError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setSelectedTags(currentTags)
      setMetadataFields(
        Object.entries(currentMetadata).map(([key, value], index) => ({
          id: `field_${index}`,
          key,
          value,
        })),
      )
      setCaseIdInput(currentCaseId ?? '')
      setCreateCaseIfMissing(false)
      setValidationError(null)
    }
  }, [isOpen, currentTags, currentMetadata, currentCaseId])

  const handleAddMetadata = () => {
    setMetadataFields((prev) => [...prev, { id: `field_${Date.now()}`, key: '', value: '' }])
  }

  const handleSave = async () => {
    const nonEmptyFields = metadataFields.filter((field) => field.key.trim() !== '')
    const keys = nonEmptyFields.map((field) => field.key)
    const duplicateKeys = keys.filter((key, index) => keys.indexOf(key) !== index)
    if (duplicateKeys.length > 0) {
      setValidationError(
        `Duplicate keys found: ${duplicateKeys.join(', ')}. Please remove or rename duplicate keys.`,
      )
      return
    }
    const cleanMetadata: Record<string, string> = {}
    nonEmptyFields.forEach((field) => {
      cleanMetadata[field.key] = field.value
    })
    const newCaseId = caseIdInput.trim() || null
    const caseChanged = newCaseId !== (currentCaseId || null)
    setSaving(true)
    try {
      await onSave(
        selectedTags,
        cleanMetadata,
        caseChanged ? { caseId: newCaseId, createCaseIfMissing } : undefined,
      )
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="top-4 right-4 bottom-4 left-auto flex w-[min(calc(100vw-2rem),28rem)] max-w-none translate-x-0 translate-y-0 flex-col gap-0 rounded-xl p-0 sm:max-w-none">
        <DialogHeader className="border-b px-4 py-4">
          <DialogTitle className="truncate">Update document</DialogTitle>
          <DialogDescription className="truncate" title={documentName}>
            {documentName}
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-4">
          <div className="space-y-2">
            <Label>Tags</Label>
            <TagCheckboxList
              tags={availableTags}
              selectedIds={selectedTags}
              onChange={setSelectedTags}
            />
          </div>
          <div className="space-y-2">
            <Label>Case</Label>
            <CaseAssignmentFields
              caseId={caseIdInput}
              onCaseIdChange={setCaseIdInput}
              createCaseIfMissing={createCaseIfMissing}
              onCreateCaseIfMissingChange={setCreateCaseIfMissing}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Metadata</Label>
              <Button type="button" variant="ghost" size="sm" onClick={handleAddMetadata}>
                <Plus data-icon="inline-start" />
                Add field
              </Button>
            </div>
            <div className="space-y-2">
              {metadataFields.map((field) => (
                <div key={field.id} className="flex items-center gap-2">
                  <Input
                    placeholder="Key"
                    value={field.key}
                    onChange={(e) =>
                      setMetadataFields((prev) =>
                        prev.map((f) => (f.id === field.id ? { ...f, key: e.target.value } : f)),
                      )
                    }
                    className="flex-1"
                  />
                  <Input
                    placeholder="Value"
                    value={field.value}
                    onChange={(e) =>
                      setMetadataFields((prev) =>
                        prev.map((f) => (f.id === field.id ? { ...f, value: e.target.value } : f)),
                      )
                    }
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Remove field"
                    onClick={() => setMetadataFields((prev) => prev.filter((f) => f.id !== field.id))}
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))}
              {metadataFields.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">No metadata fields.</p>
              ) : null}
            </div>
            {validationError ? (
              <Alert variant="destructive">
                <AlertDescription>{validationError}</AlertDescription>
              </Alert>
            ) : null}
          </div>
        </div>
        <DialogFooter className="border-t bg-muted/40 px-4 py-3">
          <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="button" onClick={() => void handleSave()} disabled={saving}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
