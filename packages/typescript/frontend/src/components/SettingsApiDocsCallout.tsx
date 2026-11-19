import { ExternalLink } from 'lucide-react';

import { fastApiDocsHref } from '@/utils/api';

/** Link to interactive FastAPI docs (mirrors the old Settings developer hub callout). */
export function SettingsApiDocsCallout() {
  const href = fastApiDocsHref();
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm">
      <p className="text-muted-foreground">Interactive API reference (OpenAPI / Swagger):</p>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2 inline-flex items-center gap-1.5 font-mono text-primary hover:underline"
      >
        {href}
        <ExternalLink className="size-3.5 shrink-0" aria-hidden />
      </a>
    </div>
  );
}