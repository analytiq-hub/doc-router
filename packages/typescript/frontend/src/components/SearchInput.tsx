import { Search } from 'lucide-react'
import { cn } from 'cn'

import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'

export function SearchInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  className?: string
}) {
  return (
    <InputGroup className={cn('w-52 max-w-full shrink-0', className)}>
      <InputGroupAddon>
        <Search />
      </InputGroupAddon>
      <InputGroupInput
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
    </InputGroup>
  )
}
