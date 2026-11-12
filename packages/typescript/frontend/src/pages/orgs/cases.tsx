'use client'

import { ArrowLeft, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import CaseList from '@/components/CaseList'
import { PageHeader } from '@/components/PageHeader'
import { useRouteParams } from '@/utils/useRouteParams'
import CaseCreate from '@/components/CaseCreate'
import { useSearchParams, useRouter } from '@/utils/appRouter'
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions'
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities'
import { Button } from '@/components/ui/button'

export default function CasesPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props)
  const searchParams = useSearchParams()
  const router = useRouter()
  const tab = searchParams.get('tab') || 'cases'
  const listPath = `/orgs/${organizationId}/cases`
  const { hasCapability: canWriteDocuments, loading: permissionsLoading } = useOrgCapability(
    organizationId,
    CAP_DOCUMENTS_WRITE,
  )
  useOrgCapabilityTabGuard(organizationId, tab, 'case-create', listPath, CAP_DOCUMENTS_WRITE)

  if (tab === 'case-create' && canWriteDocuments) {
    return (
      <div className="mx-auto max-w-6xl p-4">
        <div className="mb-6">
          <Button variant="ghost" render={<Link to={listPath} />}>
            <ArrowLeft data-icon="inline-start" />
            Back to cases
          </Button>
        </div>
        <PageHeader title="Create case" subtitle="Group documents for a claim, file, or project." />
        <CaseCreate organizationId={organizationId} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl p-4">
      <PageHeader
        title="Cases"
        subtitle="A case groups the documents for one claim, file, or project."
        actions={
          !permissionsLoading && canWriteDocuments ? (
            <Button onClick={() => router.push(`${listPath}?tab=case-create`)} data-tour="case-create">
              <Plus data-icon="inline-start" />
              New case
            </Button>
          ) : null
        }
      />
      <CaseList organizationId={organizationId} />
    </div>
  )
}
