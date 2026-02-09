'use client'

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import { DocRouterOrgApi } from '@/utils/api';
import { isColorLight } from '@/utils/colors';
import Link from 'next/link';
import { 
  Description as DocumentIcon,
  DataObject as SchemaIcon,
  Chat as PromptIcon,
  LocalOffer as TagIcon,
  Assignment as FormIcon,
  MenuBook as KnowledgeBaseIcon,
  CloudUpload as UploadIcon,
  Add as AddIcon,
  Search as SearchIcon,
  Schedule as ScheduleIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon
} from '@mui/icons-material';
import { Button, TextField, InputAdornment, Card, CardContent, Typography, CircularProgress } from '@mui/material';

interface DashboardProps {
  organizationId: string;
}

interface DashboardStats {
  documents: number;
  schemas: number;
  prompts: number;
  tags: number;
  forms: number;
  knowledgeBases: number;
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
    forms: 0,
    knowledgeBases: 0
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
        router.push(`/orgs/${organizationId}/docs/${firstId}?bbox`);
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
        const [documentsRes, schemasRes, promptsRes, tagsRes, formsRes, knowledgeBasesRes] = await Promise.all([
          docRouterOrgApi.listDocuments({ limit: 5 }),
          docRouterOrgApi.listSchemas({ limit: 1 }),
          docRouterOrgApi.listPrompts({ limit: 1 }),
          docRouterOrgApi.listTags({ limit: 10 }),
          docRouterOrgApi.listForms({ limit: 1 }),
          docRouterOrgApi.listKnowledgeBases({ limit: 1 })
        ]);

        setStats({
          documents: documentsRes.total_count,
          schemas: schemasRes.total_count,
          prompts: promptsRes.total_count,
          tags: tagsRes.total_count,
          forms: formsRes.total_count,
          knowledgeBases: knowledgeBasesRes.total_count
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
    },
    {
      title: 'Knowledge Bases',
      count: stats.knowledgeBases,
      icon: KnowledgeBaseIcon,
      href: `/orgs/${organizationId}/knowledge-bases`,
      color: 'bg-teal-500',
      description: 'Knowledge bases'
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

      {/* Stats: grid with 1, 2, 3, or 6 columns; equal-width cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {widgets.map((widget) => {
          const Icon = widget.icon;
          return (
            <Link
              key={widget.title}
              href={widget.href}
              className="flex items-center gap-2 min-w-0 px-3 py-2 rounded-lg border border-gray-200 bg-white text-gray-800 shadow-sm hover:border-gray-300 hover:shadow transition-colors"
            >
              <div className={`flex-shrink-0 p-1 rounded-md ${widget.color}`}>
                <Icon className="h-4 w-4 text-white" />
              </div>
              <span className="flex-shrink-0 text-sm font-bold text-gray-900 tabular-nums">
                {loading ? '...' : widget.count}
              </span>
              <span className="text-sm font-medium text-gray-700 truncate min-w-0">
                {widget.title}
              </span>
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
              <Link
                href={`/orgs/${organizationId}/docs${searchQuery.trim() ? `?search=${encodeURIComponent(searchQuery)}` : ''}`}
                className="inline-flex items-center py-1.5 px-3 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition-colors"
              >
                View All
              </Link>
            </div>
            <div className="space-y-3">
              {loading ? (
                <div className="text-center py-4 text-gray-500">Loading...</div>
              ) : filteredDocuments.length > 0 ? (
                filteredDocuments.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <Link
                      href={`/orgs/${organizationId}/docs/${doc.id}`}
                      className="flex items-center gap-3 min-w-0 flex-1 hover:bg-gray-100 rounded -m-1 p-1 transition-colors"
                    >
                      {getDocumentStatusIcon(doc.state)}
                      <div className="min-w-0">
                        <div className="font-medium text-sm text-gray-900 truncate">{doc.document_name}</div>
                        <div className="text-xs text-gray-500">{formatDate(doc.upload_date)}</div>
                      </div>
                    </Link>
                    <div className="flex gap-1 items-center flex-shrink-0 ml-2">
                      {doc.tag_ids.slice(0, 2).map((tagId) => {
                        const tag = availableTags.find(t => t.id === tagId);
                        return tag ? (
                          <Link
                            key={tagId}
                            href={`/orgs/${organizationId}/tags/${tag.id}`}
                            className={`px-2 py-1 leading-none rounded shadow-sm flex items-center text-xs hover:opacity-90 ${isColorLight(tag.color) ? 'text-gray-800' : 'text-white'}`}
                            style={{ backgroundColor: tag.color }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            {tag.name}
                          </Link>
                        ) : null;
                      })}
                      {doc.tag_ids.length > 2 && (
                        <span className="text-gray-500 text-sm">+{doc.tag_ids.length - 2}</span>
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
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Quick Actions</h3>
              <div className="grid grid-cols-2 gap-2">
                <Link
                  href={`/orgs/${organizationId}/docs?tab=upload`}
                  className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors"
                >
                  <UploadIcon className="h-4 w-4" />
                  Upload Document
                </Link>
                <Link
                  href={`/orgs/${organizationId}/schemas?tab=schema-create`}
                  className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors"
                >
                  <AddIcon className="h-4 w-4" />
                  Create Schema
                </Link>
                <Link
                  href={`/orgs/${organizationId}/prompts?tab=prompt-create`}
                  className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors"
                >
                  <AddIcon className="h-4 w-4" />
                  Create Prompt
                </Link>
                <Link
                  href={`/orgs/${organizationId}/tags?tab=tag-create`}
                  className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors"
                >
                  <AddIcon className="h-4 w-4" />
                  Create Tag
                </Link>
                <Link
                  href={`/orgs/${organizationId}/forms?tab=form-create`}
                  className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors"
                >
                  <AddIcon className="h-4 w-4" />
                  Create Form
                </Link>
                <Link
                  href={`/orgs/${organizationId}/knowledge-bases?tab=kb-create`}
                  className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors"
                >
                  <AddIcon className="h-4 w-4" />
                  Create Knowledge Base
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
                  <Link
                    href={`/orgs/${organizationId}/tags`}
                    className="inline-flex items-center py-1.5 px-3 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Manage Tags
                  </Link>
                </div>
                <div className="flex flex-wrap gap-2">
                  {availableTags.map((tag) => (
                    <Link
                      key={tag.id}
                      href={`/orgs/${organizationId}/tags/${tag.id}`}
                      className={`px-2 py-1 leading-none rounded shadow-sm flex items-center text-xs hover:opacity-90 ${isColorLight(tag.color) ? 'text-gray-800' : 'text-white'}`}
                      style={{ backgroundColor: tag.color }}
                    >
                      {tag.name}
                    </Link>
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