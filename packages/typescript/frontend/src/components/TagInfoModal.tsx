'use client'

import { useMemo } from 'react'
import type { Tag } from '@docrouter/sdk'

import { PropertiesDialog, type Property } from '@/components/PropertiesDialog'
import { TagBadge } from '@/components/TagBadge'
import { useAccountUserName } from '@/hooks/useAccountUserName'
import { formatLocalDate } from '@/utils/date'

interface TagWithOptionalFields extends Omit<Tag, 'updated_at'> {
  created_by?: string
  updated_at?: string
}

interface TagInfoModalProps {
  isOpen: boolean
  onClose: () => void
  tag: TagWithOptionalFields
}

const TagInfoModal: React.FC<TagInfoModalProps> = ({ isOpen, onClose, tag }) => {
  const createdBy = tag.created_by
  const { createdByName, isLoadingName } = useAccountUserName(createdBy, isOpen)

  const properties = useMemo<Property[]>(() => {
    const loading = <span className="text-muted-foreground italic">Loading…</span>
    const na = <span className="text-muted-foreground italic">Not available</span>
    const rows: Property[] = [
      { label: 'Name', value: tag.name },
      {
        label: 'Color',
        value: (
          <span className="flex flex-wrap items-center gap-2">
            <TagBadge tag={tag} />
            <span className="font-mono text-xs">{tag.color}</span>
          </span>
        ),
      },
      {
        label: 'Description',
        value: tag.description || <span className="text-muted-foreground italic">No description</span>,
      },
      { label: 'Tag ID', value: <span className="font-mono text-xs break-all">{tag.id}</span> },
      { label: 'Created', value: formatLocalDate(tag.created_at) },
    ]
    if (createdBy) {
      rows.push(
        { label: 'Created by', value: isLoadingName ? loading : createdByName ?? na },
        { label: 'Creator ID', value: <span className="font-mono text-xs break-all">{createdBy}</span> },
      )
    }
    if (tag.updated_at) {
      rows.push({ label: 'Updated', value: formatLocalDate(tag.updated_at) })
    }
    return rows
  }, [tag, createdBy, createdByName, isLoadingName])

  if (!isOpen) return null

  return <PropertiesDialog title="Tag properties" properties={properties} columns={2} onClose={onClose} />
}

export default TagInfoModal
