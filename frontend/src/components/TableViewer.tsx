'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Box, InputAdornment, TextField } from '@mui/material';
import { DataGrid, GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import SearchIcon from '@mui/icons-material/Search';
import { useRouter } from 'next/navigation';
import { getTableApi, listTagsApi, listDocumentsApi, getLLMResultApi, runLLMApi } from '@/utils/api';
import { Table } from '@/types/tables';
import { Tag, DocumentMetadata, GetLLMResultResponse, FieldMapping, FieldMappingSource } from '@/types';
import { isColorLight } from '@/utils/colors';

type Props = {
  organizationId: string;
  tableRevId: string;
};

type Row = { id: string; document_name: string } & Record<string, unknown>;

function getValueByPath(data: Record<string, unknown> | undefined, path: string): string {
  if (!data || !path) return '';
  // Convert bracket notation to dot, e.g. items[0].name -> items.0.name
  const parts = path.replace(/\[(\d+)\]/g, '.$1').split('.').filter(Boolean);
  let current: unknown = data;
  for (const part of parts) {
    if (current == null) return '';
    if (Array.isArray(current)) {
      const index = Number(part);
      if (!Number.isInteger(index) || index < 0 || index >= current.length) return '';
      current = current[index];
      continue;
    }
    if (typeof current === 'object') {
      const obj = current as Record<string, unknown>;
      current = obj[part];
      continue;
    }
    return '';
  }
  if (current === undefined || current === null) return '';
  if (typeof current === 'object') return JSON.stringify(current);
  return String(current);
}

const TableViewer: React.FC<Props> = ({ organizationId, tableRevId }) => {
  const router = useRouter();
  const [table, setTable] = useState<Table | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [searchTerm, setSearchTerm] = useState('');
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [totalRows, setTotalRows] = useState(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>(() => {
    if (typeof window !== 'undefined') {
      const isSmall = window.innerWidth < 768;
      return { page: 0, pageSize: isSmall ? 5 : 25 };
    }
    return { page: 0, pageSize: 25 };
  });
  const [docLoading, setDocLoading] = useState(false);

  // Cache of LLM results: docId -> promptRevId -> result
  const [llmCache, setLlmCache] = useState<Record<string, Record<string, GetLLMResultResponse | null>>>({});

  // Load table + tags once
  useEffect(() => {
    (async () => {
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
    })();
  }, [organizationId, tableRevId]);

  // Unique promptRevIds needed by this table
  const promptRevIds = useMemo(() => {
    const mapping: Record<string, FieldMapping> = table?.response_format?.column_mapping ?? ({} as Record<string, FieldMapping>);
    const set = new Set<string>();
    Object.values(mapping).forEach((m: FieldMapping) => {
      (m.sources ?? []).forEach((s: FieldMappingSource) => {
        if (s?.promptRevId) set.add(s.promptRevId);
      });
    });
    return Array.from(set);
  }, [table]);

  // Build grid columns: Document column + one per table column
  const gridColumns: GridColDef<Row>[] = useMemo(() => {
    const cols: GridColDef<Row>[] = [
      {
        field: 'document_name',
        headerName: 'Document',
        flex: 1.5,
        renderCell: (params) => (
          <Link href={`/orgs/${organizationId}/docs/${params.row.id}`} style={{ color: 'blue', textDecoration: 'underline' }}>
            {String(params.value ?? '')}
          </Link>
        )
      }
    ];
    const tableCols = table?.response_format?.columns || [];
    for (const c of tableCols) {
      cols.push({
        field: c.key,
        headerName: c.name,
        width: c.width ?? undefined,
        flex: c.width ? undefined : 1,
        sortable: false,
      });
    }
    return cols;
  }, [organizationId, table?.response_format?.columns]);

  // Paginated documents fetch
  const loadDocuments = useCallback(async () => {
    try {
      setDocLoading(true);
      const resp = await listDocumentsApi({
        organizationId,
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        nameSearch: searchTerm.trim() || undefined
      });
      setDocuments(resp.documents);
      setTotalRows(resp.total_count);
    } finally {
      setDocLoading(false);
    }
  }, [organizationId, paginationModel.page, paginationModel.pageSize, searchTerm]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Load (and if missing, run) required LLM results for current page documents
  useEffect(() => {
    if (!documents.length || !promptRevIds.length) return;

    const loadOrRun = async () => {
      const next = { ...llmCache } as Record<string, Record<string, GetLLMResultResponse | null>>;

      await Promise.all(
        documents.map(async (doc) => {
          next[doc.id] ||= {};
          await Promise.all(
            promptRevIds.map(async (prid) => {
              if (next[doc.id][prid] !== undefined) return;
              // 1) try to read latest
              try {
                const r = await getLLMResultApi({ organizationId, documentId: doc.id, promptRevId: prid, latest: true });
                next[doc.id][prid] = r;
                return;
              } catch {}
              // 2) if missing, run then fetch
              try {
                await runLLMApi({ organizationId, documentId: doc.id, promptRevId: prid, force: true });
                const r2 = await getLLMResultApi({ organizationId, documentId: doc.id, promptRevId: prid, latest: true });
                next[doc.id][prid] = r2;
              } catch {
                next[doc.id][prid] = null;
              }
            })
          );
        })
      );
      setLlmCache(next);
    };

    loadOrRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents, promptRevIds, organizationId]);

  // Compute rows with extracted values
  const rows: Row[] = useMemo(() => {
    const mapping: Record<string, FieldMapping> = table?.response_format?.column_mapping ?? ({} as Record<string, FieldMapping>);
    return documents.map((doc) => {
      const row: Row = { id: doc.id, document_name: doc.document_name };
      Object.entries(mapping).forEach(([colKey, mappingConfig]) => {
        const parts: string[] = [];
        const sep = mappingConfig?.concatenationSeparator ?? ' ';
        const sources = Array.isArray(mappingConfig?.sources) ? mappingConfig.sources : [];
        for (const source of sources) {
          const res = llmCache[doc.id]?.[source.promptRevId] || null;
          const data = res?.updated_llm_result && Object.keys(res.updated_llm_result).length
            ? (res.updated_llm_result as Record<string, unknown>)
            : (res?.llm_result as Record<string, unknown> | undefined);
          const v = getValueByPath(
            data,
            source.schemaFieldPath || source.schemaFieldName || ''
          );
          if (v) parts.push(v);
        }
        row[colKey] = parts.join(sep).trim();
      });
      return row;
    });
  }, [documents, llmCache, table?.response_format?.column_mapping]);

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
          placeholder="Search documents or values..."
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
          columns={gridColumns}
          getRowId={(row) => row.id}
          loading={isLoading || docLoading}
          disableRowSelectionOnClick
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          paginationMode="server"
          rowCount={totalRows}
          pageSizeOptions={[5, 25, 50, 100]}
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