'use client'

import { ArrowLeft, Plus } from 'lucide-react'
import { useEffect } from 'react'
import { Link } from 'react-router-dom'

import KnowledgeBaseList from '@/components/KnowledgeBaseList'
import KnowledgeBaseCreate from '@/components/KnowledgeBaseCreate'
import KnowledgeBaseSearch from '@/components/KnowledgeBaseSearch'
import KnowledgeBaseDocuments from '@/components/KnowledgeBaseDocuments'
import KnowledgeBaseChat from '@/components/KnowledgeBaseChat'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { useRouteParams } from '@/utils/useRouteParams'
import { useSearchParams, useRouter } from '@/utils/appRouter'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE, CONFIG_WRITE_VIEW_ONLY_HINT } from '@/utils/orgCapabilities'

export default function KnowledgeBasesPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props)
  const searchParams = useSearchParams()
  const router = useRouter()
  const tab = searchParams.get('tab') || 'knowledge-bases'
  const kbId = searchParams.get('kbId')
  const listPath = `/orgs/${organizationId}/knowledge-bases`
  const { hasCapability: canConfigWrite, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_CONFIG_WRITE,
  )

  useEffect(() => {
    if (capabilitiesLoading) return
    if (!canConfigWrite && tab === 'kb-create') {
      router.replace(`${listPath}?tab=knowledge-bases`)
      return
    }
    if (!canConfigWrite && tab === 'edit' && kbId) {
      router.replace(`${listPath}?tab=search&kbId=${encodeURIComponent(kbId)}`)
    }
  }, [capabilitiesLoading, canConfigWrite, tab, kbId, organizationId, router, listPath])

  const setTab = (newTab: string, kbIdParam?: string) => {
    if (!canConfigWrite && (newTab === 'kb-create' || newTab === 'edit')) return
    const params = new URLSearchParams()
    params.set('tab', newTab)
    if (kbIdParam) params.set('kbId', kbIdParam)
    router.push(`${listPath}?${params.toString()}`)
  }

  if (tab === 'kb-create' && canConfigWrite) {
    return (
      <div className="mx-auto max-w-6xl p-4">
        <div className="mb-6">
          <Button variant="ghost" render={<Link to={`${listPath}?tab=knowledge-bases`} />}>
            <ArrowLeft data-icon="inline-start" />
            Back to knowledge bases
          </Button>
        </div>
        <PageHeader
          title="Create knowledge base"
          subtitle="Semantic search scopes documents by tags into vector indexes."
        />
        <KnowledgeBaseCreate organizationId={organizationId} />
      </div>
    )
  }

  if (kbId) {
    return (
      <div className="mx-auto max-w-6xl p-4">
        <div className="mb-6">
          <Button variant="ghost" onClick={() => router.push(`${listPath}?tab=knowledge-bases`)}>
            <ArrowLeft data-icon="inline-start" />
            Back to knowledge bases
          </Button>
        </div>
        <div className="mb-6 flex flex-wrap gap-4 border-b border-border">
          {!capabilitiesLoading && canConfigWrite ? (
            <button
              type="button"
              onClick={() => setTab('edit', kbId)}
              className={`border-b-2 pb-3 text-sm font-medium ${
                tab === 'edit' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground'
              }`}
            >
              Edit
            </button>
          ) : null}
          {(['search', 'documents', 'chat'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t, kbId)}
              className={`border-b-2 pb-3 text-sm font-medium capitalize ${
                tab === t ? 'border-primary text-primary' : 'border-transparent text-muted-foreground'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        {tab === 'edit' && canConfigWrite ? (
          <KnowledgeBaseCreate organizationId={organizationId} kbId={kbId} />
        ) : null}
        {tab === 'search' ? <KnowledgeBaseSearch organizationId={organizationId} kbId={kbId} /> : null}
        {tab === 'documents' ? <KnowledgeBaseDocuments organizationId={organizationId} kbId={kbId} /> : null}
        {tab === 'chat' ? <KnowledgeBaseChat organizationId={organizationId} kbId={kbId} /> : null}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl p-4">
      <PageHeader
        title="Knowledge bases"
        subtitle={
          canConfigWrite
            ? 'Semantic search across documents; scopes are defined by tags.'
            : `Semantic search across documents. ${CONFIG_WRITE_VIEW_ONLY_HINT}`
        }
        actions={
          !capabilitiesLoading && canConfigWrite ? (
            <Button onClick={() => router.push(`${listPath}?tab=kb-create`)} data-tour="kb-create">
              <Plus data-icon="inline-start" />
              New knowledge base
            </Button>
          ) : null
        }
      />
      <KnowledgeBaseList organizationId={organizationId} />
    </div>
  )
}
