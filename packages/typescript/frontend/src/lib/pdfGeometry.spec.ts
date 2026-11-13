import { describe, expect, it } from 'vitest'

import { normalizeRotation, rotateRect, textractBoxes } from '@/lib/pdfGeometry'

const rect = { page: 1, left: 0.1, top: 0.2, width: 0.3, height: 0.1 }

describe('rotateRect', () => {
  it('turns a rectangle with the page, clockwise', () => {
    expect(rotateRect(rect, 0)).toEqual(rect)
    const r90 = rotateRect(rect, 90)
    expect(r90.left).toBeCloseTo(0.7)
    expect(r90.top).toBeCloseTo(0.1)
    expect(r90.width).toBeCloseTo(0.1)
    expect(r90.height).toBeCloseTo(0.3)
    const r180 = rotateRect(rect, 180)
    expect(r180.left).toBeCloseTo(0.6)
    expect(r180.top).toBeCloseTo(0.7)
    const r270 = rotateRect(rect, 270)
    expect(r270.left).toBeCloseTo(0.2)
    expect(r270.top).toBeCloseTo(0.6)
    expect(r270.width).toBeCloseTo(0.1)
  })

  it('comes back after four quarter turns', () => {
    let r = rect
    for (let i = 0; i < 4; i++) r = rotateRect(r, 90)
    expect(r.left).toBeCloseTo(rect.left)
    expect(r.top).toBeCloseTo(rect.top)
    expect(r.width).toBeCloseTo(rect.width)
  })

  it('normalizes rotations', () => {
    expect([0, 90, 360, -90, 450].map(normalizeRotation)).toEqual([0, 90, 0, 270, 90])
  })
})

describe('textractBoxes', () => {
  const box = (Left: number) => ({ BoundingBox: { Left, Top: 0.1, Width: 0.2, Height: 0.05 } })

  it('takes the words, or the lines of a page without words', () => {
    const boxes = textractBoxes({
      Blocks: [
        { BlockType: 'PAGE', Page: 1, Geometry: box(0) },
        { BlockType: 'LINE', Page: 1, Text: 'Claim CLM-1', Geometry: box(0.1) },
        { BlockType: 'WORD', Page: 1, Text: 'Claim', Geometry: box(0.1) },
        { BlockType: 'WORD', Page: 1, Text: 'CLM-1', Geometry: box(0.3) },
        { BlockType: 'LINE', Page: 2, Text: 'Total', Geometry: box(0.5) },
        { BlockType: 'WORD', Page: 3, Text: 'no geometry' },
      ],
    })
    expect(boxes.map((b) => [b.page, b.label])).toEqual([
      [1, 'Claim'],
      [1, 'CLM-1'],
      [2, 'Total'],
    ])
    expect(boxes[1]).toMatchObject({ left: 0.3, top: 0.1, width: 0.2, height: 0.05 })
  })

  it('has no boxes for other OCR output', () => {
    expect(textractBoxes({ ocr_engine: 'pypdfium2', pages: [{ index: 0, text: 'x' }] })).toEqual([])
    expect(textractBoxes(undefined)).toEqual([])
  })
})
