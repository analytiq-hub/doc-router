import type { Connection } from 'reactflow';
import type { FlowNodeType } from '@docrouter/sdk';
import {
  TOOL_IN_HANDLE,
  inputHandleCount,
  inputPortType,
  outputPortType,
  parseHandleIndex,
  portTypesCompatible,
  type FlowConnectionType,
} from './flowRf';

type RfNodeLike = {
  id: string;
  data: { flowNode: { type: string }; nodeType?: FlowNodeType };
};

export function flowNodeTypeFor(
  rfNode: RfNodeLike | undefined,
  nodeTypesByKey: Record<string, FlowNodeType>,
): FlowNodeType | undefined {
  if (!rfNode?.data.flowNode) return undefined;
  return rfNode.data.nodeType ?? nodeTypesByKey[rfNode.data.flowNode.type];
}

/**
 * Whether a canvas connection is allowed (mirrors backend graph rules).
 * Tool providers are sources only — they must never be connection targets.
 */
export function isValidFlowConnection(
  connection: Connection,
  nodes: readonly RfNodeLike[],
  nodeTypesByKey: Record<string, FlowNodeType>,
): boolean {
  const outIdx = parseHandleIndex(connection.sourceHandle, 'out-');
  if (outIdx == null) return false;

  const src = nodes.find((n) => n.id === connection.source);
  const dst = nodes.find((n) => n.id === connection.target);
  if (!src || !dst) return false;

  const srcType = flowNodeTypeFor(src, nodeTypesByKey);
  const dstType = flowNodeTypeFor(dst, nodeTypesByKey);
  if (!srcType || !dstType) return false;

  if (outIdx < 0 || outIdx >= (srcType.outputs ?? 0)) return false;

  // Tool Code / Flow Tool / KB Tool: export only; no main inputs.
  if (dstType.tool_provider) return false;

  const connectionType: FlowConnectionType = outputPortType(srcType, outIdx);

  if (connection.targetHandle === TOOL_IN_HANDLE) {
    return Boolean(srcType.tool_provider && dstType.tool_consumer);
  }

  if (srcType.tool_provider) return false;

  const inIdx = parseHandleIndex(connection.targetHandle, 'in-');
  if (inIdx == null) return false;
  if (inIdx < 0 || inIdx >= inputHandleCount(dstType)) return false;

  return portTypesCompatible(connectionType, inputPortType(dstType, inIdx));
}
