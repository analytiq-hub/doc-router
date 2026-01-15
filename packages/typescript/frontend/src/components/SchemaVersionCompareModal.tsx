import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Schema } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import { Select, MenuItem, FormControl, InputLabel, Button, CircularProgress, Alert } from '@mui/material';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';

interface SchemaVersionCompareModalProps {
  isOpen: boolean;
  onClose: () => void;
  organizationId: string;
  schemaId: string;
  currentSchema: Schema;
  onCompare: (leftSchema: Schema, rightSchema: Schema) => void;
}

const SchemaVersionCompareModal: React.FC<SchemaVersionCompareModalProps> = ({
  isOpen,
  onClose,
  organizationId,
  schemaId,
  currentSchema,
  onCompare
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [versions, setVersions] = useState<Schema[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leftVersion, setLeftVersion] = useState<number>(currentSchema.schema_version);
  const [rightVersion, setRightVersion] = useState<number>(currentSchema.schema_version);

  useEffect(() => {
    const loadVersions = async () => {
      if (!isOpen || !schemaId) return;
      
      setIsLoading(true);
      setError(null);
      try {
        const response = await docRouterOrgApi.listSchemaVersions({ schemaId });
        const sorted = response.schemas.sort((a, b) => b.schema_version - a.schema_version);
        setVersions(sorted);
        // Set defaults: left = oldest, right = current
        if (sorted.length > 0) {
          setLeftVersion(sorted[sorted.length - 1].schema_version);
          setRightVersion(currentSchema.schema_version);
        }
      } catch (err) {
        const errorMsg = getApiErrorMsg(err) || 'Failed to load schema versions';
        setError(errorMsg);
        console.error('Error loading schema versions:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadVersions();
  }, [isOpen, schemaId, docRouterOrgApi, currentSchema.schema_version]);

  const handleCompare = () => {
    const leftSchema = versions.find(v => v.schema_version === leftVersion);
    const rightSchema = versions.find(v => v.schema_version === rightVersion);
    
    if (leftSchema && rightSchema) {
      // Ensure left is older than right
      if (leftSchema.schema_version > rightSchema.schema_version) {
        onCompare(rightSchema, leftSchema);
      } else {
        onCompare(leftSchema, rightSchema);
      }
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-medium mb-4">Compare Schema Versions</h3>
        
        {error && (
          <Alert severity="error" className="mb-4">
            {error}
          </Alert>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <CircularProgress />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <FormControl size="small" className="flex-1">
                <InputLabel id="left-version-label">From Version</InputLabel>
                <Select
                  labelId="left-version-label"
                  value={leftVersion}
                  onChange={(e) => setLeftVersion(e.target.value as number)}
                  label="From Version"
                >
                  {versions.map((version) => (
                    <MenuItem key={version.schema_revid} value={version.schema_version}>
                      v{version.schema_version}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <CompareArrowsIcon className="text-gray-400" />

              <FormControl size="small" className="flex-1">
                <InputLabel id="right-version-label">To Version</InputLabel>
                <Select
                  labelId="right-version-label"
                  value={rightVersion}
                  onChange={(e) => setRightVersion(e.target.value as number)}
                  label="To Version"
                >
                  {versions.map((version) => (
                    <MenuItem key={version.schema_revid} value={version.schema_version}>
                      v{version.schema_version}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCompare}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                disabled={leftVersion === rightVersion}
              >
                Compare
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SchemaVersionCompareModal;
