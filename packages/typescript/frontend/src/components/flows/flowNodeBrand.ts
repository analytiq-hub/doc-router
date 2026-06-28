import type { FlowNodeType } from '@docrouter/sdk';

type FlowNodeBrandInput = Pick<FlowNodeType, 'key'> & {
  palette_group?: string | null;
  category?: string | null;
  tool_provider?: boolean;
  tool_consumer?: boolean;
};

/** True when the node belongs to the DocRouter product (OCR, LLM, document triggers, …). */
export function isDocRouterNodeType(nt: FlowNodeBrandInput | null | undefined): boolean {
  if (!nt) return false;
  const key = nt.key ?? '';
  if (key.startsWith('docrouter.')) return true;
  const paletteGroup = nt.palette_group?.trim().toLowerCase();
  if (paletteGroup === 'docrouter') return true;
  const category = nt.category?.trim().toLowerCase();
  if (category === 'docrouter') return true;
  return false;
}

/** Agent graph nodes (palette grouping, tool wiring, chat entry). */
export function isAiNodeType(nt: FlowNodeBrandInput | null | undefined): boolean {
  if (!nt?.key) return false;
  const paletteGroup = nt.palette_group?.trim().toLowerCase();
  if (paletteGroup === 'ai') return true;
  if (nt.tool_provider || nt.tool_consumer) return true;
  const key = nt.key;
  if (key === 'flows.trigger.chat' || key === 'flows.trigger.tool') return true;
  return false;
}

/** Icon glyph color on canvas, palette, and config modal nav. Uses Tailwind `primary` scale. */
export function flowNodeIconColorClass(opts: { isDocRouter: boolean; isTrigger: boolean }): string {
  if (opts.isDocRouter) return 'text-primary-600';
  return opts.isTrigger ? 'text-[#a8b0ba]' : 'text-[#94a3b8]';
}

/** Circular badge behind palette row icons. */
export function flowNodePaletteIconWellClass(opts: { isDocRouter: boolean; isTrigger: boolean }): string {
  if (opts.isDocRouter) return 'border-primary-200 bg-primary-50';
  return opts.isTrigger ? 'border-[#f0d9d6] bg-[#fff7f6]' : 'border-[#e6eaef] bg-white';
}
