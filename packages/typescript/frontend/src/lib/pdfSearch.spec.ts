import { describe, expect, it } from 'vitest'

import { findOnPage, pageGlyphs, pageText, type FontLike, type OpCodes, type PageGlyph } from '@/lib/pdfSearch'

// Operator codes for the tests (PDF.js's OPS in the app).
const OPS: OpCodes = {
  save: 1,
  restore: 2,
  transform: 3,
  beginText: 4,
  setCharSpacing: 5,
  setWordSpacing: 6,
  setHScale: 7,
  setLeading: 8,
  setFont: 9,
  setTextRise: 10,
  moveText: 11,
  setLeadingMoveText: 12,
  setTextMatrix: 13,
  nextLine: 14,
  showText: 15,
  setGState: 16,
  paintFormXObjectBegin: 17,
  paintFormXObjectEnd: 18,
  beginGroup: 19,
  endGroup: 20,
}

// A US Letter page at scale 1: PDF y up, viewport y down.
const VIEWPORT = [1, 0, 0, -1, 0, 792]
const SIZE = { width: 612, height: 792 }
const FONTS: Record<string, FontLike> = {
  F1: { fontMatrix: [0.001, 0, 0, 0.001, 0, 0], ascent: 0.8, descent: -0.2 },
  T3: { isType3Font: true, fontMatrix: [0.01, 0, 0, 0.01, 0, 0], bbox: [0, -20, 100, 80] },
}

type Op = [keyof OpCodes, ...unknown[]]

/** Glyphs of the given widths (1/1000 em), one per character; ' ' is a space glyph. */
const text = (chars: string, width = 500) =>
  [...chars].map((c) => ({ unicode: c, width, isSpace: c === ' ' }))

function run(ops: Op[]): PageGlyph[] {
  return pageGlyphs(
    { fnArray: ops.map(([name]) => OPS[name]), argsArray: ops.map(([, ...args]) => args) },
    OPS,
    (name) => FONTS[name] ?? null,
    VIEWPORT,
  )
}

const boxes = (glyphs: PageGlyph[]) => glyphs.map((g) => [g.text, g.left, g.top, g.right, g.bottom].map((v) => (typeof v === 'number' ? Math.round(v * 100) / 100 : v)))

describe('pageGlyphs', () => {
  it('places glyphs by their widths, from the text matrix, with the font ascent and descent', () => {
    const glyphs = run([
      ['beginText'],
      ['setFont', 'F1', 10],
      // PDF.js sends matrices as typed arrays.
      ['setTextMatrix', new Float32Array([1, 0, 0, 1, 100, 700])],
      ['showText', text('AB')],
    ])
    // 10 pt: each glyph 5 wide; ascent 8 above and descent 2 below the baseline at y = 700.
    expect(boxes(glyphs)).toEqual([
      ['A', 100, 84, 105, 94],
      ['B', 105, 84, 110, 94],
    ])
    expect(glyphs[0].size).toBe(10)
  })

  it('applies TJ numbers, character and word spacing, horizontal scale and rise', () => {
    const glyphs = run([
      ['beginText'],
      ['setFont', 'F1', 10],
      ['moveText', 100, 700],
      ['showText', [...text('A'), -500, ...text('B')]], // -500: 5 to the right
      ['setCharSpacing', 1],
      ['setWordSpacing', 3],
      ['showText', text('C D')],
      ['setHScale', 50],
      ['setTextRise', 4],
      ['showText', text('E')],
    ])
    expect(boxes(glyphs)).toEqual([
      ['A', 100, 84, 105, 94],
      ['B', 110, 84, 115, 94],
      // after B: x = 115. C: 115-120, +1 spacing; space: 121-126, +1+3; D: 130-135, +1.
      ['C', 115, 84, 120, 94],
      [' ', 121, 84, 126, 94],
      ['D', 130, 84, 135, 94],
      // x = 136; 50% horizontal scale halves the width; the rise lifts the glyph by 4.
      ['E', 136, 80, 138.5, 90],
    ])
  })

  it('follows the CTM through q/Q and form XObjects, and the line matrix through TD and T*', () => {
    const glyphs = run([
      ['save'],
      ['transform', 2, 0, 0, 2, 10, 20],
      ['beginText'],
      ['setFont', 'F1', 10],
      ['moveText', 0, 0],
      ['showText', text('A')],
      ['restore'],
      ['paintFormXObjectBegin', new Float32Array([1, 0, 0, 1, 300, 0]), null],
      ['beginText'],
      ['setFont', 'F1', 10],
      ['setLeadingMoveText', 0, 500],
      ['showText', text('B')],
      ['setLeadingMoveText', 50, -14],
      ['nextLine'],
      ['showText', text('C')],
      ['paintFormXObjectEnd'],
      ['beginText'],
      ['setFont', 'F1', 10],
      ['showText', text('D')],
    ])
    expect(boxes(glyphs)).toEqual([
      // Doubled and moved by (10, 20): x 10-20, y from 20 - 4 to 20 + 16 in PDF space.
      ['A', 10, 756, 20, 776],
      // The form moves by 300; B at y = 500.
      ['B', 300, 284, 305, 294],
      // TD 50 -14 then T* (leading 14): x = 350, y = 500 - 28 = 472.
      ['C', 350, 312, 355, 322],
      // After the form: no transform left.
      ['D', 0, 784, 5, 794],
    ])
  })

  it('measures Type3 glyphs through the font matrix', () => {
    const glyphs = run([
      ['beginText'],
      ['setFont', 'T3', 10],
      ['setTextMatrix', [1, 0, 0, 1, 100, 700]],
      ['showText', [{ unicode: 'X', width: 60 }, { unicode: 'Y', width: 40 }]],
    ])
    // Width 60 glyph units * 0.01 = 0.6 em = 6; the bbox gives ascent 0.8 and descent -0.2.
    expect(boxes(glyphs)).toEqual([
      ['X', 100, 84, 106, 94],
      ['Y', 106, 84, 110, 94],
    ])
  })
})

describe('pageText and findOnPage', () => {
  const page = () =>
    pageText(
      run([
        ['beginText'],
        ['setFont', 'F1', 10],
        ['setTextMatrix', [1, 0, 0, 1, 100, 700]],
        // "the kit" + a small kern + "chen" + a wide gap + "sink": no space glyph between words.
        ['showText', [...text('the'), -400, ...text('kit'), -50, ...text('chen'), -800, ...text('sink')]],
        ['setTextMatrix', [1, 0, 0, 1, 100, 680]],
        ['showText', text('Kitchen  window')],
      ]),
    )

  it('inserts spaces for gaps between words and for new lines, not for kerning', () => {
    expect(page().text).toBe('the kitchen sink Kitchen  window')
  })

  it('finds each match, case-insensitively, as rectangles of its glyphs', () => {
    const found = findOnPage(page(), 'KITCHEN', SIZE)
    expect(found).toHaveLength(2)
    // the: 100-115, gap 4 -> kit starts at 119; "kitchen" is 7 glyphs, with 0.5 of kerning.
    const [first] = found[0]
    expect(first.left * SIZE.width).toBeCloseTo(119)
    expect((first.left + first.width) * SIZE.width).toBeCloseTo(119 + 35 + 0.5)
    expect(first.top * SIZE.height).toBeCloseTo(84)
    expect(first.height * SIZE.height).toBeCloseTo(10)
    expect(found[1][0].left * SIZE.width).toBeCloseTo(100)
  })

  it('matches across lines with one rectangle per line, and any whitespace in the query', () => {
    const [match] = findOnPage(page(), 'sink   kitchen', SIZE)
    expect(match).toHaveLength(2)
    expect(match[0].top * SIZE.height).toBeCloseTo(84)
    expect(match[1].top * SIZE.height).toBeCloseTo(104)
    expect(findOnPage(page(), 'kitchen window', SIZE)).toHaveLength(1)
    expect(findOnPage(page(), '(', SIZE)).toEqual([])
    expect(findOnPage(page(), '   ', SIZE)).toEqual([])
  })
})
