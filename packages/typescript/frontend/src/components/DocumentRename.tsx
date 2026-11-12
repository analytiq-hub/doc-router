import { useEffect, useState } from 'react'

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

interface DocumentRenameModalProps {
  isOpen: boolean
  onClose: () => void
  documentName: string
  onSubmit: (newName: string) => Promise<void>
}

const DocumentRenameModal: React.FC<DocumentRenameModalProps> = ({
  isOpen,
  onClose,
  documentName,
  onSubmit,
}) => {
  const [newName, setNewName] = useState(documentName)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setNewName(documentName)
      setError(null)
    }
  }, [isOpen, documentName])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!newName.trim()) {
      setError('Document name cannot be empty')
      return
    }
    setIsSubmitting(true)
    try {
      await onSubmit(newName)
      onClose()
    } catch (err) {
      console.error('Document rename failed:', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  const unchanged = newName.trim() === documentName

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Rename document</DialogTitle>
          <DialogDescription>Enter a new file name for this document.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="space-y-2">
            <Label htmlFor="document-rename">Name</Label>
            <Input
              id="document-rename"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoFocus
            />
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !newName.trim() || unchanged}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default DocumentRenameModal
