import { Metadata } from 'next'
import DocumentUpload from '@/components/DocumentUpload'

export const metadata: Metadata = {
  title: 'Upload Documents',
}

export default async function UploadPage({ params }: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = await params;
  return <DocumentUpload organizationId={organizationId} />
} 