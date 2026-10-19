"use client";

import { toastActionError } from '@/utils/toastActionError';
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { Case, Tag } from '@docrouter/sdk';
import {
  DataGrid,
  GridColDef,
  GridRenderCellParams,
  GridFilterModel,
  GridSortModel,
} from '@mui/x-data-grid';
import {
  TextField,
  InputAdornment,
  IconButton,
  Menu,
  MenuItem,
  Autocomplete,
  Box,
  Tooltip,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { isColorLight } from '@/utils/colors';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useOrgCapability } from '@/hooks/useOrgPermissions';
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities';
import CaseDeleteDialog from '@/components/CaseDeleteDialog';
import { formatLocalDate } from '@/utils/date';
import { caseDisplayName } from '@/utils/caseDisplayName';
import { parseAndEncodeMetadataSearch } from '@/utils/documentListQuery';
import { fetchAllOrgTags } from '@/utils/fetchAllOrgTags';

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (typeof v === 'bigint' ? v.toString() : v));

const caseDetailHref = (organizationId: string, caseId: string) =>
  `/orgs/${organizationId}/cases/${encodeURIComponent(caseId)}`;

function caseDateTimeColumn(field: 'created_at' | 'updated_at', headerName: string): GridColDef {
  return {
    field,
    headerName,
    // Date-only column: matches formatLocalDate display and MUI day-level filter operators.
    type: 'date',
    width: 200,
    flex: 0.85,
    headerAlign: 'left',
    align: 'left',
    valueGetter: (value: unknown, row: Case) => {
      const v = (row[field] ?? value) as string | Date | null | undefined;
      if (!v) return null;
      if (v instanceof Date) return v;
      const d = new Date(v);
      return Number.isNaN(d.getTime()) ? null : d;
    },
    valueFormatter: (params: GridRenderCellParams) => {
      const p = params as unknown as { value?: unknown } | null;
      if (!p?.value) return '';
      const v = p.value as Date | string;
      const iso = v instanceof Date ? v.toISOString() : String(v);
      return formatLocalDate(iso);
    },
    renderCell: (params: GridRenderCellParams<Case>) => {
      const raw = params.row[field];
      if (!raw) return '';
      return (
        <div className="flex items-center h-full min-w-0 text-gray-600">
          <span className="truncate">{formatLocalDate(String(raw))}</span>
        </div>
      );
    },
  };
}

const CaseList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const { hasCapability: canWriteDocuments, loading: permissionsLoading } = useOrgCapability(
    organizationId,
    CAP_DOCUMENTS_WRITE,
  );
  const [deleteDialogCase, setDeleteDialogCase] = useState<Case | null>(null);
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [cases, setCases] = useState<Case[]>([]);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [metadataSearch, setMetadataSearch] = useState('');
  const [tagFilters, setTagFilters] = useState<Tag[]>([]);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });
  const [total, setTotal] = useState(0);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [sortModel, setSortModel] = useState<GridSortModel>([{ field: 'updated_at', sort: 'desc' }]);
  const [filterModel, setFilterModel] = useState<GridFilterModel>({ items: [] });

  useEffect(() => {
    void fetchAllOrgTags(docRouterOrgApi)
      .then(setAvailableTags)
      .catch((error) => toastActionError('Failed to load tags', error));
  }, [docRouterOrgApi]);

  const loadCases = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await docRouterOrgApi.listCases({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        caseIdSearch: searchTerm.trim() || undefined,
        tagIds: tagFilters.length ? tagFilters.map((t) => t.id).join(',') : undefined,
        metadataSearch: metadataSearch.trim()
          ? parseAndEncodeMetadataSearch(metadataSearch.trim()) || undefined
          : undefined,
        sort: sortModel.length ? jsonStringifyForQuery(sortModel) : undefined,
        filters: filterModel.items.length ? jsonStringifyForQuery(filterModel) : undefined,
      });
      setCases(response.cases);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading cases';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [docRouterOrgApi, paginationModel, searchTerm, metadataSearch, tagFilters, sortModel, filterModel]);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, row: Case) => {
    setAnchorEl(event.currentTarget);
    setSelectedCase(row);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedCase(null);
  };

  const openDeleteDialog = (row: Case) => {
    handleMenuClose();
    setDeleteDialogCase(row);
  };

  const columns = useMemo<GridColDef[]>(
    () => [
      {
        field: 'display_name',
        headerName: 'Case Name',
        flex: 1.5,
        valueGetter: (_value, row: Case) => caseDisplayName(row),
        renderCell: (params: GridRenderCellParams<Case>) => {
          const name = caseDisplayName(params.row);
          return (
            <Link
              href={caseDetailHref(organizationId, params.row.case_id)}
              className="text-blue-600 underline truncate font-medium"
              title={name}
            >
              {name}
            </Link>
          );
        },
      },
      {
        field: 'case_id',
        headerName: 'Case ID',
        flex: 1.2,
        renderCell: (params: GridRenderCellParams<Case>) => (
          <span className="font-mono text-sm text-gray-700 truncate" title={params.row.case_id}>
            {params.row.case_id}
          </span>
        ),
      },
      {
        field: 'tag_ids',
        headerName: 'Tags',
        flex: 1,
        sortable: false,
        renderCell: (params: GridRenderCellParams<Case>) => {
          const caseTags = availableTags.filter((tag) => params.row.tag_ids?.includes(tag.id));
          const firstTag = caseTags[0];
          const hasMoreTags = caseTags.length > 1;

          const tagChip = (tag: Tag) => {
            const bgColor = tag.color;
            const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';
            return (
              <div
                key={tag.id}
                className={`px-2 py-1 leading-none rounded shadow-sm ${textColor} flex items-center min-w-0 overflow-hidden`}
                style={{ backgroundColor: bgColor }}
                title={tag.name}
              >
                <span className="truncate min-w-0">{tag.name}</span>
              </div>
            );
          };

          if (!firstTag) {
            return <div className="text-gray-400 flex items-center h-full">-</div>;
          }

          const content = (
            <div className="flex gap-1 items-center h-full w-full min-w-0">
              {tagChip(firstTag)}
              {hasMoreTags && <span className="text-gray-500 text-sm shrink-0">...</span>}
            </div>
          );

          if (hasMoreTags) {
            const tooltipContent = (
              <Box className="flex flex-col gap-1.5 p-1">
                {caseTags.map((tag) => tagChip(tag))}
              </Box>
            );
            return (
              <Tooltip
                title={tooltipContent}
                arrow
                placement="top"
                enterDelay={200}
                componentsProps={{
                  tooltip: {
                    sx: {
                      bgcolor: 'white',
                      color: 'text.primary',
                      border: '1px solid',
                      borderColor: 'divider',
                      padding: '4px',
                      maxWidth: '300px',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                    },
                  },
                }}
              >
                <div className="w-full flex items-center h-full min-w-0">{content}</div>
              </Tooltip>
            );
          }

          return content;
        },
      },
      {
        field: 'document_count',
        headerName: 'Documents',
        width: 110,
        type: 'number',
        sortable: false,
        filterable: false,
      },
      caseDateTimeColumn('created_at', 'Created'),
      caseDateTimeColumn('updated_at', 'Updated'),
      ...(canWriteDocuments
        ? [
            {
              field: 'actions',
              headerName: '',
              width: 56,
              sortable: false,
              filterable: false,
              renderCell: (params: GridRenderCellParams<Case>) => (
                <IconButton
                  size="small"
                  disabled={permissionsLoading}
                  onClick={(e) => handleMenuOpen(e, params.row)}
                >
                  <MoreVertIcon fontSize="small" />
                </IconButton>
              ),
            },
          ]
        : []),
    ],
    [organizationId, availableTags, canWriteDocuments, permissionsLoading]
  );

  return (
    <div className="space-y-4">
      {message && <p className="text-sm text-red-600">{message}</p>}
      <div className="flex flex-wrap gap-3 items-center">
        <TextField
          size="small"
          placeholder="Search cases (ID or name)..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setPaginationModel((p) => ({ ...p, page: 0 }));
          }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
        <Autocomplete
          multiple
          size="small"
          options={availableTags}
          getOptionLabel={(t) => t.name}
          value={tagFilters}
          onChange={(_, v) => {
            setTagFilters(v);
            setPaginationModel((p) => ({ ...p, page: 0 }));
          }}
          renderTags={(value, getTagProps) =>
            value.map((tag, index) => {
              const { key, ...tagProps } = getTagProps({ index });
              return (
                <span
                  key={key}
                  {...tagProps}
                  className={`px-2 py-0.5 rounded text-xs ${
                    isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                  }`}
                  style={{ backgroundColor: tag.color }}
                >
                  {tag.name}
                </span>
              );
            })
          }
          sx={{ minWidth: 260 }}
          renderInput={(params) => <TextField {...params} placeholder="Filter by tags" />}
        />
        <TextField
          size="small"
          placeholder="Metadata (key=value,...)"
          value={metadataSearch}
          onChange={(e) => {
            setMetadataSearch(e.target.value);
            setPaginationModel((p) => ({ ...p, page: 0 }));
          }}
          sx={{ minWidth: 280, flex: 1 }}
        />
      </div>
      <div style={{ height: 480, width: '100%' }}>
        <DataGrid
          loading={isLoading}
          rows={cases}
          columns={columns}
          getRowId={(row) => row.case_id}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          pageSizeOptions={[5, 10, 25, 50]}
          rowCount={total}
          paginationMode="server"
          sortingMode="server"
          sortModel={sortModel}
          onSortModelChange={(model) => {
            setSortModel(model);
            setPaginationModel((p) => ({ ...p, page: 0 }));
          }}
          filterMode="server"
          filterModel={filterModel}
          onFilterModelChange={(model) => {
            setFilterModel(model);
            setPaginationModel((p) => ({ ...p, page: 0 }));
          }}
          disableRowSelectionOnClick
        />
      </div>
      {canWriteDocuments && (
        <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}>
          <MenuItem
            onClick={() => {
              if (selectedCase) {
                router.push(
                  `/orgs/${organizationId}/cases/${encodeURIComponent(selectedCase.case_id)}/edit`,
                );
              }
              handleMenuClose();
            }}
          >
            <EditOutlinedIcon fontSize="small" className="mr-2" /> Edit
          </MenuItem>
          <MenuItem
            onClick={() => {
              if (selectedCase) openDeleteDialog(selectedCase);
            }}
          >
            <DeleteOutlineIcon fontSize="small" className="mr-2 text-red-600" /> Delete case
          </MenuItem>
        </Menu>
      )}
      <CaseDeleteDialog
        open={deleteDialogCase != null}
        organizationId={organizationId}
        caseRow={deleteDialogCase}
        canCascadeDelete={canWriteDocuments}
        onClose={() => setDeleteDialogCase(null)}
        onDeleted={async () => {
          setIsLoading(true);
          try {
            await loadCases();
          } finally {
            setIsLoading(false);
          }
        }}
      />
    </div>
  );
};

export default CaseList;
