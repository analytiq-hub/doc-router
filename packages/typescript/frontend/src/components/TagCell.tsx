import { useLayoutEffect, useRef, useState } from 'react'
import type { Tag } from '@docrouter/sdk'
import { TagBadge } from '@/components/TagBadge'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

const GAP = 4

export function tagsThatFit(widths: number[], width: number, moreWidth: number): number {
  const ends: number[] = []
  widths.forEach((w, i) => ends.push((i ? ends[i - 1] + GAP : 0) + w))
  if (!width || !ends.length || ends[ends.length - 1] <= width) return widths.length
  let count = widths.length - 1
  while (count > 0 && ends[count - 1] + GAP + moreWidth > width) count -= 1
  return count
}

export function TagCell({ tags }: { tags: Tag[] }) {
  const box = useRef<HTMLDivElement>(null)
  const more = useRef<HTMLSpanElement>(null)
  const signature = tags.map((tag) => `${tag.id}:${tag.name}`).join('|')
  const [measured, setMeasured] = useState<{ signature: string; widths: number[] } | null>(null)
  const [room, setRoom] = useState({ width: 0, more: 0 })
  const widths = measured?.signature === signature ? measured.widths : null

  useLayoutEffect(() => {
    const container = box.current
    if (!container) return
    const update = () => setRoom({ width: container.clientWidth, more: more.current?.offsetWidth ?? 0 })
    update()
    const observer = new ResizeObserver(update)
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  useLayoutEffect(() => {
    if (widths || !box.current) return
    const badges = Array.from(box.current.querySelectorAll<HTMLElement>('[data-tag]'))
    setMeasured({ signature, widths: badges.map((badge) => badge.offsetWidth) })
  }, [signature, widths])

  if (tags.length === 0) return <span className="text-muted-foreground">—</span>

  const shown = widths ? tagsThatFit(widths, room.width, room.more) : tags.length
  const hidden = tags.slice(shown)
  return (
    <div ref={box} className="relative flex h-full min-w-0 items-center gap-1 overflow-hidden">
      {tags.slice(0, shown).map((tag) => (
        <span key={tag.id} data-tag className="inline-flex shrink-0">
          <TagBadge tag={tag} />
        </span>
      ))}
      {hidden.length ? (
        <Tooltip>
          <TooltipTrigger
            render={
              <Badge
                variant="outline"
                tabIndex={0}
                className="bg-card hover:bg-card data-popup-open:bg-card focus-visible:ring-1"
              />
            }
            aria-label={`${hidden.length} more tags: ${hidden.map((tag) => tag.name).join(', ')}`}
          >
            +{hidden.length}
          </TooltipTrigger>
          <TooltipContent
            appearance="popover"
            sideOffset={6}
            className="flex max-w-xs flex-wrap gap-1 px-2 py-1.5"
          >
            {hidden.map((tag) => (
              <TagBadge key={tag.id} tag={tag} soft />
            ))}
          </TooltipContent>
        </Tooltip>
      ) : null}
      <Badge ref={more} variant="outline" aria-hidden className="pointer-events-none invisible absolute">
        +{tags.length}
      </Badge>
    </div>
  )
}
