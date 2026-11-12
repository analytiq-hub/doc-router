const WORKER_PROBE_TIMEOUT_MS = 1500;

let workerReady: Promise<void> | null = null;

/** Some embedded browsers (e.g. Cursor's) construct Workers that never run, with no error. */
function workersRespond(): Promise<boolean> {
  return new Promise((resolve) => {
    let worker: Worker;
    const url = URL.createObjectURL(new Blob(['postMessage(1)'], { type: 'text/javascript' }));
    try {
      worker = new Worker(url);
    } catch {
      URL.revokeObjectURL(url);
      resolve(false);
      return;
    }
    const finish = (ok: boolean) => {
      window.clearTimeout(timer);
      worker.terminate();
      URL.revokeObjectURL(url);
      resolve(ok);
    };
    const timer = window.setTimeout(() => finish(false), WORKER_PROBE_TIMEOUT_MS);
    worker.onmessage = () => finish(true);
    worker.onerror = () => finish(false);
  });
}

/**
 * Resolves once PDF.js can load documents. Without working Workers, loads the PDF.js worker
 * module on the main thread: it sets `globalThis.pdfjsWorker`, which PDF.js uses instead of a Worker.
 */
export function ensurePdfjsWorker(): Promise<void> {
  workerReady ??= (async () => {
    if (await workersRespond()) return;
    await import('pdfjs-dist/build/pdf.worker.min.mjs');
  })();
  return workerReady;
}
