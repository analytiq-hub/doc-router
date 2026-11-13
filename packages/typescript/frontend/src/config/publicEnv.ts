/**
 * Build-time public config (Vite). Set `VITE_*` in the repo root `.env` (injected via vite `define`).
 */

function readPublic(key: string, fallback = ''): string {
  if (typeof process !== 'undefined') {
    const primary = process.env[key];
    if (typeof primary === 'string' && primary.trim()) return primary.trim();
  }
  const meta = import.meta.env as Record<string, string | undefined>;
  const fromMeta = meta[key];
  if (typeof fromMeta === 'string' && fromMeta.trim()) return fromMeta.trim();
  return fallback;
}

/** Browser API prefix (usually same-origin `/fastapi`). */
export function publicFastApiFrontendUrl(): string {
  return readPublic('VITE_FASTAPI_FRONTEND_URL', '/fastapi') || '/fastapi';
}

export function publicAppName(fallback = 'Smart Document Router'): string {
  return readPublic('VITE_APP_NAME', fallback) || fallback;
}

export function publicAppFavicon(fallback = '/favicon.ico'): string {
  return readPublic('VITE_APP_FAVICON', fallback) || fallback;
}

/** Orchestrator-style pdfjs-dist viewer (Track B). Set `VITE_PDF_VIEWER_V2=1` to enable. */
export function publicPdfViewerV2(): boolean {
  const raw = readPublic('VITE_PDF_VIEWER_V2', '');
  return raw === '1' || raw.toLowerCase() === 'true';
}
