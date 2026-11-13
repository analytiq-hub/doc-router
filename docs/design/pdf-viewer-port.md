# PDF viewer port (Track B)

Port doc-router’s document PDF pane from **react-pdf + MUI** to orchestrator-style **`pdfjs-dist` `PDFViewer`** with doc-router **loader, highlight adapter, and API wiring**. Reference implementation: sibling tree `../doc-orchestrator` (`components/PdfViewer.tsx`, `lib/pdfSearch.ts`, `lib/pdfGeometry.ts`, `docs/design/pdf-viewer.md`).

**Status:** Phase 2 in progress — full orchestrator `PdfViewerCore` (toolbar, annotations, `pdfSearch` find); overlays + doc-router menus next.  
**Branch:** `devel` → cutover on `main` after soak.

---

## Locked product decisions (2026-03-25)

| # | Decision |
|---|----------|
| 1 | **Extraction highlight visuals:** orchestrator-style **flat rects** in v1 (`primary` overlay tokens). Optional **amber clip-path** parity with legacy react-pdf in **v1.1** (non-blocking). |
| 2 | **In-viewer find:** **port `pdfSearch.ts`** from orchestrator (glyph index, match rects, active match). Do not keep legacy debounced `pdfTextSearch` for the toolbar find UI. |
| 3 | **Annotations:** **Supported in v1** — same Edge-style toolbar subset as orchestrator (highlight, draw, text, image, eraser, undo, save copy with annotations, print). Annotations are **client-only** (download copy); not stored in doc-router. |
| 4 | **Toolbar chrome:** **Match orchestrator** (single dense row, `@container` compression, filename in toolbar, no separate MUI menubar / brand-colored bar). |

**Still out of scope v1:** connector PDF versioning, `ranges` streaming, `onStale` version refresh (orchestrator connector model). Doc-router continues **blob fetch + processing poll** via `DocRouterOrgApi`.

---

## Goals

- Remove `react-pdf`, `MuiPdfThemeIsland`, `styles/theme.ts`, and all `@mui/*` / `@emotion/*` used only for the PDF pane.
- Preserve doc-router **extraction/forms find**, **bbox mode** (`?bbox`), **OCR modal**, rerun OCR, processing states, and sidebar callbacks (`onPdfDocumentReady`, `onViewerPageChange`, `onViewerFileNameChange`).
- No backend API changes.

## Architecture

```text
DocumentViewerPage
  └── DocRouterPdfViewer          (same external props as PDFViewer.tsx today)
        ├── useDocRouterPdfDocument   blob URL, revoke, metadata poll, errors
        ├── PdfViewerCore               ported orchestrator viewer (PDF.js + toolbar + annotations)
        └── useDocRouterOverlays        HighlightInfo + bbox → PageRect portals
```

**Single import site:** `DocumentViewerPage` dynamic import → `DocRouterPdfViewer` (replace `@/components/PDFViewer`).

### Frozen public props

| Prop | Consumer |
|------|----------|
| `organizationId`, `id` | Loader |
| `highlightInfo?` | Overlay adapter + page jump |
| `initialShowBoundingBoxes?` | `?bbox` |
| `onPdfDocumentReady?` | Extraction/forms PDF fallback (`PDFDocumentProxy`) |
| `onViewerPageChange?` | Text tab |
| `onViewerFileNameChange?` | Text tab, OCR |

---

## Module map

| Path | Notes |
|------|--------|
| `components/pdf/viewer/DocRouterPdfViewer.tsx` | Shell: loader + core + doc-router menu extras |
| `components/pdf/viewer/PdfViewerCore.tsx` | Port from orchestrator; annotations **on** |
| `components/pdf/viewer/Overlay.tsx` | Port `Overlay` + portal pattern |
| `components/pdf/viewer/docRouterMenuExtras.tsx` | Rerun OCR, OCR outputs, bbox toggle |
| `hooks/useDocRouterPdfDocument.ts` | Blob lifecycle + poll (from current `PDFViewer.tsx`) |
| `hooks/useDocRouterOverlays.ts` | `HighlightInfo` + OCR blocks → `PageRect[]` |
| `lib/pdfGeometry.ts` | Port `PageRect`, `rotateRect`, `Rotation` |
| `lib/pdfSearch.ts` | Port + `pdfSearch.test.ts` |
| `utils/pdfTextSearch.ts` | Keep for **`useOCRBlocks` PDF fallback** until unified (may wrap pdfSearch later) |
| `utils/pdfjsWorker.ts` | Align with `pdfjs-dist@^6.4.299` |

**Remove at cutover:** `components/PDFViewer.tsx`, `components/pdf/MuiPdfThemeIsland.tsx`, `styles/theme.ts`.

---

## Highlight adapter

Orchestrator overlays: `createPortal` into PDF.js page divs with normalized `PageRect` (0–1, top-left).

| Source | Maps to |
|--------|---------|
| `highlightInfo.blocks` | `PageRect` via existing `getTextractNormalizedBox` + `ocrBlockPageNum` |
| `highlightInfo.pdfFallbackHits` | `PageRect` (same coords as today) |
| Bbox mode | OCR WORD/LINE blocks → `boxes` with optional `label` |
| Viewer find (`pdfSearch`) | `matches` rects + `active` index (orchestrator pattern) |
| Extraction overlays (v1) | Flat rects, `border-primary/70 bg-primary/5` (or extraction-specific token in v1.1) |

**Preserve:** multi-match cycle on repeated extraction find; `findNextHighlightedPage` → `scrollWithin` / `goTo(page)`; `rotateRect` for viewer rotation.

---

## Find strategy

| Use case | Implementation |
|----------|------------------|
| Toolbar find (Ctrl/Cmd+F) | **`lib/pdfSearch.ts`** (ported) |
| Extraction sidebar fallback when OCR misses | **`pdfTextSearch`** / `useOCRBlocks` until a shared rect builder exists |
| Unification (optional v1.1) | Single `PageRect` builder used by pdfSearch + fallback |

---

## Annotations (v1)

Port orchestrator toolbar tools per `doc-orchestrator/docs/design/pdf-viewer.md` §5:

- Highlight (marker + “text only” option), draw, text, image, eraser, undo.
- Save / save-with-annotations (download), print.
- Tool settings in local storage (`useToolSetting` pattern).

**Not persisted** to doc-router MongoDB; behavior matches orchestrator.

---

## Phases and PR sequence

### Phase 0 — Spike (3–5 d)

- Add explicit `pdfjs-dist@^6.4.299`; verify Vite worker with `ensurePdfjsWorker()`.
- Minimal core: blob → pages scroll, `onPageChange`, no overlays.
- **PR 1:** `docs/design/pdf-viewer-port.md` + deps + spike.

### Phase 1 — Loader + flag (4–6 d)

- `useDocRouterPdfDocument`; processing / error UI.
- `VITE_PDF_VIEWER_V2` (via `publicEnv.ts`) toggles `DocRouterPdfViewer` vs legacy.
- **PR 2:** loader + feature flag.

### Phase 2 — Core + toolbar + annotations (8–12 d)

- Port `PdfViewerCore` including **annotation** toolbar (orchestrator parity).
- Toolbar layout **matches orchestrator** (filename in bar, container queries).
- **PR 3:** core viewer (no doc-router overlays yet).

### Phase 3 — `pdfSearch` (4–6 d)

- Port `pdfSearch.ts` + tests; wire toolbar find to core overlay `matches`.
- **PR 4:** in-viewer find.

### Phase 4 — Highlight adapter (6–8 d)

- `useDocRouterOverlays`; wire `highlightInfo`, bbox, `?bbox` polling.
- `onPdfDocumentReady` from loaded `PDFDocumentProxy`.
- **PR 5:** extraction/forms find + bbox.

### Phase 5 — Doc-router extras (3–5 d)

- Rerun OCR, OCR output `DraggablePanel`, document properties, download/print paths.
- **PR 6:** parity with legacy doc-router menus (minus MUI).

### Phase 6 — Cutover (2–3 d)

- Default flag on; remove legacy `PDFViewer.tsx`, MUI island, `react-pdf`.
- **PR 7:** delete legacy + `package.json` cleanup (Phase 9 exit).

### Phase 7 — Tests (3–5 d)

- Puppeteer: open doc, scroll, find, bbox toggle, extraction highlight smoke.
- Unit: overlay builder + `pdfSearch` / `pdfGeometry` tests.
- **PR 8:** tests.

### Phase 8 — v1.1 (optional)

- Amber / clip-path extraction highlight styling if product wants pixel parity with old viewer.

---

## Rollout

1. `VITE_PDF_VIEWER_V2=1` locally → staging → production default on in cutover PR.
2. Soak one release with flag before deleting legacy (flag can be short if tests green).

---

## Acceptance (cutover)

- [ ] Extraction + forms find (OCR + PDF fallback) and match cycling.
- [ ] `?bbox` and bbox toggle.
- [ ] Text tab page sync while scrolling.
- [ ] Toolbar find via `pdfSearch`.
- [ ] Annotations: download annotated copy works; no server persistence.
- [ ] No `@mui` / `react-pdf` in `src/`.
- [ ] `npm run typecheck` + `npm run build`.

---

## References

- Orchestrator: `../doc-orchestrator/packages/typescript/frontend/src/components/PdfViewer.tsx`
- Orchestrator design: `../doc-orchestrator/docs/design/pdf-viewer.md`
- Doc-router legacy: `packages/typescript/frontend/src/components/PDFViewer.tsx`
- UI migration: [ui-migration.md](./ui-migration.md) Phase 8/9
