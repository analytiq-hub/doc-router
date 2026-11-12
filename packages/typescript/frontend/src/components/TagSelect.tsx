'use client'

import type { Tag } from '@docrouter/sdk'

import { TagBadge } from '@/components/TagBadge'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type TagSelectProps = {
  tags: Tag[]
  value: Tag | null
  onChange: (tag: Tag | null) => void
  disabled?: boolean
  label?: string
  placeholder?: string
}

/** Single-tag picker (shadcn Select, no autocomplete). */
export function TagSelect({
  tags,
  value,
  onChange,
  disabled = false,
  label,
  placeholder = 'Select a tag…',
}: TagSelectProps) {
  return (
    <div className="space-y-2">
      {label ? <Label>{label}</Label> : null}
      {value ? (
        <div className="mb-1">
          <TagBadge tag={value} />
        </div>
      ) : null}
      <Select
        value={value?.id ?? ''}
        disabled={disabled}
        items={tags.map((tag) => ({ value: tag.id, label: tag.name }))}
        onValueChange={(next) => onChange(tags.find((tag) => tag.id === next) ?? null)}
      >
        <SelectTrigger className="w-full max-w-md" aria-label={label ?? 'Tag'}>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent className="max-h-64">
          {tags.map((tag) => (
            <SelectItem key={tag.id} value={tag.id}>
              {tag.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
