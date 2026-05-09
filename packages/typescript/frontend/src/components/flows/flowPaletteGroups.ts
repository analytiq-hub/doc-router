import type { FlowNodeType } from '@docrouter/sdk';

export type FlowPaletteSectionId = 'docrouter' | 'app' | 'flow' | 'core' | 'trigger';

export const FLOW_PALETTE_SECTION_ORDER: FlowPaletteSectionId[] = [
  'docrouter',
  'app',
  'flow',
  'core',
  'trigger',
];

const FLOW_PALETTE_LABELS: Record<FlowPaletteSectionId, string> = {
  docrouter: 'DocRouter',
  app: 'App',
  flow: 'Flow',
  core: 'Core',
  trigger: 'Trigger',
};

/** Short blurb under each group in the picker (overview), similar to categorized node creator UIs. */
const FLOW_PALETTE_DESCRIPTIONS: Record<FlowPaletteSectionId, string> = {
  docrouter: 'OCR, extraction, tags, and other document steps for this product.',
  app: 'Calls into external apps and services (saved integrations and credentials).',
  flow: 'Branch, merge, and other ways to route or combine items on the graph.',
  core: 'HTTP requests, code, webhooks, and other general building blocks.',
  trigger: 'Start a run manually, from HTTP, or from a document context.',
};

const FLOW_KEYS_FLOW = new Set(['flows.branch', 'flows.merge']);

function isPaletteSection(id: string): id is FlowPaletteSectionId {
  return (
    id === 'docrouter' ||
    id === 'app' ||
    id === 'flow' ||
    id === 'core' ||
    id === 'trigger'
  );
}

export function paletteSectionLabel(section: FlowPaletteSectionId): string {
  return FLOW_PALETTE_LABELS[section];
}

export function paletteSectionDescription(section: FlowPaletteSectionId): string {
  return FLOW_PALETTE_DESCRIPTIONS[section];
}

/** Mirrors backend `resolve_palette_group` for stale payloads without `palette_group`. */
export function paletteSectionForNodeType(nt: FlowNodeType): FlowPaletteSectionId {
  const raw = nt.palette_group?.trim().toLowerCase();
  if (raw && isPaletteSection(raw)) return raw;

  const key = nt.key ?? '';

  if (nt.is_trigger) return 'trigger';
  if (key.startsWith('docrouter.')) return 'docrouter';
  if (FLOW_KEYS_FLOW.has(key)) return 'flow';
  if (key.startsWith('flows.')) return 'core';

  return 'app';
}

/** True when the section display name matches the query (helps find buckets by typed group name). */
export function paletteSectionMatchesQuery(section: FlowPaletteSectionId, qLower: string): boolean {
  if (!qLower) return false;
  const label = paletteSectionLabel(section).toLowerCase();
  if (label.includes(qLower)) return true;
  return paletteSectionDescription(section).toLowerCase().includes(qLower);
}
