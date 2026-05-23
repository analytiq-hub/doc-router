import type { FlowNodeType } from '@docrouter/sdk';
import type { DocRouterEnumBy } from './flowSchemaParameterUtils';

export type FlowPaletteAction = {
  key: string;
  label: string;
  groupLabel: string;
  parameters: Record<string, unknown>;
};

export type FlowPaletteActionGroup = {
  label: string;
  actions: FlowPaletteAction[];
};

function stringLabels(values: unknown[], names: unknown[] | undefined): string[] {
  return values.map((v, i) => {
    const fromNames = names?.[i];
    if (typeof fromNames === 'string' && fromNames.trim()) return fromNames.trim();
    return String(v);
  });
}

function paletteActionLabel(operationLabel: string, resourceLabel: string): string {
  if (resourceLabel.trim().toLowerCase() === 'file/folder') {
    return `${operationLabel} files and folders`;
  }
  return `${operationLabel} ${resourceLabel.trim().toLowerCase()}`;
}

function paletteActionGroupLabel(resourceLabel: string): string {
  return `${resourceLabel.trim()} actions`.toUpperCase();
}

/**
 * Build palette drill-in actions from ``resource`` + ``operation`` with ``x-ui-enum-by``.
 * Returns empty when the node has at most one action (no drill-in needed).
 */
export function paletteActionGroupsForNodeType(nt: FlowNodeType): FlowPaletteActionGroup[] {
  const root = nt.parameter_schema;
  if (!root || typeof root !== 'object') return [];
  const props = (root as { properties?: Record<string, unknown> }).properties;
  if (!props || typeof props !== 'object') return [];

  const resourceSchema = props.resource;
  const operationSchema = props.operation;
  if (!resourceSchema || typeof resourceSchema !== 'object') return [];
  if (!operationSchema || typeof operationSchema !== 'object') return [];

  const resourceEnum = (resourceSchema as { enum?: unknown[] }).enum;
  if (!Array.isArray(resourceEnum) || resourceEnum.length === 0) return [];

  const enumBy = (operationSchema as { 'x-ui-enum-by'?: DocRouterEnumBy })['x-ui-enum-by'];
  if (!enumBy?.field || enumBy.field !== 'resource' || !enumBy.variants) return [];

  const resourceLabels = stringLabels(
    resourceEnum,
    (resourceSchema as { 'x-ui-enum-names'?: unknown[] })['x-ui-enum-names'],
  );

  const groups: FlowPaletteActionGroup[] = [];
  for (let i = 0; i < resourceEnum.length; i += 1) {
    const resourceValue = resourceEnum[i];
    const resourceKey = String(resourceValue);
    const resourceLabel = resourceLabels[i] ?? resourceKey;
    const variant = enumBy.variants[resourceKey];
    const opEnum = variant?.enum;
    if (!Array.isArray(opEnum) || opEnum.length === 0) continue;

    const opLabels = stringLabels(opEnum, variant['x-ui-enum-names']);
    const actions: FlowPaletteAction[] = opEnum.map((operationValue, j) => {
      const operationKey = String(operationValue);
      const operationLabel = opLabels[j] ?? operationKey;
      return {
        key: `${resourceKey}:${operationKey}`,
        label: paletteActionLabel(operationLabel, resourceLabel),
        groupLabel: paletteActionGroupLabel(resourceLabel),
        parameters: {
          resource: resourceValue,
          operation: operationValue,
        },
      };
    });
    groups.push({ label: paletteActionGroupLabel(resourceLabel), actions });
  }

  const total = groups.reduce((n, g) => n + g.actions.length, 0);
  if (total <= 1) return [];
  return groups;
}

export function paletteActionsForNodeType(nt: FlowNodeType): FlowPaletteAction[] {
  return paletteActionGroupsForNodeType(nt).flatMap((g) => g.actions);
}

export function nodeTypeHasPaletteActions(nt: FlowNodeType): boolean {
  return paletteActionsForNodeType(nt).length > 0;
}

export type FlowPalettePlacement = {
  typeKey: string;
  parameters?: Record<string, unknown>;
  nameHint?: string;
};

export const FLOW_NODE_PARAMS_MIME = 'application/flow-node-params';

export function serializeFlowNodeDragPayload(placement: FlowPalettePlacement): string {
  return JSON.stringify({
    parameters: placement.parameters,
    nameHint: placement.nameHint,
  });
}

export function parseFlowNodeDragPayload(typeKey: string, dataTransfer: DataTransfer): FlowPalettePlacement {
  const raw = dataTransfer.getData(FLOW_NODE_PARAMS_MIME);
  if (!raw) return { typeKey };
  try {
    const parsed = JSON.parse(raw) as { parameters?: unknown; nameHint?: unknown };
    const parameters =
      parsed.parameters && typeof parsed.parameters === 'object' && !Array.isArray(parsed.parameters)
        ? (parsed.parameters as Record<string, unknown>)
        : undefined;
    const nameHint = typeof parsed.nameHint === 'string' && parsed.nameHint.trim() ? parsed.nameHint.trim() : undefined;
    return { typeKey, parameters, nameHint };
  } catch {
    return { typeKey };
  }
}

export function setFlowNodeDragData(
  dataTransfer: DataTransfer,
  placement: FlowPalettePlacement,
): void {
  dataTransfer.effectAllowed = 'copy';
  dataTransfer.setData('application/flow-node-type', placement.typeKey);
  dataTransfer.setData('text/plain', placement.typeKey);
  if (placement.parameters || placement.nameHint) {
    dataTransfer.setData(FLOW_NODE_PARAMS_MIME, serializeFlowNodeDragPayload(placement));
  }
}
