import { Navigate } from 'react-router-dom'

import { lastSettingsPath } from '@/utils/navMemory'

/** `/settings` opens where the user left it; the first time, on Profile. */
export default function SettingsPage() {
  return <Navigate to={lastSettingsPath() ?? '/settings/user/profile'} replace />
}
