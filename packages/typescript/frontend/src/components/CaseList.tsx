"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { Case, Tag } from '@docrouter/sdk';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { TextField, InputAdornment, IconButton, Menu, MenuItem, Autocomplete } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { isColorLight } from '@/utils/colors';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { formatLocalDate } from '@/utils/date';
import { parseAndEncodeMetadataSearch } from '@/utils/documentListQuery';
import { toast } from 'react-toastify';

const CaseList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
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

  useEffect(() => {
    void docRouterOrgApi.listTags({ limit: 200 }).then((r) => setAvailableTags(r.tags)).catch(() => {});
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
      });
      setCases(response.cases);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading cases';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [docRouterOrgApi, paginationModel, searchTerm, metadataSearch, tagFilters]);

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

  const handleDelete = async (row: Case) => {
    if (!window.confirm(`Delete case "${row.case_id}"? Documents will be kept and unassigned.`)) {
      return;
    }
    try {
      setIsLoading(true);
      await docRouterOrgApi.deleteCase({ caseId: row.case_id, cascade: false });
      toast.success('Case deleted');
      handleMenuClose();
      await loadCases();
    } catch (error) {
      toast.error(getApiErrorMsg(error) || 'Error deleting case');
    } finally {
      setIsLoading(false);
    }
  };

  const columns = useMemo<GridColDef[]>(
    () => [
      {
        field: 'case_id',
        headerName: 'Case ID',
        flex: 1.2,
        renderCell: (params: GridRenderCellParams<Case>) => (
          <Link
            href={`/orgs/${organizationId}/cases/${encodeURIComponent(params.row.case_id)}`}
            className="text-blue-600 underline truncate"
            title={params.value as string}
          >
            {params.value as string}
          </Link>
        ),
      },
      {
        field: 'display_name',
        headerName: 'Display name',
        flex: 1.5,
      },
      {
        field: 'document_count',
        headerName: 'Documents',
        width: 110,
        type: 'number',
      },
      {
        field: 'updated_at',
        headerName: 'Updated',
        flex: 1,
        valueFormatter: (value) => formatLocalDate(String(value)),
      },
      {
        field: 'actions',
        headerName: '',
        width: 56,
        sortable: false,
        filterable: false,
        renderCell: (params: GridRenderCellParams<Case>) => (
          <IconButton size="small" onClick={(e) => handleMenuOpen(e, params.row)}>
            <MoreVertIcon fontSize="small" />
          </IconButton>
        ),
      },
    ],
    [organizationId]
  );

  return (
    <div className="space-y-4">
      {message && <p className="text-sm text-red-600">{message}</p>}
      <div className="flex flex-wrap gap-3 items-center">
        <TextField
          size="small"
          placeholder="Search case ID..."
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
          disableRowSelectionOnClick
        />
      </div>
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}>
        <MenuItem
          onClick={() => {
            if (selectedCase) {
              router.push(`/orgs/${organizationId}/cases/${encodeURIComponent(selectedCase.case_id)}/edit`);
            }
            handleMenuClose();
          }}
        >
          <EditOutlinedIcon fontSize="small" className="mr-2" /> Edit
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedCase) void handleDelete(selectedCase);
          }}
        >
          <DeleteOutlineIcon fontSize="small" className="mr-2 text-red-600" /> Delete case
        </MenuItem>
      </Menu>
    </div>
  );
};

export default CaseList;
