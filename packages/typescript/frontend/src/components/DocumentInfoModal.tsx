import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Document, Tag } from '@docrouter/sdk'

import { PropertiesDialog } from '@/components/PropertiesDialog'
import { TagBadge } from '@/components/TagBadge'
import { DocRouterAccountApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'

interface DocumentInfoModalProps {
  isOpen: boolean
  onClose: () => void
  document: Document
  organizationId: string
  availableTags?: Tag[]
}

const DocumentInfoModal: React.FC<DocumentInfoModalProps> = ({
  isOpen,
  onClose,
  document,
  organizationId,
  availableTags = [],
}) => {
  const [uploadedByUserId, setUploadedByUserId] = useState<string | null>(null)
  const [isLoadingUserId, setIsLoadingUserId] = useState(false)
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])
  const tagsById = useMemo(() => new Map(availableTags.map((tag) => [tag.id, tag])), [availableTags])

  useEffect(() => {
    if (isOpen && document.uploaded_by) {
      setIsLoadingUserId(true)
      docRouterAccountApi
        .listUsers({ search_name: document.uploaded_by, limit: 1 })
        .then((response) => {
          const user = response.users.find(
            (u) => u.name?.toLowerCase() === document.uploaded_by.toLowerCase(),
          )
          setUploadedByUserId(user?.id ?? null)
        })
        .catch((error) => {
          console.error('Error fetching user ID:', error)
          setUploadedByUserId(null)
        })
        .finally(() => setIsLoadingUserId(false))
    } else {
      setUploadedByUserId(null)
    }
  }, [isOpen, document.uploaded_by, docRouterAccountApi])

  if (!isOpen) return null

  const tagValue =
    document.tag_ids && document.tag_ids.length > 0 ? (
      <ul className="space-y-1.5">
        {document.tag_ids.map((tagId) => {
          const tag = tagsById.get(tagId)
          return (
            <li key={tagId} className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{tagId}</span>
              {tag ? <TagBadge tag={tag} /> : <span className="text-muted-foreground italic">Unknown tag</span>}
            </li>
          )
        })}
      </ul>
    ) : (
      '—'
    )

  const metadataValue =
    document.metadata && Object.keys(document.metadata).length > 0 ? (
      <dl className="space-y-1">
        {Object.entries(document.metadata).map(([key, value]) => (
          <div key={key}>
            <dt className="inline font-medium after:content-[':']">{key}</dt>{' '}
            <dd className="inline">{value}</dd>
          </div>
        ))}
      </dl>
    ) : (
      '—'
    )

  return (
    <PropertiesDialog
      title="Document properties"
      description={document.document_name}
      columns={2}
      onClose={onClose}
      properties={[
        { label: 'Name', value: document.document_name },
        { label: 'State', value: document.state?.replaceAll('_', ' ') ?? '—' },
        { label: 'Document ID', value: <span className="font-mono text-xs break-all">{document.id}</span> },
        { label: 'PDF ID', value: <span className="font-mono text-xs break-all">{document.pdf_id}</span> },
        {
          label: 'Type',
          value: document.type?.trim() ? document.type : '—',
        },
        {
          label: 'Case',
          value: document.case_id ? (
            <Link
              to={`/orgs/${organizationId}/cases/${encodeURIComponent(document.case_id)}`}
              className="text-primary hover:underline"
            >
              {document.case_id}
            </Link>
          ) : (
            '—'
          ),
        },
        { label: 'Uploaded', value: formatLocalDate(document.upload_date) },
        { label: 'Uploaded by', value: document.uploaded_by?.trim() || '—' },
        {
          label: 'Uploader ID',
          value: isLoadingUserId ? (
            <span className="text-muted-foreground">Loading…</span>
          ) : uploadedByUserId ? (
            <span className="font-mono text-xs break-all">{uploadedByUserId}</span>
          ) : (
            '—'
          ),
        },
        { label: 'Tags', value: tagValue },
        { label: 'Metadata', value: metadataValue },
      ]}
    />
  )
}

export default DocumentInfoModal
