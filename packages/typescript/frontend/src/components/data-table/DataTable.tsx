import {
  type CellContext,
  type ColumnDef,
  getCoreRowModel,
  type RowSelectionState,
  useReactTable,
  type VisibilityState,
} from '@tanstack/react-table'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Columns3,
  EllipsisVertical,
  EyeOff,
  ListFilter,
  Trash2,
} from 'lucide-react'
import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

import { ColumnsPopover } from './ColumnsPopover'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export interface PaginationModel {
  page: number
  pageSize: number
}
export type SortModel = { field: string; sort: 'asc' | 'desc' }[]

/** A column, in the shape of the Material grid's column definition so a page changes little. */
export interface DataTableColumn<Row> {
  /** The row's property, and the name the server sorts and the column menu lists it by. */
  field: string
  headerName: string
  /** Share of the free width (like the grid's `flex`); with `width`, a fixed width. */
  flex?: number
  width?: number
  minWidth?: number
  /** Default true: a click on the header asks the server to sort by it. */
  sortable?: boolean
  /** The cell's content, instead of the value. */
  renderCell?: (params: { row: Row; value: unknown }) => ReactNode
  /** The value shown (and given to `renderCell`); default `row[field]`. */
  valueGetter?: (value: never, row: Row) => unknown
  valueFormatter?: (value: never) => string
  /** Default true: the column menu can hide it. */
  hideable?: boolean
  /** Default true: the header's right edge can be dragged to resize it. */
  resizable?: boolean
  /** A column the viewer added (a metadata key): the menu offers Delete column, which takes it away, where
   * Hide column only hides it. The page removes it from its own list. */
  onDelete?: () => void
  /** The filter field this column is filtered by (the page's filter panel knows it); none: no Filter item. */
  filterField?: string
}

export interface DataTableProps<Row> {
  rows: Row[]
  columns: DataTableColumn<Row>[]
  /** All rows on the server, for the pager; default: the rows given. */
  rowCount?: number
  loading?: boolean
  /** With `onPaginationModelChange`: the page is the server's, and `rows` is that page. Without them the
   * table pages the rows itself. */
  paginationModel?: PaginationModel
  onPaginationModelChange?: (model: PaginationModel) => void
  pageSizeOptions?: number[]
  /** With `onSortModelChange`: the server sorts. Without them the table sorts the rows it has (the page,
   * with server paging) by the column's value. */
  sortModel?: SortModel
  onSortModelChange?: (model: SortModel) => void
  /** No pager, and no Columns button (the header menu still has Manage columns). */
  hideFooter?: boolean
  /** No sorting at all: headers are plain labels. */
  disableSorting?: boolean
  /** No menu button on the headers. */
  disableColumnMenu?: boolean
  /** Rows are as tall as their cells need, and text wraps (default: one 36px line, long text ends in an ellipsis). */
  autoRowHeight?: boolean
  /** A checkbox column. Ids stay selected across pages; the header box takes the page's rows. */
  checkboxSelection?: boolean
  selectedIds?: ReadonlySet<string>
  onSelectedIdsChange?: (ids: Set<string>) => void
  /** Columns that start hidden (the Columns dialog shows them). */
  hiddenColumns?: string[]
  /** The filter fields that have an active filter: their columns show a filter icon. */
  activeFilterFields?: ReadonlySet<string>
  /** "Filter..." on a column (or its filter icon) asks the page to open its filter panel for this field. */
  onFilterColumn?: (filterField: string) => void
  getRowId?: (row: Row) => string
  'aria-label'?: string
}

const CHECKBOX_WIDTH = 48
// The narrowest a column can be dragged to (its `minWidth` when it has a larger one).
const MIN_RESIZED_WIDTH = 50
const RESIZE_STEP = 10

/** Sorting by a column's value: numbers and dates by size, text by name (digits as numbers). Empty values
 * come last whichever way it sorts, so `direction` does not turn them. */
function compareValues(a: unknown, b: unknown, direction: 1 | -1): number {
  const empty = (value: unknown) => value === null || value === undefined || value === ''
  if (empty(a) || empty(b)) return empty(a) === empty(b) ? 0 : empty(a) ? 1 : -1
  const key = (value: unknown) => (value instanceof Date ? value.getTime() : value)
  const [x, y] = [key(a), key(b)]
  if (typeof x === 'number' && typeof y === 'number') return (x - y) * direction
  return String(x).localeCompare(String(y), undefined, { numeric: true, sensitivity: 'base' }) * direction
}

function cellText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (value instanceof Date) return value.toLocaleString()
  return String(value)
}

/**
 * A table for server-driven lists (the pages do the paging, sorting and filtering and pass the
 * rows): sticky header, striped rows, sort by header, a pager, optional row checkboxes and a column
 * menu. TanStack Table keeps the column and selection state; shadcn's table parts draw it. Columns
 * take the free width by `flex` like the Material grid's (a CSS grid with `minmax(min, Nfr)`), and
 * the table scrolls sideways only when their minimum widths do not fit.
 */
export function DataTable<Row>({
  rows,
  columns,
  rowCount,
  loading = false,
  paginationModel,
  onPaginationModelChange,
  pageSizeOptions = [10, 25, 50, 100],
  sortModel,
  onSortModelChange,
  hideFooter = false,
  disableSorting = false,
  disableColumnMenu = false,
  autoRowHeight = false,
  checkboxSelection = false,
  selectedIds,
  onSelectedIdsChange,
  hiddenColumns = [],
  activeFilterFields,
  onFilterColumn,
  getRowId = (row) => (row as { id: string }).id,
  'aria-label': ariaLabel,
}: DataTableProps<Row>) {
  const [visibility, setVisibility] = useState<VisibilityState>(() =>
    Object.fromEntries(hiddenColumns.map((field) => [field, false])),
  )
  // Manage columns opens under the header row, flush with the table's right edge, as the Material grid's does.
  const [columnsOpen, setColumnsOpen] = useState(false)
  // Widths the user dragged columns to, in px by column id; they take the place of `flex` and `width`.
  const [resized, setResized] = useState<Record<string, number>>({})
  const headerRow = useRef<HTMLTableRowElement>(null)
  // A column the page takes away (a metadata key removed from the picker) must not come back hidden or
  // resized when it is added again: when a column that was there has gone, forget what was set for it. A
  // column that was never there is left alone (one a page hides by default may arrive late), and a default-
  // hidden column that goes and returns is hidden again.
  const columnIds = columns.map((column) => column.field).join('\n')
  const hiddenByDefault = hiddenColumns.join('\n')
  const knownColumns = useRef<Set<string> | null>(null)
  useEffect(() => {
    const present = new Set(columnIds.split('\n'))
    const gone = [...(knownColumns.current ?? present)].filter((id) => !present.has(id))
    knownColumns.current = present
    if (!gone.length) return
    const hidden = new Set(hiddenByDefault.split('\n'))
    setVisibility((current) => {
      const next = { ...current }
      for (const id of gone) {
        if (hidden.has(id)) next[id] = false
        else delete next[id]
      }
      return next
    })
    setResized((current) => Object.fromEntries(Object.entries(current).filter(([id]) => !gone.includes(id))))
  }, [columnIds, hiddenByDefault])
  const pagerLabel = useId() // two tables can be on a page: the ids must differ

  const definitions: ColumnDef<Row>[] = columns.map((column) => ({
    id: column.field,
    header: column.headerName,
    accessorFn: (row) => {
      const value = (row as Record<string, unknown>)[column.field]
      return column.valueGetter ? column.valueGetter(value as never, row) : value
    },
    cell: ({ getValue, row }) => {
      const value = getValue()
      if (column.renderCell) return column.renderCell({ row: row.original, value })
      return column.valueFormatter ? column.valueFormatter(value as never) : cellText(value)
    },
    meta: column,
  }))

  // Paging and sorting are the page's (server) when it passes both the model and its handler, else ours.
  const serverPaging = paginationModel !== undefined && onPaginationModelChange !== undefined
  const serverSort = sortModel !== undefined && onSortModelChange !== undefined
  const [localPaging, setLocalPaging] = useState<PaginationModel>({ page: 0, pageSize: 25 })
  const [localSort, setLocalSort] = useState<SortModel>([])
  const total = rowCount ?? rows.length
  // The table's own page can run past the end when the rows shrink (a search on page 2): it shows the
  // last page that has rows.
  const lastLocalPage = Math.max(0, Math.ceil(total / localPaging.pageSize) - 1)
  const pagination = serverPaging ? paginationModel : { ...localPaging, page: Math.min(localPaging.page, lastLocalPage) }
  // Fewer or more rows (a search) is a new list: back to the first page, so clearing the search does not
  // jump back to the page it was on. The line above keeps the page in range until this runs.
  useEffect(() => {
    if (!serverPaging) setLocalPaging((current) => (current.page === 0 ? current : { ...current, page: 0 }))
  }, [total, serverPaging])
  const setPagination = serverPaging ? onPaginationModelChange : setLocalPaging
  const sort = serverSort ? sortModel : localSort
  const setSort = serverSort ? onSortModelChange : setLocalSort
  const valueOf = (field: string, row: Row) =>
    (definitions.find((definition) => definition.id === field) as { accessorFn: (row: Row, index: number) => unknown }).accessorFn(row, 0)
  const ordered =
    !serverSort && sort.length
      ? [...rows].sort((a, b) =>
          compareValues(valueOf(sort[0].field, a), valueOf(sort[0].field, b), sort[0].sort === 'desc' ? -1 : 1),
        )
      : rows
  const shown = serverPaging
    ? ordered
    : ordered.slice(pagination.page * pagination.pageSize, (pagination.page + 1) * pagination.pageSize)

  const rowSelection: RowSelectionState = Object.fromEntries([...(selectedIds ?? [])].map((id) => [id, true]))
  const table = useReactTable({
    data: shown,
    columns: definitions,
    getCoreRowModel: getCoreRowModel(),
    getRowId,
    state: { columnVisibility: visibility, rowSelection },
    onColumnVisibilityChange: setVisibility,
    onRowSelectionChange: (updater) => {
      const next = typeof updater === 'function' ? updater(rowSelection) : updater
      onSelectedIdsChange?.(new Set(Object.keys(next).filter((id) => next[id])))
    },
    manualPagination: true,
    manualSorting: true,
    autoResetAll: false,
    enableRowSelection: checkboxSelection,
  })

  const leaf = table.getVisibleLeafColumns()
  const hideableColumns = table
    .getAllLeafColumns()
    .filter((column) => (column.columnDef.meta as DataTableColumn<Row>).hideable !== false)
  const meta = (id: string) => leaf.find((column) => column.id === id)?.columnDef.meta as DataTableColumn<Row>
  const template = [
    ...(checkboxSelection ? [`${CHECKBOX_WIDTH}px`] : []),
    ...leaf.map((column) => {
      const m = meta(column.id)
      if (resized[column.id] !== undefined) return `${resized[column.id]}px`
      return m.flex !== undefined
        ? `minmax(${m.minWidth ?? 0}px, ${m.flex}fr)`
        : `${m.width ?? m.minWidth ?? 100}px`
    }),
  ].join(' ')
  // The least width the columns need: below it the table scrolls instead of squeezing them.
  const minTableWidth =
    (checkboxSelection ? CHECKBOX_WIDTH : 0) +
    leaf.reduce((sum, column) => {
      const m = meta(column.id)
      if (resized[column.id] !== undefined) return sum + resized[column.id]
      return sum + (m.flex !== undefined ? (m.minWidth ?? 0) : (m.width ?? m.minWidth ?? 100))
    }, 0)

  const resizeTo = (id: string, width: number) =>
    setResized((current) => ({ ...current, [id]: Math.max(meta(id).minWidth ?? MIN_RESIZED_WIDTH, Math.round(width)) }))
  const resetWidth = (id: string) =>
    setResized((current) => {
      const { [id]: _dropped, ...rest } = current
      return rest
    })
  // Dragging the handle: the column takes the pointer's distance from where it started.
  const startResize = (event: React.PointerEvent<HTMLElement>, id: string) => {
    event.preventDefault()
    const handle = event.currentTarget
    const startX = event.clientX
    const startWidth = (handle.parentElement as HTMLElement).getBoundingClientRect().width
    handle.setPointerCapture?.(event.pointerId)
    handle.dataset.resizing = 'true'
    const move = (moved: PointerEvent) => resizeTo(id, startWidth + moved.clientX - startX)
    const stop = () => {
      delete handle.dataset.resizing
      handle.removeEventListener('pointermove', move)
      handle.removeEventListener('pointerup', stop)
      handle.removeEventListener('pointercancel', stop)
    }
    handle.addEventListener('pointermove', move)
    handle.addEventListener('pointerup', stop)
    handle.addEventListener('pointercancel', stop)
  }

  const { page, pageSize } = pagination
  const first = total === 0 ? 0 : page * pageSize + 1
  const last = Math.min(total, (page + 1) * pageSize)
  const lastPage = Math.max(0, Math.ceil(total / pageSize) - 1)

  const toggleSort = (field: string) => {
    const current = sort.find((item) => item.field === field)?.sort
    // asc, then desc, then none, as the Material grid did.
    setSort(current === undefined ? [{ field, sort: 'asc' }] : current === 'asc' ? [{ field, sort: 'desc' }] : [])
  }

  const pageRows = table.getRowModel().rows
  const allOnPage = pageRows.length > 0 && pageRows.every((row) => row.getIsSelected())
  const someOnPage = pageRows.some((row) => row.getIsSelected())

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-border/60 bg-card">
      <div className="min-h-0 flex-1 overflow-auto" aria-busy={loading}>
        <table role="table" aria-label={ariaLabel} className="block text-sm" style={{ minWidth: minTableWidth }}>
          <TableHeader role="rowgroup" className="sticky top-0 z-10 block bg-muted [&_tr]:border-b-0">
            <TableRow ref={headerRow} role="row" className="grid items-center border-b-0 hover:bg-muted" style={{ gridTemplateColumns: template }}>
              {checkboxSelection ? (
                <TableHead role="columnheader" className="flex h-10 items-center">
                  <Checkbox
                    aria-label="Select all rows"
                    checked={allOnPage}
                    indeterminate={someOnPage && !allOnPage}
                    onCheckedChange={(checked) => table.toggleAllPageRowsSelected(checked === true)}
                  />
                </TableHead>
              ) : null}
              {leaf.map((column) => {
                const m = meta(column.id)
                const sorted = sort.find((item) => item.field === column.id)?.sort
                const sortable = !disableSorting && m.sortable !== false
                const filterable = m.filterField !== undefined && onFilterColumn !== undefined
                const filtered = m.filterField !== undefined && activeFilterFields?.has(m.filterField)
                const hideable = m.hideable !== false
                return (
                  <TableHead
                    key={column.id}
                    role="columnheader"
                    aria-label={m.headerName}
                    aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : undefined}
                    className="group/head relative flex h-10 items-center gap-1 overflow-hidden font-normal"
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column.id)}
                        className="inline-flex min-w-0 items-center gap-1 rounded-sm outline-none focus-visible:ring-3 focus-visible:ring-ring"
                      >
                        <span className="truncate">{m.headerName}</span>
                        {sorted === 'desc' ? (
                          <ArrowDown className="size-3.5 shrink-0" aria-hidden />
                        ) : (
                          // Unsorted: a faint arrow on hover says the column can be sorted.
                          <ArrowUp
                            className={`size-3.5 shrink-0 ${sorted ? '' : 'opacity-0 group-hover/head:opacity-40'}`}
                            aria-hidden
                          />
                        )}
                      </button>
                    ) : (
                      <span className="truncate">{m.headerName}</span>
                    )}
                    {filtered ? (
                      <button
                        type="button"
                        aria-label={`Edit the filter on ${m.headerName}`}
                        onClick={() => onFilterColumn?.(m.filterField as string)}
                        className="shrink-0 rounded-sm text-primary outline-none focus-visible:ring-3 focus-visible:ring-ring"
                      >
                        <ListFilter className="size-3.5" aria-hidden />
                      </button>
                    ) : null}
                    {!disableColumnMenu && (sortable || filterable || hideable || m.onDelete) ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Column menu for ${m.headerName}`}
                            className="absolute top-1/2 right-2 -translate-y-1/2 bg-muted opacity-0 group-hover/head:opacity-100 pointer-coarse:opacity-100 focus-visible:opacity-100 data-popup-open:opacity-100"
                          />
                        }
                      >
                        <EllipsisVertical />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" sideOffset={0} className="min-w-36 whitespace-nowrap">
                        {sortable ? (
                          <>
                            <DropdownMenuItem onClick={() => setSort([{ field: column.id, sort: 'asc' }])}>
                              <ArrowUp />
                              Sort by ASC
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setSort([{ field: column.id, sort: 'desc' }])}>
                              <ArrowDown />
                              Sort by DESC
                            </DropdownMenuItem>
                            {sorted ? (
                              <DropdownMenuItem onClick={() => setSort([])}>
                                <ArrowUpDown />
                                Unsort
                              </DropdownMenuItem>
                            ) : null}
                          </>
                        ) : null}
                        {sortable && filterable ? <DropdownMenuSeparator /> : null}
                        {filterable ? (
                          <DropdownMenuItem onClick={() => onFilterColumn?.(m.filterField as string)}>
                            <ListFilter />
                            Filter
                          </DropdownMenuItem>
                        ) : null}
                        {(sortable || filterable) && (hideable || m.onDelete) ? <DropdownMenuSeparator /> : null}
                        {hideable ? (
                          <DropdownMenuItem onClick={() => column.toggleVisibility(false)}>
                            <EyeOff />
                            Hide column
                          </DropdownMenuItem>
                        ) : null}
                        {m.onDelete ? (
                          <DropdownMenuItem
                            onClick={() => {
                              // Forget what was set for it, so a column added again starts as new.
                              column.toggleVisibility(true)
                              resetWidth(column.id)
                              m.onDelete?.()
                            }}
                          >
                            <Trash2 />
                            Delete column
                          </DropdownMenuItem>
                        ) : null}
                        <DropdownMenuItem onClick={() => setColumnsOpen(true)}>
                          <Columns3 />
                          Manage columns
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                    ) : null}
                    {m.resizable !== false ? (
                      <div
                        role="separator"
                        aria-orientation="vertical"
                        aria-label={`Resize ${m.headerName}`}
                        tabIndex={0}
                        title="Drag to resize, double-click to reset"
                        onPointerDown={(event) => startResize(event, column.id)}
                        onDoubleClick={() => resetWidth(column.id)}
                        onKeyDown={(event) => {
                          if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
                          event.preventDefault()
                          const width = (event.currentTarget.parentElement as HTMLElement).getBoundingClientRect().width
                          resizeTo(column.id, width + (event.key === 'ArrowRight' ? RESIZE_STEP : -RESIZE_STEP))
                        }}
                        // The separator shows only while the pointer is over the column's header (as the Material grid's does),
                        // stronger on the handle itself, and stays while it is dragged or has the keyboard focus.
                        className="absolute inset-y-0 right-0 w-2 cursor-col-resize touch-none outline-none after:absolute after:inset-y-2 after:right-0 after:w-px after:bg-border after:opacity-0 group-hover/head:after:opacity-100 hover:after:w-0.5 hover:after:bg-primary focus-visible:after:w-0.5 focus-visible:after:bg-primary focus-visible:after:opacity-100 data-[resizing=true]:after:w-0.5 data-[resizing=true]:after:bg-primary data-[resizing=true]:after:opacity-100"
                      />
                    ) : null}
                  </TableHead>
                )
              })}
            </TableRow>
          </TableHeader>
          <TableBody role="rowgroup" className="block">
            {pageRows.map((row) => (
              <TableRow
                key={row.id}
                role="row"
                data-state={row.getIsSelected() ? 'selected' : undefined}
                className="grid items-center border-b-0 even:bg-muted/60 data-[state=selected]:bg-primary-soft"
                style={{ gridTemplateColumns: template }}
              >
                {checkboxSelection ? (
                  <TableCell role="cell" className="flex min-w-0 items-center">
                    <Checkbox
                      aria-label="Select row"
                      checked={row.getIsSelected()}
                      onCheckedChange={(checked) => row.toggleSelected(checked === true)}
                    />
                  </TableCell>
                ) : null}
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} role="cell" data-field={cell.column.id} className={
                      autoRowHeight
                        ? 'flex min-h-9 min-w-0 items-center py-1 leading-snug whitespace-normal [overflow-wrap:anywhere]'
                        : 'flex min-h-9 min-w-0 items-center overflow-hidden py-0 [&>a]:inline-block [&>a]:max-w-full [&>a]:truncate'
                    }>
                    {/* Called, not given to flexRender: that would make each render's function a new component and remount the cell. */}
                    {(cell.column.columnDef.cell as (context: CellContext<Row, unknown>) => ReactNode)(cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
            {pageRows.length === 0 && !loading ? (
              <tr role="row" className="block">
                <td role="cell" className="block p-6 text-center text-muted-foreground">
                  No rows
                </td>
              </tr>
            ) : null}
          </TableBody>
        </table>
      </div>
      {loading ? <div className="h-0.5 w-full animate-pulse bg-primary" role="progressbar" aria-label="Loading" /> : null}
      {hideFooter ? null : (
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-3 py-1.5 text-sm">
        <Button variant="ghost" onClick={() => setColumnsOpen(true)}>
          <Columns3 data-icon="inline-start" />
          Columns
        </Button>
        <div className="flex items-center gap-3 text-muted-foreground">
          <span id={pagerLabel}>Rows per page</span>
          <Select
            value={String(pageSize)}
            items={pageSizeOptions.map((size) => ({ value: String(size), label: String(size) }))}
            onValueChange={(next) => next && setPagination({ page: 0, pageSize: Number(next) })}
          >
            <SelectTrigger size="sm" aria-labelledby={pagerLabel}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {pageSizeOptions.map((size) => (
                <SelectItem key={size} value={String(size)}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span aria-live="polite">{total === 0 ? '0 of 0' : `${first}–${last} of ${total}`}</span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Previous page"
            disabled={page <= 0}
            onClick={() => setPagination({ page: page - 1, pageSize })}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Next page"
            disabled={page >= lastPage}
            onClick={() => setPagination({ page: page + 1, pageSize })}
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
      )}
      {columnsOpen ? (
        <ColumnsPopover
          anchor={headerRow.current}
          columns={hideableColumns.map((column) => ({
            id: column.id,
            label: (column.columnDef.meta as DataTableColumn<Row>).headerName,
            visible: column.getIsVisible(),
          }))}
          isDefault={hideableColumns.every((column) => column.getIsVisible() === !hiddenColumns.includes(column.id))}
          onToggle={(id, visible) => table.getColumn(id)?.toggleVisibility(visible)}
          onSetAll={(visible) => hideableColumns.forEach((column) => column.toggleVisibility(visible))}
          onReset={() => setVisibility(Object.fromEntries(hiddenColumns.map((field) => [field, false])))}
          onClose={() => setColumnsOpen(false)}
        />
      ) : null}
    </div>
  )
}
