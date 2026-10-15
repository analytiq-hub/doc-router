import { Metadata } from 'next';
import UploadPageClient from './UploadPageClient';

export const metadata: Metadata = {
  title: 'Upload Documents',
};

export default async function UploadPage({
  params,
}: {
  params: Promise<{ organizationId: string }>;
}) {
  const { organizationId } = await params;
  return <UploadPageClient organizationId={organizationId} />;
}
