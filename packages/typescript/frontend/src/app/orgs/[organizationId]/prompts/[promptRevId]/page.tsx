import PromptCreate from '@/components/PromptCreate';

export default async function PromptEditPage({ params }: { params: { organizationId: string, promptRevId: string } }) {
  // Fetch the prompt data server-side (or you can do it client-side in PromptCreate)
  // For now, just pass promptId and organizationId to PromptCreate
  return (
    <PromptCreate organizationId={params.organizationId} promptRevId={params.promptRevId} />
  );
}
