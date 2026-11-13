import 'pdfjs-dist/web/pdf_viewer.css'

import {
  AnnotationEditorParamsType,
  AnnotationEditorType,
  AnnotationMode,
  getDocument,
  GlobalWorkerOptions,
  OPS,
  PDFDateString,
  type PDFDocumentProxy,
} from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { EventBus, PDFLinkService, PDFViewer } from 'pdfjs-dist/web/pdf_viewer.mjs'
import {
  ArrowDownToLine,
  ArrowUpToLine,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Eraser,
  FileDown,
  Highlighter,
  ImagePlus,
  Info,
  Maximize,
  MoreHorizontal,
  MousePointer2,
  MoveHorizontal,
  Pencil,
  Printer,
  RotateCcw,
  RotateCw,
  Save,
  Search,
  Type,
  Undo2,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { ErrorAlert } from '@/components/ErrorAlert'
import { PropertiesDialog, type Property } from '@/components/PropertiesDialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { saveBlob } from '@/lib/download'
import { normalizeRotation, rotateRect, type PageRect, type Rotation } from '@/lib/pdfGeometry'
import { findOnPage, pageGlyphs, pageText, type FontLike, type PageText } from '@/lib/pdfSearch'
import { useDebounced } from '@/lib/useDebounced'
import { ensurePdfjsWorker } from '@/utils/pdfjsWorker'
import { cn } from 'cn'

// The worker is bundled with the app (no CDN). PDF.js's own viewer (PDFViewer) draws the pages, the
// text layer, the PDF's annotations and the annotation editors; no scripting manager is given, so a
// PDF cannot run script in this page.
GlobalWorkerOptions.workerSrc = workerUrl

// The zoom menu's sizes, in percent.
const ZOOM_PRESETS = [50, 75, 100, 125, 150, 200, 300]
const MIN_SCALE = 0.25
const MAX_SCALE = 8
// A page's canvas holds at most this many pixels; beyond it PDF.js zooms the canvas with CSS and
// draws the part in view sharply on a second, detail canvas. Bounds the cost of large scans.
const MAX_CANVAS_PIXELS = 16 * 1024 * 1024
// Bytes per range request: PDF.js fetches the parts of the file the pages in view need.

type FitMode = 'page-width' | 'page-fit' | 'manual'

// The highlighter's thickness (PDF.js's freehand highlight), in PDF points, as Firefox offers it.
const HIGHLIGHT_THICKNESS = { min: 8, max: 24, initial: 12 }
// The pen's thickness and the text's font size, in PDF points (PDF.js's ranges: 1-20, 5-100).
const INK_THICKNESS = { min: 1, max: 20, initial: 2 }
const TEXT_SIZE = { min: 6, max: 48, initial: 12 }

// Colors written into the PDF (document content, not app styling): the highlighter's, offered by
// our menu and by PDF.js's highlight toolbar, and the pen's and text's.
const HIGHLIGHTS = [
  { label: 'Yellow', name: 'yellow', value: '#FFFF98' },
  { label: 'Green', name: 'green', value: '#53FFBC' },
  { label: 'Blue', name: 'blue', value: '#80EBFF' },
  { label: 'Pink', name: 'pink', value: '#FFCBE6' },
  { label: 'Red', name: 'red', value: '#FF4F5F' },
] as const
const HIGHLIGHT_COLORS = HIGHLIGHTS.map((h) => `${h.name}=${h.value}`).join(',')
const PEN_COLORS = [
  { label: 'Black', value: '#000000' },
  { label: 'Blue', value: '#0754a6' },
  { label: 'Red', value: '#c62836' },
  { label: 'Green', value: '#16804a' },
  { label: 'Orange', value: '#e8710a' },
  { label: 'Purple', value: '#7b1fa2' },
] as const

/** Color swatches, as radio buttons. */
function Swatches({
  label,
  colors,
  value,
  onChange,
}: {
  label: string
  colors: readonly { label: string; value: string }[]
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium">Colors</p>
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-3">
        {colors.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={value === option.value}
            aria-label={option.label}
            title={option.label}
            onClick={() => onChange(option.value)}
            className={cn(
              'size-8 rounded-full border border-input outline-offset-2 focus-visible:outline-2 focus-visible:outline-ring',
              value === option.value && 'outline-2 outline-foreground',
            )}
            // The swatch is the color written into the PDF (document content, not app styling).
            style={{ backgroundColor: option.value }}
          />
        ))}
      </div>
    </div>
  )
}

/** A labelled slider with words at its ends ("Thin", "Thick"). */
function Range({
  id,
  label,
  min,
  max,
  value,
  onChange,
  ends,
  disabled,
}: {
  id: string
  label: string
  min: number
  max: number
  value: number
  onChange: (value: number) => void
  ends: [string, string]
  disabled?: boolean
}) {
  return (
    <div className="flex flex-col gap-2">
      <p id={id} className="text-sm font-medium">
        {label}
      </p>
      <Slider
        aria-labelledby={id}
        min={min}
        max={max}
        step={1}
        value={[value]}
        onValueChange={(next) => onChange(Array.isArray(next) ? next[0] : next)}
        disabled={disabled}
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{ends[0]}</span>
        <span>{ends[1]}</span>
      </div>
    </div>
  )
}

/** A preview of a stroke in a color and width. */
function StrokePreview({ color, width }: { color: string; width: number }) {
  return (
    <svg viewBox="0 0 240 48" className="h-12 w-full" aria-hidden>
      <path d="M10 36 C 50 6, 90 6, 120 24 S 190 42, 230 12" fill="none" stroke={color} strokeLinecap="round" strokeWidth={width} />
    </svg>
  )
}

/** An annotation tool with options, in one button: a click selects the tool; a click on the tool
 * when it is already selected opens its options (colors, size). The tool's color shows under its
 * icon, and a small corner arrow says it has options. (Options do not open on hover: a hover menu
 * opens by accident, and is out of reach by touch and keyboard.) */
function ToolWithOptions({
  label,
  icon: Icon,
  active,
  color,
  disabled,
  onSelect,
  children,
}: {
  label: string
  icon: typeof Highlighter
  active: boolean
  color: string
  disabled: boolean
  onSelect: () => void
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover
      open={open && active}
      onOpenChange={(next) => {
        if (next && !active) {
          onSelect()
          return
        }
        setOpen(next)
      }}
    >
      <PopoverTrigger
        render={
          <Button
            variant={active ? 'secondary' : 'ghost'}
            size="icon-sm"
            aria-label={label}
            aria-pressed={active}
            title={active ? `${label}: click again for color and size` : label}
            disabled={disabled}
            className="relative"
          />
        }
      >
        <Icon />
        {/* The tool's color, written into the PDF: document content, not app styling. */}
        <span className="absolute bottom-0.5 left-1.5 h-1 w-4 rounded-full" style={{ backgroundColor: color }} aria-hidden />
        <ChevronDown className="absolute right-0 bottom-0 size-2.5! text-muted-foreground" aria-hidden />
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72">
        <div className="flex flex-col gap-4">{children}</div>
      </PopoverContent>
    </Popover>
  )
}

/** Save with annotations: a disk with a pen, as Edge shows it. */
function SaveAnnotatedIcon() {
  return (
    <span className="relative inline-flex" aria-hidden>
      <Save />
      <Pencil className="absolute -right-1 -bottom-1 size-3! rounded-sm bg-card" />
    </span>
  )
}

/** PDF.js's annotation editor manager, which PDFViewer keeps private: reached through the layer
 * properties it hands its page views (pdfjs-dist 6.4). Only used to clear the selection. */
function editorManager(viewer: PDFViewer | null): { unselectAll(): void } | null {
  const layers = (viewer as unknown as { _layerProperties?: { annotationEditorUIManager?: { unselectAll(): void } } })
    ?._layerProperties
  return layers?.annotationEditorUIManager ?? null
}

const TOOL_SETTINGS_KEY = 'pdfViewer.tools'

function readToolSettings(): Record<string, unknown> {
  try {
    return JSON.parse(localStorage.getItem(TOOL_SETTINGS_KEY) ?? '{}') as Record<string, unknown>
  } catch {
    return {}
  }
}

/** A toolbar setting (a color, a size), kept in the browser from one document to the next. A stored
 * value of another type than the default (an older version's) is ignored. */
function useToolSetting<T extends string | number | boolean>(name: string, initial: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    const stored = readToolSettings()[name]
    return typeof stored === typeof initial ? (stored as T) : initial
  })
  const set = useCallback(
    (next: T) => {
      setValue(next)
      try {
        localStorage.setItem(TOOL_SETTINGS_KEY, JSON.stringify({ ...readToolSettings(), [name]: next }))
      } catch {
        // Storage full or disabled: the setting lasts for this document only.
      }
    },
    [name],
  )
  return [value, set]
}

function Overlay({ rect, rotation, className }: { rect: PageRect; rotation: Rotation; className: string }) {
  const r = rotation ? rotateRect(rect, rotation) : rect
  return (
    <div
      className={cn('absolute', className)}
      title={rect.label}
      style={{ left: `${r.left * 100}%`, top: `${r.top * 100}%`, width: `${r.width * 100}%`, height: `${r.height * 100}%` }}
    />
  )
}

/** One match of the find query: its page and one rectangle per line (fractions of the page as PDF.js
 * shows it at rotation 0, its own /Rotate applied). */
interface FindMatch {
  page: number
  rects: PageRect[]
}

interface IndexedPage {
  text: PageText
  size: { width: number; height: number }
}

/** A page's glyphs and searchable text (see lib/pdfSearch.ts), from its operator list. */
async function indexPage(pdf: PDFDocumentProxy, pageNumber: number): Promise<IndexedPage> {
  const page = await pdf.getPage(pageNumber)
  const viewport = page.getViewport({ scale: 1 })
  // The page content only, as the text layer: annotation appearances are not searched.
  const list = await page.getOperatorList({ annotationMode: AnnotationMode.DISABLE })
  // The fonts arrive in commonObjs while the operator list is built; wait for any still loading.
  const names = new Set<string>()
  list.fnArray.forEach((fn, i) => {
    const args = list.argsArray[i] as unknown[]
    if (fn === OPS.setFont) names.add(String(args[0]))
    if (fn === OPS.setGState) {
      for (const [key, value] of (args[0] ?? []) as [string, unknown][]) {
        if (key === 'Font') names.add(String((value as unknown[])[0]))
      }
    }
  })
  const fonts = new Map<string, FontLike>()
  await Promise.all(
    [...names].map(
      (name) =>
        new Promise<void>((resolve) => {
          const keep = (font: unknown) => {
            if (font) fonts.set(name, font as FontLike)
            resolve()
          }
          if (page.commonObjs.has(name)) keep(page.commonObjs.get(name))
          else page.commonObjs.get(name, keep)
        }),
    ),
  )
  const glyphs = pageGlyphs(list, OPS, (name) => fonts.get(name) ?? null, viewport.transform)
  return { text: pageText(glyphs), size: { width: viewport.width, height: viewport.height } }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]} (${bytes.toLocaleString()} bytes)`
}

function pdfDate(value: unknown): string | null {
  if (typeof value !== 'string' || !value) return null
  return PDFDateString.toDateObject(value)?.toLocaleString() ?? value
}

async function documentProperties(pdf: PDFDocumentProxy, fileName: string): Promise<Property[]> {
  const [{ info }, { length }, first] = await Promise.all([pdf.getMetadata(), pdf.getDownloadInfo(), pdf.getPage(1)])
  const fields = (info ?? {}) as Record<string, unknown>
  const text = (key: string) => (typeof fields[key] === 'string' && fields[key] ? String(fields[key]) : null)
  return [
    { label: 'File name', value: fileName },
    { label: 'File size', value: formatBytes(length) },
    { label: 'Title', value: text('Title') },
    { label: 'Author', value: text('Author') },
    { label: 'Subject', value: text('Subject') },
    { label: 'Keywords', value: text('Keywords') },
    { label: 'Created', value: pdfDate(fields.CreationDate) },
    { label: 'Modified', value: pdfDate(fields.ModDate) },
    { label: 'Creator', value: text('Creator') },
    { label: 'Producer', value: text('Producer') },
    { label: 'PDF version', value: text('PDFFormatVersion') },
    { label: 'Fast web view', value: fields.IsLinearized ? 'Yes' : 'No' },
    { label: 'Pages', value: String(pdf.numPages) },
    { label: 'Page rotation', value: `${first.rotate}°` },
  ]
}

const annotatedName = (fileName: string) => `${fileName.replace(/\.pdf$/i, '')} (annotated).pdf`

/**
 * A PDF in the page, drawn by PDF.js's viewer (docs/design/pdf-viewer.md section 3): pages load by
 * byte range from `url` as they come into view (`ranges`), and only the pages in view are drawn.
 * Scroll, zoom and fit, rotate, find text (our exact find, lib/pdfSearch.ts), annotate (highlight,
 * draw, text, image: kept in the page only, saved as a downloaded copy), print, download and see the
 * PDF's properties. `boxes` draws rectangles (OCR bounding boxes) over the pages. `onStale` is
 * called when the file's version is gone (404 or 409), so the caller can ask for the current one.
 * `loading` replaces the placeholder shown until the first page is drawn.
 */
export type PageNavigationRequest = { page: number; seq: number }

export type PdfViewerCoreProps = {
  url: string
  fileName?: string
  onPageChange?: (page: number) => void
  onDocumentReady?: (pdf: PDFDocumentProxy) => void
  boxes?: PageRect[]
  /** Bumps `seq` to jump the viewer when extraction highlight cycles pages. */
  pageNavigation?: PageNavigationRequest
  /** Doc-router items in the toolbar more menu (OCR, bbox, …). */
  menuExtras?: ReactNode
  loading?: ReactNode
  className?: string
  initialPage?: number
}

export function PdfViewerCore({
  url,
  fileName = 'document.pdf',
  onPageChange,
  onDocumentReady,
  boxes = [],
  pageNavigation,
  menuExtras,
  loading,
  className,
  initialPage = 1,
}: PdfViewerCoreProps) {
  const container = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<PDFViewer | null>(null)
  const eventBusRef = useRef<EventBus | null>(null)
  const findInput = useRef<HTMLInputElement>(null)
  const initialPageRef = useRef(initialPage)
  const printFrame = useRef<HTMLIFrameElement>(null)
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [scale, setScale] = useState(1)
  const [fitMode, setFitMode] = useState<FitMode>('page-width')
  const [rotation, setRotation] = useState<Rotation>(0)
  const [current, setCurrent] = useState(1)
  const [pageInput, setPageInput] = useState('1')
  const [properties, setProperties] = useState<Property[] | null>(null)
  const [tool, setTool] = useState<number>(AnnotationEditorType.NONE)
  // The annotation tools (docs/design/pdf-viewer.md section 5), as Edge shows them; signatures stay
  // off. The toolbar sets each tool's color and size for the next annotation it makes, never an
  // existing one (that is the color picker on the annotation's own floating toolbar). The choices
  // are kept in the browser, from one document to the next.
  const [penColor, setPenColor] = useToolSetting('penColor', PEN_COLORS[0].value as string)
  const [penThickness, setPenThickness] = useToolSetting('penThickness', INK_THICKNESS.initial)
  const [textColor, setTextColor] = useToolSetting('textColor', PEN_COLORS[0].value as string)
  const [textSize, setTextSize] = useToolSetting('textSize', TEXT_SIZE.initial)
  // PDF.js has one highlight mode: it follows the text when a drag starts on a text span, and
  // draws freehand (a marker) when it starts anywhere else, so which one you get depends on a few
  // pixels. Here it is a marker everywhere, unless "Text only highlight" is on (as in Edge).
  const [textOnly, setTextOnly] = useToolSetting<boolean>('highlightTextOnly', false)
  const [highlightColor, setHighlightColor] = useToolSetting('highlightColor', HIGHLIGHTS[0].value as string)
  const [thickness, setThickness] = useToolSetting('highlightThickness', HIGHLIGHT_THICKNESS.initial)
  // The eraser: a click on an annotation deletes it (PDF.js has no eraser of its own).
  const [erasing, setErasing] = useState(false)
  // Whether there are annotations (to save), and whether some are not saved yet.
  const [annotated, setAnnotated] = useState(false)
  const [saving, setSaving] = useState(false)
  // The page divs PDF.js has drawn, by page number: overlays are mounted into them.
  const [pageDivs, setPageDivs] = useState<Map<number, HTMLElement>>(new Map())

  const [findOpen, setFindOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [matches, setMatches] = useState<FindMatch[]>([])
  // Each page's glyphs and text, built once per document on the first search.
  const index = useRef(new Map<number, Promise<IndexedPage>>())
  const [active, setActive] = useState(0)
  const [searching, setSearching] = useState(false)
  const debouncedQuery = useDebounced(query.trim(), 250)

  const onDocumentReadyRef = useRef(onDocumentReady)
  useEffect(() => {
    onDocumentReadyRef.current = onDocumentReady
  }, [onDocumentReady])
  useEffect(() => onPageChange?.(current), [current, onPageChange])

  const [pdfjsReady, setPdfjsReady] = useState(false)
  useEffect(() => {
    let cancelled = false
    void ensurePdfjsWorker().then(() => {
      if (!cancelled) setPdfjsReady(true)
    })
    return () => {
      cancelled = true
    }
  }, [])

  // The viewer: created once, with its event bus; the document is set into it when loaded.
  useEffect(() => {
    const element = container.current
    if (!element || !pdfjsReady) return
    // PDF.js focuses its container when an annotation is removed (its toolbar's Delete) and after
    // some edits, with a plain focus(): the browser then scrolls the page to show the viewer, and
    // the document jumps from under the user. Its focus never scrolls.
    const focus = element.focus.bind(element)
    element.focus = (options?: FocusOptions) => focus({ ...options, preventScroll: true })
    const eventBus = new EventBus()
    const linkService = new PDFLinkService({ eventBus })
    const viewer = new PDFViewer({
      container: element,
      eventBus,
      linkService,
      annotationMode: AnnotationMode.ENABLE_FORMS,
      annotationEditorMode: AnnotationEditorType.NONE,
      // The highlight colors: the highlight editor's color picker reads them, and fails (no color,
      // a script error) without them. Firefox's viewer's defaults.
      annotationEditorHighlightColors: HIGHLIGHT_COLORS,
      maxCanvasPixels: MAX_CANVAS_PIXELS,
      enableDetailCanvas: true,
      removePageBorders: true,
    })
    linkService.setViewer(viewer)
    viewerRef.current = viewer
    eventBusRef.current = eventBus
    eventBus.on('pagechanging', ({ pageNumber }: { pageNumber: number }) => {
      setCurrent(pageNumber)
      setPageInput(String(pageNumber))
    })
    eventBus.on('scalechanging', ({ scale: next }: { scale: number }) => setScale(next))
    eventBus.on('rotationchanging', ({ pagesRotation }: { pagesRotation: number }) =>
      setRotation(normalizeRotation(pagesRotation)),
    )
    eventBus.on('pagerendered', ({ pageNumber, source }: { pageNumber: number; source: { div: HTMLElement } }) =>
      setPageDivs((divs) => (divs.get(pageNumber) === source.div ? divs : new Map(divs).set(pageNumber, source.div))),
    )
    eventBus.on('annotationeditormodechanged', ({ mode }: { mode: number }) => setTool(mode))
    eventBus.on('editingstateschanged', ({ details }: { details: { isEmpty?: boolean } }) => {
      if (typeof details.isEmpty === 'boolean') setAnnotated(!details.isEmpty)
    })
    return () => {
      viewer.setDocument(null as unknown as PDFDocumentProxy)
      viewerRef.current = null
      eventBusRef.current = null
      // Back to the element's own focus (the instance property shadowed the prototype's).
      Reflect.deleteProperty(element, 'focus')
    }
  }, [pdfjsReady])

  // Load the document from a blob URL (doc-router fetch); full file is already local.
  useEffect(() => {
    if (!pdfjsReady) return
    let cancelled = false
    setError(null)
    setReady(false)
    setPdf(null)
    setPageDivs(new Map())
    const task = getDocument({
      url,
      withCredentials: false,
      disableRange: true,
      disableAutoFetch: false,
      enableXfa: false,
      fontExtraProperties: true,
    })
    task.promise
      .then((loaded) => {
        if (cancelled) return
        const viewer = viewerRef.current
        const eventBus = eventBusRef.current
        if (!viewer || !eventBus) return
        index.current = new Map()
        eventBus.on('pagesinit', () => {
          if (cancelled) return
          viewer.currentScaleValue = 'page-width'
          if (initialPageRef.current > 1) {
            viewer.currentPageNumber = Math.min(initialPageRef.current, viewer.pagesCount)
          }
          setReady(true)
        }, { once: true })
        viewer.setDocument(loaded)
        ;(viewer.linkService as PDFLinkService).setDocument(loaded)
        setPdf(loaded)
        onDocumentReadyRef.current?.(loaded)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setError(e)
      })
    return () => {
      cancelled = true
      setAnnotated(false)
      void task.destroy()
    }
  }, [url, pdfjsReady])

  // Fit to the width or the page again when the viewer is resized (PDF.js does not refit itself).
  useEffect(() => {
    const element = container.current
    if (!element || !ready || fitMode === 'manual' || typeof ResizeObserver === 'undefined') return
    const viewer = viewerRef.current
    if (viewer) viewer.currentScaleValue = fitMode
    // The border box: a scrollbar coming or going does not change it, so refitting cannot loop.
    const observer = new ResizeObserver(() => {
      if (viewerRef.current) viewerRef.current.currentScaleValue = fitMode
    })
    observer.observe(element, { box: 'border-box' })
    return () => observer.disconnect()
  }, [fitMode, ready])

  // Scroll the viewer only, never the page around it (scrollIntoView would scroll both).
  const scrollWithin = useCallback((page: number, fraction = 0) => {
    const element = container.current
    const pageDiv = viewerRef.current?.getPageView(page - 1)?.div as HTMLElement | undefined
    if (!element || !pageDiv) return
    const into = fraction ? fraction * pageDiv.offsetHeight - element.clientHeight / 3 : 0
    element.scrollTo({ top: pageDiv.offsetTop + into })
  }, [])

  const goTo = useCallback(
    (page: number) => {
      const viewer = viewerRef.current
      if (!viewer || !pdf) return
      const target = Math.min(pdf.numPages, Math.max(1, Math.round(page)))
      viewer.currentPageNumber = target
      setCurrent(target)
      setPageInput(String(target))
    },
    [pdf],
  )

  const lastPageNavSeq = useRef(0)
  useEffect(() => {
    if (!pageNavigation || !ready || pageNavigation.seq === lastPageNavSeq.current) return
    lastPageNavSeq.current = pageNavigation.seq
    goTo(pageNavigation.page)
    scrollWithin(pageNavigation.page)
  }, [pageNavigation, ready, goTo, scrollWithin])

  // Find: search the PDF's text whenever the (debounced) query changes. Matches show as pages are
  // searched; searching reads every page, so it also loads the rest of the file.
  const firstShown = useRef(false)
  useEffect(() => {
    if (!pdf || !findOpen || !debouncedQuery) {
      setMatches([])
      setSearching(false)
      return
    }
    let cancelled = false
    firstShown.current = false
    setMatches([])
    setActive(0)
    setSearching(true)
    ;(async () => {
      const found: FindMatch[] = []
      for (let page = 1; page <= pdf.numPages && !cancelled; page++) {
        let indexed = index.current.get(page)
        if (!indexed) {
          indexed = indexPage(pdf, page)
          index.current.set(page, indexed)
        }
        const { text, size: pageSize } = await indexed
        const before = found.length
        for (const rects of findOnPage(text, debouncedQuery, pageSize)) found.push({ page, rects })
        if (!cancelled && (found.length > before || page % 20 === 0)) setMatches([...found])
      }
      if (cancelled) return
      setMatches([...found])
      setSearching(false)
    })().catch(() => !cancelled && setSearching(false))
    return () => {
      cancelled = true
    }
  }, [pdf, findOpen, debouncedQuery])

  const showMatch = useCallback(
    (target: number) => {
      if (matches.length === 0) return
      const i = ((target % matches.length) + matches.length) % matches.length
      setActive(i)
      const { page, rects } = matches[i]
      setCurrent(page)
      setPageInput(String(page))
      scrollWithin(page, rotateRect(rects[0], rotation).top)
    },
    [matches, rotation, scrollWithin],
  )

  // Bring the first match into view as soon as there is one.
  useEffect(() => {
    if (matches.length && !firstShown.current) {
      firstShown.current = true
      showMatch(0)
    }
  }, [matches, showMatch])

  const openFind = useCallback(() => {
    setFindOpen(true)
    requestAnimationFrame(() => findInput.current?.select())
  }, [])

  const closeFind = () => {
    setFindOpen(false)
    setQuery('')
  }

  // Ctrl+F / Cmd+F opens the viewer's find bar instead of the browser's.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'f') {
        event.preventDefault()
        openFind()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openFind])

  // Highlight text: a press on the text layer's background (not on a span) would start PDF.js's
  // freehand highlight; stop it before PDF.js sees it, and let the text selection start instead.
  useEffect(() => {
    const element = container.current
    if (!element || tool !== AnnotationEditorType.HIGHLIGHT || !textOnly) return
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement
      if (target.classList.contains('textLayer') || target.classList.contains('endOfContent')) {
        event.stopPropagation()
      }
    }
    element.addEventListener('pointerdown', onPointerDown, { capture: true })
    return () => element.removeEventListener('pointerdown', onPointerDown, { capture: true })
  }, [tool, textOnly])

  // The eraser: PDF.js lets any annotation be selected while an editing mode is on. A press on an
  // annotation selects it, and the release deletes it; a press anywhere else does nothing (it would
  // start drawing).
  useEffect(() => {
    const element = container.current
    if (!element || !erasing) return
    const onAnnotation = (event: Event) => (event.target as HTMLElement).closest('.annotationEditorLayer > div')
    const onPointerDown = (event: PointerEvent) => {
      if (!onAnnotation(event)) {
        event.stopPropagation()
        event.preventDefault()
      }
    }
    const onPointerUp = (event: PointerEvent) => {
      if (onAnnotation(event)) {
        setTimeout(() => eventBusRef.current?.dispatch('editingaction', { source: null, name: 'delete' }), 0)
      }
    }
    element.addEventListener('pointerdown', onPointerDown, { capture: true })
    element.addEventListener('pointerup', onPointerUp, { capture: true })
    return () => {
      element.removeEventListener('pointerdown', onPointerDown, { capture: true })
      element.removeEventListener('pointerup', onPointerUp, { capture: true })
    }
  }, [erasing])

  const chooseTool = (mode: number) => {
    const viewer = viewerRef.current
    if (!viewer || !pdf) return
    setErasing(false)
    viewer.annotationEditorMode = { mode }
    // The tool's color and size, for the next annotation it makes.
    if (mode === AnnotationEditorType.HIGHLIGHT) {
      setParam(AnnotationEditorParamsType.HIGHLIGHT_COLOR, highlightColor)
      setParam(AnnotationEditorParamsType.HIGHLIGHT_THICKNESS, thickness)
    } else if (mode === AnnotationEditorType.INK) {
      setParam(AnnotationEditorParamsType.INK_COLOR, penColor)
      setParam(AnnotationEditorParamsType.INK_THICKNESS, penThickness)
    } else if (mode === AnnotationEditorType.FREETEXT) {
      setParam(AnnotationEditorParamsType.FREETEXT_COLOR, textColor)
      setParam(AnnotationEditorParamsType.FREETEXT_SIZE, textSize)
    }
    // An image is added from a file: open the file picker at once.
    if (mode === AnnotationEditorType.STAMP) {
      eventBusRef.current?.dispatch('switchannotationeditorparams', {
        source: null,
        type: AnnotationEditorParamsType.CREATE,
        value: null,
      })
    }
  }

  // A tool's color or size for the next annotation. PDF.js gives a parameter to the selected
  // annotations when there are any (and a new one stays selected after it is drawn), and only
  // otherwise makes it the default: clear the selection first, so the toolbar never recolors an
  // annotation behind the user's back and always shows what comes next.
  const setParam = (type: number, value: unknown) => {
    editorManager(viewerRef.current)?.unselectAll()
    eventBusRef.current?.dispatch('switchannotationeditorparams', { source: null, type, value })
  }

  const chooseHighlightColor = (value: string) => {
    setHighlightColor(value)
    setParam(AnnotationEditorParamsType.HIGHLIGHT_COLOR, value)
  }
  const chooseThickness = (value: number) => {
    setThickness(value)
    setParam(AnnotationEditorParamsType.HIGHLIGHT_THICKNESS, value)
  }
  const choosePenColor = (value: string) => {
    setPenColor(value)
    setParam(AnnotationEditorParamsType.INK_COLOR, value)
  }
  const choosePenThickness = (value: number) => {
    setPenThickness(value)
    setParam(AnnotationEditorParamsType.INK_THICKNESS, value)
  }
  const chooseTextColor = (value: string) => {
    setTextColor(value)
    setParam(AnnotationEditorParamsType.FREETEXT_COLOR, value)
  }
  const chooseTextSize = (value: number) => {
    setTextSize(value)
    setParam(AnnotationEditorParamsType.FREETEXT_SIZE, value)
  }
  const chooseEraser = () => {
    const viewer = viewerRef.current
    if (!viewer || !pdf) return
    // Any editing mode makes every annotation selectable; the eraser keeps presses off the page.
    if (tool === AnnotationEditorType.NONE) {
      viewer.annotationEditorMode = { mode: AnnotationEditorType.INK }
    }
    setErasing(true)
  }
  const undo = () => eventBusRef.current?.dispatch('editingaction', { source: null, name: 'undo' })

  // The file as it is, or with the annotations written into it.
  const fileBytes = async (withAnnotations: boolean) => {
    if (!pdf) throw new Error('The PDF is not loaded')
    return withAnnotations ? pdf.saveDocument() : pdf.getData()
  }

  const download = () =>
    void fileBytes(false)
      .then((bytes) => saveBlob(new Blob([bytes as BlobPart], { type: 'application/pdf' }), fileName))
      .catch(setError)

  const saveWithAnnotations = () => {
    setSaving(true)
    void fileBytes(true)
      .then((bytes) => {
        saveBlob(new Blob([bytes as BlobPart], { type: 'application/pdf' }), annotatedName(fileName))
        pdf?.annotationStorage.resetModified()
      })
      .catch(setError)
      .finally(() => setSaving(false))
  }

  const [printUrl, setPrintUrl] = useState<string | null>(null)
  useEffect(() => () => void (printUrl && URL.revokeObjectURL(printUrl)), [printUrl])
  const print = () =>
    void fileBytes(annotated)
      .then((bytes) => {
        const frame = printFrame.current
        if (!frame) return
        const next = URL.createObjectURL(new Blob([bytes as BlobPart], { type: 'application/pdf' }))
        setPrintUrl(next)
        frame.onload = () => frame.contentWindow?.print()
        frame.src = next
      })
      .catch(setError)

  const zoomTo = (next: number) => {
    const viewer = viewerRef.current
    if (!viewer) return
    setFitMode('manual')
    viewer.currentScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, next))
  }
  const zoom = (factor: number) => {
    const viewer = viewerRef.current
    if (!viewer) return
    setFitMode('manual')
    viewer.currentScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, viewer.currentScale * factor))
  }
  // Every page changes size when turned: refit, and stay on the page in view (PDF.js keeps the
  // scroll position in pixels, which lands on another page).
  const rotate = (degrees: number) => {
    const viewer = viewerRef.current
    if (!viewer) return
    const pageNumber = viewer.currentPageNumber
    viewer.pagesRotation = normalizeRotation(viewer.pagesRotation + degrees)
    if (fitMode !== 'manual') viewer.currentScaleValue = fitMode
    viewer.scrollPageIntoView({ pageNumber })
  }

  // The overlays of each page drawn so far: OCR boxes and find matches, mounted into PDF.js's page div.
  const activeMatch = matches[active] ?? null
  const overlays = useMemo(() => {
    const byPage = new Map<number, { boxes: PageRect[]; matches: PageRect[][]; active: number | null }>()
    const entry = (page: number) => {
      let value = byPage.get(page)
      if (!value) byPage.set(page, (value = { boxes: [], matches: [], active: null }))
      return value
    }
    for (const box of boxes) entry(box.page ?? 1).boxes.push(box)
    for (const match of matches) {
      const value = entry(match.page)
      if (match === activeMatch) value.active = value.matches.length
      value.matches.push(match.rects)
    }
    return byPage
  }, [boxes, matches, activeMatch])
  const editing = tool !== AnnotationEditorType.NONE

  const portals: ReactNode[] = []
  for (const [page, value] of overlays) {
    const div = pageDivs.get(page)
    if (!div?.isConnected) continue
    portals.push(
      createPortal(
        <div className="pointer-events-none absolute inset-0 z-10" aria-hidden data-overlay>
          {value.boxes.map((box, i) => (
            <Overlay
              key={`b${i}`}
              rect={box}
              rotation={rotation}
              className={cn('border border-primary/70 bg-primary/5', !editing && 'pointer-events-auto')}
            />
          ))}
          {value.matches.flatMap((rects, i) =>
            rects.map((rect, part) => (
              <Overlay
                key={`m${i}-${part}`}
                rect={rect}
                rotation={rotation}
                className={cn('rounded-xs', i === value.active ? 'bg-primary/40 outline-2 outline-primary' : 'bg-primary/20')}
              />
            )),
          )}
        </div>,
        div,
        `overlay-${page}`,
      ),
    )
  }

  const total = pdf?.numPages ?? 0
  const toolsDisabled = !ready

  return (
    <div className={cn('flex h-full min-h-0 flex-col overflow-hidden bg-card', className)}>
      <div className="@container flex items-center gap-1 overflow-hidden border-b bg-card px-2 py-1.5">
        <p className="mr-1 hidden min-w-0 max-w-[14rem] truncate text-sm font-medium @3xl:block" title={fileName}>
          {fileName}
        </p>
        <div className="mr-1 hidden h-5 w-px shrink-0 bg-border @3xl:block" aria-hidden />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Previous page"
          className="shrink-0"
          disabled={current <= 1}
          onClick={() => goTo(current - 1)}
        >
          <ChevronLeft />
        </Button>
        <form
          className="flex shrink-0 items-center gap-1 text-sm"
          onSubmit={(event) => {
            event.preventDefault()
            goTo(Number(pageInput) || 1)
          }}
        >
          <Input
            aria-label="Page"
            value={pageInput}
            onChange={(e) => setPageInput(e.target.value)}
            className="h-8 w-12 px-1 text-center"
            inputMode="numeric"
          />
          <span className="whitespace-nowrap text-muted-foreground">of {total || '…'}</span>
        </form>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Next page"
          className="shrink-0"
          disabled={current >= total}
          onClick={() => goTo(current + 1)}
        >
          <ChevronRight />
        </Button>
        <div className="mx-1 h-5 w-px shrink-0 bg-border" aria-hidden />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom out"
          className="hidden @2xl:inline-flex"
          disabled={!ready}
          onClick={() => zoom(1 / 1.25)}
        >
          <ZoomOut />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Zoom ${Math.round(scale * 100)}%`}
                className="w-16 shrink-0 px-1 tabular-nums"
                disabled={!ready}
              />
            }
          >
            {Math.round(scale * 100)}%
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-44">
            <DropdownMenuGroup>
              <DropdownMenuCheckboxItem
                closeOnClick
                checked={fitMode === 'page-width'}
                onCheckedChange={() => setFitMode('page-width')}
              >
                <MoveHorizontal />
                Fit to width
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem
                closeOnClick
                checked={fitMode === 'page-fit'}
                onCheckedChange={() => setFitMode('page-fit')}
              >
                <Maximize />
                Fit to page
              </DropdownMenuCheckboxItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              {ZOOM_PRESETS.map((percent) => (
                <DropdownMenuItem key={percent} onClick={() => zoomTo(percent / 100)}>
                  {percent}%
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom in"
          className="hidden @2xl:inline-flex"
          disabled={!ready}
          onClick={() => zoom(1.25)}
        >
          <ZoomIn />
        </Button>
        <div className="mx-1 h-5 w-px shrink-0 bg-border" aria-hidden />
        <div role="group" aria-label="Annotation tools" className="flex items-center gap-0.5">
          <Button
            variant={tool === AnnotationEditorType.NONE && !erasing ? 'secondary' : 'ghost'}
            size="icon-sm"
            aria-label="Select"
            aria-pressed={tool === AnnotationEditorType.NONE && !erasing}
            title="Select"
            disabled={toolsDisabled}
            onClick={() => chooseTool(AnnotationEditorType.NONE)}
          >
            <MousePointer2 />
          </Button>
          <ToolWithOptions
            label="Highlight"
            icon={Highlighter}
            active={tool === AnnotationEditorType.HIGHLIGHT && !erasing}
            color={highlightColor}
            disabled={toolsDisabled}
            onSelect={() => chooseTool(AnnotationEditorType.HIGHLIGHT)}
          >
            <Swatches label="Highlight color" colors={HIGHLIGHTS} value={highlightColor} onChange={chooseHighlightColor} />
            <StrokePreview color={highlightColor} width={thickness * 1.2} />
            <Range
              id="highlight-thickness"
              label="Thickness"
              min={HIGHLIGHT_THICKNESS.min}
              max={HIGHLIGHT_THICKNESS.max}
              value={thickness}
              onChange={chooseThickness}
              ends={['Thin', 'Thick']}
              disabled={textOnly}
            />
            <div className="flex items-center justify-between gap-3 border-t pt-3">
              <label htmlFor="highlight-text-only" className="text-sm">
                Text only highlight
              </label>
              <Switch id="highlight-text-only" checked={textOnly} onCheckedChange={setTextOnly} />
            </div>
            <p className="-mt-2 text-xs text-muted-foreground">
              {textOnly ? 'Highlights only the text you drag over.' : 'Marks anywhere you drag, like a marker.'}
            </p>
          </ToolWithOptions>
          <ToolWithOptions
            label="Draw"
            icon={Pencil}
            active={tool === AnnotationEditorType.INK && !erasing}
            color={penColor}
            disabled={toolsDisabled}
            onSelect={() => chooseTool(AnnotationEditorType.INK)}
          >
            <Swatches label="Pen color" colors={PEN_COLORS} value={penColor} onChange={choosePenColor} />
            <StrokePreview color={penColor} width={penThickness * 1.2} />
            <Range
              id="pen-thickness"
              label="Thickness"
              min={INK_THICKNESS.min}
              max={INK_THICKNESS.max}
              value={penThickness}
              onChange={choosePenThickness}
              ends={['Thin', 'Thick']}
            />
          </ToolWithOptions>
          <ToolWithOptions
            label="Text"
            icon={Type}
            active={tool === AnnotationEditorType.FREETEXT && !erasing}
            color={textColor}
            disabled={toolsDisabled}
            onSelect={() => chooseTool(AnnotationEditorType.FREETEXT)}
          >
            <Swatches label="Text color" colors={PEN_COLORS} value={textColor} onChange={chooseTextColor} />
            {/* The text as it will be written into the PDF (document content, not app styling). */}
            <p className="truncate font-[Helvetica,Arial,sans-serif]" style={{ color: textColor, fontSize: textSize * 1.33 }}>
              Sample text
            </p>
            <Range
              id="text-size"
              label="Font size"
              min={TEXT_SIZE.min}
              max={TEXT_SIZE.max}
              value={textSize}
              onChange={chooseTextSize}
              ends={['Small', 'Large']}
            />
            <p className="text-xs text-muted-foreground">PDF text annotations use one font: Helvetica.</p>
          </ToolWithOptions>
          <Button
            variant={erasing ? 'secondary' : 'ghost'}
            size="icon-sm"
            aria-label="Eraser"
            aria-pressed={erasing}
            title="Eraser: click an annotation to remove it"
            disabled={toolsDisabled}
            onClick={chooseEraser}
          >
            <Eraser />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Undo"
            title="Undo (Ctrl+Z)"
            className="hidden @lg:inline-flex"
            disabled={!annotated}
            onClick={undo}
          >
            <Undo2 />
          </Button>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-0.5">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Save with annotations"
            className="hidden @md:inline-flex"
            title={saving ? 'Saving…' : 'Save with annotations (download a copy with your annotations)'}
            disabled={!annotated || saving}
            onClick={saveWithAnnotations}
          >
            <SaveAnnotatedIcon />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Find in document"
            title="Find (Ctrl+F)"
            className="hidden @lg:inline-flex"
            aria-pressed={findOpen}
            onClick={openFind}
          >
            <Search />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label="More viewer actions" />}>
              <MoreHorizontal />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-60">
              <DropdownMenuGroup>
                <DropdownMenuItem disabled={!pdf} onClick={download}>
                  <Save />
                  Save
                </DropdownMenuItem>
                <DropdownMenuItem disabled={!annotated || saving} onClick={saveWithAnnotations}>
                  <FileDown />
                  Save with annotations
                </DropdownMenuItem>
                <DropdownMenuItem disabled={!pdf} onClick={print}>
                  <Printer />
                  {annotated ? 'Print with annotations' : 'Print'}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={openFind}>
                  <Search />
                  Find in document…
                  <DropdownMenuShortcut>Ctrl+F</DropdownMenuShortcut>
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem
                  disabled={toolsDisabled}
                  onClick={() => chooseTool(AnnotationEditorType.STAMP)}
                >
                  <ImagePlus />
                  Add image…
                </DropdownMenuItem>
                <DropdownMenuItem disabled={!annotated} onClick={undo}>
                  <Undo2 />
                  Undo
                  <DropdownMenuShortcut>Ctrl+Z</DropdownMenuShortcut>
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem disabled={!ready || current <= 1} onClick={() => goTo(current - 1)}>
                  <ChevronLeft />
                  Previous page
                </DropdownMenuItem>
                <DropdownMenuItem disabled={!ready || current >= total} onClick={() => goTo(current + 1)}>
                  <ChevronRight />
                  Next page
                </DropdownMenuItem>
                <DropdownMenuItem disabled={!ready} onClick={() => goTo(1)}>
                  <ArrowUpToLine />
                  First page
                </DropdownMenuItem>
                <DropdownMenuItem disabled={!ready} onClick={() => goTo(total)}>
                  <ArrowDownToLine />
                  Last page
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem disabled={!ready} onClick={() => rotate(90)}>
                  <RotateCw />
                  Rotate clockwise
                </DropdownMenuItem>
                <DropdownMenuItem disabled={!ready} onClick={() => rotate(-90)}>
                  <RotateCcw />
                  Rotate counterclockwise
                </DropdownMenuItem>
              </DropdownMenuGroup>
              {menuExtras}
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled={!pdf} onClick={() => pdf && void documentProperties(pdf, fileName).then(setProperties)}>
                <Info />
                Document properties…
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {findOpen ? (
        <div className="flex flex-wrap items-center gap-2 border-b bg-card px-3 py-2" role="search">
          <Input
            ref={findInput}
            aria-label="Find in document"
            placeholder="Find in document"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                showMatch(active + (event.shiftKey ? -1 : 1))
              } else if (event.key === 'Escape') {
                closeFind()
              }
            }}
            className="h-8 w-64"
          />
          <span className="min-w-24 text-sm text-muted-foreground tabular-nums" aria-live="polite">
            {!debouncedQuery
              ? ''
              : matches.length
                ? `${active + 1} of ${matches.length}${searching ? '…' : ''}`
                : searching
                  ? 'Searching…'
                  : 'No matches'}
          </span>
          <Button variant="ghost" size="icon-sm" aria-label="Previous match" disabled={!matches.length} onClick={() => showMatch(active - 1)}>
            <ChevronUp />
          </Button>
          <Button variant="ghost" size="icon-sm" aria-label="Next match" disabled={!matches.length} onClick={() => showMatch(active + 1)}>
            <ChevronDown />
          </Button>
          <span className="text-xs text-muted-foreground">Searches the PDF's text, not scanned images.</span>
          <Button variant="ghost" size="icon-sm" aria-label="Close find" className="ml-auto" onClick={closeFind}>
            <X />
          </Button>
        </div>
      ) : null}
      {error ? (
        <div className="p-3">
          <ErrorAlert error={error} />
        </div>
      ) : null}
      <div className="relative min-h-0 flex-1 bg-muted">
        {/* PDFViewer needs an absolutely positioned scroll container with the viewer div inside. */}
        <div
          ref={container}
          className={cn(
            'pdf-viewer-scroller absolute inset-0 overflow-auto',
            tool === AnnotationEditorType.HIGHLIGHT && !textOnly && !erasing && 'pdf-marker',
            erasing && 'pdf-erasing',
          )}
        >
          <div className="pdfViewer" />
        </div>
        {!ready && !error ? (
          <div className="absolute inset-0">
            {loading ?? (
              <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
                Loading PDF…
              </div>
            )}
          </div>
        ) : null}
      </div>
      {portals}
      <iframe ref={printFrame} title="Print PDF" className="hidden" />
      {properties ? (
        <PropertiesDialog
          title={fileName}
          description="PDF properties"
          properties={properties}
          onClose={() => setProperties(null)}
        />
      ) : null}
    </div>
  )
}
