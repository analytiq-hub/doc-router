import { describe, expect, it } from 'vitest';

import {
  flowNodeIconColorClass,
  flowNodePaletteIconWellClass,
  isAiNodeType,
  isDocRouterNodeType,
} from './flowNodeBrand';

describe('flowNodeBrand', () => {
  it('detects docrouter nodes by palette_group or key prefix', () => {
    expect(isDocRouterNodeType({ key: 'docrouter.ocr', palette_group: 'docrouter' })).toBe(true);
    expect(isDocRouterNodeType({ key: 'docrouter.llm_run', palette_group: null })).toBe(true);
    expect(isDocRouterNodeType({ key: 'flows.code', palette_group: 'core' })).toBe(false);
  });

  it('detects document triggers even when palette_group is trigger', () => {
    expect(
      isDocRouterNodeType({
        key: 'docrouter.trigger',
        palette_group: 'trigger',
        category: 'DocRouter',
      }),
    ).toBe(true);
  });

  it('detects AI / agent graph nodes', () => {
    expect(isAiNodeType({ key: 'flows.agent', palette_group: 'ai' })).toBe(true);
    expect(isAiNodeType({ key: 'flows.tool.code', palette_group: 'ai', tool_provider: true })).toBe(true);
    expect(isAiNodeType({ key: 'flows.trigger.chat', palette_group: 'trigger' })).toBe(true);
    expect(isAiNodeType({ key: 'flows.code', palette_group: 'core' })).toBe(false);
  });

  it('uses primary color for docrouter icons', () => {
    expect(flowNodeIconColorClass({ isDocRouter: true, isTrigger: false })).toBe('text-primary-600');
    expect(flowNodeIconColorClass({ isDocRouter: false, isTrigger: false })).toBe('text-[#94a3b8]');
  });

  it('uses primary-tinted palette wells for docrouter nodes', () => {
    expect(flowNodePaletteIconWellClass({ isDocRouter: true, isTrigger: false })).toContain('primary');
  });
});
