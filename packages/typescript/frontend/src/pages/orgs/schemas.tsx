'use client'

import { ArrowLeft, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import SchemaList from '@/components/SchemaList'
import { PageHeader } from '@/components/PageHeader'
import { useRouteParams } from '@/utils/useRouteParams'
import SchemaCreate from '@/components/SchemaCreate'
import { useSearchParams, useRouter } from '@/utils/appRouter'
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'
import { Button } from '@/components/ui/button'

export default function SchemasPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props)
  const searchParams = useSearchParams()
  const router = useRouter()
  const tab = searchParams.get('tab') || 'schemas'
  const listPath = `/orgs/${organizationId}/schemas`
  const { hasCapability: canConfigWrite, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_CONFIG_WRITE,
  )
  useOrgCapabilityTabGuard(organizationId, tab, 'schema-create', listPath, CAP_CONFIG_WRITE)

  if (tab === 'schema-create' && canConfigWrite) {
    return (
      <div className="mx-auto max-w-6xl p-4">
        <div className="mb-6">
          <Button variant="ghost" render={<Link to={listPath} />}>
            <ArrowLeft data-icon="inline-start" />
            Back to schemas
          </Button>
        </div>
        <PageHeader
          title="Create schema"
          subtitle="Define the JSON shape for data extracted from documents."
        />
        <SchemaCreate organizationId={organizationId} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl p-4">
      <PageHeader
        title="Schemas"
        subtitle="Schemas define the structure for extracting key fields from your documents."
        actions={
          !capabilitiesLoading && canConfigWrite ? (
            <Button onClick={() => router.push(`${listPath}?tab=schema-create`)} data-tour="schema-create">
              <Plus data-icon="inline-start" />
              New schema
            </Button>
          ) : null
        }
      />
      <SchemaList organizationId={organizationId} />
    </div>
  )
}
