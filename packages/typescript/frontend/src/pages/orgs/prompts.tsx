'use client'

import { ArrowLeft, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import PromptList from '@/components/PromptList'
import { PageHeader } from '@/components/PageHeader'
import { useRouteParams } from '@/utils/useRouteParams'
import PromptCreate from '@/components/PromptCreate'
import { useSearchParams, useRouter } from '@/utils/appRouter'
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'
import { Button } from '@/components/ui/button'

export default function PromptsPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props)
  const searchParams = useSearchParams()
  const router = useRouter()
  const tab = searchParams.get('tab') || 'prompts'
  const listPath = `/orgs/${organizationId}/prompts`
  const { hasCapability: canConfigWrite, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_CONFIG_WRITE,
  )
  useOrgCapabilityTabGuard(organizationId, tab, 'prompt-create', listPath, CAP_CONFIG_WRITE)

  if (tab === 'prompt-create' && canConfigWrite) {
    return (
      <div className="mx-auto max-w-6xl p-4">
        <div className="mb-6">
          <Button variant="ghost" render={<Link to={listPath} />}>
            <ArrowLeft data-icon="inline-start" />
            Back to prompts
          </Button>
        </div>
        <PageHeader title="Create prompt" subtitle="Define extraction instructions, schema, tags, and model." />
        <PromptCreate organizationId={organizationId} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl p-4">
      <PageHeader
        title="Prompts"
        subtitle="Prompts define extraction instructions; tags choose which documents they run on."
        actions={
          !capabilitiesLoading && canConfigWrite ? (
            <Button onClick={() => router.push(`${listPath}?tab=prompt-create`)} data-tour="prompt-create">
              <Plus data-icon="inline-start" />
              New prompt
            </Button>
          ) : null
        }
      />
      <PromptList organizationId={organizationId} />
    </div>
  )
}
