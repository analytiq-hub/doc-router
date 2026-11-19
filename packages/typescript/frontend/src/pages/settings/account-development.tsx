import { Navigate } from 'react-router-dom'

/** LLM, cloud, and worker settings are items in the settings menu. */
export default function DevelopmentSettingsPage() {
  return <Navigate to="/settings/account/development/llm-manager" replace />
}
