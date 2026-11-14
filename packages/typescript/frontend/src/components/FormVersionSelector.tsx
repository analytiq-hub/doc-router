import React, { useEffect, useMemo, useState } from 'react'
import { DocRouterOrgApi } from '@/utils/api'
import { Form } from '@docrouter/sdk'
import { getApiErrorMsg } from '@/utils/api'
import { RevisionVersionSelector } from '@/components/RevisionVersionSelector'

interface FormVersionSelectorProps {
  organizationId: string
  formId: string
  currentVersion: number
  onVersionSelect: (formRevId: string, version: number) => void
}

const FormVersionSelector: React.FC<FormVersionSelectorProps> = ({
  organizationId,
  formId,
  currentVersion,
  onVersionSelect,
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const [versions, setVersions] = useState<Form[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedVersion, setSelectedVersion] = useState<number>(currentVersion)

  useEffect(() => {
    const loadVersions = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await docRouterOrgApi.listFormVersions({ formId })
        const sorted = response.forms.sort((a, b) => b.form_version - a.form_version)
        setVersions(sorted)
      } catch (err) {
        const errorMsg = getApiErrorMsg(err) || 'Failed to load form versions'
        setError(errorMsg)
        console.error('Error loading form versions:', err)
      } finally {
        setIsLoading(false)
      }
    }

    if (formId) {
      void loadVersions()
    }
  }, [formId, docRouterOrgApi])

  useEffect(() => {
    setSelectedVersion(currentVersion)
  }, [currentVersion])

  const options = useMemo(
    () =>
      versions.map((version) => ({
        version: version.form_version,
        revId: version.form_revid,
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

export default FormVersionSelector