'use client'

import { useMemo } from 'react'
import type { Form } from '@docrouter/sdk'

import { PropertiesDialog, type Property } from '@/components/PropertiesDialog'
import { useAccountUserName } from '@/hooks/useAccountUserName'
import { formatLocalDate } from '@/utils/date'

interface FormInfoModalProps {
  isOpen: boolean
  onClose: () => void
  form: Form
}

const FormInfoModal: React.FC<FormInfoModalProps> = ({ isOpen, onClose, form }) => {
  const { createdByName, isLoadingName } = useAccountUserName(form.created_by, isOpen)

  const properties = useMemo<Property[]>(
    () => [
      { label: 'Name', value: form.name },
      { label: 'Version', value: `v${form.form_version}` },
      { label: 'Form ID', value: <span className="font-mono text-xs break-all">{form.form_id}</span> },
      { label: 'Revision ID', value: <span className="font-mono text-xs break-all">{form.form_revid}</span> },
      { label: 'Created', value: formatLocalDate(form.created_at) },
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
      { label: 'Creator ID', value: <span className="font-mono text-xs break-all">{form.created_by}</span> },
    ],
    [form, createdByName, isLoadingName],
  )

  if (!isOpen) return null

  return <PropertiesDialog title="Form properties" properties={properties} columns={2} onClose={onClose} />
}

export default FormInfoModal
