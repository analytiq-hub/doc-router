'use client'

import { useMemo } from 'react'
import type { Prompt } from '@docrouter/sdk'

import { PropertiesDialog, type Property } from '@/components/PropertiesDialog'
import { useAccountUserName } from '@/hooks/useAccountUserName'
import { formatLocalDate } from '@/utils/date'

interface PromptInfoModalProps {
  isOpen: boolean
  onClose: () => void
  prompt: Prompt
}

const PromptInfoModal: React.FC<PromptInfoModalProps> = ({ isOpen, onClose, prompt }) => {
  const { createdByName, isLoadingName } = useAccountUserName(prompt.created_by, isOpen)

  const properties = useMemo<Property[]>(
    () => [
      { label: 'Name', value: prompt.name },
      { label: 'Version', value: `v${prompt.prompt_version}` },
      { label: 'Prompt ID', value: <span className="font-mono text-xs break-all">{prompt.prompt_id}</span> },
      { label: 'Revision ID', value: <span className="font-mono text-xs break-all">{prompt.prompt_revid}</span> },
      { label: 'Created', value: formatLocalDate(prompt.created_at) },
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
      { label: 'Creator ID', value: <span className="font-mono text-xs break-all">{prompt.created_by}</span> },
    ],
    [prompt, createdByName, isLoadingName],
  )

  if (!isOpen) return null

  return <PropertiesDialog title="Prompt properties" properties={properties} columns={2} onClose={onClose} />
}

export default PromptInfoModal
