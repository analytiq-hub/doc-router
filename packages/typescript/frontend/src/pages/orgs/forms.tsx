'use client'

import { ArrowLeft, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import FormList from '@/components/FormList'
import { PageHeader } from '@/components/PageHeader'
import { useRouteParams } from '@/utils/useRouteParams'
import FormCreate from '@/components/FormCreate'
import { useSearchParams, useRouter } from '@/utils/appRouter'
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'
import { Button } from '@/components/ui/button'

export default function FormsPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props)
  const searchParams = useSearchParams()
  const router = useRouter()
  const tab = searchParams.get('tab') || 'forms'
  const listPath = `/orgs/${organizationId}/forms`
  const { hasCapability: canConfigWrite, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_CONFIG_WRITE,
  )
  useOrgCapabilityTabGuard(organizationId, tab, 'form-create', listPath, CAP_CONFIG_WRITE)

  if (tab === 'form-create' && canConfigWrite) {
    return (
      <div className="mx-auto max-w-6xl p-4">
        <div className="mb-6">
          <Button variant="ghost" render={<Link to={listPath} />}>
            <ArrowLeft data-icon="inline-start" />
            Back to forms
          </Button>
        </div>
        <PageHeader title="Create form" subtitle="Build a Form.io form for human review of extracted data." />
        <FormCreate organizationId={organizationId} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl p-4">
      <PageHeader
        title="Forms"
        subtitle="Forms support human review and correction of extracted document data."
        actions={
          !capabilitiesLoading && canConfigWrite ? (
            <Button onClick={() => router.push(`${listPath}?tab=form-create`)} data-tour="form-create">
              <Plus data-icon="inline-start" />
              New form
            </Button>
          ) : null
        }
      />
      <FormList organizationId={organizationId} />
    </div>
  )
}
