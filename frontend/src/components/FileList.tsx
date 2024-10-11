import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useSession } from 'next-auth/react';
import { AppSession } from '@/app/types/AppSession';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { Box } from '@mui/material';

interface File {
  id: string;
  filename: string;
  upload_date: string;
  uploaded_by: string;
  retrieved_by: string[];
}

const FileList: React.FC = () => {
  const { data: session } = useSession() as { data: AppSession | null };
  const [files, setFiles] = useState<File[]>([]);
  const [skipRows, setSkipRows] = useState<number>(0);
  const [countRows, setCountRows] = useState<number>(0);
  const [totalRows, setTotalRows] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });

  const fetchFiles = useCallback(async () => {
    try {
      if (session?.apiAccessToken) {
        const response = await axios.get<File[]>(
          `http://localhost:8000/list?skip=${paginationModel.page * paginationModel.pageSize}&limit=${paginationModel.pageSize}`,
          {
            headers: { Authorization: `Bearer ${session.apiAccessToken}` }
          }
        );
        console.log('response headers', response.headers);
        setFiles(response.data);
        const skipCount = parseInt(response.headers['x-skip'] || '0', 10);
        const totalRowsCount = parseInt(response.headers['x-total-count'] || '0', 10);
        setSkipRows(skipCount);
        setCountRows(response.data.length);
        setTotalRows(totalRowsCount);
      } else {
        console.error('No API access token available');
      }
    } catch (error) {
      console.error('Error fetching files:', error);
    }
  }, [paginationModel.page, paginationModel.pageSize, session?.apiAccessToken]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  // Calculate the current range
  const startRange = skipRows + 1;
  const endRange = Math.min(startRange + countRows - 1, totalRows);

  const columns: GridColDef[] = [
    { field: 'filename', headerName: 'Filename', flex: 1 },
    {
      field: 'upload_date',
      headerName: 'Upload Date',
      flex: 1,
      valueGetter: (params: { row: { upload_date: string } }) =>
        params.row ? new Date(params.row['upload_date']).toLocaleString() : '',
    },
    { field: 'uploaded_by', headerName: 'Uploaded By', flex: 1 },
    {
      field: 'retrieved_by',
      headerName: 'Retrieved By',
      flex: 1,
      valueGetter: (params: { row?: { retrieved_by?: string[] } }) =>
        params.row && Array.isArray(params.row['retrieved_by'])
          ? params.row['retrieved_by'].join(', ')
          : '',
    },
  ];

  return (
    <Box sx={{ height: 400, width: '100%' }}>
      <DataGrid
        rows={files}
        columns={columns}
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        pageSizeOptions={[5, 10, 25]}
        rowCount={totalRows}
        paginationMode="server"
        disableRowSelectionOnClick
        getRowId={(row) => row.id}
        sx={{
          '& .MuiDataGrid-row:nth-of-type(odd)': {
            backgroundColor: 'rgba(0, 0, 0, 0.04)', // Zebra stripe color
          },
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'rgba(0, 0, 0, 0.1)', // Darker gray for hover
          },
        }}
      />
      <div>
        {totalRows > 0 ? `Showing ${startRange}-${endRange} of ${totalRows} documents` : 'No documents found'}
      </div>
    </Box>
  );
};

export default FileList;
