'use client';

/** Backend `engine.py` persists `run_data[node_id].error` as `{ message, node_id, node_name, stack }`. */
export function NodeRunErrorDetails({ error }: { error: unknown }) {
  if (!error || typeof error !== 'object') return null;
  const rec = error as Record<string, unknown>;
  const message = typeof rec.message === 'string' ? rec.message : null;
  if (message == null || message === '') return null;
  const nodeName = typeof rec.node_name === 'string' ? rec.node_name : null;
  const stack = typeof rec.stack === 'string' && rec.stack.trim() !== '' ? rec.stack : null;
  const title = nodeName ? `${nodeName}` : 'Error details';
  return (
    <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-950">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-red-800">{title}</div>
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
