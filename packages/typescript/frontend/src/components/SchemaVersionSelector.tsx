import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Schema } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import { Select, MenuItem, FormControl, InputLabel, CircularProgress, Alert } from '@mui/material';

interface SchemaVersionSelectorProps {
  organizationId: string;
  schemaId: string;
  currentVersion: number;
  currentSchemaRevId: string;
  onVersionSelect: (schemaRevId: string, version: number) => void;
}

const SchemaVersionSelector: React.FC<SchemaVersionSelectorProps> = ({
  organizationId,
  schemaId,
  currentVersion,
  currentSchemaRevId,
  onVersionSelect
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [versions, setVersions] = useState<Schema[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number>(currentVersion);

  useEffect(() => {
    const loadVersions = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await docRouterOrgApi.listSchemaVersions({ schemaId });
        setVersions(response.schemas);
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

  const handleVersionChange = (event: React.ChangeEvent<{ value: unknown }>) => {
    const version = event.target.value as number;
    setSelectedVersion(version);
    
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
        <CircularProgress size={20} />
        <span className="text-sm text-gray-600">Loading versions...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Alert severity="error" className="text-sm">
        {error}
      </Alert>
    );
  }

  if (versions.length <= 1) {
    return (
      <div className="text-sm text-gray-600">
        Version {currentVersion} (only version)
      </div>
    );
  }

  return (
    <FormControl size="small" className="min-w-[200px]">
      <InputLabel id="version-select-label">Version</InputLabel>
      <Select
        labelId="version-select-label"
        value={selectedVersion}
        onChange={handleVersionChange}
        label="Version"
      >
        {versions.map((version) => (
          <MenuItem key={version.schema_revid} value={version.schema_version}>
            <div className="flex items-center justify-between w-full">
              <span>
                v{version.schema_version}
                {version.schema_version === currentVersion && (
                  <span className="ml-2 text-xs text-blue-600 font-semibold">(Current)</span>
                )}
              </span>
              <span className="text-xs text-gray-500 ml-4">
                {formatDate(version.created_at)}
              </span>
            </div>
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
};

export default SchemaVersionSelector;
