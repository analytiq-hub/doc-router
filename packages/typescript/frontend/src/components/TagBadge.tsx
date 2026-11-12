import type { Tag } from '@docrouter/sdk'
import { Badge } from '@/components/ui/badge'
import { readableTextColor } from '@/lib/color'

export const DEFAULT_TAG_COLOR = '#3B82F6'

export function TagBadge({ tag }: { tag: Pick<Tag, 'name' | 'color'> }) {
  const background = tag.color ?? DEFAULT_TAG_COLOR
  const textColor = readableTextColor(background)
  return (
    <Badge
      className="max-w-full border-0"
      title={tag.name}
      style={{ backgroundColor: background, color: textColor === 'white' ? '#fff' : '#111827' }}
    >
      <span className="truncate">{tag.name}</span>
    </Badge>
  )
}
