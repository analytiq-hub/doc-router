'use client';

import React, { createContext, useContext } from 'react';
import type { FlowExecution } from '@docrouter/sdk';

/** Payload when inserting a node on an existing edge (split source → new → target). */
export type EdgeInsertPayload = {
  edgeId: string;
  source: string;
  target: string;
  sourceHandle: string | null;
  targetHandle: string | null;
  /** Flow coordinates (same space as node `position`) — typically the edge path midpoint. */
  flowPosition: { x: number; y: number };
};

/** Actions for the editable flow canvas (node toolbar, edge controls). Executions read-only view omits this provider. */
export type FlowCanvasActions = {
  onRunWorkflow?: () => void;
  onToggleNodeDisabled: (nodeId: string) => void;
  onDeleteNode: (nodeId: string) => void;
  onOpenNodeSettings: (nodeId: string) => void;
  onDeleteEdge: (edgeId: string) => void;
  /** Start add-node flow to split this edge (opens palette; chosen type is wired inline). */
  onBeginInsertOnEdge?: (payload: EdgeInsertPayload) => void;
};

const FlowCanvasActionsContext = createContext<FlowCanvasActions | null>(null);

export function FlowCanvasActionsProvider({
  value,
  children,
}: {
  value: FlowCanvasActions | null;
  children: React.ReactNode;
}) {
  return <FlowCanvasActionsContext.Provider value={value}>{children}</FlowCanvasActionsContext.Provider>;
}

export function useFlowCanvasActions(): FlowCanvasActions | null {
  return useContext(FlowCanvasActionsContext);
}

/** Latest execution while editing — used for per-node status badges without cloning the nodes array. */
const FlowExecutionVisualContext = createContext<FlowExecution | null | undefined>(undefined);

export function FlowExecutionVisualProvider({
  execution,
  children,
}: {
  execution: FlowExecution | null | undefined;
  children: React.ReactNode;
}) {
  return <FlowExecutionVisualContext.Provider value={execution}>{children}</FlowExecutionVisualContext.Provider>;
}

export function useFlowExecutionVisual(): FlowExecution | null | undefined {
  return useContext(FlowExecutionVisualContext);
}
