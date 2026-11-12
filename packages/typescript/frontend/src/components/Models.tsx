import React, { useMemo, useState } from 'react'
import { DataTable, type DataTableColumn } from '@/components/data-table'
import { SearchInput } from '@/components/SearchInput'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type ModelRow = {
  id: number
  name: string
  description: string
  status: string
}

const Models: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('')

  const mockData: ModelRow[] = [
    { id: 1, name: 'Model 1', description: 'Description 1', status: 'Active' },
    { id: 2, name: 'Model 2', description: 'Description 2', status: 'Inactive' },
  ]

  const rows = useMemo(() => {
    const q = searchTerm.trim().toLowerCase()
    if (!q) return mockData
    return mockData.filter(
      (row) =>
        row.name.toLowerCase().includes(q) ||
        row.description.toLowerCase().includes(q) ||
        row.status.toLowerCase().includes(q),
    )
  }, [searchTerm])

  const columns: DataTableColumn<ModelRow>[] = useMemo(
    () => [
      { field: 'name', headerName: 'Model name', flex: 1, minWidth: 160 },
      { field: 'description', headerName: 'Description', flex: 2, minWidth: 200 },
      { field: 'status', headerName: 'Status', width: 120 },
    ],
    [],
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Models (under construction)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <SearchInput
          className="max-w-md"
          placeholder="Search models…"
          value={searchTerm}
          onChange={setSearchTerm}
        />
        <DataTable rows={rows} columns={columns} pageSizeOptions={[5, 10, 20]} disableColumnMenu />
      </CardContent>
    </Card>
  )
}

export default Models
