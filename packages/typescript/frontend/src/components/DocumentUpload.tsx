'use client'

import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { CloudUpload, Loader2, Plus, Trash2 } from 'lucide-react'
import type { Tag } from '@docrouter/sdk'

import { useOrgAllTags } from '@/api/orgQueries'
import { CaseAssignmentFields } from './CaseAssignmentFields'
import { TagBadge } from '@/components/TagBadge'
import { TagCheckboxList } from '@/components/TagCheckboxList'
import InfoTooltip from '@/components/InfoTooltip'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities'
import { DocRouterOrgApi } from '@/utils/api'
import { randomUUID } from '@/utils/uuid'
import { toast } from 'react-toastify'
import { toastActionError } from '@/utils/toastActionError'
import { useOrgCapability } from '@/hooks/useOrgPermissions'

interface DocumentUploadProps {
  organizationId: string
  defaultCaseId?: string
}

interface PendingUploadFile {
  id: string
  file: File
}

const DocumentUpload: React.FC<DocumentUploadProps> = ({ organizationId, defaultCaseId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const { hasCapability: canUpload, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_DOCUMENTS_WRITE,
  )
  const { data: availableTags = [] } = useOrgAllTags(organizationId, canUpload || capabilitiesLoading)

  const [files, setFiles] = useState<PendingUploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [metadataFields, setMetadataFields] = useState<Array<{ id: string; key: string; value: string }>>([])
  const [validationError, setValidationError] = useState<string | null>(null)
  const [activeStep, setActiveStep] = useState(0)
  const [caseId, setCaseId] = useState(defaultCaseId ?? '')

  useEffect(() => {
    setCaseId(defaultCaseId ?? '')
  }, [defaultCaseId])

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newRows: PendingUploadFile[] = acceptedFiles.map((file) => ({
      id: randomUUID(),
      file,
    }))
    setFiles((prev) => [...prev, ...newRows])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: !canUpload || capabilitiesLoading,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/gif': ['.gif'],
      'image/webp': ['.webp'],
      'image/bmp': ['.bmp'],
      'image/tiff': ['.tiff', '.tif'],
    },
    multiple: true,
  })

  const handleUpload = async () => {
    if (files.length === 0) return
    if (!canUpload) {
      toast.error('You do not have permission to upload documents.')
      return
    }

    const metadata = Object.fromEntries(
      metadataFields.filter((field) => field.key.trim() !== '').map((field) => [field.key, field.value]),
    )

    setUploading(true)

    try {
      await Promise.all(
        files.map(({ file }) =>
          docRouterOrgApi.uploadDocumentMultipart({
            name: file.name,
            file,
            tag_ids: selectedTags,
            metadata,
            case_id: caseId.trim() || undefined,
          }),
        ),
      )

      const fileNames = files.map((row) => row.file.name).join(', ')
      const tagNames =
        selectedTags.length > 0
          ? availableTags
              .filter((tag) => selectedTags.includes(tag.id))
              .map((tag) => tag.name)
              .join(', ')
          : 'no tags'

      toast.success(
        `Uploaded ${files.length} file(s): ${fileNames}${tagNames !== 'no tags' ? ` (${tagNames})` : ''}`,
      )

      setFiles([])
      setSelectedTags([])
      setMetadataFields([])
      setCaseId(defaultCaseId ?? '')
      setActiveStep(0)
    } catch (error) {
      console.error('Error uploading files:', error)
      toastActionError('Upload failed', error)
    } finally {
      setUploading(false)
    }
  }

  const handleAddMetadata = () => {
    setMetadataFields((prev) => [...prev, { id: `field_${Date.now()}`, key: '', value: '' }])
  }

  const handleRemoveMetadata = (id: string) => {
    setMetadataFields((prev) => prev.filter((field) => field.id !== id))
  }

  const handleMetadataKeyChange = (id: string, newKey: string) => {
    setMetadataFields((prev) => prev.map((field) => (field.id === id ? { ...field, key: newKey } : field)))
    setValidationError(null)
  }

  const handleMetadataValueChange = (id: string, newValue: string) => {
    setMetadataFields((prev) => prev.map((field) => (field.id === id ? { ...field, value: newValue } : field)))
    setValidationError(null)
  }

  const handleNextStep = useCallback(() => {
    if (activeStep === 1) {
      const nonEmptyFields = metadataFields.filter((field) => field.key.trim() !== '')
      const keys = nonEmptyFields.map((field) => field.key)
      const duplicateKeys = keys.filter((key, index) => keys.indexOf(key) !== index)

      if (duplicateKeys.length > 0) {
        setValidationError(
          `Duplicate keys found: ${duplicateKeys.join(', ')}. Please remove or rename duplicate keys.`,
        )
        return
      }
    }

    setActiveStep((prev) => Math.min(prev + 1, 2))
    setValidationError(null)
  }, [activeStep, metadataFields])

  const handlePrevStep = useCallback(() => {
    setActiveStep((prev) => Math.max(prev - 1, 0))
    setValidationError(null)
  }, [])

  const handleDeleteFile = useCallback(
    (id: string) => {
      setFiles((prevFiles) => prevFiles.filter((row) => row.id !== id))
      if (files.length === 1) {
        setActiveStep(0)
      }
    },
    [files.length],
  )

  const selectedTagObjects = useMemo(
  () => availableTags.filter((tag) => selectedTags.includes(tag.id)),
  [availableTags, selectedTags],
  )

  if (!capabilitiesLoading && !canUpload) {
    return (
      <div className="mx-auto max-w-3xl p-4 text-muted-foreground">
        You do not have permission to upload documents. Contact an organization admin if you need upload access.
      </div>
    )
  }

  const stepButton = (step: number, label: string, enabled: boolean) => (
    <button
      type="button"
      disabled={!enabled}
      className={`flex flex-col items-center disabled:cursor-not-allowed ${
        activeStep >= step ? 'text-primary' : 'text-muted-foreground'
      }`}
      onClick={() => enabled && setActiveStep(step)}
    >
      <div
        className={`mb-1 flex h-8 w-8 items-center justify-center rounded-full ${
          activeStep >= step ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
        }`}
      >
        {step + 1}
      </div>
      <span className="text-sm">{label}</span>
    </button>
  )

  const fileRow = (row: PendingUploadFile) => (
    <div key={row.id} className="flex items-center justify-between px-2 py-1 odd:bg-muted/40">
      <span className="truncate text-sm">{row.file.name}</span>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={`Remove ${row.file.name}`}
        onClick={() => handleDeleteFile(row.id)}
      >
        <Trash2 className="text-destructive" />
      </Button>
    </div>
  )

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 hidden items-center gap-2 md:flex">
        <h2 className="text-xl font-bold">Upload Documents</h2>
        <InfoTooltip
          title="Document Upload"
          content={
            <>
              <p className="mb-2">Upload documents to be processed by AI prompts. Supported file formats:</p>
              <ul className="mb-2 list-inside list-disc space-y-1">
                <li>
                  <strong>PDF files</strong> (.pdf)
                </li>
                <li>
                  <strong>Word documents</strong> (.doc, .docx)
                </li>
                <li>
                  <strong>Excel files</strong> (.xls, .xlsx)
                </li>
                <li>
                  <strong>CSV files</strong> (.csv)
                </li>
                <li>
                  <strong>Text files</strong> (.txt, .md)
                </li>
                <li>
                  <strong>Image files</strong> (.jpg, .jpeg, .png, .gif, .webp, .bmp, .tiff, .tif)
                </li>
              </ul>
              <p className="mb-2">
                <strong>Note:</strong> Select appropriate tags for your documents to control which prompts are run.
                Images will be processed using OCR to extract text.
              </p>
            </>
          }
        />
      </div>

      <div className="mb-6">
        <div className="flex items-center justify-between">
          {stepButton(0, 'Select Files', true)}
          <div className={`mx-2 h-1 flex-1 ${activeStep >= 1 ? 'bg-primary' : 'bg-muted'}`} />
          {stepButton(1, 'Tags & Metadata', files.length > 0)}
          <div className={`mx-2 h-1 flex-1 ${activeStep >= 2 ? 'bg-primary' : 'bg-muted'}`} />
          {stepButton(2, 'Upload', files.length > 0)}
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6 shadow-sm">
        {activeStep === 0 && (
          <div>
            <h3 className="mb-4 text-lg font-medium">Select Files</h3>
            <p className="mb-3 text-sm text-muted-foreground">
              PDF, Word, Excel, CSV, text, markdown, and common image formats.
            </p>
            <div
              {...getRootProps()}
              className="cursor-pointer rounded-lg border-2 border-dashed border-border p-6 transition-colors hover:bg-muted/40"
            >
              <input {...getInputProps()} />
              <CloudUpload className="mx-auto mb-2 size-12 text-muted-foreground" />
              <p className="text-center text-sm">
                {isDragActive ? 'Drop files here…' : 'Drag files here, or click to select files'}
              </p>
            </div>

            {files.length > 0 ? (
              <div className="mt-4">
                <Label className="mb-2 block">Selected files</Label>
                <div className="max-h-40 overflow-y-auto rounded-md border">{files.map(fileRow)}</div>
              </div>
            ) : null}

            <div className="mt-6 flex justify-end">
              <Button type="button" onClick={handleNextStep} disabled={files.length === 0}>
                Continue
              </Button>
            </div>
          </div>
        )}

        {activeStep === 1 && (
          <div>
            <h3 className="mb-4 text-lg font-medium">Tags &amp; Metadata (optional)</h3>

            <div className="mb-6 rounded-lg bg-muted/40 p-3">
              <Label className="mb-2 block">Selected files</Label>
              <div className="max-h-32 overflow-y-auto text-sm">{files.map(fileRow)}</div>
            </div>

            <div className="space-y-6">
              <CaseAssignmentFields
                organizationId={organizationId}
                caseId={caseId}
                onCaseIdChange={setCaseId}
              />

              <div className="space-y-2">
                <Label>Tags</Label>
                <p className="text-sm text-muted-foreground">
                  Select tags so documents are processed by the right prompts.
                </p>
                <TagCheckboxList tags={availableTags} selectedIds={selectedTags} onChange={setSelectedTags} />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Metadata</Label>
                  <Button type="button" variant="ghost" size="sm" onClick={handleAddMetadata}>
                    <Plus data-icon="inline-start" />
                    Add field
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">Key-value pairs attached to all uploaded documents.</p>
                <div className="space-y-2">
                  {metadataFields.map((field) => (
                    <div key={field.id} className="flex items-center gap-2">
                      <Input
                        placeholder="Key"
                        value={field.key}
                        onChange={(e) => handleMetadataKeyChange(field.id, e.target.value)}
                        className="flex-1"
                      />
                      <Input
                        placeholder="Value"
                        value={field.value}
                        onChange={(e) => handleMetadataValueChange(field.id, e.target.value)}
                        className="flex-1"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Remove field"
                        onClick={() => handleRemoveMetadata(field.id)}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  ))}
                  {metadataFields.length === 0 ? (
                    <p className="text-sm italic text-muted-foreground">No metadata fields.</p>
                  ) : null}
                </div>
                {validationError ? (
                  <Alert variant="destructive">
                    <AlertDescription>{validationError}</AlertDescription>
                  </Alert>
                ) : null}
              </div>
            </div>

            <div className="mt-6 flex justify-between gap-2">
              <Button type="button" variant="outline" onClick={handlePrevStep}>
                Back
              </Button>
              <Button type="button" onClick={handleNextStep}>
                Continue
              </Button>
            </div>
          </div>
        )}

        {activeStep === 2 && (
          <div>
            <h3 className="mb-4 text-lg font-medium">Upload files</h3>

            <div className="mb-6 space-y-4 rounded-lg bg-muted/40 p-4">
              <div>
                <Label className="mb-2 block">Selected files</Label>
                <div className="text-sm">{files.map(fileRow)}</div>
              </div>

              <div>
                <Label className="mb-2 block">Selected tags</Label>
                <div className="flex flex-wrap gap-1">
                  {selectedTagObjects.length > 0 ? (
                    selectedTagObjects.map((tag: Tag) => <TagBadge key={tag.id} tag={tag} />)
                  ) : (
                    <span className="text-sm italic text-muted-foreground">No tags selected</span>
                  )}
                </div>
              </div>

              <div>
                <Label className="mb-2 block">Metadata</Label>
                <div className="space-y-1">
                  {metadataFields.filter((field) => field.key.trim() !== '').length > 0 ? (
                    metadataFields
                      .filter((field) => field.key.trim() !== '')
                      .map((field) => (
                        <div key={field.id} className="flex text-sm">
                          <span className="mr-2 font-medium text-muted-foreground">{field.key}:</span>
                          <span>{field.value || '(empty)'}</span>
                        </div>
                      ))
                  ) : (
                    <span className="text-sm italic text-muted-foreground">No metadata fields</span>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-between gap-2">
              <Button type="button" variant="outline" onClick={handlePrevStep} disabled={uploading}>
                Back
              </Button>
              <Button type="button" onClick={() => void handleUpload()} disabled={uploading || !canUpload}>
                {uploading ? <Loader2 className="animate-spin" data-icon="inline-start" /> : <CloudUpload data-icon="inline-start" />}
                {uploading ? 'Uploading…' : 'Upload files'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default DocumentUpload
