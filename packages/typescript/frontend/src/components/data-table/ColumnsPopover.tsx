import { useState } from 'react'

import { SearchInput } from '@/components/SearchInput'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent } from '@/components/ui/popover'

export interface ColumnChoice {
  id: string
  label: string
  visible: boolean
}

/**
 * Manage columns, as the Material grid's panel: a popover under the header row, flush with the table's right edge, with
 * a search box, a checkbox per column, a Show/Hide all box and Reset (the columns the table started
 * with). No backdrop: a click outside or Esc closes it.
 */
export function ColumnsPopover({
  anchor,
  columns,
  isDefault,
  onToggle,
  onSetAll,
  onReset,
  onClose,
}: {
  anchor: HTMLElement | null
  columns: ColumnChoice[]
  /** Whether the columns shown are the ones the table started with. */
  isDefault: boolean
  onToggle: (id: string, visible: boolean) => void
  onSetAll: (visible: boolean) => void
  onReset: () => void
  onClose: () => void
}) {
  const [search, setSearch] = useState('')
  const shown = columns.filter((column) => column.label.toLowerCase().includes(search.trim().toLowerCase()))
  const all = columns.length > 0 && columns.every((column) => column.visible)
  const some = columns.some((column) => column.visible)

  return (
    <Popover open onOpenChange={(open) => !open && onClose()}>
      <PopoverContent anchor={anchor} align="end" sideOffset={0} className="w-75 gap-0 p-0">
        <div className="p-2">
          <SearchInput value={search} onChange={setSearch} placeholder="Search columns" className="max-w-none" />
        </div>
        <div className="flex max-h-64 flex-col overflow-y-auto border-t border-border py-1">
          {shown.map((column) => (
            <Label key={column.id} className="flex cursor-pointer items-center gap-2 px-3 py-1.5 font-normal">
              <Checkbox checked={column.visible} onCheckedChange={(checked) => onToggle(column.id, checked === true)} />
              {column.label}
            </Label>
          ))}
          {shown.length === 0 ? <p className="px-3 py-1.5 text-muted-foreground">No columns</p> : null}
        </div>
        <div className="flex items-center justify-between border-t border-border px-3 py-1.5">
          <Label className="flex cursor-pointer items-center gap-2 font-normal">
            <Checkbox
              checked={all}
              indeterminate={some && !all}
              onCheckedChange={(checked) => onSetAll(checked === true)}
            />
            Show/Hide all
          </Label>
          <Button variant="ghost" size="sm" disabled={isDefault} onClick={onReset}>
            Reset
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
