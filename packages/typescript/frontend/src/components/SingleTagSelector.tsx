'use client'

import type { Tag } from '@docrouter/sdk'

import { TagSelect } from '@/components/TagSelect'

interface SingleTagSelectorProps {
  availableTags: Tag[]
  selectedTag: Tag | null
  onChange: (tag: Tag | null) => void
  disabled?: boolean
  placeholder?: string
  label?: string
}

/** @deprecated Use `TagSelect` directly in new code. */
const SingleTagSelector: React.FC<SingleTagSelectorProps> = (props) => (
  <TagSelect
    tags={props.availableTags}
    value={props.selectedTag}
    onChange={props.onChange}
    disabled={props.disabled}
    label={props.label}
    placeholder={props.placeholder}
  />
)

export default SingleTagSelector
