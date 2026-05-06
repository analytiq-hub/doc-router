/**
 * Re-exports from `@docrouter/sdk` for app-local convenience.
 * The canonical implementation and unit tests live in the TypeScript SDK.
 */
export {
  type FlowRfEdge,
  type FlowRfNode,
  type FlowRfNodeData,
  inputHandleCount,
  parseHandleIndex,
  revisionContentFingerprint,
  revisionToRF,
  rfToConnections,
  rfToRevision,
} from '@docrouter/sdk';
