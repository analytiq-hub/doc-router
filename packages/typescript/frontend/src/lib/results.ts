/** A value with no structure: shown as it is. */
export type Leaf = string | number | boolean | null

export const isLeaf = (value: unknown): value is Leaf =>
  value === null || ['string', 'number', 'boolean'].includes(typeof value)

function leafText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (isLeaf(value)) return String(value).replace(/\s+/g, ' ').trim()
  if (Array.isArray(value)) return value.length === 1 ? '1 item' : `${value.length} items`
  return `${Object.keys(value as object).length} fields`
}

/** One-line summary for a collapsed extraction row. */
export function resultPreview(result: Record<string, unknown> | null | undefined, fields = 3): string {
  if (!result) return ''
  const entries = Object.entries(result)
  if (!entries.length) return 'No fields'
  if (entries.length === 1) return leafText(entries[0][1])
  const shown = entries.slice(0, fields).map(([key, value]) => `${key}: ${leafText(value)}`)
  return entries.length > fields ? `${shown.join(' · ')} · …` : shown.join(' · ')
}
