/** Load patched Formio CSS (same as Next `<link href="/formio.full.css" />`). */
export function ensureFormioStyles(): void {
  if (typeof document === 'undefined') return;
  const href = '/formio.full.css';
  if (document.querySelector(`link[rel="stylesheet"][href="${href}"]`)) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = href;
  document.head.appendChild(link);
}
