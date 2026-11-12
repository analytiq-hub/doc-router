import { ListFilter, Plus, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

/** One filter: a field, an operator and a value (the filter-model item the list routes take). */
export interface FilterItem {
  id?: string | number
  field: string
  operator: string
  /** Text; for a `case` field an object `{ id, name }`. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value?: any
}

/** The filter model the list routes take as `filters` (JSON): every item must hold. */
export interface FilterModel {
  items: FilterItem[]
  logicOperator?: 'and' | 'or'
}

/** A field the filter can test. `path` is text that also takes a glob; `select` has fixed options; `tag`
 * is one of the options (a document needs every tag asked for); `case` is a case found by name (its
 * value is `{ id, name }`). */
export interface FilterField {
  field: string
  label: string
  kind: 'text' | 'path' | 'select' | 'date' | 'tag' | 'case'
  /** At most one filter on this field (the server takes one case, say): a second row cannot pick it. */
  single?: boolean
  options?: { value: string; label: string }[]
}

const TEXT_OPERATORS = [
  { value: 'contains', label: 'contains' },
  { value: 'equals', label: 'equals' },
  { value: 'doesNotEqual', label: 'does not equal' },
  { value: 'startsWith', label: 'starts with' },
  { value: 'endsWith', label: 'ends with' },
  { value: 'isAnyOf', label: 'is any of (comma-separated)' },
  { value: 'isEmpty', label: 'is empty' },
  { value: 'isNotEmpty', label: 'is not empty' },
]
const OPERATORS: Record<FilterField['kind'], { value: string; label: string }[]> = {
  text: TEXT_OPERATORS,
  path: [...TEXT_OPERATORS, { value: 'glob', label: 'matches glob (? * **)' }],
  select: [
    { value: 'is', label: 'is' },
    { value: 'not', label: 'is not' },
  ],
  date: [
    { value: 'is', label: 'is' },
    { value: 'after', label: 'is after' },
    { value: 'before', label: 'is before' },
  ],
  tag: [{ value: 'is', label: 'is' }],
  case: [{ value: 'is', label: 'is' }],
}
const NO_VALUE = new Set(['isEmpty', 'isNotEmpty'])

const operatorLabel = (kind: FilterField['kind'], operator: string) =>
  OPERATORS[kind].find((o) => o.value === operator)?.label ?? operator

/** One line for a filter: "Path matches glob claims/**". */
export function describeFilter(item: FilterItem, fields: FilterField[]): string {
  const field = fields.find((f) => f.field === item.field)
  const kind = field?.kind ?? 'text'
  const raw = item.value
  const value = NO_VALUE.has(item.operator)
    ? ''
    : kind === 'case'
      ? String((raw as { name?: string } | undefined)?.name ?? '')
      : String(field?.options?.find((o) => o.value === raw)?.label ?? raw ?? '')
  return [field?.label ?? item.field, operatorLabel(kind, item.operator), value].filter(Boolean).join(' ')
}

/** A filter has a value, or needs none. */
export const isActiveFilter = (item: FilterItem) =>
  NO_VALUE.has(item.operator) || (item.value !== undefined && item.value !== null && item.value !== '')

/** The columns with the `filterField` that filters each: the column's own name when the filter has
 * that field, else its alias (the Case column's `case_name` is filtered as `case.name`). */
export function withFilterFields<C extends { field: string }>(
  columns: C[],
  fields: FilterField[],
  aliases: Record<string, string> = {},
): (C & { filterField?: string })[] {
  return columns.map((column) => {
    const filterField = fields.some((f) => f.field === column.field) ? column.field : aliases[column.field]
    return filterField ? { ...column, filterField } : column
  })
}

/** The filter items a URL's `filters` parameter carries (the filter model as JSON); none when it is absent
 * or not JSON. */
export function filtersFromParam(raw: string | null): FilterItem[] {
  try {
    const items = (JSON.parse(raw ?? 'null') as { items?: unknown } | null)?.items
    if (!Array.isArray(items)) return []
    return items.flatMap((item, index) =>
      item && typeof item.field === 'string' && typeof item.operator === 'string' ? [{ ...item, id: item.id ?? index }] : [],
    )
  } catch {
    return []
  }
}

/** The fields that have an active filter. */
export const activeFields = (items: FilterItem[]) => new Set(items.filter(isActiveFilter).map((item) => item.field))

// Row ids come from a counter that starts again on every page load, while filters loaded from a URL keep
// the ids they were saved with: a new id must skip the ones in use, or two rows would share one.
let nextId = 1
const newItem = (field: FilterField, rows: FilterItem[]): FilterItem => {
  const taken = new Set(rows.map((row) => String(row.id)))
  let id = `f${nextId++}`
  while (taken.has(id)) id = `f${nextId++}`
  return {
    id,
    field: field.field,
    operator: OPERATORS[field.kind][0].value,
    value: undefined,
  }
}

/** The field a new row starts with: the first one not already used where only one filter is allowed. */
const freeField = (fields: FilterField[], rows: FilterItem[]): FilterField | undefined =>
  fields.find((f) => !(f.single && rows.some((row) => row.field === f.field))) ?? fields[0]


/**
 * Any number of filters, all of which must hold: a "Filters" button with a panel of rows (field,
 * operator, value), and the active ones as removable chips. The grid's own filter allows one item, so
 * the filter lives here and goes to the server in the grid's filter-model format.
 */
export function FilterBuilder({
  fields,
  value,
  onChange,
  request,
}: {
  fields: FilterField[]
  value: FilterItem[]
  onChange: (items: FilterItem[]) => void
  /** Opens the panel for a column ("Filter..." in its menu): with a row for its field, the ones it has
   * first. A new object each time, so asking twice opens it twice. */
  request?: { field: string } | null
}) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<FilterItem[]>([])
  const active = value.filter(isActiveFilter)
  // The fields a row can pick: not one that only allows a single filter and is used in another row.
  const available = (row: FilterItem) =>
    fields.filter((f) => !(f.single && draft.some((other) => other.id !== row.id && other.field === f.field)))
  const kindOf = (item: FilterItem) => fields.find((f) => f.field === item.field)?.kind ?? 'text'
  const update = (id: FilterItem['id'], patch: Partial<FilterItem>) =>
    setDraft((rows) => rows.map((row) => (row.id === id ? { ...row, ...patch } : row)))

  // The panel starts from what is applied; for a column, with a row for that field when it has none.
  const openPanel = (field?: string) => {
    const rows = value.map((item) => ({ ...item }))
    const target = fields.find((f) => f.field === field) ?? (rows.length ? undefined : freeField(fields, rows))
    if (target && !rows.some((row) => row.field === target.field)) rows.push(newItem(target, rows))
    setDraft(rows)
    setOpen(true)
  }
  useEffect(() => {
    if (request) openPanel(request.field)
    // Only a new request opens it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request])

  return (
    <>
      <Popover
        open={open}
        onOpenChange={(next) => (next ? openPanel() : setOpen(false))}
      >
        <PopoverTrigger render={<Button variant="outline" />}>
          <ListFilter data-icon="inline-start" />
          {active.length ? `Filters (${active.length})` : 'Filters'}
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[38rem] max-w-[calc(100vw-2rem)]">
          <div className="flex flex-col gap-3">
            {draft.map((item) => {
              const field = fields.find((f) => f.field === item.field)
              const kind = kindOf(item)
              return (
                <div key={item.id} className="flex items-center gap-2">
                  <Select
                    value={item.field}
                    items={available(item).map((f) => ({ value: f.field, label: f.label }))}
                    onValueChange={(next) => {
                      const target = fields.find((f) => f.field === next)
                      if (target) update(item.id, { field: target.field, operator: OPERATORS[target.kind][0].value, value: undefined })
                    }}
                  >
                    <SelectTrigger aria-label="Filter field" className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="max-h-72">
                      {available(item).map((f) => (
                        <SelectItem key={f.field} value={f.field}>
                          {f.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select
                    value={item.operator}
                    items={OPERATORS[kind]}
                    onValueChange={(next) => next && update(item.id, { operator: next })}
                  >
                    <SelectTrigger aria-label="Filter operator" className="w-44">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {OPERATORS[kind].map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {NO_VALUE.has(item.operator) ? (
                    <span className="flex-1" />
                  ) : kind === 'case' ? (
                    <span className="flex-1 text-sm text-muted-foreground">Case filters are not available here.</span>
                  ) : kind === 'select' || kind === 'tag' ? (
                    <Select
                      value={(item.value as string | undefined) ?? null}
                      items={field?.options ?? []}
                      onValueChange={(next) => update(item.id, { value: next ?? undefined })}
                    >
                      <SelectTrigger aria-label="Filter value" className="flex-1">
                        <SelectValue placeholder="Value" />
                      </SelectTrigger>
                      <SelectContent>
                        {(field?.options ?? []).map((o) => (
                          <SelectItem key={o.value} value={o.value}>
                            {o.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      aria-label="Filter value"
                      className="flex-1"
                      type={kind === 'date' ? 'date' : 'text'}
                      placeholder="Value"
                      value={(item.value as string | undefined) ?? ''}
                      onChange={(event) => update(item.id, { value: event.target.value })}
                    />
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Remove filter"
                    onClick={() => setDraft((rows) => rows.filter((row) => row.id !== item.id))}
                  >
                    <X />
                  </Button>
                </div>
              )
            })}
            <div className="flex items-center justify-between gap-2">
              <Button
                variant="ghost"
                disabled={fields.length === 0}
                onClick={() => setDraft((rows) => [...rows, newItem(freeField(fields, rows) as FilterField, rows)])}
              >
                <Plus data-icon="inline-start" />
                Add filter
              </Button>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    onChange([])
                    setOpen(false)
                  }}
                >
                  Clear all
                </Button>
                <Button
                  onClick={() => {
                    onChange(draft.filter(isActiveFilter))
                    setOpen(false)
                  }}
                >
                  Apply
                </Button>
              </div>
            </div>
          </div>
        </PopoverContent>
      </Popover>
      {active.map((item) => (
        <span
          key={item.id}
          className="inline-flex h-9 max-w-80 items-center gap-1 rounded-lg bg-primary-soft pl-3 text-sm text-primary"
        >
          <span className="truncate">{describeFilter(item, fields)}</span>
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Remove filter ${describeFilter(item, fields)}`}
            onClick={() => onChange(value.filter((other) => other !== item))}
          >
            <X />
          </Button>
        </span>
      ))}
    </>
  )
}
