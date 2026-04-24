import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { DataGrid, type GridColDef, type GridRenderCellParams } from '@mui/x-data-grid';
import { IconButton, Menu, MenuItem, Tooltip } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ToggleOnIcon from '@mui/icons-material/ToggleOn';
import ToggleOffIcon from '@mui/icons-material/ToggleOff';
import { getApiErrorMsg } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import FlowStatusBadge from './FlowStatusBadge';
import { useFlowApi } from './useFlowApi';
import type { FlowListItem } from '@docrouter/sdk';

type FlowListRow = FlowListItem & { id: string };

const FlowList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const api = useFlowApi(organizationId);

  const [rows, setRows] = useState<FlowListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 20 });

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selected, setSelected] = useState<FlowListItem | null>(null);

  const gridRows: FlowListRow[] = useMemo(
    () => rows.map((r) => ({ ...r, id: r.flow.flow_id })),
    [rows],
  );

  const load = useCallback(async () => {
    try {
      setIsLoading(true);
      setMessage('');
      const res = await api.listFlows({
        limit: paginationModel.pageSize,
        offset: paginationModel.page * paginationModel.pageSize,
      });
      setRows(res.items);
      setTotal(res.total);
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Error loading flows');
    } finally {
      setIsLoading(false);
    }
  }, [api, paginationModel.page, paginationModel.pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, item: FlowListItem) => {
    setAnchorEl(event.currentTarget);
    setSelected(item);
  };
  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelected(null);
  };

  const handleEdit = useCallback((item: FlowListItem) => {
    router.push(`/orgs/${organizationId}/flows/${item.flow.flow_id}`);
    handleMenuClose();
  }, [organizationId, router]);

  const handleRun = useCallback(async (item: FlowListItem) => {
    try {
      await api.runFlow(item.flow.flow_id, {});
      // keep it simple for phase 1; later show snackbar + switch to executions tab
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to run flow');
    } finally {
      handleMenuClose();
    }
  }, [api, load]);

  const handleToggleActive = useCallback(async (item: FlowListItem) => {
    try {
      if (item.flow.active) {
        await api.deactivateFlow(item.flow.flow_id);
      } else {
        await api.activateFlow(item.flow.flow_id);
      }
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to update flow activation');
    } finally {
      handleMenuClose();
    }
  }, [api, load]);

  const handleDelete = useCallback(async (item: FlowListItem) => {
    const ok = window.confirm(`Delete flow “${item.flow.name}”?`);
    if (!ok) return;
    try {
      await api.deleteFlow(item.flow.flow_id);
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to delete flow');
    } finally {
      handleMenuClose();
    }
  }, [api, load]);

  const columns: GridColDef<FlowListRow>[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1,
        valueGetter: (_v, row) => row.flow.name,
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        sortable: false,
        renderCell: ({ row }) => <FlowStatusBadge active={row.flow.active} />,
      },
      {
        field: 'version',
        headerName: 'Version',
        width: 110,
        valueGetter: (_v, row) => row.flow.flow_version,
      },
      {
        field: 'updated_at',
        headerName: 'Updated',
        type: 'dateTime',
        width: 220,
        headerAlign: 'left',
        align: 'left',
        valueGetter: (_v, row) => {
          const v = row.flow.updated_at as string | null | undefined;
          if (!v) return null;
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
        renderCell: (params: GridRenderCellParams) => {
          const v = (params.row as FlowListRow).flow.updated_at;
          if (!v) return '';
          const formatted = formatLocalDate(v);
          return (
            <div className="text-gray-600" title={formatted}>
              {formatted}
            </div>
          );
        },
      },
      {
        field: 'actions',
        headerName: '',
        width: 120,
        sortable: false,
        filterable: false,
        renderCell: ({ row }) => {
          const item = row;
          return (
            <div className="flex items-center gap-2">
              <Tooltip title="Edit">
                <IconButton size="small" onClick={() => handleEdit(item)}>
                  <EditOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Run">
                <IconButton size="small" onClick={() => void handleRun(item)}>
                  <PlayArrowIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <IconButton size="small" onClick={(e) => handleMenuOpen(e, item)}>
                <MoreVertIcon fontSize="small" />
              </IconButton>
            </div>
          );
        },
      },
    ],
    [handleEdit, handleRun, handleToggleActive, handleDelete],
  );

  return (
    <div className="bg-white border border-gray-200 rounded-lg">
      {message && <div className="px-4 py-3 text-sm text-red-600">{message}</div>}
      <div style={{ height: 600, width: '100%' }}>
        <DataGrid
          rows={gridRows}
          columns={columns}
          loading={isLoading}
          paginationMode="server"
          rowCount={total}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          pageSizeOptions={[10, 20, 50]}
          disableRowSelectionOnClick
        />
      </div>

      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}>
        {selected && (
          <>
            <MenuItem onClick={() => handleEdit(selected)}>
              <EditOutlinedIcon fontSize="small" style={{ marginRight: 8 }} />
              Edit
            </MenuItem>
            <MenuItem onClick={() => void handleRun(selected)}>
              <PlayArrowIcon fontSize="small" style={{ marginRight: 8 }} />
              Run
            </MenuItem>
            <MenuItem onClick={() => void handleToggleActive(selected)}>
              {selected.flow.active ? (
                <>
                  <ToggleOffIcon fontSize="small" style={{ marginRight: 8 }} />
                  Deactivate
                </>
              ) : (
                <>
                  <ToggleOnIcon fontSize="small" style={{ marginRight: 8 }} />
                  Activate
                </>
              )}
            </MenuItem>
            <MenuItem onClick={() => void handleDelete(selected)}>
              <DeleteOutlineIcon fontSize="small" style={{ marginRight: 8 }} />
              Delete
            </MenuItem>
          </>
        )}
      </Menu>
    </div>
  );
};

export default FlowList;

