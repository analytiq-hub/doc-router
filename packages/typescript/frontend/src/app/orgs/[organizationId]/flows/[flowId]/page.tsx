import FlowDetailPageClient from './FlowDetailPageClient';

export default async function FlowDetailPage({
  params,
}: {
  params: Promise<{ organizationId: string; flowId: string }>;
}) {
  const { organizationId, flowId } = await params;
  return <FlowDetailPageClient organizationId={organizationId} flowId={flowId} />;
}
