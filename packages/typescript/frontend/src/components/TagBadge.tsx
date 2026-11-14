import type { Tag } from '@docrouter/sdk'
import { Badge } from '@/components/ui/badge'
import { readableTextColor } from '@/lib/color'

export const DEFAULT_TAG_COLOR = '#3B82F6'

export function TagBadge({
  tag,
  soft = false,
}: {
  tag: Pick<Tag, 'name' | 'color'>
  /** Pastel fill for popovers and other light surfaces. */
  soft?: boolean
}) {
  const color = tag.color ?? DEFAULT_TAG_COLOR
  const background = soft
    ? `color-mix(in srgb, ${color} 22%, var(--card))`
    : color
  const textColor = soft ? 'black' : readableTextColor(color)
  return (
    <Badge
      className="max-w-full border-0"
      title={tag.name}
      style={{
        backgroundColor: background,
        color: textColor === 'white' ? '#fff' : '#111827',
      }}
    >
      <span className="truncate">{tag.name}</span>
    </Badge>
  )
}
