'use client';

import { Navigate } from 'react-router-dom';

/** Legacy URL; queue workers moved under System → Queues. */
export default function DevelopmentWorkerSettingsRedirect() {
  return <Navigate to="/settings/account/queues" replace />;
}