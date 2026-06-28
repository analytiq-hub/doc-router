import { useCallback, useEffect, useRef } from 'react';
import type { Edge, EdgeChange, Node, NodeChange } from 'reactflow';
import type { FlowRfNodeData } from './flowRf';
import {
  cloneFlowGraphSnapshot,
  FLOW_GRAPH_PATCH_BURST_MS,
  FLOW_GRAPH_UNDO_MAX_STACK,
  shouldPushUndoForEdgeChanges,
  shouldPushUndoForNodeChanges,
  type FlowGraphSnapshot,
} from './flowGraphUndo';

export function useFlowGraphUndo(
  flowId: string | null | undefined,
  nodes: Node<FlowRfNodeData>[],
  edges: Edge[],
  onNodesChange: (next: Node<FlowRfNodeData>[]) => void,
  onEdgesChange: (next: Edge[]) => void,
) {
  const undoStackRef = useRef<FlowGraphSnapshot[]>([]);
  const isUndoingRef = useRef(false);
  const dragSessionActiveRef = useRef(false);
  const patchBurstRef = useRef<{ timer?: ReturnType<typeof setTimeout>; pushed: boolean }>({
    pushed: false,
  });
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  nodesRef.current = nodes;
  edgesRef.current = edges;

  useEffect(() => {
    undoStackRef.current = [];
    dragSessionActiveRef.current = false;
    const burst = patchBurstRef.current;
    if (burst.timer) clearTimeout(burst.timer);
    patchBurstRef.current = { pushed: false };
  }, [flowId]);

  useEffect(() => {
    return () => {
      const burst = patchBurstRef.current;
      if (burst.timer) clearTimeout(burst.timer);
    };
  }, []);

  const pushUndoSnapshot = useCallback(() => {
    if (isUndoingRef.current) return;
    undoStackRef.current.push(cloneFlowGraphSnapshot(nodesRef.current, edgesRef.current));
    if (undoStackRef.current.length > FLOW_GRAPH_UNDO_MAX_STACK) {
      undoStackRef.current.shift();
    }
  }, []);

  const beginDragUndoSession = useCallback(() => {
    if (isUndoingRef.current || dragSessionActiveRef.current) return;
    dragSessionActiveRef.current = true;
    pushUndoSnapshot();
  }, [pushUndoSnapshot]);

  const endDragUndoSession = useCallback(() => {
    dragSessionActiveRef.current = false;
  }, []);

  const pushUndoBeforePatch = useCallback(() => {
    if (isUndoingRef.current) return;
    const burst = patchBurstRef.current;
    if (!burst.pushed) {
      pushUndoSnapshot();
      burst.pushed = true;
    }
    if (burst.timer) clearTimeout(burst.timer);
    burst.timer = setTimeout(() => {
      burst.pushed = false;
      burst.timer = undefined;
    }, FLOW_GRAPH_PATCH_BURST_MS);
  }, [pushUndoSnapshot]);

  const prepareNodeChanges = useCallback(
    (changes: NodeChange[]) => {
      if (shouldPushUndoForNodeChanges(changes, dragSessionActiveRef.current)) {
        pushUndoSnapshot();
      }
    },
    [pushUndoSnapshot],
  );

  const prepareEdgeChanges = useCallback(
    (changes: EdgeChange[]) => {
      if (shouldPushUndoForEdgeChanges(changes)) pushUndoSnapshot();
    },
    [pushUndoSnapshot],
  );

  const undo = useCallback(() => {
    const stack = undoStackRef.current;
    if (!stack.length) return false;
    isUndoingRef.current = true;
    dragSessionActiveRef.current = false;
    try {
      const snap = stack.pop()!;
      onNodesChange(snap.nodes);
      onEdgesChange(snap.edges);
    } finally {
      isUndoingRef.current = false;
    }
    return true;
  }, [onEdgesChange, onNodesChange]);

  return {
    pushUndoSnapshot,
    pushUndoBeforePatch,
    beginDragUndoSession,
    endDragUndoSession,
    prepareNodeChanges,
    prepareEdgeChanges,
    undo,
  };
};
