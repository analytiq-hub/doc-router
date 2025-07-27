'use client'

import { FlowProvider } from '@/contexts/FlowContext';
import Flows from '@/components/Flows';

export default function FlowsPage({ params }: { params: { organizationId: string } }) {
  return (
    <FlowProvider>
      <Flows organizationId={params.organizationId} />
    </FlowProvider>
  );
}
