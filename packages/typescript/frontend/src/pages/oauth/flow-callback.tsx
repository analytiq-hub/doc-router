'use client';

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

/** Popup OAuth landing — API redirects here after `/v0/callback/flow-oauth`. */
export default function FlowOAuthCallbackPage() {
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const status = searchParams.get('status') === 'success' ? 'success' : 'error';

    const notifyAndClose = () => {
      try {
        const ch = new BroadcastChannel('flow-oauth-callback');
        ch.postMessage(status);
        ch.close();
      } catch {
        /* popup may block BroadcastChannel */
      }
      try {
        window.close();
      } catch {
        /* ignore */
      }
    };

    notifyAndClose();
    const timer = window.setTimeout(notifyAndClose, 50);
    return () => window.clearTimeout(timer);
  }, [searchParams]);

  return (
    <p className="mt-8 text-center text-sm text-gray-600">Completing authorization…</p>
  );
}
