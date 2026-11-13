/** A rectangle on a page, in fractions of the page's width and height (0-1, origin top left), as
 * Textract reports its boxes and as the find highlights are computed. */
export interface PageRect {
  /** 1-based page number. */
  page: number
  left: number
  top: number
  width: number
  height: number
  /** Shown on hover (a bounding box's word). */
  label?: string
}

/** Rotations the viewer offers, clockwise, in degrees. */
export type Rotation = 0 | 90 | 180 | 270

export function normalizeRotation(degrees: number): Rotation {
  return ((((Math.round(degrees / 90) * 90) % 360) + 360) % 360) as Rotation
}

/** Where `rect` (on the unrotated page) is once the page is turned clockwise by `rotation`. */
export function rotateRect<T extends PageRect>(rect: T, rotation: Rotation): T {
  const { left, top, width, height } = rect
  switch (rotation) {
    case 90:
      return { ...rect, left: 1 - top - height, top: left, width: height, height: width }
    case 180:
      return { ...rect, left: 1 - left - width, top: 1 - top - height }
    case 270:
      return { ...rect, left: top, top: 1 - left - width, width: height, height: width }
    default:
      return rect
  }
}

interface TextractBlock {
  BlockType?: string
  Page?: number
  Text?: string
  Geometry?: { BoundingBox?: { Left?: number; Top?: number; Width?: number; Height?: number } }
}

/** The word boxes of a Textract OCR result (the line boxes on a page without words). Other OCR
 * output (the embedded PDF text) has no boxes, and gives an empty list. */
export function textractBoxes(ocrJson: unknown): PageRect[] {
  const blocks = (ocrJson as { Blocks?: unknown } | null)?.Blocks
  if (!Array.isArray(blocks)) return []
  const byPage = new Map<number, { words: PageRect[]; lines: PageRect[] }>()
  for (const block of blocks as TextractBlock[]) {
    if (block.BlockType !== 'WORD' && block.BlockType !== 'LINE') continue
    const box = block.Geometry?.BoundingBox
    if (!box || [box.Left, box.Top, box.Width, box.Height].some((v) => typeof v !== 'number')) continue
    const page = Number(block.Page ?? 1)
    const entry = byPage.get(page) ?? { words: [], lines: [] }
    byPage.set(page, entry)
    const rect: PageRect = {
      page,
      left: box.Left as number,
      top: box.Top as number,
      width: box.Width as number,
      height: box.Height as number,
      label: block.Text,
    }
    ;(block.BlockType === 'WORD' ? entry.words : entry.lines).push(rect)
  }
  return [...byPage.keys()]
    .sort((a, b) => a - b)
    .flatMap((page) => {
      const entry = byPage.get(page)!
      return entry.words.length ? entry.words : entry.lines
    })
}
