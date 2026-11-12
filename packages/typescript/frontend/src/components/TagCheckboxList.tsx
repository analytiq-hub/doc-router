'use client'

import type { Tag } from '@docrouter/sdk'

import { TagBadge } from '@/components/TagBadge'
import { Checkbox } from '@/components/ui/checkbox'

type TagCheckboxListProps = {
  tags: Tag[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
  emptyLabel?: string
}

/** Multi-select tags without autocomplete (checkbox list). */
export function TagCheckboxList({
  tags,
  selectedIds,
  onChange,
  disabled = false,
  emptyLabel = 'No tags in this organization.',
}: TagCheckboxListProps) {
  const toggle = (id: string, checked: boolean) => {
    onChange(checked ? [...selectedIds, id] : selectedIds.filter((x) => x !== id))
  }

  if (!tags.length) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>
  }

  return (
    <ul className="max-h-52 space-y-1 overflow-y-auto rounded-md border border-border bg-card p-2">
      {tags.map((tag) => {
        const checked = selectedIds.includes(tag.id)
        return (
          <li key={tag.id}>
            <label className="flex cursor-pointer items-center gap-2 rounded-sm px-1 py-1.5 hover:bg-muted/60">
              <Checkbox
                checked={checked}
                disabled={disabled}
                onCheckedChange={(next) => toggle(tag.id, next === true)}
                aria-label={tag.name}
              />
              <TagBadge tag={tag} />
            </label>
          </li>
        )
      })}
    </ul>
  )
}
