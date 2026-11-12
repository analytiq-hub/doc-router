'use client'

import { useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn } from 'cn'

type MetadataKeysInputProps = {
  value: string[]
  onChange: (next: string[]) => void
  disabled?: boolean
  placeholder?: string
  className?: string
}

/** Free-form list of metadata key tokens (comma or Enter to add). */
export function MetadataKeysInput({
  value,
  onChange,
  disabled = false,
  placeholder = '* or document_type, invoice_number',
  className,
}: MetadataKeysInputProps) {
  const [draft, setDraft] = useState('')

  const addKey = (raw: string) => {
    const key = raw.trim().replace(/,+$/, '').trim()
    if (!key) return
    if (!value.includes(key)) onChange([...value, key])
    setDraft('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addKey(draft)
    } else if (e.key === 'Backspace' && !draft && value.length > 0) {
      onChange(value.slice(0, -1))
    }
  }

  const remove = (key: string) => onChange(value.filter((k) => k !== key))

  return (
    <div
      className={cn(
        'flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-2 py-1.5',
        disabled && 'opacity-60',
        className,
      )}
    >
      {value.map((key) => (
        <Badge key={key} variant="secondary" className="gap-0.5 pr-0.5 font-normal">
          {key}
          <button
            type="button"
            className="rounded-sm p-0.5 hover:bg-muted"
            disabled={disabled}
            onClick={() => remove(key)}
            aria-label={`Remove ${key}`}
          >
            <X className="size-3" />
          </button>
        </Badge>
      ))}
      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => addKey(draft)}
        disabled={disabled}
        placeholder={value.length ? 'Add key…' : placeholder}
        className="h-7 min-w-[10rem] flex-1 border-0 bg-transparent px-1 shadow-none focus-visible:ring-0"
      />
    </div>
  )
}
