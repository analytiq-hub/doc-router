import { describe, expect, it } from 'vitest';
import type { OCRBlock } from '@docrouter/sdk';
import { findNextHighlightedPage } from '@/lib/findNextHighlightedPage';

const block = (page: number): OCRBlock =>
  ({ BlockType: 'WORD', Page: page, Geometry: { BoundingBox: { Left: 0, Top: 0, Width: 0.1, Height: 0.1 } } }) as OCRBlock;

describe('findNextHighlightedPage', () => {
  it('returns first match page on new search', () => {
    const info = { blocks: [block(3), block(5)], promptId: 'p', value: 'x' };
    expect(findNextHighlightedPage(info, 1, false)).toBe(3);
  });

  it('cycles to next page on same search', () => {
    const info = { blocks: [block(3), block(5)], promptId: 'p', value: 'x' };
    expect(findNextHighlightedPage(info, 3, true)).toBe(5);
    expect(findNextHighlightedPage(info, 5, true)).toBe(3);
  });
});
