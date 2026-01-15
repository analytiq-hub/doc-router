import React from 'react';
import ReactDiffViewer from 'react-diff-viewer-continued';
import { Prompt } from '@docrouter/sdk';

interface PromptDiffViewProps {
  leftPrompt: Prompt;  // Older version
  rightPrompt: Prompt; // Newer version
  onClose: () => void;
}

const PromptDiffView: React.FC<PromptDiffViewProps> = ({
  leftPrompt,
  rightPrompt,
  onClose
}) => {
  // Compare prompt content (text)
  const leftContent = leftPrompt.content || '';
  const rightContent = rightPrompt.content || '';

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-white rounded-lg shadow-xl w-full max-w-6xl mx-4 max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Prompt Version Comparison</h3>
            <p className="text-sm text-gray-600 mt-1">
              Comparing v{leftPrompt.prompt_version} vs v{rightPrompt.prompt_version}
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
            oldValue={leftContent}
            newValue={rightContent}
            splitView={true}
            leftTitle={`Version ${leftPrompt.prompt_version} (${new Date(leftPrompt.created_at).toLocaleDateString()})`}
            rightTitle={`Version ${rightPrompt.prompt_version} (${new Date(rightPrompt.created_at).toLocaleDateString()})`}
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

export default PromptDiffView;
