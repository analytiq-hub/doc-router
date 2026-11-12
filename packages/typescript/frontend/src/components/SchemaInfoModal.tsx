'use client'

import { useMemo } from 'react'
import type { Schema } from '@docrouter/sdk'

import { PropertiesDialog, type Property } from '@/components/PropertiesDialog'
import { useAccountUserName } from '@/hooks/useAccountUserName'
import { formatLocalDate } from '@/utils/date'

interface SchemaInfoModalProps {
  isOpen: boolean
  onClose: () => void
  schema: Schema
}

const SchemaInfoModal: React.FC<SchemaInfoModalProps> = ({ isOpen, onClose, schema }) => {
  const { createdByName, isLoadingName } = useAccountUserName(schema.created_by, isOpen)

  const properties = useMemo<Property[]>(
    () => [
      { label: 'Name', value: schema.name },
      { label: 'Version', value: `v${schema.schema_version}` },
      { label: 'Schema ID', value: <span className="font-mono text-xs break-all">{schema.schema_id}</span> },
      { label: 'Revision ID', value: <span className="font-mono text-xs break-all">{schema.schema_revid}</span> },
      { label: 'Created', value: formatLocalDate(schema.created_at) },
      {
        label: 'Created by',
        value: isLoadingName ? (
          <span className="text-muted-foreground italic">Loading…</span>
        ) : createdByName ? (
          createdByName
        ) : (
          <span className="text-muted-foreground italic">Not available</span>
        ),
      },
      { label: 'Creator ID', value: <span className="font-mono text-xs break-all">{schema.created_by}</span> },
    ],
    [schema, createdByName, isLoadingName],
  )

  if (!isOpen) return null

  return <PropertiesDialog title="Schema properties" properties={properties} columns={2} onClose={onClose} />
}

export default SchemaInfoModal
