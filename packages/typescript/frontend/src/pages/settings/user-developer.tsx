import { Navigate } from 'react-router-dom'

/** Account tokens, organization tokens, and webhooks are items in the settings menu. */
export default function DeveloperPage() {
  return <Navigate to="/settings/user/developer/account-access-tokens" replace />
}
