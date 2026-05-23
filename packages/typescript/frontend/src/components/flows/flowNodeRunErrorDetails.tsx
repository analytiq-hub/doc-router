'use client';

/** Backend `engine.py` persists `run_data[node_id].error` (see `docs/docrouter_fulltrace.md`). */
export function NodeRunErrorDetails({ error }: { error: unknown }) {
  if (!error || typeof error !== 'object') return null;
  const rec = error as Record<string, unknown>;
  const message = typeof rec.message === 'string' ? rec.message : null;
  if (message == null || message === '') return null;
  const nodeName = typeof rec.node_name === 'string' ? rec.node_name : null;
  const stack = typeof rec.stack === 'string' && rec.stack.trim() !== '' ? rec.stack : null;
  const cause = typeof rec.cause === 'string' && rec.cause.trim() !== '' ? rec.cause : null;
  const httpCode = typeof rec.http_code === 'number' ? rec.http_code : null;
  const title = nodeName ? `${nodeName}` : 'Error details';
  return (
    <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-950">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-red-800">{title}</div>
        {cause ? <span className="font-mono text-[10px] text-red-700">{cause}</span> : null}
        {httpCode != null ? (
          <span className="rounded bg-red-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-red-800">
            HTTP {httpCode}
          </span>
        ) : null}
      </div>
      <pre className="mt-1.5 whitespace-pre-wrap break-words font-mono text-xs leading-snug">{message}</pre>
      {stack && (
        <>
          <div className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-red-700">Stack trace</div>
          <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-snug text-red-900">
            {stack}
          </pre>
        </>
      )}
    </div>
  );
}
