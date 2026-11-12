'use client'

import type { LucideIcon } from 'lucide-react'
import {
  ArrowRight,
  BookOpen,
  Braces,
  CheckCircle2,
  CircleAlert,
  Clock,
  CloudUpload,
  FileText,
  FormInput,
  Loader2,
  MessageSquare,
  Plus,
  Tags,
} from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Link } from 'react-router-dom'

import {
  useInvalidateOrgLists,
  useOrgDocuments,
  useOrgForms,
  useOrgKnowledgeBases,
  useOrgPrompts,
  useOrgSchemas,
  useOrgAllTags,
} from '@/api/orgQueries'
import { PageHeader } from '@/components/PageHeader'
import { SearchInput } from '@/components/SearchInput'
import { TagBadge } from '@/components/TagBadge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useRouter } from '@/utils/appRouter'
import { DocRouterOrgApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'

interface DashboardProps {
  organizationId: string
}

const DASHBOARD_ACCEPT = {
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/csv': ['.csv'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/gif': ['.gif'],
  'image/webp': ['.webp'],
  'image/bmp': ['.bmp'],
  'image/tiff': ['.tiff', '.tif'],
}

type StatWidget = {
  title: string
  href: string
  icon: LucideIcon
  iconClassName: string
  count: number | undefined
}

function StatCard({ widget }: { widget: StatWidget }) {
  const Icon = widget.icon
  return (
    <Link
      to={widget.href}
      className="group rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring"
      aria-label={
        widget.count === undefined
          ? widget.title
          : `${widget.count.toLocaleString()} ${widget.title.toLowerCase()}`
      }
    >
      <Card className="h-full transition-colors group-hover:bg-muted/50">
        <CardContent className="flex items-center gap-3">
          <div className={cn('flex size-9 shrink-0 items-center justify-center rounded-lg', widget.iconClassName)}>
            <Icon className="size-4" aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-muted-foreground">{widget.title}</p>
            <p className="text-xl font-semibold tabular-nums">
              {widget.count === undefined ? '…' : widget.count.toLocaleString()}
            </p>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function documentStateIcon(state: string) {
  const normalized = state.toLowerCase()
  if (normalized === 'ready' || normalized === 'processed' || normalized === 'completed') {
    return <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
  }
  if (normalized === 'error' || normalized === 'failed') {
    return <CircleAlert className="size-4 shrink-0 text-destructive" aria-hidden />
  }
  return <Clock className="size-4 shrink-0 text-muted-foreground" aria-hidden />
}

function MoreLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link to={to} className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
      {children}
      <ArrowRight className="size-4" aria-hidden />
    </Link>
  )
}

const Dashboard: React.FC<DashboardProps> = ({ organizationId }) => {
  const router = useRouter()
  const invalidate = useInvalidateOrgLists(organizationId)
  const [searchQuery, setSearchQuery] = useState('')
  const [dashboardUploading, setDashboardUploading] = useState(false)
  const [dashboardUploadError, setDashboardUploadError] = useState<string | null>(null)

  const countParams = { skip: 0, limit: 1 } as const
  const documentsRecent = useOrgDocuments(organizationId, { skip: 0, limit: 5 })
  const documentsCount = useOrgDocuments(organizationId, countParams)
  const schemasCount = useOrgSchemas(organizationId, countParams)
  const promptsCount = useOrgPrompts(organizationId, countParams)
  const formsCount = useOrgForms(organizationId, countParams)
  const knowledgeBasesCount = useOrgKnowledgeBases(organizationId, countParams)
  const { data: allTags = [] } = useOrgAllTags(organizationId)

  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])

  const onDashboardDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return
      setDashboardUploadError(null)
      setDashboardUploading(true)
      try {
        const results = await Promise.all(
          acceptedFiles.map((file) =>
            docRouterOrgApi.uploadDocumentMultipart({ name: file.name, file, tag_ids: [], metadata: {} }),
          ),
        )
        const firstId = results[0]?.document?.document_id
        if (firstId) {
          void invalidate.documents()
          router.push(`/orgs/${organizationId}/docs/${firstId}?bbox`)
        } else {
          setDashboardUploadError('Upload succeeded but no document ID returned.')
        }
      } catch (err) {
        console.error('Dashboard upload error:', err)
        setDashboardUploadError(err instanceof Error ? err.message : 'Upload failed. Please try again.')
      } finally {
        setDashboardUploading(false)
      }
    },
    [docRouterOrgApi, invalidate, organizationId, router],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: onDashboardDrop,
    accept: DASHBOARD_ACCEPT,
    multiple: true,
    disabled: dashboardUploading,
  })

  const widgets: StatWidget[] = useMemo(
    () => [
      {
        title: 'Documents',
        count: documentsCount.data?.total_count,
        href: `/orgs/${organizationId}/docs`,
        icon: FileText,
        iconClassName: 'bg-primary/15 text-primary',
      },
      {
        title: 'Schemas',
        count: schemasCount.data?.total_count,
        href: `/orgs/${organizationId}/schemas`,
        icon: Braces,
        iconClassName: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
      },
      {
        title: 'Prompts',
        count: promptsCount.data?.total_count,
        href: `/orgs/${organizationId}/prompts`,
        icon: MessageSquare,
        iconClassName: 'bg-violet-500/15 text-violet-700 dark:text-violet-400',
      },
      {
        title: 'Tags',
        count: allTags.length,
        href: `/orgs/${organizationId}/tags`,
        icon: Tags,
        iconClassName: 'bg-amber-500/15 text-amber-800 dark:text-amber-300',
      },
      {
        title: 'Forms',
        count: formsCount.data?.total_count,
        href: `/orgs/${organizationId}/forms`,
        icon: FormInput,
        iconClassName: 'bg-rose-500/15 text-rose-700 dark:text-rose-400',
      },
      {
        title: 'Knowledge bases',
        count: knowledgeBasesCount.data?.total_count,
        href: `/orgs/${organizationId}/knowledge-bases`,
        icon: BookOpen,
        iconClassName: 'bg-teal-500/15 text-teal-700 dark:text-teal-400',
      },
    ],
    [
      allTags.length,
      documentsCount.data?.total_count,
      formsCount.data?.total_count,
      knowledgeBasesCount.data?.total_count,
      organizationId,
      promptsCount.data?.total_count,
      schemasCount.data?.total_count,
    ],
  )

  const recentDocuments = documentsRecent.data?.documents ?? []
  const recentLoading = documentsRecent.isPending

  const filteredDocuments = useMemo(() => {
    if (!searchQuery.trim()) return recentDocuments
    const q = searchQuery.toLowerCase()
    return recentDocuments.filter((doc) => doc.document_name.toLowerCase().includes(q))
  }, [recentDocuments, searchQuery])

  const tagById = useMemo(() => new Map(allTags.map((t) => [t.id, t])), [allTags])
  const tagsForDisplay = useMemo(() => allTags.slice(0, 12), [allTags])

  const docsListUrl = `/orgs/${organizationId}/docs${
    searchQuery.trim() ? `?search=${encodeURIComponent(searchQuery)}` : ''
  }`

  const quickActions = [
    { label: 'Upload document', href: `/orgs/${organizationId}/docs?tab=upload`, icon: CloudUpload },
    { label: 'Create schema', href: `/orgs/${organizationId}/schemas?tab=schema-create`, icon: Plus },
    { label: 'Create prompt', href: `/orgs/${organizationId}/prompts?tab=prompt-create`, icon: Plus },
    { label: 'Manage tags', href: `/orgs/${organizationId}/tags`, icon: Tags },
    { label: 'Create form', href: `/orgs/${organizationId}/forms?tab=form-create`, icon: Plus },
    { label: 'Create knowledge base', href: `/orgs/${organizationId}/knowledge-bases?tab=kb-create`, icon: Plus },
  ]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Dashboard"
        subtitle="Overview of your organization’s resources."
        actions={
          <>
            <SearchInput
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search recent documents…"
              className="min-w-[220px] sm:min-w-[260px]"
            />
            <Button render={<Link to={`/orgs/${organizationId}/docs?tab=upload`} />}>
              <CloudUpload data-icon="inline-start" />
              Upload
            </Button>
          </>
        }
      />

      <Card className="border-dashed" data-tour="dashboard-upload">
        <CardContent>
          <div
            {...getRootProps()}
            className={cn(
              'flex min-h-[140px] cursor-pointer flex-col items-center justify-center rounded-lg px-6 py-10 transition-colors',
              isDragActive ? 'bg-primary-soft ring-2 ring-primary/40' : 'bg-muted/40 hover:bg-muted/60',
            )}
          >
            <input {...getInputProps()} />
            {dashboardUploading ? (
              <>
                <Loader2 className="mb-3 size-10 animate-spin text-muted-foreground" aria-hidden />
                <p className="text-sm text-muted-foreground">Uploading and starting extraction…</p>
              </>
            ) : (
              <>
                <CloudUpload className="mb-3 size-12 text-muted-foreground" aria-hidden />
                <p className="text-sm font-medium">
                  {isDragActive ? 'Drop document(s) here' : 'Drop a document here or click to upload'}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  OCR and default extraction will run; you’ll be taken to the document page.
                </p>
              </>
            )}
          </div>
          {dashboardUploadError ? (
            <Alert variant="destructive" className="mt-3">
              <AlertDescription>{dashboardUploadError}</AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
        {widgets.map((widget) => (
          <StatCard key={widget.title} widget={widget} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent documents</CardTitle>
            <CardAction>
              <MoreLink to={docsListUrl}>View all</MoreLink>
            </CardAction>
          </CardHeader>
          <CardContent>
            {recentLoading ? (
              <p className="py-4 text-center text-sm text-muted-foreground">Loading…</p>
            ) : filteredDocuments.length > 0 ? (
              <ul className="divide-y divide-border">
                {filteredDocuments.map((doc) => (
                  <li key={doc.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3 first:pt-0 last:pb-0">
                    <Link
                      to={`/orgs/${organizationId}/docs/${doc.id}`}
                      className="flex min-w-0 flex-1 items-center gap-2 rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring"
                    >
                      {documentStateIcon(doc.state)}
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{doc.document_name}</span>
                        <span className="text-xs text-muted-foreground">
                          {doc.upload_date ? formatLocalDate(String(doc.upload_date)) : '—'}
                        </span>
                      </span>
                    </Link>
                    <div className="flex max-w-full flex-wrap items-center gap-1">
                      {doc.tag_ids.slice(0, 2).map((tagId) => {
                        const tag = tagById.get(tagId)
                        return tag ? (
                          <Link key={tagId} to={`/orgs/${organizationId}/tags/${tag.id}`} onClick={(e) => e.stopPropagation()}>
                            <TagBadge tag={tag} />
                          </Link>
                        ) : null
                      })}
                      {doc.tag_ids.length > 2 ? (
                        <span className="text-xs text-muted-foreground">+{doc.tag_ids.length - 2}</span>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-4 text-center text-sm text-muted-foreground">
                {searchQuery.trim()
                  ? `No recent documents match “${searchQuery}”.`
                  : 'No documents yet. Upload your first document to get started.'}
              </p>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Quick actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {quickActions.map(({ label, href, icon: Icon }) => (
                  <Button
                    key={label}
                    variant="outline"
                    className="h-auto justify-start gap-2 py-2.5"
                    render={<Link to={href} />}
                  >
                    <Icon className="size-4 shrink-0" aria-hidden />
                    <span className="truncate">{label}</span>
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          {tagsForDisplay.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Tags</CardTitle>
                <CardAction>
                  <MoreLink to={`/orgs/${organizationId}/tags`}>Manage tags</MoreLink>
                </CardAction>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {tagsForDisplay.map((tag) => (
                    <Link key={tag.id} to={`/orgs/${organizationId}/tags/${tag.id}`}>
                      <TagBadge tag={tag} />
                    </Link>
                  ))}
                  {allTags.length > tagsForDisplay.length ? (
                    <span className="self-center text-xs text-muted-foreground">
                      +{allTags.length - tagsForDisplay.length} more
                    </span>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export default Dashboard
