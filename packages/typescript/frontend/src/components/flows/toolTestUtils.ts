import type { Edge } from 'reactflow';
import type { FlowNode, FlowNodeType, FlowPinData } from '@docrouter/sdk';
import { TOOL_IN_HANDLE } from '@docrouter/sdk';

/** KB Tool LLM arguments schema (mirrors backend `_KB_TOOL_PARAMETERS_SCHEMA`). */
export const KB_TOOL_ARGUMENTS_SCHEMA: Record<string, unknown> = {
  type: 'object',
  properties: {
    query: {
      type: 'string',
      description: 'Search query to find relevant information in the knowledge base',
    },
    top_k: {
      type: 'integer',
      description: 'Number of results to return (default: 5)',
    },
    metadata_filter: {
      type: 'object',
      description: 'Optional metadata filters (document_name, tag_ids, etc.)',
    },
    coalesce_neighbors: {
      type: 'integer',
      description: 'Number of neighboring chunks to include for context (default: from KB config)',
    },
  },
  required: ['query'],
};

function isToolEdge(edge: Pick<Edge, 'targetHandle' | 'data'>): boolean {
  if (edge.targetHandle === TOOL_IN_HANDLE) return true;
  const ct = (edge.data as { connectionType?: string } | undefined)?.connectionType;
  return ct === 'flows.tool';
}

/** JSON Schema used to seed the Path B test-arguments editor. */
export function toolArgumentsSchemaForNode(
  flowNode: FlowNode,
  nodeType: FlowNodeType | null | undefined,
): Record<string, unknown> {
  const params = (flowNode.parameters ?? {}) as Record<string, unknown>;
  const key = nodeType?.key ?? flowNode.type;
  if (key === 'flows.kb_tool') {
    return KB_TOOL_ARGUMENTS_SCHEMA;
  }
  const schema = params.parameters_schema;
  if (schema && typeof schema === 'object' && !Array.isArray(schema)) {
    return schema as Record<string, unknown>;
  }
  return { type: 'object', properties: {} };
}

/** Build default arguments from a JSON Schema object (backend `example_arguments_from_schema` parity). */
export function exampleArgumentsFromSchema(schema: Record<string, unknown>): Record<string, unknown> {
  if (schema.type !== 'object') return {};
  const props = schema.properties;
  if (!props || typeof props !== 'object' || Array.isArray(props)) return {};
  const required = Array.isArray(schema.required) ? new Set(schema.required as string[]) : new Set<string>();
  const out: Record<string, unknown> = {};
  for (const [key, spec] of Object.entries(props as Record<string, Record<string, unknown>>)) {
    if (!spec || typeof spec !== 'object') continue;
    if ('default' in spec) {
      out[key] = spec.default;
    } else if (required.has(key)) {
      const t = spec.type;
      if (t === 'string') out[key] = '';
      else if (t === 'integer') out[key] = 0;
      else if (t === 'number') out[key] = 0;
      else if (t === 'boolean') out[key] = false;
      else if (t === 'object') out[key] = {};
      else if (t === 'array') out[key] = [];
    }
  }
  return out;
}

export function toolNameFromNode(flowNode: FlowNode): string {
  const raw = (flowNode.parameters ?? {}) as Record<string, unknown>;
  return String(raw.tool_name ?? '').trim();
}

/** Tool consumer node id wired from this tool provider, if any. */
export function findToolConsumerId(toolNodeId: string, edges: readonly Edge[]): string | null {
  for (const e of edges) {
    if (e.source !== toolNodeId || !isToolEdge(e)) continue;
    return e.target;
  }
  return null;
}

/** Optional pin payload to seed test arguments from a wired consumer's pinned main input. */
export function pinArgumentsForToolTest(
  consumerNodeId: string | null,
  pinData: FlowPinData | null | undefined,
): Record<string, unknown> | null {
  if (!consumerNodeId || !pinData) return null;
  const raw = pinData[consumerNodeId];
  if (!raw || typeof raw !== 'object') return null;
  const main = (raw as { main?: unknown }).main;
  if (!Array.isArray(main) || !main.length) return null;
  const slot0 = main[0];
  if (!Array.isArray(slot0) || !slot0.length) return null;
  const first = slot0[0];
  if (!first || typeof first !== 'object') return null;
  const json = (first as { json?: unknown }).json;
  if (!json || typeof json !== 'object' || Array.isArray(json)) return null;
  const obj = json as Record<string, unknown>;
  const toolArgs = obj.tool_arguments;
  if (toolArgs && typeof toolArgs === 'object' && !Array.isArray(toolArgs)) {
    return { ...(toolArgs as Record<string, unknown>) };
  }
  return { ...obj };
}
