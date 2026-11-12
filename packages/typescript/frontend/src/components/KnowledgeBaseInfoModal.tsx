'use client'

import { Loader2, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { KnowledgeBase, KBStatus } from '@docrouter/sdk'

import { PropertiesDialog, type Property } from '@/components/PropertiesDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DocRouterOrgApi } from '@/utils/api'
import { toastActionError } from '@/utils/toastActionError'
import { formatLocalDate } from '@/utils/date'
import { toast } from 'sonner'

interface KnowledgeBaseInfoModalProps {
  isOpen: boolean
  onClose: () => void
  kb: KnowledgeBase
  organizationId: string
  onReconcile?: () => void
}

function statusVariant(status: KBStatus): 'success' | 'warning' | 'danger' | 'outline' {
  switch (status) {
    case 'active':
      return 'success'
    case 'indexing':
      return 'warning'
    case 'error':
      return 'danger'
    default:
      return 'outline'
  }
}

function formatInterval(seconds?: number) {
  if (!seconds) return 'N/A'
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

function emptyEm(value: React.ReactNode, fallback = '—') {
  if (value === null || value === undefined || value === '') return <span className="text-muted-foreground italic">{fallback}</span>
  return value
}

const KnowledgeBaseInfoModal: React.FC<KnowledgeBaseInfoModalProps> = ({
  isOpen,
  onClose,
  kb,
  organizationId,
  onReconcile,
}) => {
  const [isReconciling, setIsReconciling] = useState(false)
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])

  const properties = useMemo<Property[]>(() => {
    const preprocess = kb.chunking_preprocess
    return [
      { label: 'Name', value: kb.name },
      {
        label: 'Status',
        value: (
          <Badge variant={statusVariant(kb.status)} className="capitalize">
            {kb.status}
          </Badge>
        ),
      },
      { label: 'Description', value: emptyEm(kb.description, 'No description') },
      {
        label: 'System prompt',
        value: (
          <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap font-mono text-xs">
            {kb.system_prompt || 'No system prompt'}
          </pre>
        ),
      },
      { label: 'KB ID', value: <span className="font-mono text-xs">{kb.kb_id}</span> },
      { label: 'Embedding model', value: <span className="font-mono text-xs">{kb.embedding_model}</span> },
      { label: 'Dimensions', value: String(kb.embedding_dimensions) },
      { label: 'Chunker', value: kb.chunker_type },
      { label: 'Chunk size', value: `${kb.chunk_size} tokens` },
      { label: 'Chunk overlap', value: `${kb.chunk_overlap} tokens` },
      {
        label: 'Chunk preset',
        value: emptyEm(
          kb.chunking_preset != null ? kb.chunking_preset : null,
          '(legacy default)',
        ),
      },
      {
        label: 'Preprocess',
        value: preprocess ? (
          <ul className="list-inside list-disc text-xs">
            <li>prefer_markdown: {String(preprocess.prefer_markdown)}</li>
            <li>strip_page_numbers: {String(preprocess.strip_page_numbers)}</li>
            <li>strip_page_breaks: {String(preprocess.strip_page_breaks)}</li>
            <li>prepend_heading_path: {String(preprocess.prepend_heading_path)}</li>
            <li>heading_split_depth: {preprocess.heading_split_depth}</li>
            <li>
              strip_patterns:{' '}
              {preprocess.strip_patterns?.length
                ? `${preprocess.strip_patterns.length} regex(es)`
                : 'none'}
            </li>
          </ul>
        ) : (
          <span className="text-muted-foreground italic text-xs">Legacy KB (no custom preprocess)</span>
        ),
      },
      { label: 'Coalesce neighbors', value: String(kb.coalesce_neighbors ?? 1) },
      {
        label: 'Min vector score',
        value:
          kb.min_vector_score != null ? (
            String(kb.min_vector_score)
          ) : (
            <span className="text-muted-foreground">None (no cutoff)</span>
          ),
      },
      { label: 'Documents', value: kb.document_count.toLocaleString() },
      { label: 'Chunks', value: kb.chunk_count.toLocaleString() },
      {
        label: 'Tag IDs',
        value:
          (kb.tag_ids?.length ?? 0) > 0 ? (
            <div className="flex flex-wrap gap-1">
              {(kb.tag_ids ?? []).map((tagId) => (
                <span key={tagId} className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                  {tagId}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-muted-foreground italic">No tags</span>
          ),
      },
      { label: 'Created', value: formatLocalDate(kb.created_at) },
      { label: 'Updated', value: formatLocalDate(kb.updated_at) },
      {
        label: 'Reconcile',
        value: (
          <div className="space-y-1 text-xs">
            <div className="flex items-center gap-2">
              <span>Periodic:</span>
              <Badge variant={kb.reconcile_enabled ? 'success' : 'outline'}>
                {kb.reconcile_enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
            {kb.reconcile_enabled && kb.reconcile_interval_seconds ? (
              <p>Interval: {formatInterval(kb.reconcile_interval_seconds)}</p>
            ) : null}
            <p>
              Last run:{' '}
              {kb.last_reconciled_at ? (
                formatLocalDate(kb.last_reconciled_at)
              ) : (
                <span className="text-muted-foreground italic">Never</span>
              )}
            </p>
          </div>
        ),
      },
    ]
  }, [kb])

  if (!isOpen) return null

  const handleReconcile = async () => {
    setIsReconciling(true)
    try {
      const result = await docRouterOrgApi.reconcileKnowledgeBase({
        kbId: kb.kb_id,
        dry_run: false,
      })
      toast.success(
        `Reconciliation complete: ${result.missing_documents.length} missing, ` +
          `${result.stale_documents.length} stale, ${result.orphaned_vectors} orphaned vectors`,
      )
      onReconcile?.()
    } catch (error) {
      toastActionError('Reconciliation failed', error)
    } finally {
      setIsReconciling(false)
    }
  }

  return (
    <PropertiesDialog
      title="Knowledge base properties"
      description={kb.name}
      properties={properties}
      columns={2}
      onClose={onClose}
      footer={
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t bg-muted/40 px-4 py-3">
          <Button type="button" variant="outline" size="sm" disabled={isReconciling} onClick={() => void handleReconcile()}>
            {isReconciling ? (
              <Loader2 className="animate-spin" data-icon="inline-start" />
            ) : (
              <RefreshCw data-icon="inline-start" />
            )}
            {isReconciling ? 'Reconciling…' : 'Reconcile now'}
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    />
  )
}

export default KnowledgeBaseInfoModal
