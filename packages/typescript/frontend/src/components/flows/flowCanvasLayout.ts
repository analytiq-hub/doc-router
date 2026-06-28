import dagre from '@dagrejs/dagre';
import type { Edge, Node } from 'reactflow';
import type { FlowNodeType } from '@docrouter/sdk';
import { TOOL_IN_HANDLE, edgeConnectionType } from './flowRf';
import type { FlowRfNodeData } from './flowRf';
import { FLOW_CANVAS_GRID_PX, snapToFlowGrid } from './canvasGrid';

export type FlowCanvasLayoutTarget = 'selection' | 'all';

export type FlowCanvasLayoutNodeResult = { id: string; x: number; y: number };

export type FlowCanvasLayoutResult = {
  nodes: FlowCanvasLayoutNodeResult[];
};

type BoundingBox = { x: number; y: number; width: number; height: number };

type LayoutNode = Node<FlowRfNodeData>;

const DEFAULT_NODE_SIZE = FLOW_CANVAS_GRID_PX * 4; // 96px — matches FlowCanvasNode body
/** Dagre rank/column gaps (75% of prior tidy-up spacing — ~¼ shorter edges). */
const NODE_X_SPACING = (FLOW_CANVAS_GRID_PX * 15) / 4; // 90px horizontal rank gap
const NODE_Y_SPACING = FLOW_CANVAS_GRID_PX * 3; // 72px
const SUBGRAPH_SPACING = (FLOW_CANVAS_GRID_PX * 15) / 4; // 90px
const TOOL_X_SPACING = (FLOW_CANVAS_GRID_PX * 3) / 2; // 36px
const TOOL_Y_SPACING = (FLOW_CANVAS_GRID_PX * 15) / 4; // 90px

function isToolEdge(edge: Edge): boolean {
  return edge.targetHandle === TOOL_IN_HANDLE || edgeConnectionType(edge) === 'flows.tool';
}

function nodeTypeFor(
  node: LayoutNode,
  nodeTypesByKey: Record<string, FlowNodeType>,
): FlowNodeType | undefined {
  return node.data.nodeType ?? nodeTypesByKey[node.data.flowNode.type];
}

function isToolConsumer(node: LayoutNode, nodeTypesByKey: Record<string, FlowNodeType>): boolean {
  return Boolean(nodeTypeFor(node, nodeTypesByKey)?.tool_consumer);
}

function isToolProvider(node: LayoutNode, nodeTypesByKey: Record<string, FlowNodeType>): boolean {
  return Boolean(nodeTypeFor(node, nodeTypesByKey)?.tool_provider);
}

/** Dagre layout uses the 96×96 node body, not React Flow’s measured wrapper (label below). */
function getNodeDimensions(_node: LayoutNode): { width: number; height: number } {
  return { width: DEFAULT_NODE_SIZE, height: DEFAULT_NODE_SIZE };
}

function sortByPosition(a: { x: number; y: number }, b: { x: number; y: number }): number {
  const yDiff = a.y - b.y;
  return yDiff === 0 ? a.x - b.x : yDiff;
}

function compositeBoundingBox(boxes: BoundingBox[]): BoundingBox {
  const { minX, minY, maxX, maxY } = boxes.reduce(
    (bbox, box) => ({
      minX: Math.min(bbox.minX, box.x),
      maxX: Math.max(bbox.maxX, box.x + box.width),
      minY: Math.min(bbox.minY, box.y),
      maxY: Math.max(bbox.maxY, box.y + box.height),
    }),
    { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity },
  );
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function boundingBoxFromNode(node: LayoutNode): BoundingBox {
  const { width, height } = getNodeDimensions(node);
  return { x: node.position.x, y: node.position.y, width, height };
}

function boundingBoxFromDagreNode(node: dagre.Node): BoundingBox {
  return {
    x: node.x - node.width / 2,
    y: node.y - node.height / 2,
    width: node.width,
    height: node.height,
  };
}

function boundingBoxFromGraph(graph: dagre.graphlib.Graph): BoundingBox {
  return compositeBoundingBox(graph.nodes().map((id) => boundingBoxFromDagreNode(graph.node(id))));
}

function intersects(container: BoundingBox, target: BoundingBox, padding = 0): boolean {
  const targetWithPadding = {
    x: target.x - padding,
    y: target.y - padding,
    width: target.width + padding * 2,
    height: target.height + padding * 2,
  };
  const noIntersection =
    targetWithPadding.x + targetWithPadding.width < container.x ||
    targetWithPadding.x > container.x + container.width ||
    targetWithPadding.y + targetWithPadding.height < container.y ||
    targetWithPadding.y > container.y + container.height;
  return !noIntersection;
}

function createDagreGraph(layoutNodes: LayoutNode[], layoutEdges: Edge[]) {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));

  const nodeIdSet = new Set(layoutNodes.map((n) => n.id));
  const sortedNodes = [...layoutNodes].sort((a, b) => sortByPosition(a.position, b.position));

  sortedNodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node);
    graph.setNode(node.id, { width, height, x: node.position.x, y: node.position.y });
  });

  layoutEdges
    .filter((e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target))
    .sort((a, b) => sortByPosition({ x: a.targetX ?? 0, y: a.targetY ?? 0 }, { x: b.targetX ?? 0, y: b.targetY ?? 0 }))
    .forEach((e) => graph.setEdge(e.source, e.target));

  return graph;
}

function createDagreSubGraph(nodeIds: string[], parent: dagre.graphlib.Graph) {
  const subGraph = new dagre.graphlib.Graph();
  subGraph.setGraph({
    rankdir: 'LR',
    edgesep: NODE_Y_SPACING,
    nodesep: NODE_Y_SPACING,
    ranksep: NODE_X_SPACING,
  });
  subGraph.setDefaultEdgeLabel(() => ({}));
  const nodeIdSet = new Set(nodeIds);

  parent
    .nodes()
    .filter((id) => nodeIdSet.has(id))
    .forEach((id) => subGraph.setNode(id, parent.node(id)));

  parent
    .edges()
    .filter((e) => nodeIdSet.has(e.v) && nodeIdSet.has(e.w))
    .forEach((e) => subGraph.setEdge(e.v, e.w, parent.edge(e)));

  return subGraph;
}

function createDagreVerticalGraph(subgraphBoxes: Array<{ id: string; box: BoundingBox }>) {
  const subGraph = new dagre.graphlib.Graph();
  subGraph.setGraph({
    rankdir: 'TB',
    align: 'UL',
    edgesep: SUBGRAPH_SPACING,
    nodesep: SUBGRAPH_SPACING,
    ranksep: SUBGRAPH_SPACING,
  });
  subGraph.setDefaultEdgeLabel(() => ({}));

  subgraphBoxes.forEach(({ id, box: { x, y, width, height } }) => {
    subGraph.setNode(id, { x, y, width, height });
  });

  subgraphBoxes.forEach((node, index) => {
    if (!subgraphBoxes[index + 1]) return;
    subGraph.setEdge(node.id, subgraphBoxes[index + 1].id);
  });

  return subGraph;
}

function createToolSubGraph(nodeIds: string[], parent: dagre.graphlib.Graph) {
  const subGraph = new dagre.graphlib.Graph();
  subGraph.setGraph({
    rankdir: 'TB',
    edgesep: TOOL_X_SPACING,
    nodesep: TOOL_X_SPACING,
    ranksep: TOOL_Y_SPACING,
  });
  subGraph.setDefaultEdgeLabel(() => ({}));
  const nodeIdSet = new Set(nodeIds);

  parent
    .nodes()
    .filter((id) => nodeIdSet.has(id))
    .forEach((id) => subGraph.setNode(id, parent.node(id)));

  // Reverse edges so the tool consumer ranks above providers (tools render below).
  parent
    .edges()
    .filter((e) => nodeIdSet.has(e.v) && nodeIdSet.has(e.w))
    .forEach((e) => subGraph.setEdge(e.w, e.v));

  return subGraph;
}

function connectedToolProviderIds(
  consumerId: string,
  toolEdges: Edge[],
  nodesById: Record<string, LayoutNode>,
  nodeTypesByKey: Record<string, FlowNodeType>,
): string[] {
  return toolEdges
    .filter((e) => e.target === consumerId)
    .map((e) => e.source)
    .filter((id) => {
      const node = nodesById[id];
      return node ? isToolProvider(node, nodeTypesByKey) : false;
    });
}

function incomingMainEdgeCount(nodeId: string, mainEdges: Edge[]): number {
  return mainEdges.filter((e) => e.target === nodeId).length;
}

/** Among siblings, prefer the child on the parent's row (main spine); tie-break by x. */
function pickSpineChildId(
  childIds: string[],
  boxes: Record<string, BoundingBox>,
  parent: BoundingBox,
): string {
  return childIds.reduce((best, id) => {
    const box = boxes[id];
    const bestBox = boxes[best];
    if (!box) return best;
    if (!bestBox) return id;
    const rowDistA = Math.abs(box.y - parent.y);
    const rowDistB = Math.abs(bestBox.y - parent.y);
    if (rowDistA !== rowDistB) return rowDistA < rowDistB ? id : best;
    return box.x > bestBox.x ? id : best;
  }, childIds[0] ?? '');
}

/**
 * When a node fans out to several targets, keep the main-flow child on the parent's row
 * and push side branches downward (e.g. split → llm stays level, split → ocr goes below).
 */
function alignForkBranches(
  boxes: Record<string, BoundingBox>,
  mainEdges: Edge[],
  excludedNodeIds: ReadonlySet<string>,
): void {
  const childrenByParent = new Map<string, string[]>();
  for (const e of mainEdges) {
    if (excludedNodeIds.has(e.source) || excludedNodeIds.has(e.target)) continue;
    if (!boxes[e.source] || !boxes[e.target]) continue;
    const list = childrenByParent.get(e.source) ?? [];
    list.push(e.target);
    childrenByParent.set(e.source, list);
  }

  for (const [parentId, childIds] of childrenByParent) {
    if (childIds.length < 2) continue;
    const parent = boxes[parentId];
    if (!parent) continue;

    const uniqueChildIds = [...new Set(childIds)];
    if (uniqueChildIds.length < 2) continue;

    const spineChildId = pickSpineChildId(uniqueChildIds, boxes, parent);
    const spineChild = boxes[spineChildId];
    if (spineChild) spineChild.y = parent.y;

    const minBranchY = parent.y + parent.height + NODE_Y_SPACING;
    for (const childId of uniqueChildIds) {
      if (childId === spineChildId) continue;
      const branch = boxes[childId];
      if (!branch || branch.y >= minBranchY) continue;
      shiftSubtreeDown(boxes, childId, mainEdges, minBranchY - branch.y, excludedNodeIds);
    }
  }
}

/** Walk the main-flow spine and align all nodes on it to a single row. */
function straightenMainFlowSpine(
  boxes: Record<string, BoundingBox>,
  mainEdges: Edge[],
  excludedNodeIds: ReadonlySet<string>,
): void {
  const candidates = Object.keys(boxes).filter(
    (id) => !excludedNodeIds.has(id) && incomingMainEdgeCount(id, mainEdges) === 0,
  );
  if (!candidates.length) return;

  const startId = candidates.sort(
    (a, b) => (boxes[a]?.x ?? 0) - (boxes[b]?.x ?? 0),
  )[0]!;
  const startBox = boxes[startId];
  if (!startBox) return;

  const spine: string[] = [];
  let current: string | undefined = startId;
  while (current) {
    spine.push(current);
    const childIds = [
      ...new Set(
        mainEdges
          .filter((e) => e.source === current)
          .map((e) => e.target)
          .filter((id) => !excludedNodeIds.has(id) && boxes[id]),
      ),
    ];
    if (!childIds.length) break;
    const parentBox = boxes[current];
    if (!parentBox) break;
    current = pickSpineChildId(childIds, boxes, parentBox);
  }

  for (const id of spine) {
    const box = boxes[id];
    if (box) box.y = startBox.y;
  }
}

/** Shift a branch subtree down; stop at merge nodes (in-degree > 1). */
function shiftSubtreeDown(
  boxes: Record<string, BoundingBox>,
  startId: string,
  mainEdges: Edge[],
  deltaY: number,
  excludedNodeIds: ReadonlySet<string> = new Set(),
): void {
  if (excludedNodeIds.has(startId) || incomingMainEdgeCount(startId, mainEdges) > 1) return;

  const visited = new Set<string>();
  const queue = [startId];
  while (queue.length) {
    const id = queue.shift()!;
    if (visited.has(id) || excludedNodeIds.has(id)) continue;
    if (incomingMainEdgeCount(id, mainEdges) > 1) continue;
    visited.add(id);
    const box = boxes[id];
    if (box) box.y += deltaY;
    mainEdges.filter((e) => e.source === id).forEach((e) => queue.push(e.target));
  }
}

/**
 * Dagre LR may place fork branches above the main spine; prefer side branches below
 * their parent so edges do not cross the horizontal main-flow line.
 * Same-row spine children are left alone — fork alignment handles side branches.
 */
export function preferMainFlowBranchesBelow(
  boxes: Record<string, BoundingBox>,
  mainEdges: Edge[],
  excludedNodeIds: ReadonlySet<string> = new Set(),
): void {
  const edges = mainEdges.filter(
    (e) =>
      boxes[e.source] &&
      boxes[e.target] &&
      !excludedNodeIds.has(e.source) &&
      !excludedNodeIds.has(e.target),
  );
  let changed = true;
  let guard = 0;
  while (changed && guard++ < 64) {
    changed = false;
    for (const e of edges) {
      const src = boxes[e.source];
      const dst = boxes[e.target];
      if (!src || !dst) continue;
      // Only correct branches placed above the parent row; same-row spine is fine.
      if (dst.y >= src.y) continue;
      const minChildY = src.y + src.height + NODE_Y_SPACING;
      shiftSubtreeDown(boxes, e.target, mainEdges, minChildY - dst.y, excludedNodeIds);
      changed = true;
    }
  }
}

/**
 * Auto-layout flow canvas nodes (dagre), mirroring n8n “Tidy up”:
 * left-to-right main flow, tool nodes below agents, disconnected groups stacked vertically.
 */
export function computeFlowCanvasLayout(args: {
  nodes: LayoutNode[];
  edges: Edge[];
  nodeTypesByKey: Record<string, FlowNodeType>;
  target: FlowCanvasLayoutTarget;
}): FlowCanvasLayoutResult {
  const { nodes, edges, nodeTypesByKey, target } = args;
  if (nodes.length === 0) return { nodes: [] };

  const nodesById = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const nodeIdSet = new Set(nodes.map((n) => n.id));
  const mainEdges = edges.filter((e) => !isToolEdge(e));
  const toolEdges = edges.filter((e) => isToolEdge(e));

  const layoutMainEdges = mainEdges.filter((e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target));
  const layoutToolEdges = toolEdges.filter((e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target));

  const boundingBoxBefore = compositeBoundingBox(nodes.map(boundingBoxFromNode));

  const attachedToolProviderIds = new Set<string>();
  for (const node of nodes) {
    if (!isToolConsumer(node, nodeTypesByKey)) continue;
    for (const providerId of connectedToolProviderIds(
      node.id,
      layoutToolEdges,
      nodesById,
      nodeTypesByKey,
    )) {
      attachedToolProviderIds.add(providerId);
    }
  }

  const parentGraph = createDagreGraph(nodes, layoutMainEdges);

  const subgraphs = dagre.graphlib.alg
    .components(parentGraph)
    .filter(
      (nodeIds) => !(nodeIds.length === 1 && attachedToolProviderIds.has(nodeIds[0] ?? '')),
    )
    .map((nodeIds) => {
    const expandedIds = new Set(nodeIds);
    for (const id of nodeIds) {
      const node = nodesById[id];
      if (!node || !isToolConsumer(node, nodeTypesByKey)) continue;
      for (const providerId of connectedToolProviderIds(
        id,
        layoutToolEdges,
        nodesById,
        nodeTypesByKey,
      )) {
        expandedIds.add(providerId);
      }
    }

    const expandedNodeIds = [...expandedIds];
    const subgraph = createDagreSubGraph(expandedNodeIds, parentGraph);
    for (const id of expandedNodeIds) {
      if (subgraph.hasNode(id)) continue;
      const node = nodesById[id];
      if (!node) continue;
      const { width, height } = getNodeDimensions(node);
      subgraph.setNode(id, { width, height, x: node.position.x, y: node.position.y });
    }

    const toolConsumers = subgraph
      .nodes()
      .map((id) => nodesById[id])
      .filter((n): n is LayoutNode => Boolean(n) && isToolConsumer(n, nodeTypesByKey));

    const toolGroups = toolConsumers.map((consumer) => {
      const providerIds = connectedToolProviderIds(consumer.id, layoutToolEdges, nodesById, nodeTypesByKey);
      if (providerIds.length === 0) return null;

      const allToolNodeIds = [...providerIds, consumer.id];
      const toolGraph = createToolSubGraph(allToolNodeIds, subgraph);
      for (const providerId of providerIds) {
        if (!subgraph.hasNode(providerId)) continue;
        subgraph.removeNode(providerId);
      }
      layoutToolEdges
        .filter((e) => allToolNodeIds.includes(e.source) && allToolNodeIds.includes(e.target))
        .forEach((e) => {
          // Layout-only reversal: consumer → provider so dagre TB places tools below the agent.
          if (!toolGraph.hasEdge(e.target, e.source)) {
            toolGraph.setEdge(e.target, e.source);
          }
        });

      const rootEdges = subgraph
        .edges()
        .filter((e) => e.v === consumer.id || e.w === consumer.id);

      dagre.layout(toolGraph, { disableOptimalOrderHeuristic: true });
      const toolBoundingBox = boundingBoxFromGraph(toolGraph);
      subgraph.setNode(consumer.id, {
        width: toolBoundingBox.width,
        height: toolBoundingBox.height,
      });
      rootEdges.forEach((e) => subgraph.setEdge(e));

      return { graph: toolGraph, consumerId: consumer.id };
    }).filter((g): g is NonNullable<typeof g> => g != null);

    dagre.layout(subgraph, { disableOptimalOrderHeuristic: true });

    return { graph: subgraph, toolGroups, boundingBox: boundingBoxFromGraph(subgraph) };
  });

  const compositeGraph = createDagreVerticalGraph(
    subgraphs.map(({ boundingBox }, index) => ({ box: boundingBox, id: index.toString() })),
  );
  dagre.layout(compositeGraph, { disableOptimalOrderHeuristic: true });

  const boundingBoxByNodeId: Record<string, BoundingBox> = {};

  subgraphs.forEach(({ graph, toolGroups }, index) => {
    const subgraphPosition = compositeGraph.node(index.toString());
    const toolConsumerIds = new Set(toolGroups.map((g) => g.consumerId));
    const offset = {
      x: 0,
      y: subgraphPosition.y - subgraphPosition.height / 2,
    };

    graph.nodes().forEach((nodeId) => {
      const { x, y, width, height } = graph.node(nodeId);
      const positioned = {
        x: x + offset.x - width / 2,
        y: y + offset.y - height / 2,
        width,
        height,
      };

      if (toolConsumerIds.has(nodeId)) {
        const toolGroup = toolGroups.find((g) => g.consumerId === nodeId);
        if (!toolGroup) return;

        const parentOffset = { x: positioned.x, y: positioned.y };
        toolGroup.graph.nodes().forEach((toolNodeId) => {
          const toolNode = toolGroup.graph.node(toolNodeId);
          boundingBoxByNodeId[toolNodeId] = {
            x: toolNode.x + parentOffset.x - toolNode.width / 2,
            y: toolNode.y + parentOffset.y - toolNode.height / 2,
            width: toolNode.width,
            height: toolNode.height,
          };
        });
        return;
      }

      boundingBoxByNodeId[nodeId] = positioned;
    });
  });

  const toolLayoutExcludedIds = new Set(
    nodes
      .filter((n) => isToolProvider(n, nodeTypesByKey) || isToolConsumer(n, nodeTypesByKey))
      .map((n) => n.id),
  );

  alignForkBranches(boundingBoxByNodeId, layoutMainEdges, toolLayoutExcludedIds);
  straightenMainFlowSpine(boundingBoxByNodeId, layoutMainEdges, toolLayoutExcludedIds);
  preferMainFlowBranchesBelow(
    boundingBoxByNodeId,
    layoutMainEdges,
    toolLayoutExcludedIds,
  );

  // Top-align tool groups with the main-flow row (n8n AI vertical correction).
  subgraphs.forEach(({ toolGroups }) => {
    for (const { graph } of toolGroups) {
      const toolNodeIds = graph.nodes();
      const boxes = toolNodeIds
        .map((id) => boundingBoxByNodeId[id])
        .filter((box): box is BoundingBox => box != null);
      if (boxes.length === 0) continue;

      const toolGraphBoundingBox = compositeBoundingBox(boxes);
      const toolNodeVerticalCorrection = toolGraphBoundingBox.height / 2 - DEFAULT_NODE_SIZE / 2;
      toolGraphBoundingBox.y += toolNodeVerticalCorrection;

      const hasConflictingNodes = Object.entries(boundingBoxByNodeId)
        .filter(([id]) => !graph.hasNode(id))
        .some(([, nodeBoundingBox]) =>
          intersects(toolGraphBoundingBox, nodeBoundingBox, NODE_Y_SPACING),
        );

      if (!hasConflictingNodes) {
        for (const toolNodeId of toolNodeIds) {
          const box = boundingBoxByNodeId[toolNodeId];
          if (box) box.y += toolNodeVerticalCorrection;
        }
      }
    }
  });

  const positionedNodes = Object.entries(boundingBoxByNodeId).map(([id, boundingBox]) => ({
    id,
    boundingBox,
  }));
  const boundingBoxAfter = compositeBoundingBox(positionedNodes.map((n) => n.boundingBox));

  const anchor = {
    x: boundingBoxAfter.x - boundingBoxBefore.x,
    y: boundingBoxAfter.y - boundingBoxBefore.y,
  };

  const layoutNodes = positionedNodes.map(({ id, boundingBox }) => {
    const snapped = snapToFlowGrid({
      x: boundingBox.x - anchor.x,
      y: boundingBox.y - anchor.y,
    });
    return { id, x: snapped.x, y: snapped.y };
  });

  if (target === 'all') {
    return { nodes: layoutNodes };
  }

  // Selection tidy-up: only reposition nodes that were in scope; others stay put.
  const layoutIdSet = new Set(layoutNodes.map((n) => n.id));
  return {
    nodes: layoutNodes.filter((n) => layoutIdSet.has(n.id)),
  };
}

/** Resolve layout target: >1 selected node → selection, otherwise whole graph. */
export function flowCanvasLayoutTarget(nodes: LayoutNode[]): FlowCanvasLayoutTarget {
  const selectedCount = nodes.filter((n) => n.selected).length;
  return selectedCount > 1 ? 'selection' : 'all';
}

export function flowCanvasLayoutNodes(
  allNodes: LayoutNode[],
  target: FlowCanvasLayoutTarget,
): LayoutNode[] {
  if (target === 'selection') {
    return allNodes.filter((n) => n.selected);
  }
  return allNodes;
}
