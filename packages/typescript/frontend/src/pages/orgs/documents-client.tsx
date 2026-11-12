'use client'

import { ArrowLeft, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import OrgDocumentList from '@/components/OrgDocumentList'
import DocumentUpload from '@/components/DocumentUpload'
import { DocumentUploadInfoTooltip } from '@/components/DocumentUploadInfoTooltip'
import { PageHeader } from '@/components/PageHeader'
import { useSearchParams, useRouter } from '@/utils/appRouter'
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions'
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities'
import { OrgPageContainer } from '@/components/OrgPageContainer'
import { Button } from '@/components/ui/button'
import { docsListPath, docsUploadPath } from '@/utils/documentsRoutes'

interface DocumentsPageClientProps {
  organizationId: string
}

export default function DocumentsPageClient({ organizationId }: DocumentsPageClientProps) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const tab = searchParams.get('tab')
  const caseIdFromQuery = searchParams.get('case_id') ?? undefined
  const listPath = docsListPath(organizationId, caseIdFromQuery)
  const uploadPath = docsUploadPath(organizationId, caseIdFromQuery)
  const { hasCapability: canUpload, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_DOCUMENTS_WRITE,
  )
  useOrgCapabilityTabGuard(organizationId, tab ?? '', 'upload', listPath, CAP_DOCUMENTS_WRITE)

  if (tab === 'upload' && canUpload) {
    return (
      <OrgPageContainer>
        <div className="mb-6">
          <Button variant="ghost" render={<Link to={listPath} />}>
            <ArrowLeft data-icon="inline-start" />
            Back to documents
          </Button>
        </div>
        <PageHeader
          title="Upload documents"
          titleAdornment={<DocumentUploadInfoTooltip />}
          subtitle="Add files to process with prompts. Tags and metadata on upload apply to each document."
        />
        <DocumentUpload organizationId={organizationId} defaultCaseId={caseIdFromQuery} />
      </OrgPageContainer>
    )
  }

  return (
    <OrgPageContainer>
      <div data-tour="documents">
        <PageHeader
          title="Documents"
          subtitle="Browse uploaded files, rerun extraction, and manage tags and metadata."
          actions={
            !capabilitiesLoading && canUpload ? (
              <Button onClick={() => router.push(uploadPath)} data-tour="upload-documents">
                <Plus data-icon="inline-start" />
                Upload documents
              </Button>
            ) : null
          }
        />
      </div>
      <OrgDocumentList organizationId={organizationId} initialCaseIdFilter={caseIdFromQuery} />
    </OrgPageContainer>
  )
}
