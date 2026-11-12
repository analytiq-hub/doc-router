import { getApiErrorMsg } from '@/utils/api'
import { Alert, AlertDescription } from '@/components/ui/alert'

/** The message of a failed request, or nothing when there is no error. */
export function ErrorAlert({ error, className }: { error: unknown; className?: string }) {
  if (!error) return null
  const message = getApiErrorMsg(error) ?? (error instanceof Error ? error.message : String(error))
  return (
    <Alert variant="destructive" className={className}>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
