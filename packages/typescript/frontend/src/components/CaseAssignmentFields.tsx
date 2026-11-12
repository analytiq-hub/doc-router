'use client'

import { Loader2, Plus } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Case } from '@docrouter/sdk'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field, FieldContent, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useDebounced } from '@/lib/useDebounced'
import { DocRouterOrgApi } from '@/utils/api'
import { caseDisplayName } from '@/utils/caseDisplayName'
import { toastActionError } from '@/utils/toastActionError'
import { toast } from 'react-toastify'

const CASE_SEARCH_LIMIT = 25

export type CaseAssignMode = 'none' | 'search' | 'create'

type CaseAssignmentFieldsProps = {
  organizationId: string
  caseId: string
  onCaseIdChange: (value: string) => void
  disabled?: boolean
  /** When false, only direct case ID entry (e.g. bulk assign). Default true. */
  allowNameLookup?: boolean
  onAssignModeChange?: (mode: CaseAssignMode) => void
}

export function CaseAssignmentFields({
  organizationId,
  caseId,
  onCaseIdChange,
  disabled = false,
  allowNameLookup = true,
  onAssignModeChange,
}: CaseAssignmentFieldsProps) {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const [mode, setMode] = useState<CaseAssignMode>(() => (caseId.trim() ? 'search' : 'none'))
  const [searchQuery, setSearchQuery] = useState('')
  const [newCaseName, setNewCaseName] = useState('')
  const debouncedSearch = useDebounced(searchQuery.trim())
  const [searchResults, setSearchResults] = useState<Case[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  const setAssignMode = (next: CaseAssignMode) => {
    setMode(next)
    onAssignModeChange?.(next)
    if (next === 'none') {
      onCaseIdChange('')
      setSelectedCase(null)
    }
  }

  useEffect(() => {
    onAssignModeChange?.(mode)
  }, [mode, onAssignModeChange])

  useEffect(() => {
    if (!caseId.trim()) {
      setSelectedCase(null)
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const row = await docRouterOrgApi.getCase({ caseId: caseId.trim() })
        if (!cancelled) setSelectedCase(row)
      } catch {
        if (!cancelled) setSelectedCase(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [caseId, docRouterOrgApi])

  const loadSearch = useCallback(async () => {
    if (!allowNameLookup || mode !== 'search' || !debouncedSearch) {
      setSearchResults([])
      setSearchError(null)
      return
    }
    setSearchLoading(true)
    setSearchError(null)
    try {
      const res = await docRouterOrgApi.listCases({
        caseIdSearch: debouncedSearch,
        limit: CASE_SEARCH_LIMIT,
      })
      setSearchResults(res.cases)
    } catch (error) {
      setSearchResults([])
      setSearchError('Could not search cases')
      console.error(error)
    } finally {
      setSearchLoading(false)
    }
  }, [allowNameLookup, debouncedSearch, docRouterOrgApi, mode])

  useEffect(() => {
    void loadSearch()
  }, [loadSearch])

  const handleSelectCase = (row: Case) => {
    onCaseIdChange(row.case_id)
    setSelectedCase(row)
  }

  const handleClearSelection = () => {
    onCaseIdChange('')
    setSelectedCase(null)
  }

  const handleCreateCase = async (name: string) => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('Enter a case name to create')
      return
    }
    setCreateLoading(true)
    try {
      const created = await docRouterOrgApi.createCase({ body: { name: trimmed } })
      onCaseIdChange(created.case_id)
      setSelectedCase(created)
      setNewCaseName(trimmed)
      toast.success('Case created and selected for assignment')
    } catch (error) {
      toastActionError('Failed to create case', error)
    } finally {
      setCreateLoading(false)
    }
  }

  const selectedLabel = selectedCase ? caseDisplayName(selectedCase) : null
  const showNoMatchesCreate =
    mode === 'search' && !searchLoading && !!debouncedSearch && searchResults.length === 0 && !searchError

  if (!allowNameLookup) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Label className="shrink-0">Case</Label>
        </div>
        <Field>
          <FieldLabel htmlFor="case-id-input">Case ID</FieldLabel>
          <FieldContent>
            <Input
              id="case-id-input"
              value={caseId}
              onChange={(e) => onCaseIdChange(e.target.value)}
              disabled={disabled}
              placeholder="24-character id (from the cases list)"
              className="font-mono text-xs"
            />
          </FieldContent>
        </Field>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Label className="shrink-0">Case</Label>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="case-assign-mode"
              checked={mode === 'none'}
              disabled={disabled}
              onChange={() => setAssignMode('none')}
            />
            None
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="case-assign-mode"
              checked={mode === 'search'}
              disabled={disabled}
              onChange={() => setAssignMode('search')}
            />
            Find existing
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="case-assign-mode"
              checked={mode === 'create'}
              disabled={disabled}
              onChange={() => setAssignMode('create')}
            />
            Create new case
          </label>
        </div>
      </div>

      {mode !== 'none' && caseId.trim() ? (
        <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="font-medium truncate">{selectedLabel ?? 'Selected case'}</p>
              <p className="font-mono text-xs text-muted-foreground truncate">{caseId.trim()}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={disabled}
              onClick={handleClearSelection}
            >
              Clear
            </Button>
          </div>
        </div>
      ) : null}

      {mode === 'none' ? null : mode === 'create' ? (
        <Field>
          <FieldLabel htmlFor="new-case-name">New case name</FieldLabel>
          <FieldContent className="space-y-2">
            <Input
              id="new-case-name"
              value={newCaseName}
              onChange={(e) => setNewCaseName(e.target.value)}
              disabled={disabled}
              placeholder="e.g. Smith — auto loss"
            />
            <Button
              type="button"
              disabled={disabled || createLoading || !newCaseName.trim()}
              onClick={() => void handleCreateCase(newCaseName)}
            >
              {createLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" data-icon="inline-start" />
              ) : (
                <Plus data-icon="inline-start" />
              )}
              Create case and assign
            </Button>
          </FieldContent>
          <FieldDescription>
            Creates a new case with a server-assigned id. Names may repeat; assignment always uses the
            case id.
          </FieldDescription>
        </Field>
      ) : (
        <>
          <Field>
            <FieldLabel htmlFor="case-name-search">Search cases</FieldLabel>
            <FieldContent>
              <Input
                id="case-name-search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                disabled={disabled}
                placeholder="Type case name or id"
              />
            </FieldContent>
          </Field>

          {searchLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching…
            </p>
          ) : null}
          {searchError ? <p className="text-sm text-destructive">{searchError}</p> : null}

          {showNoMatchesCreate ? (
            <Alert>
              <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <span>No cases match “{debouncedSearch}”.</span>
                <Button
                  type="button"
                  size="sm"
                  disabled={disabled || createLoading}
                  onClick={() => void handleCreateCase(debouncedSearch)}
                >
                  {createLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" data-icon="inline-start" />
                  ) : (
                    <Plus data-icon="inline-start" />
                  )}
                  Create case
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}

          {!searchLoading && debouncedSearch && searchResults.length > 0 ? (
            <ul className="max-h-48 space-y-1 overflow-y-auto rounded-md border p-1" role="listbox">
              {searchResults.map((row) => {
                const active = row.case_id === caseId.trim()
                return (
                  <li key={row.case_id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={active}
                      disabled={disabled}
                      className={`flex w-full flex-col rounded-sm px-2 py-1.5 text-left text-sm hover:bg-muted ${
                        active ? 'bg-muted font-medium' : ''
                      }`}
                      onClick={() => handleSelectCase(row)}
                    >
                      <span className="truncate">{caseDisplayName(row)}</span>
                      <span className="font-mono text-xs text-muted-foreground">{row.case_id}</span>
                      <span className="text-xs text-muted-foreground">
                        {row.document_count} document{row.document_count === 1 ? '' : 's'}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          ) : null}
        </>
      )}
    </div>
  )
}
