/**
 * Keeps `=` flow parameter expressions aligned with **canvas display names** for `_node[…]`
 * references (primary handle for upstream outputs).
 *
 * - **Rename:** rewrite `_node['Old']` → `_node["New"]` (canonical double-quoted key via JSON.stringify).
 * - **Delete:** rewrite references to the removed display name to a sentinel key so evaluation fails clearly.
 *
 * **Edges:** Changing wires does not change node names; no expression rewrite is needed for reconnection alone.
 */

import type { FlowNode } from '@docrouter/sdk';
import type { Node } from 'reactflow';
import type { FlowRfNodeData } from './flowRf';

/** Mirrors Python `node_name`: trimmed `name`, else node `id`. */
export function flowCanvasDisplayName(node: Pick<FlowNode, 'id' | 'name'>): string {
  const n = (node.name ?? '').trim();
  return n.length > 0 ? n : node.id;
}

function escapeRegexLiteral(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Sentinel inserted into `_node[…]` after the referenced node is deleted from the graph. */
export const FLOW_EXPR_REMOVED_NODE_SENTINEL = '__docrouter_removed_node__';

/**
 * Rewrite `_node['…']` / `_node["…"]` where the inner string equals `oldDisplay` (exact match).
 * Replacement uses JSON.stringify(newDisplay) so special characters stay valid inside `[…]`.
 */
export function rewriteNodePrimaryRefsInExpression(exprBody: string, oldDisplay: string, newDisplay: string): string {
  if (oldDisplay === newDisplay) return exprBody;
  const escapedOld = escapeRegexLiteral(oldDisplay);
  const newKey = `_node[${JSON.stringify(newDisplay)}]`;
  const re = new RegExp(`_node\\[(['"])${escapedOld}\\1\\]`, 'g');
  return exprBody.replace(re, newKey);
}

/** Replace references to a removed node's display name with the sentinel key. */
export function rewriteNodePrimaryRefsRemove(exprBody: string, removedDisplay: string): string {
  const escapedOld = escapeRegexLiteral(removedDisplay);
  const sentinelKey = `_node[${JSON.stringify(FLOW_EXPR_REMOVED_NODE_SENTINEL)}]`;
  const re = new RegExp(`_node\\[(['"])${escapedOld}\\1\\]`, 'g');
  return exprBody.replace(re, sentinelKey);
}

function mapDeepStrings(obj: unknown, fn: (s: string) => string): unknown {
  if (typeof obj === 'string') return fn(obj);
  if (Array.isArray(obj)) return obj.map((x) => mapDeepStrings(x, fn));
  if (obj && typeof obj === 'object') {
    const o = obj as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(o)) {
      out[k] = mapDeepStrings(o[k], fn);
    }
    return out;
  }
  return obj;
}

/**
 * Apply `rewriter` only to strings whose trimmed value starts with `=` (expression parameters).
 */
export function rewriteExpressionFieldsDeep(obj: unknown, rewriter: (exprBody: string) => string): unknown {
  return mapDeepStrings(obj, (s) => {
    const t = s.trimStart();
    if (!t.startsWith('=')) return s;
    const leadLen = s.length - t.length;
    const lead = s.slice(0, leadLen);
    const body = t.slice(1);
    return `${lead}=${rewriter(body)}`;
  });
}

export function rewriteRfNodesDisplayRefsRename(
  rfNodes: Node<FlowRfNodeData>[],
  oldDisplay: string,
  newDisplay: string,
): Node<FlowRfNodeData>[] {
  return rfNodes.map((n) => ({
    ...n,
    data: {
      ...n.data,
      flowNode: {
        ...n.data.flowNode,
        parameters: rewriteExpressionFieldsDeep(n.data.flowNode.parameters, (body) =>
          rewriteNodePrimaryRefsInExpression(body, oldDisplay, newDisplay),
        ) as FlowNode['parameters'],
      },
    },
  }));
}

export function rewriteRfNodesDisplayRefsRemove(
  rfNodes: Node<FlowRfNodeData>[],
  removedDisplay: string,
): Node<FlowRfNodeData>[] {
  return rfNodes.map((n) => ({
    ...n,
    data: {
      ...n.data,
      flowNode: {
        ...n.data.flowNode,
        parameters: rewriteExpressionFieldsDeep(n.data.flowNode.parameters, (body) =>
          rewriteNodePrimaryRefsRemove(body, removedDisplay),
        ) as FlowNode['parameters'],
      },
    },
  }));
}
