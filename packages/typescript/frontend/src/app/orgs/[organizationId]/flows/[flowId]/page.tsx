import FlowDetailPageClient from './FlowDetailPageClient';

export default async function FlowDetailPage({
  params,
}: {
  params: Promise<{ organizationId: string; flowId: string }>;
}) {
  const { organizationId, flowId } = await params;
  // Remount when opening another flow — otherwise rfNodes/rfEdges from the previous canvas can stick around
  // briefly (same dynamic route segment) and show stale nodes such as Manual Trigger on `/flows/new`.
  return (
    <FlowDetailPageClient key={`${organizationId}:${flowId}`} organizationId={organizationId} flowId={flowId} />
  );
}
