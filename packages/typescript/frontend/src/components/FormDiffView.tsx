import React from 'react';
import ReactDiffViewer from 'react-diff-viewer-continued';
import { Form } from '@docrouter/sdk';

interface FormDiffViewProps {
  leftForm: Form;  // Older version
  rightForm: Form; // Newer version
  onClose: () => void;
}

const FormDiffView: React.FC<FormDiffViewProps> = ({
  leftForm,
  rightForm,
  onClose
}) => {
  // Convert form response_format to formatted JSON strings for comparison
  const leftJson = JSON.stringify(leftForm.response_format, null, 2);
  const rightJson = JSON.stringify(rightForm.response_format, null, 2);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-white rounded-lg shadow-xl w-full max-w-6xl mx-4 max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Form Version Comparison</h3>
            <p className="text-sm text-gray-600 mt-1">
              Comparing v{leftForm.form_version} vs v{rightForm.form_version}
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
            leftTitle={`Version ${leftForm.form_version} (${new Date(leftForm.created_at).toLocaleDateString()})`}
            rightTitle={`Version ${rightForm.form_version} (${new Date(rightForm.created_at).toLocaleDateString()})`}
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

export default FormDiffView;
