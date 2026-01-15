import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Schema } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';

interface SchemaVersionSelectorProps {
  organizationId: string;
  schemaId: string;
  currentVersion: number;
  onVersionSelect: (schemaRevId: string, version: number) => void;
}

const SchemaVersionSelector: React.FC<SchemaVersionSelectorProps> = ({
  organizationId,
  schemaId,
  currentVersion,
  onVersionSelect
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [versions, setVersions] = useState<Schema[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number>(currentVersion);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const loadVersions = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await docRouterOrgApi.listSchemaVersions({ schemaId });
        // Sort by version descending (newest first)
        const sorted = response.schemas.sort((a, b) => b.schema_version - a.schema_version);
        setVersions(sorted);
      } catch (err) {
        const errorMsg = getApiErrorMsg(err) || 'Failed to load schema versions';
        setError(errorMsg);
        console.error('Error loading schema versions:', err);
      } finally {
        setIsLoading(false);
      }
    };

    if (schemaId) {
      loadVersions();
    }
  }, [schemaId, docRouterOrgApi]);

  useEffect(() => {
    setSelectedVersion(currentVersion);
  }, [currentVersion]);

  const handleVersionChange = (version: number) => {
    setSelectedVersion(version);
    setIsOpen(false);
    
    // Find the schema revision for this version
    const selectedSchema = versions.find(v => v.schema_version === version);
    if (selectedSchema) {
      onVersionSelect(selectedSchema.schema_revid, version);
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2">
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
        <span className="text-sm text-gray-600">Loading versions...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm">
        {error}
      </div>
    );
  }

  if (versions.length <= 1) {
    return (
      <div className="text-sm text-gray-600 px-3 py-1.5">
        Version {currentVersion} (only version)
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="h-8 mb-2 flex items-center gap-2 px-3 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-w-[200px] justify-between"
      >
        <div className="flex items-center gap-2">
          <span>v{selectedVersion}</span>
          {selectedVersion === currentVersion && (
            <span className="px-1.5 py-0.5 text-xs font-semibold text-blue-600 bg-blue-50 rounded">Current</span>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'transform rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          ></div>
          <div className="absolute z-20 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
            {versions.map((version) => (
              <button
                key={version.schema_revid}
                onClick={() => handleVersionChange(version.schema_version)}
                className={`w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors ${
                  version.schema_version === selectedVersion ? 'bg-blue-50' : ''
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">v{version.schema_version}</span>
                    {version.schema_version === currentVersion && (
                      <span className="px-1.5 py-0.5 text-xs font-semibold text-blue-600 bg-blue-100 rounded">Current</span>
                    )}
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatDate(version.created_at)}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default SchemaVersionSelector;
