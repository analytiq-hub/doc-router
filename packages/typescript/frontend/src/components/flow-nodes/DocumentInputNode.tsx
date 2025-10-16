import React from 'react';
import { Handle, Position } from 'reactflow';
import { DocumentTextIcon } from '@heroicons/react/24/outline';

interface DocumentInputNodeProps {
  id: string;
  data: {
    label: string;
    documentId?: string;
    documentName?: string;
  };
}

const DocumentInputNode: React.FC<DocumentInputNodeProps> = () => {
  return (
    <div className="bg-white border-2 border-gray-200 rounded-lg p-4 shadow-sm min-w-[200px]">
      <div className="flex items-center space-x-2 mb-3">
        <DocumentTextIcon className="h-5 w-5 text-blue-600" />
        <span className="font-medium text-sm text-gray-900">Document Input</span>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-blue-500 border-2 border-white"
      />
    </div>
  );
};

export default DocumentInputNode; 