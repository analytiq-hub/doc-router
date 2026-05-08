import FlowsPageClient, { type FlowsTab } from './FlowsPageClient';

type PageProps = {
  params: Promise<{ organizationId: string }>;
  searchParams: Promise<{ tab?: string; newFlow?: string; newCredential?: string; bootstrapCredential?: string }>;
};

export default async function FlowsPage(props: PageProps) {
  const { organizationId } = await props.params;
  const sp = await props.searchParams;
  const rawTab = sp.tab || 'flows';
  const tab: FlowsTab =
    rawTab === 'credentials' || rawTab === 'executions' ? rawTab : 'flows';
  const newFlow = sp.newFlow === '1';
  const autoCreateCredential =
    sp.newCredential === '1' || sp.bootstrapCredential === '1';

  return (
    <FlowsPageClient
      organizationId={organizationId}
      tab={tab}
      newFlow={newFlow}
      autoCreateCredential={autoCreateCredential}
    />
  );
}
