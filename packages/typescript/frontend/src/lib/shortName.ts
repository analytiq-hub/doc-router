/** Truncate a name for confirm dialog copy. */
export function shortName(name: string | null | undefined, max = 40): string {
  const text = name ?? ''
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text
}
