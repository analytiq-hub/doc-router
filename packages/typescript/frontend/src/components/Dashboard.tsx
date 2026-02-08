'use client'

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import { DocRouterOrgApi } from '@/utils/api';
import Link from 'next/link';
import { 
  Description as DocumentIcon,
  Schema as SchemaIcon,
  Psychology as PromptIcon,
  Label as TagIcon,
  Assignment as FormIcon,
  CloudUpload as UploadIcon,
  Add as AddIcon,
  Search as SearchIcon,
  Schedule as ScheduleIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon
} from '@mui/icons-material';
import { Button, TextField, InputAdornment, Chip, Card, CardContent, Typography, CircularProgress } from '@mui/material';

interface DashboardProps {
  organizationId: string;
}

interface DashboardStats {
  documents: number;
  schemas: number;
  prompts: number;
  tags: number;
  forms: number;
}

interface RecentDocument {
  id: string;
  document_name: string;
  upload_date: string;
  state: string;
  tag_ids: string[];
}


const DASHBOARD_ACCEPT = {
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/csv': ['.csv'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/gif': ['.gif'],
  'image/webp': ['.webp'],
  'image/bmp': ['.bmp'],
  'image/tiff': ['.tiff', '.tif']
};

const Dashboard: React.FC<DashboardProps> = ({ organizationId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [stats, setStats] = useState<DashboardStats>({
    documents: 0,
    schemas: 0,
    prompts: 0,
    tags: 0,
    forms: 0
  });
  const [recentDocuments, setRecentDocuments] = useState<RecentDocument[]>([]);
  const [availableTags, setAvailableTags] = useState<Array<{id: string; name: string; color: string}>>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [dashboardUploading, setDashboardUploading] = useState(false);
  const [dashboardUploadError, setDashboardUploadError] = useState<string | null>(null);

  const onDashboardDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    setDashboardUploadError(null);
    setDashboardUploading(true);
    try {
      const documents = await Promise.all(
        acceptedFiles.map(
          (file) =>
            new Promise<{ name: string; content: string; tag_ids: string[]; metadata: Record<string, string> }>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve({
                name: file.name,
                content: reader.result as string,
                tag_ids: [],
                metadata: {}
              });
              reader.onerror = () => reject(reader.error);
              reader.readAsDataURL(file);
            })
        )
      );
      const response = await docRouterOrgApi.uploadDocuments({ documents });
      const firstId = response.documents[0]?.document_id;
      if (firstId) {
        router.push(`/orgs/${organizationId}/docs/${firstId}`);
      } else {
        setDashboardUploadError('Upload succeeded but no document ID returned.');
      }
    } catch (err) {
      console.error('Dashboard upload error:', err);
      setDashboardUploadError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
    } finally {
      setDashboardUploading(false);
    }
  }, [organizationId, docRouterOrgApi, router]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: onDashboardDrop,
    accept: DASHBOARD_ACCEPT,
    multiple: true,
    disabled: dashboardUploading
  });

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [documentsRes, schemasRes, promptsRes, tagsRes, formsRes] = await Promise.all([
          docRouterOrgApi.listDocuments({ limit: 5 }),
          docRouterOrgApi.listSchemas({ limit: 1 }),
          docRouterOrgApi.listPrompts({ limit: 1 }),
          docRouterOrgApi.listTags({ limit: 10 }),
          docRouterOrgApi.listForms({ limit: 1 })
        ]);

        setStats({
          documents: documentsRes.total_count,
          schemas: schemasRes.total_count,
          prompts: promptsRes.total_count,
          tags: tagsRes.total_count,
          forms: formsRes.total_count
        });

        setRecentDocuments(documentsRes.documents);
        setAvailableTags(tagsRes.tags);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, [docRouterOrgApi]);

  const widgets = [
    {
      title: 'Documents',
      count: stats.documents,
      icon: DocumentIcon,
      href: `/orgs/${organizationId}/docs`,
      color: 'bg-blue-500',
      description: 'Uploaded documents'
    },
    {
      title: 'Schemas',
      count: stats.schemas,
      icon: SchemaIcon,
      href: `/orgs/${organizationId}/schemas`,
      color: 'bg-green-500',
      description: 'Data schemas'
    },
    {
      title: 'Prompts',
      count: stats.prompts,
      icon: PromptIcon,
      href: `/orgs/${organizationId}/prompts`,
      color: 'bg-purple-500',
      description: 'AI prompts'
    },
    {
      title: 'Tags',
      count: stats.tags,
      icon: TagIcon,
      href: `/orgs/${organizationId}/tags`,
      color: 'bg-orange-500',
      description: 'Document tags'
    },
    {
      title: 'Forms',
      count: stats.forms,
      icon: FormIcon,
      href: `/orgs/${organizationId}/forms`,
      color: 'bg-red-500',
      description: 'Data forms'
    }
  ];

  const getDocumentStatusIcon = (state: string) => {
    switch (state.toLowerCase()) {
      case 'ready':
      case 'processed':
        return <CheckIcon className="h-4 w-4 text-green-500" />;
      case 'processing':
        return <ScheduleIcon className="h-4 w-4 text-yellow-500" />;
      case 'error':
      case 'failed':
        return <ErrorIcon className="h-4 w-4 text-red-500" />;
      default:
        return <ScheduleIcon className="h-4 w-4 text-gray-500" />;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const filteredDocuments = useMemo(() => {
    if (!searchQuery.trim()) {
      return recentDocuments;
    }
    return recentDocuments.filter(doc => 
      doc.document_name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [recentDocuments, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Header with Search */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Dashboard</h2>
          <p className="text-gray-600">
            Overview of your organization&apos;s resources.
          </p>
        </div>
        <div className="flex gap-3">
          <TextField
            size="small"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon className="h-5 w-5 text-gray-400" />
                </InputAdornment>
              ),
            }}
            className="min-w-[250px]"
          />
          <Link href={`/orgs/${organizationId}/docs?tab=upload`}>
            <Button
              variant="contained"
              startIcon={<UploadIcon />}
              className="bg-blue-600 hover:bg-blue-700"
            >
              Upload
            </Button>
          </Link>
        </div>
      </div>

      {/* Dashboard dropzone: upload (no tags) → OCR + default extraction → document page */}
      <Card className="border-2 border-dashed border-gray-300 hover:border-blue-400 transition-colors">
        <CardContent className="py-8">
          <div
            {...getRootProps()}
            className={`
              flex flex-col items-center justify-center cursor-pointer rounded-lg py-10 px-6
              transition-colors min-h-[140px]
              ${isDragActive ? 'bg-blue-50 border-2 border-blue-400' : 'bg-gray-50/80 hover:bg-gray-100'}
            `}
          >
            <input {...getInputProps()} />
            {dashboardUploading ? (
              <>
                <CircularProgress size={40} className="mb-3" />
                <Typography className="text-gray-500">Uploading and starting extraction…</Typography>
              </>
            ) : (
              <>
                <UploadIcon className="h-12 w-12 text-gray-500 mb-3" />
                <Typography variant="subtitle1" className="font-medium text-gray-700">
                  {isDragActive
                    ? 'Drop document(s) here'
                    : 'Drop a document here or click to upload'}
                </Typography>
                <Typography variant="body2" className="mt-1 text-gray-500">
                  OCR and default extraction will run; you’ll be taken to the document page.
                </Typography>
              </>
            )}
          </div>
          {dashboardUploadError && (
            <Typography color="error" variant="body2" className="mt-3 text-center text-red-600">
              {dashboardUploadError}
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Stats Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
        {widgets.map((widget) => {
          const Icon = widget.icon;
          return (
            <Link
              key={widget.title}
              href={widget.href}
              className="block bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow duration-200"
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`p-3 rounded-lg ${widget.color}`}>
                  <Icon className="h-6 w-6 text-white" />
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-gray-900">
                    {loading ? '...' : stats[widget.title.toLowerCase() as keyof DashboardStats]}
                  </div>
                </div>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  {widget.title}
                </h3>
                <p className="text-sm text-gray-600">
                  {widget.description}
                </p>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <Card>
          <CardContent>
            <div className="flex items-center justify-between mb-4">
              <Typography variant="h6" className="font-semibold">
                Recent Documents
              </Typography>
              <Link href={`/orgs/${organizationId}/docs${searchQuery.trim() ? `?search=${encodeURIComponent(searchQuery)}` : ''}`}>
                <Button size="small" variant="outlined">
                  View All
                </Button>
              </Link>
            </div>
            <div className="space-y-3">
              {loading ? (
                <div className="text-center py-4 text-gray-500">Loading...</div>
              ) : filteredDocuments.length > 0 ? (
                filteredDocuments.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      {getDocumentStatusIcon(doc.state)}
                      <div>
                        <div className="font-medium text-sm">{doc.document_name}</div>
                        <div className="text-xs text-gray-500">{formatDate(doc.upload_date)}</div>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      {doc.tag_ids.slice(0, 2).map((tagId) => {
                        const tag = availableTags.find(t => t.id === tagId);
                        return tag ? (
                          <Chip
                            key={tagId}
                            label={tag.name}
                            size="small"
                            style={{ backgroundColor: tag.color, color: 'white', fontSize: '0.7rem' }}
                          />
                        ) : null;
                      })}
                      {doc.tag_ids.length > 2 && (
                        <Chip
                          label={`+${doc.tag_ids.length - 2}`}
                          size="small"
                          variant="outlined"
                          className="text-xs"
                        />
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-4 text-gray-500">
                  {searchQuery.trim() ? 
                    `No documents found matching "${searchQuery}"` : 
                    "No documents yet. Upload your first document to get started."
                  }
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Second Column: Stacked Quick Actions and Tag Usage */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <Card>
            <CardContent>
              <Typography variant="h6" className="font-semibold mb-4">
                Quick Actions
              </Typography>
              <div className="grid grid-cols-2 gap-3">
                <Link href={`/orgs/${organizationId}/docs?tab=upload`}>
                  <Button
                    variant="outlined"
                    fullWidth
                    startIcon={<UploadIcon />}
                    className="h-12"
                  >
                    Upload Document
                  </Button>
                </Link>
                <Link href={`/orgs/${organizationId}/schemas?tab=schema-create`}>
                  <Button
                    variant="outlined"
                    fullWidth
                    startIcon={<AddIcon />}
                    className="h-12"
                  >
                    Create Schema
                  </Button>
                </Link>
                <Link href={`/orgs/${organizationId}/prompts?tab=prompt-create`}>
                  <Button
                    variant="outlined"
                    fullWidth
                    startIcon={<AddIcon />}
                    className="h-12"
                  >
                    Create Prompt
                  </Button>
                </Link>
                <Link href={`/orgs/${organizationId}/tags?tab=tag-create`}>
                  <Button
                    variant="outlined"
                    fullWidth
                    startIcon={<AddIcon />}
                    className="h-12"
                  >
                    Create Tag
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>

          {/* Tag Usage */}
          {availableTags.length > 0 && (
            <Card>
              <CardContent>
                <div className="flex items-center justify-between mb-4">
                  <Typography variant="h6" className="font-semibold">
                    Tag Usage
                  </Typography>
                  <Link href={`/orgs/${organizationId}/tags`}>
                    <Button size="small" variant="outlined">
                      Manage Tags
                    </Button>
                  </Link>
                </div>
                <div className="flex flex-wrap gap-2">
                  {availableTags.map((tag) => (
                    <Chip
                      key={tag.id}
                      label={tag.name}
                      style={{ backgroundColor: tag.color, color: 'white' }}
                      className="hover:opacity-80 cursor-pointer"
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;