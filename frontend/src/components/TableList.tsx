import React, { useState, useEffect, useCallback } from 'react';
import { listTablesApi, deleteTableApi, updateTableApi, createTableApi, listTagsApi } from '@/utils/api';
import { Table, Tag } from '@/types/index';
import { getApiErrorMsg } from '@/utils/api';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { TextField, InputAdornment, IconButton, Menu, MenuItem } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import DownloadIcon from '@mui/icons-material/Download';
import DriveFileRenameOutlineIcon from '@mui/icons-material/DriveFileRenameOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import colors from 'tailwindcss/colors';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'react-toastify';
import TableNameModal from '@/components/TableNameModal';
import { isColorLight } from '@/utils/colors';

const TableList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const [tables, setTables] = useState<Table[]>([]);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(5);
  const [total, setTotal] = useState(0);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTable, setSelectedTable] = useState<Table | null>(null);
  const [isNameModalOpen, setIsNameModalOpen] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);

  const loadTables = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await listTablesApi({
        organizationId: organizationId,
        skip: page * pageSize,
        limit: pageSize
      });
      setTables(response.tables);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading tables';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, organizationId]);

  const loadTags = useCallback(async () => {
    try {
      const response = await listTagsApi({ organizationId: organizationId });
      setAvailableTags(response.tags);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading tags';
      setMessage('Error: ' + errorMsg);
    }
  }, [organizationId]);

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      try {
        await Promise.all([loadTables(), loadTags()]);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [loadTables, loadTags]);

  const handleView = (table: Table) => {
    router.push(`/orgs/${organizationId}/tables/${table.table_revid}/view`);
  };

  const handleEdit = (table: Table) => {
    router.push(`/orgs/${organizationId}/tables/${table.table_revid}`);
    handleMenuClose();
  };

  const handleNameTable = (table: Table) => {
    setSelectedTable(table);
    setIsCloning(false);
    setIsNameModalOpen(true);
    handleMenuClose();
  };

  const handleNameSubmit = async (newName: string) => {
    if (!selectedTable) return;

    try {
      const tableConfig = {
        name: newName,
        response_format: selectedTable.response_format,
        tag_ids: selectedTable.tag_ids ?? []
      };

      if (isCloning) {
        await createTableApi({
          organizationId: organizationId,
          ...tableConfig
        });
      } else {
        await updateTableApi({
          organizationId: organizationId,
          tableId: selectedTable.table_id,
          table: tableConfig
        });
      }

      await loadTables();
    } catch (error) {
      console.error(`Error ${isCloning ? 'cloning' : 'renaming'} table:`, error);
      toast.error(`Failed to ${isCloning ? 'clone' : 'rename'} table`);
      throw error;
    }
  };

  const handleDelete = async (tableId: string) => {
    try {
      setIsLoading(true);
      await deleteTableApi({ organizationId: organizationId, tableId });
      setTables(tables.filter(t => t.table_id !== tableId));
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error deleting table';
      setMessage('Error: ' + errorMsg);
      toast.error('Failed to delete table');
    } finally {
      setIsLoading(false);
      handleMenuClose();
    }
  };

  const handleCloseNameModal = () => {
    setIsNameModalOpen(false);
    setSelectedTable(null);
    setIsCloning(false);
  };

  const handleDownload = (table: Table) => {
    try {
      const tableJson = JSON.stringify(table.response_format, null, 2);
      const blob = new Blob([tableJson], { type: 'application/json' });

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${table.name.replace(/\s+/g, '_')}_table.json`;

      document.body.appendChild(a);
      a.click();

      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 100);

      handleMenuClose();
    } catch (error) {
      console.error('Error downloading table:', error);
      setMessage('Error: Failed to download table');
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, table: Table) => {
    setAnchorEl(event.currentTarget);
    setSelectedTable(table);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleCloneOperation = (table: Table) => {
    setSelectedTable(table);
    setIsCloning(true);
    setIsNameModalOpen(true);
    handleMenuClose();
  };

  const filteredTables = tables.filter(table =>
    table.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Table Name',
      flex: 1,
      headerAlign: 'left',
      align: 'left',
      renderCell: params => (
        <div className="text-blue-600 cursor-pointer hover:underline" onClick={() => handleView(params.row)}>
          {params.row.name}
        </div>
      )
    },
    {
      field: 'tag_ids',
      headerName: 'Tags',
      width: 200,
      headerAlign: 'left',
      align: 'left',
      renderCell: params => {
        const tableTags = availableTags.filter(tag => params.row.tag_ids?.includes(tag.id));
        return (
          <div className="flex gap-1 flex-wrap items-center h-full">
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
        );
      }
    },
    {
      field: 'table_version',
      headerName: 'Version',
      width: 100,
      headerAlign: 'left',
      align: 'left',
      renderCell: params => <div className="text-gray-600">v{params.row.table_version}</div>
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      headerAlign: 'center',
      align: 'center',
      sortable: false,
      renderCell: params => (
        <div>
          <IconButton onClick={e => handleMenuOpen(e, params.row)} disabled={isLoading} className="text-gray-600 hover:bg-gray-50">
            <MoreVertIcon />
          </IconButton>
        </div>
      )
    }
  ];

  return (
    <div className="p-4 mx-auto">
      <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 hidden md:block">
        <p className="text-sm">
          Tables define columnar data validated against a row schema. Below is a list of your existing tables. If none are available,{' '}
          <Link href={`/orgs/${organizationId}/tables?tab=table-create`} className="text-blue-600 font-medium hover:underline">
            click here
          </Link>{' '}
          or use the tab above to create a new table.
        </p>
      </div>
      <h2 className="text-xl font-bold mb-4 hidden md:block">Tables</h2>

      <div className="mb-4">
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search tables..."
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

      {message && (
        <div className={`mb-4 p-3 rounded ${message.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'}`}>
          {message}
        </div>
      )}

      <div style={{ height: 400, width: '100%' }}>
        <DataGrid
          rows={filteredTables}
          columns={columns}
          getRowId={row => row.table_revid}
          initialState={{
            pagination: {
              paginationModel: { pageSize: 5 }
            },
            sorting: {
              sortModel: [{ field: 'table_revid', sort: 'desc' }]
            }
          }}
          pageSizeOptions={[5, 10, 20]}
          disableRowSelectionOnClick
          loading={isLoading}
          paginationMode="server"
          rowCount={total}
          onPaginationModelChange={model => {
            setPage(model.page);
            setPageSize(model.pageSize);
          }}
          sx={{
            '& .MuiDataGrid-cell': {
              padding: 'px'
            },
            '& .MuiDataGrid-row:nth-of-type(odd)': {
              backgroundColor: colors.gray[100]
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: `${colors.gray[200]} !important`
            }
          }}
        />
      </div>

      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}>
        <MenuItem
          onClick={() => {
            if (selectedTable) handleNameTable(selectedTable);
          }}
          className="flex items-center gap-2"
        >
          <DriveFileRenameOutlineIcon fontSize="small" className="text-indigo-800" />
          <span>Rename</span>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedTable) handleCloneOperation(selectedTable);
          }}
          className="flex items-center gap-2"
        >
          <ContentCopyIcon fontSize="small" className="text-purple-600" />
          <span>Clone</span>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedTable) handleEdit(selectedTable);
          }}
          className="flex items-center gap-2"
        >
          <EditOutlinedIcon fontSize="small" className="text-blue-600" />
          <span>Edit</span>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedTable) handleDownload(selectedTable);
          }}
          className="flex items-center gap-2"
        >
          <DownloadIcon fontSize="small" className="text-green-600" />
          <span>Download</span>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedTable) handleDelete(selectedTable.table_id);
          }}
          className="flex items-center gap-2"
        >
          <DeleteOutlineIcon fontSize="small" className="text-red-600" />
          <span>Delete</span>
        </MenuItem>
      </Menu>

      {selectedTable && (
        <TableNameModal
          isOpen={isNameModalOpen}
          onClose={handleCloseNameModal}
          tableName={isCloning ? `${selectedTable.name} (Copy)` : selectedTable.name}
          onSubmit={handleNameSubmit}
          isCloning={isCloning}
          organizationId={organizationId}
        />
      )}
    </div>
  );
};

export default TableList;