import React from 'react';
import ReactDiffViewer from 'react-diff-viewer-continued';
import { Schema } from '@docrouter/sdk';

interface SchemaDiffViewProps {
  leftSchema: Schema;  // Older version
  rightSchema: Schema; // Newer version
  onClose: () => void;
}

const SchemaDiffView: React.FC<SchemaDiffViewProps> = ({
  leftSchema,
  rightSchema,
  onClose
}) => {
  // Convert schemas to formatted JSON strings for comparison
  const leftJson = JSON.stringify(leftSchema.response_format.json_schema, null, 2);
  const rightJson = JSON.stringify(rightSchema.response_format.json_schema, null, 2);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-white rounded-lg shadow-xl w-full max-w-6xl mx-4 max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Schema Version Comparison</h3>
            <p className="text-sm text-gray-600 mt-1">
              Comparing v{leftSchema.schema_version} vs v{rightSchema.schema_version}
            </p>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            Close
          </button>
        </div>

        {/* Diff Viewer */}
        <div className="flex-1 overflow-auto">
          <ReactDiffViewer
            oldValue={leftJson}
            newValue={rightJson}
            splitView={true}
            leftTitle={`Version ${leftSchema.schema_version} (${new Date(leftSchema.created_at).toLocaleDateString()})`}
            rightTitle={`Version ${rightSchema.schema_version} (${new Date(rightSchema.created_at).toLocaleDateString()})`}
            showDiffOnly={false}
            useDarkTheme={false}
            styles={{
              variables: {
                light: {
                  codeFoldGutterBackground: '#f0f0f0',
                  codeFoldBackground: '#f0f0f0',
                }
              },
              contentText: {
                fontSize: '14px',
                fontFamily: 'monospace'
              }
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default SchemaDiffView;
