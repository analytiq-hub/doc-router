import type { FlowNode } from '@docrouter/sdk';

/** Node types that reference another flow via `parameters.target_flow_id`. */
export const TARGET_FLOW_NODE_TYPES = new Set(['flows.flow_tool', 'flows.execute_flow']);

export function targetFlowIdFromParameters(
  parameters: Record<string, unknown> | null | undefined,
): string | null {
  const raw = parameters?.target_flow_id;
  if (typeof raw !== 'string') return null;
  const trimmed = raw.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function targetFlowIdFromFlowNode(node: FlowNode): string | null {
  if (!TARGET_FLOW_NODE_TYPES.has(node.type)) return null;
  return targetFlowIdFromParameters(node.parameters as Record<string, unknown> | undefined);
}

export function flowEditorPath(organizationId: string, flowId: string): string {
  return `/orgs/${encodeURIComponent(organizationId)}/flows/${encodeURIComponent(flowId)}`;
}

export function targetFlowSubtitle(
  targetFlowId: string,
  flowNameById: Record<string, string>,
): string {
  const name = flowNameById[targetFlowId]?.trim();
  return name ? `Flow: ${name}` : `Flow: ${targetFlowId}`;
}
