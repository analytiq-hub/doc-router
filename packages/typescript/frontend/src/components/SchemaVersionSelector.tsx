import React, { useEffect, useMemo, useState } from 'react'
import { DocRouterOrgApi } from '@/utils/api'
import { Schema } from '@docrouter/sdk'
import { getApiErrorMsg } from '@/utils/api'
import { RevisionVersionSelector } from '@/components/RevisionVersionSelector'

interface SchemaVersionSelectorProps {
  organizationId: string
  schemaId: string
  currentVersion: number
  onVersionSelect: (schemaRevId: string, version: number) => void
}

const SchemaVersionSelector: React.FC<SchemaVersionSelectorProps> = ({
  organizationId,
  schemaId,
  currentVersion,
  onVersionSelect,
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const [versions, setVersions] = useState<Schema[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedVersion, setSelectedVersion] = useState<number>(currentVersion)

  useEffect(() => {
    const loadVersions = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await docRouterOrgApi.listSchemaVersions({ schemaId })
        const sorted = response.schemas.sort((a, b) => b.schema_version - a.schema_version)
        setVersions(sorted)
      } catch (err) {
        const errorMsg = getApiErrorMsg(err) || 'Failed to load schema versions'
        setError(errorMsg)
        console.error('Error loading schema versions:', err)
      } finally {
        setIsLoading(false)
      }
    }

    if (schemaId) {
      void loadVersions()
    }
  }, [schemaId, docRouterOrgApi])

  useEffect(() => {
    setSelectedVersion(currentVersion)
  }, [currentVersion])

  const options = useMemo(
    () =>
      versions.map((version) => ({
        version: version.schema_version,
        revId: version.schema_revid,
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

export default SchemaVersionSelector