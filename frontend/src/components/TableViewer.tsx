'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Chip, InputAdornment, TextField, Checkbox } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import SearchIcon from '@mui/icons-material/Search';
import { useRouter } from 'next/navigation';
import { getTableApi, listTagsApi } from '@/utils/api';
import { Table, TableColumn } from '@/types/tables';
import { Tag } from '@/types';
import { FieldMapping } from '@/types/forms';
import { isColorLight } from '@/utils/colors';
import colors from 'tailwindcss/colors';

type Props = {
  organizationId: string;
  tableRevId: string;
};

type Row = {
  id: string;
  key: string;
  name: string;
  width?: number;
  aggregate?: boolean;
  mapping?: FieldMapping;
};

const TableViewer: React.FC<Props> = ({ organizationId, tableRevId }) => {
  const router = useRouter();
  const [table, setTable] = useState<Table | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [tags, setTags] = useState<Tag[]>([]);
  const [searchTerm, setSearchTerm] = useState('');

  const load = useCallback(async () => {
    try {
      setIsLoading(true);
      const [t, tagResp] = await Promise.all([
        getTableApi({ organizationId, tableRevId }),
        listTagsApi({ organizationId })
      ]);
      setTable(t);
      setTags(tagResp.tags);
    } finally {
      setIsLoading(false);
    }
  }, [organizationId, tableRevId]);

  useEffect(() => {
    load();
  }, [load]);

  const columnsDef: GridColDef<Row>[] = useMemo(() => [
    { field: 'key', headerName: 'Key', flex: 1 },
    { field: 'name', headerName: 'Name', flex: 1.5 },
    {
      field: 'width',
      headerName: 'Width',
      width: 100,
      valueFormatter: ({ value }) => (value === undefined || value === null ? '' : String(value))
    },
    {
      field: 'aggregate',
      headerName: 'Aggregate',
      width: 120,
      sortable: false,
      renderCell: ({ value }) => <Checkbox size="small" checked={Boolean(value)} disabled />
    },
    {
      field: 'mapping',
      headerName: 'Mapping',
      flex: 2,
      sortable: false,
      renderCell: (params) => {
        const mapping = params.value as FieldMapping | undefined;

        if (!mapping) return <span className="text-gray-400">—</span>;

        return (
          <div className="flex gap-1 flex-wrap items-center">
            {mapping.sources.map((s, idx) => (
              <Chip
                key={`${s.promptName}-${s.schemaFieldName}-${idx}`}
                label={`${s.promptName}: ${s.schemaFieldName}`}
                size="small"
                sx={{ backgroundColor: colors.gray[100] }}
              />
            ))}
            {mapping.mappingType === 'concatenated' && (
              <span className="text-xs text-gray-500 ml-1">
                sep: {'"'}{mapping.concatenationSeparator || ' '}{'"'}
              </span>
            )}
          </div>
        );
      }
    }
  ], []);

  const rows: Row[] = useMemo(() => {
    const cols = table?.response_format?.columns || [];
    const mapping = table?.response_format?.column_mapping || {};
    const filtered = cols.filter(
      (c: TableColumn) =>
        c.key.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (c.name || '').toLowerCase().includes(searchTerm.toLowerCase())
    );
    return filtered.map((c: TableColumn) => ({
      id: c.key,
      key: c.key,
      name: c.name,
      width: c.width,
      aggregate: Boolean((c as Record<string, unknown>).aggregate),
      mapping: mapping[c.key] as FieldMapping | undefined
    }));
  }, [table, searchTerm]);

  const tableTags = useMemo(
    () => tags.filter(tag => (table?.tag_ids ?? []).includes(tag.id)),
    [tags, table?.tag_ids]
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/orgs/${organizationId}/tables`)}
            className="px-3 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            ← Back to Tables
          </button>
          <h2 className="text-xl font-bold">
            {table?.name || 'Loading…'} {table ? <span className="text-gray-500 text-base">v{table.table_version}</span> : null}
          </h2>
          <div className="flex gap-1 flex-wrap">
            {tableTags.map(tag => (
              <div
                key={tag.id}
                className={`px-2 py-1 rounded text-xs ${isColorLight(tag.color) ? 'text-gray-800' : 'text-white'} flex items-center`}
                style={{ backgroundColor: tag.color }}
              >
                {tag.name}
              </div>
            ))}
          </div>
        </div>
        {table && (
          <button
            onClick={() => router.push(`/orgs/${organizationId}/tables/${table.table_revid}`)}
            className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Edit Table
          </button>
        )}
      </div>

      <div className="max-w-xl">
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search columns..."
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            )
          }}
        />
      </div>

      <div style={{ height: 500, width: '100%' }}>
        <DataGrid
          rows={rows}
          columns={columnsDef}
          getRowId={(row) => row.id}
          loading={isLoading}
          disableRowSelectionOnClick
          sx={{
            '& .MuiDataGrid-row:nth-of-type(odd)': {
              backgroundColor: 'rgba(0, 0, 0, 0.04)',
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.1)',
            },
          }}
        />
      </div>
    </Box>
  );
};

export default TableViewer;