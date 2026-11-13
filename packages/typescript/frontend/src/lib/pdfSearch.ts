import type { PageRect } from '@/lib/pdfGeometry'

// Find in a PDF, with the exact position of every glyph.
//
// The glyph boxes come from the page's operator list (what PDF.js draws), walked with the same
// text-positioning math as PDF.js's canvas (CanvasGraphics.showText and showType3Text in pdf.mjs):
// text and line matrices, font size, character and word spacing, horizontal scale, rise, the CTM
// (cm, q/Q, form XObjects) and each glyph's advance width. So a match covers exactly the glyphs drawn
// on the canvas, whatever the fonts, kerning or spacing. The text layer is not used: it draws in a
// stand-in font, so positions inside its spans are approximate.
//
// The search text is built from the same glyphs: their Unicode text (NFKC, as PDF.js's text layer),
// with a space where the gap between two glyphs is wider than a share of the font size or the line
// changes. PDF.js's worker turns TJ, ' and " into showText (with spacing numbers), nextLine and the
// spacing operators before the operator list reaches the page.
//
// This module does not import PDF.js, so it runs in unit tests: the caller passes the operator codes
// (PDF.js's `OPS`), the operator list and a lookup for the fonts.

/** A 2D affine transform [a, b, c, d, e, f], as in PDF and PDF.js. */
type Matrix = [number, number, number, number, number, number]

const IDENTITY: Matrix = [1, 0, 0, 1, 0, 0]
const FONT_IDENTITY: Matrix = [0.001, 0, 0, 0.001, 0, 0]

/** `m1` after `m2`: a point is transformed by `m2`, then by `m1` (PDF.js's Util.transform). */
function multiply(m1: readonly number[], m2: readonly number[]): Matrix {
  const [a1, b1, c1, d1, e1, f1] = m1
  const [a2, b2, c2, d2, e2, f2] = m2
  return [
    a1 * a2 + c1 * b2,
    b1 * a2 + d1 * b2,
    a1 * c2 + c1 * d2,
    b1 * c2 + d1 * d2,
    a1 * e2 + c1 * f2 + e1,
    b1 * e2 + d1 * f2 + f1,
  ]
}

/** A matrix argument of an operator: PDF.js sends arrays or typed arrays (Float32Array). */
function matrixArg(value: unknown): number[] | null {
  if (Array.isArray(value) || ArrayBuffer.isView(value)) {
    const m = Array.from(value as ArrayLike<number>)
    return m.length >= 6 ? m.slice(0, 6) : null
  }
  return null
}

function apply(m: readonly number[], x: number, y: number): [number, number] {
  return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]
}

/** The operator codes this needs, from PDF.js's `OPS`. */
export interface OpCodes {
  save: number
  restore: number
  transform: number
  beginText: number
  setCharSpacing: number
  setWordSpacing: number
  setHScale: number
  setLeading: number
  setFont: number
  setTextRise: number
  moveText: number
  setLeadingMoveText: number
  setTextMatrix: number
  nextLine: number
  showText: number
  setGState: number
  paintFormXObjectBegin: number
  paintFormXObjectEnd: number
  beginGroup: number
  endGroup: number
}

/** What is needed of a PDF.js font (a commonObjs font object). `ascent` and `descent` (fractions of
 * the em) are sent only when the document is opened with `fontExtraProperties`. */
export interface FontLike {
  fontMatrix?: number[]
  vertical?: boolean
  isType3Font?: boolean
  ascent?: number
  descent?: number
  bbox?: number[]
}

/** A glyph of a PDF.js showText argument (the numbers between glyphs are TJ spacing). */
interface GlyphLike {
  unicode?: string
  width?: number
  isSpace?: boolean
  vmetric?: number[]
}

/** One drawn glyph: its text and its box on the page, in viewport pixels (scale 1). */
export interface PageGlyph {
  text: string
  left: number
  top: number
  right: number
  bottom: number
  /** The font size in viewport pixels, for the spacing rules. */
  size: number
  /** The baseline direction, in viewport pixels (a unit vector): text can be rotated. */
  dirX: number
  dirY: number
}

interface GraphicsState {
  ctm: Matrix
  textMatrix: Matrix
  x: number
  y: number
  lineX: number
  lineY: number
  charSpacing: number
  wordSpacing: number
  hScale: number
  leading: number
  font: FontLike | null
  fontSize: number
  fontDirection: number
  rise: number
}

const DEFAULT_ASCENT = 0.8
const DEFAULT_DESCENT = -0.2

/**
 * The glyphs a page draws, in drawing order, walking its operator list as PDF.js's canvas does.
 * `viewport` maps PDF user space to viewport pixels (`page.getViewport({ scale: 1 }).transform`).
 */
export function pageGlyphs(
  operatorList: { fnArray: number[]; argsArray: unknown[] },
  ops: OpCodes,
  fontNamed: (name: string) => FontLike | null,
  viewport: readonly number[],
): PageGlyph[] {
  const glyphs: PageGlyph[] = []
  let state: GraphicsState = {
    ctm: [...IDENTITY],
    textMatrix: [...IDENTITY],
    x: 0,
    y: 0,
    lineX: 0,
    lineY: 0,
    charSpacing: 0,
    wordSpacing: 0,
    hScale: 1,
    leading: 0,
    font: null,
    fontSize: 0,
    fontDirection: 1,
    rise: 0,
  }
  const stack: GraphicsState[] = []
  const save = () => stack.push({ ...state })
  const restore = () => {
    state = stack.pop() ?? state
  }
  const setFont = (name: string, size: number) => {
    state.font = fontNamed(name)
    state.fontDirection = size < 0 ? -1 : 1
    state.fontSize = Math.abs(size)
  }
  const moveText = (x: number, y: number) => {
    state.x = state.lineX += x
    state.y = state.lineY += y
  }

  const showText = (items: (GlyphLike | number)[]) => {
    const font = state.font
    const fontSize = state.fontSize
    if (!font || fontSize === 0) return
    const type3 = Boolean(font.isType3Font)
    const fontMatrix = font.fontMatrix ?? FONT_IDENTITY
    const vertical = Boolean(font.vertical)
    const textHScale = state.hScale * state.fontDirection
    // Glyph run space -> viewport pixels: viewport, CTM, text matrix, then the run's origin and the
    // horizontal scale (canvas: transform(textMatrix), translate(x, y + rise), scale(hScale, ±1)).
    const run = multiply(multiply(viewport, multiply(state.ctm, state.textMatrix)), [
      textHScale,
      0,
      0,
      state.fontDirection,
      state.x,
      state.y + state.rise,
    ])
    const ascent = font.ascent ?? (type3 ? emExtent(font, 3, DEFAULT_ASCENT) : DEFAULT_ASCENT)
    const descent = font.descent ?? (type3 ? emExtent(font, 1, DEFAULT_DESCENT) : DEFAULT_DESCENT)
    const widthAdvanceScale = fontSize * fontMatrix[0]
    const spacingDir = vertical ? 1 : -1
    const [ox, oy] = apply(run, 0, 0)
    const [ux, uy] = apply(run, 1, 0)
    const unit = Math.hypot(ux - ox, uy - oy) || 1
    const dirX = (ux - ox) / unit
    const dirY = (uy - oy) / unit
    const size = fontSize * Math.hypot(run[2], run[3])

    let x = 0
    for (const item of items) {
      if (typeof item === 'number') {
        x += (spacingDir * item * fontSize) / 1000
        continue
      }
      const spacing = (item.isSpace ? state.wordSpacing : 0) + state.charSpacing
      let advance: number
      let box: [number, number, number, number] // x0, y0, x1, y1 in glyph run space
      if (type3) {
        // showType3Text: the advance is the glyph width through the font matrix, times the size.
        advance = apply(fontMatrix, item.width ?? 0, 0)[0] * fontSize
        box = [x, descent * fontSize, x + advance, ascent * fontSize]
      } else if (vertical && item.vmetric) {
        // showText, vertical: the glyph is drawn at (vx, x + vy) below the run's origin.
        const vx = -item.vmetric[1] * widthAdvanceScale
        const vy = item.vmetric[2] * widthAdvanceScale
        advance = -item.vmetric[0] * widthAdvanceScale
        const baseline = -(x + vy)
        box = [vx, baseline + descent * fontSize, vx + fontSize, baseline + ascent * fontSize]
      } else {
        advance = (item.width ?? 0) * widthAdvanceScale
        box = [x, descent * fontSize, x + advance, ascent * fontSize]
      }
      const corners = [
        apply(run, box[0], box[1]),
        apply(run, box[2], box[1]),
        apply(run, box[0], box[3]),
        apply(run, box[2], box[3]),
      ]
      const unicode = (item.unicode ?? '').normalize('NFKC')
      glyphs.push({
        text: item.isSpace && !unicode.trim() ? ' ' : unicode,
        left: Math.min(...corners.map((c) => c[0])),
        top: Math.min(...corners.map((c) => c[1])),
        right: Math.max(...corners.map((c) => c[0])),
        bottom: Math.max(...corners.map((c) => c[1])),
        size,
        dirX,
        dirY,
      })
      x += vertical ? advance - spacing * state.fontDirection : advance + spacing * state.fontDirection
    }
    if (vertical) state.y -= x
    else state.x += x * textHScale
  }

  const { fnArray, argsArray } = operatorList
  for (let i = 0; i < fnArray.length; i++) {
    const fn = fnArray[i]
    const args = (argsArray[i] ?? []) as unknown[]
    switch (fn) {
      case ops.save:
      case ops.beginGroup:
        save()
        break
      case ops.restore:
      case ops.endGroup:
      case ops.paintFormXObjectEnd:
        restore()
        break
      case ops.paintFormXObjectBegin: {
        save()
        const matrix = matrixArg(args[0])
        if (matrix) state.ctm = multiply(state.ctm, matrix)
        break
      }
      case ops.transform:
        state.ctm = multiply(state.ctm, matrixArg(args) ?? IDENTITY)
        break
      case ops.beginText:
        state.textMatrix = [...IDENTITY]
        state.x = state.lineX = 0
        state.y = state.lineY = 0
        break
      case ops.setCharSpacing:
        state.charSpacing = Number(args[0])
        break
      case ops.setWordSpacing:
        state.wordSpacing = Number(args[0])
        break
      case ops.setHScale:
        state.hScale = Number(args[0]) / 100
        break
      case ops.setLeading:
        state.leading = -Number(args[0])
        break
      case ops.setTextRise:
        state.rise = Number(args[0])
        break
      case ops.setFont:
        setFont(String(args[0]), Number(args[1]))
        break
      case ops.setGState:
        for (const [key, value] of (args[0] ?? []) as [string, unknown][]) {
          if (key === 'Font') {
            const [name, size] = value as [string, number]
            setFont(name, size)
          }
        }
        break
      case ops.moveText:
        moveText(Number(args[0]), Number(args[1]))
        break
      case ops.setLeadingMoveText:
        state.leading = Number(args[1])
        moveText(Number(args[0]), Number(args[1]))
        break
      case ops.setTextMatrix: {
        const m = matrixArg(args[0]) ?? matrixArg(args) ?? IDENTITY
        state.textMatrix = [m[0], m[1], m[2], m[3], m[4], m[5]]
        state.x = state.lineX = 0
        state.y = state.lineY = 0
        break
      }
      case ops.nextLine:
        moveText(0, state.leading)
        break
      case ops.showText:
        showText((args[0] ?? []) as (GlyphLike | number)[])
        break
    }
  }
  return glyphs
}

/** A Type3 font's ascent (bbox index 3) or descent (1), in ems: the bbox through the font matrix. */
function emExtent(font: FontLike, index: 1 | 3, fallback: number): number {
  if (!font.bbox || !font.fontMatrix) return fallback
  return apply(font.fontMatrix, 0, font.bbox[index])[1]
}

/** Where a glyph's box starts and ends along a direction, and where its middle is across it. */
function along(g: PageGlyph, dirX: number, dirY: number) {
  const xs = [g.left, g.right]
  const ys = [g.top, g.bottom]
  const projections = xs.flatMap((x) => ys.map((y) => x * dirX + y * dirY))
  const middleX = (g.left + g.right) / 2
  const middleY = (g.top + g.bottom) / 2
  return { start: Math.min(...projections), end: Math.max(...projections), across: -middleX * dirY + middleY * dirX }
}

/** Gaps wider than this share of the font size, along the baseline, are a space. */
const WORD_GAP = 0.15
/** A glyph this share of the font size off the previous glyph's line starts a new line. */
const LINE_SHIFT = 0.5

/** Whether `b` is on another line than `a` (off its baseline, or back before its start). */
export function startsLine(a: PageGlyph, b: PageGlyph): boolean {
  const size = Math.max(a.size, b.size, 1)
  const first = along(a, a.dirX, a.dirY)
  const second = along(b, a.dirX, a.dirY)
  return Math.abs(second.across - first.across) > LINE_SHIFT * size || second.start < first.start - size
}

/** A page's searchable text: one string and, for each character, the glyph it comes from (-1 for
 * the spaces inserted between words and lines). */
export interface PageText {
  text: string
  owners: number[]
  glyphs: PageGlyph[]
}

export function pageText(glyphs: PageGlyph[]): PageText {
  let text = ''
  const owners: number[] = []
  const add = (chars: string, owner: number) => {
    for (const char of chars) {
      text += char
      owners.push(owner)
    }
  }
  glyphs.forEach((glyph, index) => {
    const previous = glyphs[index - 1]
    if (previous && glyph.text.trim() && text && !/\s$/.test(text)) {
      const gap = along(glyph, previous.dirX, previous.dirY).start - along(previous, previous.dirX, previous.dirY).end
      if (startsLine(previous, glyph) || gap > WORD_GAP * Math.max(previous.size, glyph.size, 1)) add(' ', -1)
    }
    add(glyph.text, index)
  })
  return { text, owners, glyphs }
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Each match of `query` on a page (case-insensitive; whitespace in the query matches any run of
 * whitespace), as one rectangle per line of its glyphs, in fractions of the page (`pageSize`: the
 * viewport at scale 1).
 */
export function findOnPage(page: PageText, query: string, pageSize: { width: number; height: number }): PageRect[][] {
  const words = query.trim().split(/\s+/).filter(Boolean)
  if (!words.length || !pageSize.width || !pageSize.height) return []
  const pattern = new RegExp(words.map(escapeRegExp).join('\\s+'), 'gi')
  const found: PageRect[][] = []
  for (let match = pattern.exec(page.text); match; match = pattern.exec(page.text)) {
    const glyphs: PageGlyph[] = []
    for (let i = match.index; i < match.index + match[0].length; i++) {
      const owner = page.owners[i]
      const glyph = owner >= 0 ? page.glyphs[owner] : undefined
      if (glyph && glyph.text.trim() && glyphs[glyphs.length - 1] !== glyph) glyphs.push(glyph)
    }
    const lines: PageGlyph[][] = []
    for (const glyph of glyphs) {
      const line = lines[lines.length - 1]
      if (line && !startsLine(line[line.length - 1], glyph)) line.push(glyph)
      else lines.push([glyph])
    }
    const rects = lines.map((line) => {
      const left = Math.min(...line.map((g) => g.left))
      const top = Math.min(...line.map((g) => g.top))
      const right = Math.max(...line.map((g) => g.right))
      const bottom = Math.max(...line.map((g) => g.bottom))
      return {
        page: 0,
        left: left / pageSize.width,
        top: top / pageSize.height,
        width: (right - left) / pageSize.width,
        height: (bottom - top) / pageSize.height,
      }
    })
    if (rects.length) found.push(rects)
  }
  return found
}
