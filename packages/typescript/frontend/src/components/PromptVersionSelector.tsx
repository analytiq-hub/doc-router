import React, { useEffect, useMemo, useState } from 'react'
import { DocRouterOrgApi } from '@/utils/api'
import { Prompt } from '@docrouter/sdk'
import { getApiErrorMsg } from '@/utils/api'
import { RevisionVersionSelector } from '@/components/RevisionVersionSelector'

interface PromptVersionSelectorProps {
  organizationId: string
  promptId: string
  currentVersion: number
  onVersionSelect: (promptRevId: string, version: number) => void
}

const PromptVersionSelector: React.FC<PromptVersionSelectorProps> = ({
  organizationId,
  promptId,
  currentVersion,
  onVersionSelect,
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const [versions, setVersions] = useState<Prompt[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedVersion, setSelectedVersion] = useState<number>(currentVersion)

  useEffect(() => {
    const loadVersions = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await docRouterOrgApi.listPromptVersions({ promptId })
        const sorted = response.prompts.sort((a, b) => b.prompt_version - a.prompt_version)
        setVersions(sorted)
      } catch (err) {
        const errorMsg = getApiErrorMsg(err) || 'Failed to load prompt versions'
        setError(errorMsg)
        console.error('Error loading prompt versions:', err)
      } finally {
        setIsLoading(false)
      }
    }

    if (promptId) {
      void loadVersions()
    }
  }, [promptId, docRouterOrgApi])

  useEffect(() => {
    setSelectedVersion(currentVersion)
  }, [currentVersion])

  const options = useMemo(
    () =>
      versions.map((version) => ({
        version: version.prompt_version,
        revId: version.prompt_revid,
        createdAt: version.created_at,
      })),
    [versions],
  )

  return (
    <RevisionVersionSelector
      versions={options}
      currentVersion={currentVersion}
      selectedVersion={selectedVersion}
      loading={isLoading}
      error={error}
      onSelect={(revId, version) => {
        setSelectedVersion(version)
        onVersionSelect(revId, version)
      }}
    />
  )
}

export default PromptVersionSelector