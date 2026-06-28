import type { Edge, EdgeChange, Node, NodeChange } from 'reactflow';
import type { FlowRfNodeData } from './flowRf';

export const FLOW_GRAPH_UNDO_MAX_STACK = 50;
export const FLOW_GRAPH_PATCH_BURST_MS = 400;

export type FlowGraphSnapshot = {
  nodes: Node<FlowRfNodeData>[];
  edges: Edge[];
};

export function cloneFlowGraphSnapshot(
  nodes: Node<FlowRfNodeData>[],
  edges: Edge[],
): FlowGraphSnapshot {
  return {
    nodes: structuredClone(nodes),
    edges: structuredClone(edges),
  };
}

/**
 * Whether React Flow node changes should record an undo snapshot (before applying).
 * While `dragSessionActive`, position updates are suppressed — the snapshot is taken in
 * `onNodeDragStart` / `onSelectionDragStart` instead.
 */
export function shouldPushUndoForNodeChanges(changes: NodeChange[], dragSessionActive: boolean): boolean {
  if (dragSessionActive) return false;

  for (const change of changes) {
    if (change.type === 'select' || change.type === 'dimensions') continue;
    if (change.type === 'position') {
      // In-flight drags emit many position frames; one snapshot is taken in onNodeDragStart.
      if (change.dragging === true) continue;
      if (change.position != null || change.positionAbsolute != null) return true;
      continue;
    }
    return true;
  }
  return false;
}

/** Whether React Flow edge changes should record an undo snapshot (before applying). */
export function shouldPushUndoForEdgeChanges(changes: EdgeChange[]): boolean {
  return changes.some((change) => change.type !== 'select');
}

/** Skip canvas undo when the user is typing in a form control or Monaco. */
export function isFlowEditorEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  if (target.closest('.monaco-editor')) return true;
  return false;
}

export function isFlowEditorUndoKey(e: KeyboardEvent): boolean {
  return (e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey;
}
