import { Tags } from 'lucide-react'
import { useState } from 'react'
import type { Tag } from '@docrouter/sdk'
import { TagBadge } from '@/components/TagBadge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

export function PromptTagFilter({
  tags,
  selectedIds,
  onChange,
}: {
  tags: Tag[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const toggle = (id: string) => {
    onChange(selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id])
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button variant="outline" />}>
        <Tags data-icon="inline-start" />
        {selectedIds.length ? `Tags (${selectedIds.length})` : 'Filter by tags'}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 max-h-80 overflow-y-auto p-2">
        <ul className="flex flex-col gap-1">
          {tags.map((tag) => (
            <li key={tag.id}>
              <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted">
                <Checkbox
                  checked={selectedIds.includes(tag.id)}
                  onCheckedChange={() => toggle(tag.id)}
                  aria-label={tag.name}
                />
                <TagBadge tag={tag} />
              </label>
            </li>
          ))}
        </ul>
        {selectedIds.length > 0 ? (
          <Button variant="ghost" className="mt-2 w-full" onClick={() => onChange([])}>
            Clear tags
          </Button>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}
