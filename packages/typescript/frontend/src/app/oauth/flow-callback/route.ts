/**
 * Popup OAuth landing page — static HTML only (no root layout / providers).
 * API redirects here after `/v0/callback/flow-oauth` exchanges the code.
 */
export function GET(request: Request) {
  const url = new URL(request.url);
  const status = url.searchParams.get('status') === 'success' ? 'success' : 'error';

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>OAuth</title>
</head>
<body>
<script>
(function () {
  var status = ${JSON.stringify(status)};
  function notifyAndClose() {
    try {
      var ch = new BroadcastChannel('flow-oauth-callback');
      ch.postMessage(status);
      ch.close();
    } catch (e) {}
    try {
      window.close();
    } catch (e) {}
  }
  notifyAndClose();
  setTimeout(notifyAndClose, 50);
})();
</script>
</body>
</html>`;

  return new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}
