import type { FlowConnectionType, FlowNodeType } from './types/flows';
import { inputHandleCount } from './flow-rf';

export type { FlowConnectionType };

function portTypesList(
  raw: string[] | undefined,
  count: number,
  defaultType: FlowConnectionType = 'main',
): FlowConnectionType[] {
  if (count <= 0) return [];
  if (raw?.length) {
    const out = raw.slice(0, count) as FlowConnectionType[];
    while (out.length < count) out.push(defaultType);
    return out;
  }
  return Array.from({ length: count }, () => defaultType);
}

export function inputPortTypes(nt: FlowNodeType | null | undefined): FlowConnectionType[] {
  return portTypesList(nt?.input_port_types, inputHandleCount(nt));
}

export function outputPortTypes(nt: FlowNodeType | null | undefined): FlowConnectionType[] {
  const outputs = Math.max(0, nt?.outputs ?? 0);
  const defaultType: FlowConnectionType = nt?.tool_provider ? 'flows.tool' : 'main';
  return portTypesList(nt?.output_port_types, outputs, defaultType);
}

export function inputPortType(
  nt: FlowNodeType | null | undefined,
  index: number,
): FlowConnectionType {
  return inputPortTypes(nt)[index] ?? 'main';
}

export function outputPortType(
  nt: FlowNodeType | null | undefined,
  index: number,
): FlowConnectionType {
  const t = outputPortTypes(nt)[index] ?? (nt?.tool_provider ? 'flows.tool' : 'main');
  if (nt?.tool_provider && t === 'main') return 'flows.tool';
  return t;
}

export function portTypesCompatible(
  sourceType: FlowConnectionType,
  targetType: FlowConnectionType,
): boolean {
  return sourceType === targetType;
}

export function edgeConnectionType(edge: { data?: { connectionType?: FlowConnectionType } }): FlowConnectionType {
  return edge.data?.connectionType ?? 'main';
}
