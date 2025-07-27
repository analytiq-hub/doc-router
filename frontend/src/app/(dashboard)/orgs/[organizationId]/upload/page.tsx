import { Metadata } from 'next'
import DocumentUpload from '@/components/DocumentUpload'

export const metadata: Metadata = {
  title: 'Upload Documents',
}

export default function UploadPage({ params }: { params: { organizationId: string } }) {
  return <DocumentUpload organizationId={params.organizationId} />
} 