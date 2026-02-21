# Doc Router app.docrouter.ai – Load performance (8.27s)

## Why reload takes ~8.27 seconds

From network waterfalls (87 requests, ~6.44 MB transferred):

1. **Backend API latency (dominant)**
   - **`/fastapi/v0/orgs/.../ocr/download/blocks/{document_id}`** – ~5.4 s
     - Returns full OCR blocks JSON; large payload + TTFB.
   - **`/fastapi/v0/orgs/.../llm/result/{document_id}`** – ~3.2 s (and duplicate calls ~1.5–1.7 s later)
   - **`/fastapi/v0/orgs/.../prompts?...`** – ~2.7–4.4 s
   - **`/fastapi/v0/orgs/.../documents/...?file_type=pdf`** – ~2.3 s (PDF binary)
   - **`/fastapi/v0/account/organizations`** – ~2.0–2.2 s (two calls)
   - **`/fastapi/v0/orgs/.../chat/threads`**, **`/chat/tools`**, **`/llm/models/chat_only`** – ~2.7–3.2 s each

2. **No browser caching of static assets**
   - All ~80+ JS chunks and CSS show **200** (full download).
   - No **304 Not Modified** or "from disk cache" for `_next/static/chunks/*.js` or `_next/static/media/*.mjs`.
   - So every reload re-downloads 6+ MB of JS/CSS (e.g. `4442.*.js` ~1.2 s, `pdf.worker.min.*.mjs` ~1.0–1.7 s).

3. **Redundant / duplicate requests**
   - **`/orgs/undefined/docs`** and **`/orgs/undefined/dashboard`** – ~3.27–3.28 s each (RSC/prefetch with `organizationId` not yet resolved).
   - Same org data fetched twice with different `_rsc` params (e.g. knowledge-bases, forms, prompts, schemas, tags, docs, dashboard).
   - **Document + LLM**: `DocumentPageProvider` fetches the document once; `PDFExtractionSidebar` can still call `getDocument(pdf)` when `documentPage` is null, then `listPrompts` and `getLLMResult`, so document (and possibly LLM) are effectively fetched more than once on cold load.
   - **Duplicate LLM result fetch**: `PDFExtractionSidebar` has two separate `useEffect` hooks that can both trigger `getLLMResult('default')`:
     - Lines 57–105: `fetchData` — starts the fetch and sets `defaultLlmFetchStartedRef.current = true`
     - Lines 108–126: fires when `documentPage?.documentState === 'llm_completed'`
     Both effects run on initial render when the context already has `llm_completed` state. There is a race: both see `defaultLlmFetchStartedRef.current === false` before either writes `true`, so two requests fire for the same LLM result.
   - **Duplicate org list fetch**: `GET /account/organizations` fires twice simultaneously. The `fetchInFlightRef` guard in `OrganizationContext` is supposed to prevent this, but React 18 Strict Mode invokes effects twice in development. Also, a session status change between `loading` and `authenticated` can trigger a second execution of the same effect before the ref is set.

4. **Serial fetch waterfall in `PDFExtractionSidebar`**
   The `fetchData` effect chain is fully sequential:
   `get document state` → `listPrompts` (4.4 s) → `getLLMResult` (1.6 s)
   This creates a ~6 s serial chain before extraction results appear. The prompts and LLM result fetches are independent once document state is known; they could be parallelised. Additionally, the `fetchData` `useEffect` dependency array includes `llmResults`, `loadingPrompts`, and `failedPrompts` (line 105), causing the effect to re-subscribe and potentially re-run on every state change within the sidebar.

5. **DOMContentLoaded / Load vs Finish**
   - **DOMContentLoaded** ~235 ms, **Load** ~425 ms (initial HTML + critical resources).
   - **Finish** ~8.27 s = when **all** network requests (including slow API and all JS chunks) complete. So "total load" in the network tab is dominated by those slow API and uncached static requests.

---

## What was changed in this repo

- **Next.js static asset caching**
  In `packages/typescript/frontend/next.config.mjs`, `headers()` was added so `/_next/static/*` is served with:
  - `Cache-Control: public, max-age=28800`
  Static cache age: **8 hours** (`max-age=28800`), so a post-midnight release is picked up after the next refresh the following day. The hosting layer must not override these headers (e.g. self-hosted Node/Docker).
  **Note:** On Vercel, static assets may already get similar headers; if you use a CDN/reverse proxy, ensure it does not strip or shorten `Cache-Control` for `/_next/static/*`.

---

## Further optimizations (recommended)

### 1. Backend API (highest impact)

- **OCR blocks** (`/ocr/download/blocks`):
  - ✅ **Done:** `Cache-Control: private, max-age=3600` (1h) added in `app/routes/ocr.py`.
  - Ensure response is gzip'd (optional).
  - Consider pagination or "by-page" endpoint so the client doesn't wait for the full document's blocks (optional).
  - Add DB/cache indexing if `get_ocr_json` is slow (e.g. blob key lookups).
- **LLM result** (`/llm/result`):
  - Reduce payload (e.g. omit heavy fields until needed).
  - Do **not** cache (data is dynamic per document).
- **Prompts** (`/prompts?skip=0&limit=100&document_id=...`):
  - 4.4 s for a list query suggests a missing MongoDB index. Add a compound index on `{ org_id, document_id }` (or whichever fields the query filters on).
  - Do **not** cache (list is dynamic).
- **Chat threads/tools, LLM models**:
  - `GET /llm/models?chat_only=true` is static per deployment — cache aggressively (e.g. `max-age=300` or longer).
  - Threads/tools: add DB indexes; consider HTTP ETag so unchanged responses return 304.
- **Account/organizations**:
  - Cache per user/session where possible; avoid duplicate calls (see frontend).

### 2. Frontend

- **Fix `orgs/undefined`** ✅ **Done**
  - Layout sidebar and header now derive org id from the URL path (`/orgs/[id]/...`) when `currentOrganization` is not yet loaded, so links never point to `/orgs/undefined/...` and Next.js no longer prefetches those bad URLs. TourGuide steps use the same pathname-derived org id. When no org id is available (e.g. not on an org page), sidebar menu items render as non-clickable placeholders.
- **Fix duplicate LLM result fetch in `PDFExtractionSidebar`**
  - Merge the two `useEffect` hooks (lines 57–105 and 108–126 of `PDFExtractionSidebar.tsx`) that both trigger `getLLMResult('default')` into a single effect, or move the `defaultLlmFetchStartedRef` check inside an atomic `useCallback` that both effects call, ensuring the ref is set before the async call returns.
- **Break serial fetch waterfall in `PDFExtractionSidebar`**
  - Once document state is available from `DocumentPageContext`, fire `listPrompts` and `getLLMResult('default')` in parallel (`Promise.all`). Currently they are sequential: prompts finish → LLM fetch starts, adding ~4 s to display time.
  - Remove `llmResults`, `loadingPrompts`, and `failedPrompts` from the `fetchData` `useEffect` dependency array (line 105); use refs for those guards instead to avoid the effect re-running on every state update.
- **Deduplicate data fetching** (partial) ✅ **Sidebar/document**
  - `PDFExtractionSidebar` now waits briefly (250ms) when `documentPage` is null so `DocumentPageProvider` can set context first; only then does it call `getDocument` if context is still null, avoiding a duplicate fetch when the provider is about to load.
  - Consolidate org-scoped list fetches (knowledge-bases, forms, prompts, schemas, tags, docs, dashboard) so they are not triggered twice with different `_rsc` for the same data — **not yet done**.
- **Fix duplicate organizations fetch**
  - In `OrganizationContext`, move the in-flight guard (`fetchInFlightRef`) to be set synchronously before the `async` call (before `await`), not inside a closure. In React 18 Strict Mode, effects fire twice; a `useRef` guard set inside an async callback can be seen as `false` by the second invocation. Setting it synchronously at the top of the effect body prevents this.
- **Defer non-critical API calls** ✅ **Done**
  - Chat panel is visible immediately. Threads, tools, and models are loaded on first use: threads when the user opens the thread dropdown, tools when they open the tools dropdown, models when they open the model dropdown. This avoids threads/tools/models requests on initial page load so they don't stretch "Finish" time.

### 3. Infrastructure

- **CDN**
  - Serve `/_next/static/*` (and optionally API if you add cache rules) from a CDN to reduce latency for JS/CSS and, if applicable, API.
- **HTTP/2**
  - Ensure the app and any reverse proxy use HTTP/2 so many small requests (e.g. chunks) are multiplexed efficiently.

---

## Quick checklist

- [x] Cache-Control for `/_next/static/*` in Next.js config (done in repo).
- [ ] Ensure deployment/CDN does not override or strip those headers.
- [ ] Backend: compress and/or paginate OCR blocks (optional). Do not cache LLM result or prompts; add `Cache-Control` for models endpoint only (e.g. `max-age=300`).
- [x] Backend: add `Cache-Control: private, max-age=3600` for OCR blocks endpoint.
- [x] Backend: add MongoDB compound index on `prompts` collection for list_prompts (organization_id + prompt_revisions tag_ids).
- [x] Frontend: fix `organizationId` so no `/orgs/undefined` RSC requests (derive from pathname in Layout + TourGuide).
- [x] Frontend: merge the two competing `useEffect` hooks in `PDFExtractionSidebar` that both fetch the default LLM result.
- [x] Frontend: parallelize `listPrompts` + `getLLMResult` in `PDFExtractionSidebar` instead of sequential waterfall.
- [x] Frontend: remove `llmResults`/`loadingPrompts`/`failedPrompts` from `fetchData` effect dependency array; use refs for guards.
- [x] Frontend: fix `fetchInFlightRef` guard in `OrganizationContext` to be set synchronously (before `await`) to survive React 18 Strict Mode double-invocation.
- [x] Frontend: defer `AgentTab` API calls (threads, tools, models) until the chat panel is first expanded.
- [x] Frontend: `PDFViewer` waits 250ms for `DocumentPageContext` before calling `getDocument`, avoiding duplicate `documents/...?file_type=pdf` when provider is loading.

---

## Network trace (reload) – static vs dynamic

**Static (cache):** `/_next/static/*` (JS, CSS, `pdf.worker.min.mjs`) is already served with `Cache-Control: public, max-age=28800` in `next.config.mjs`. With cache enabled, reloads should serve these from disk. Ensure deployment/CDN does not strip these headers. Favicon: reference it consistently (one URL) so it can be cached.

**Dynamic (deduplicate):** From traces, duplicate GETs were seen for:
- **`/v0/account/organizations`** – Guard in `OrganizationContext` is set synchronously to avoid double fetch; other call sites (dashboard, OrganizationManager, UserInviteModal) are different routes. If duplicates remain on the doc page, consider a shared client-side cache (e.g. SWR/React Query) keyed by URL+params.
- **`/v0/orgs/.../documents/...?file_type=pdf`** – `DocumentPageContext` fetches once; `PDFExtractionSidebar` and `PDFViewer` now wait 250ms for context before calling `getDocument`, so the doc page should issue a single document fetch.
- **`/v0/orgs/.../prompts`**, **`/llm/result`**, **`/ocr/download/blocks`** – If still duplicated, ensure a single effect/hook per document (refs and dependency arrays as in `PDFExtractionSidebar`). OCR has a per-`OCRProvider` cache; one provider per doc page would avoid duplicate OCR fetches.
