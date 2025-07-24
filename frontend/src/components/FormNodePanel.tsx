import React from 'react';

interface FormNodePanelProps {
  onAddNode: (type: string) => void;
  onClose: () => void;
  isOpen: boolean;
}

const NODE_TYPES = [
  { type: 'note', label: 'Sticky Note', icon: '📝', description: 'Add a sticky note to your canvas.' },
  { type: 'text', label: 'Text Field', icon: '🔤', description: 'Single-line text input.' },
  // Add more node types here...
];

const FormNodePanel: React.FC<FormNodePanelProps> = ({ onAddNode, onClose, isOpen }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed top-0 right-0 w-80 h-full bg-white shadow-lg z-50 border-l border-gray-200 flex flex-col">
      <div className="flex items-center justify-between p-4 border-b">
        <span className="font-bold text-lg">Add Node</span>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-xl">&times;</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {NODE_TYPES.map((node) => (
          <div
            key={node.type}
            className="flex items-center gap-3 p-3 rounded hover:bg-gray-100 cursor-pointer mb-2"
            onClick={() => onAddNode(node.type)}
          >
            <span className="text-2xl">{node.icon}</span>
            <div>
              <div className="font-semibold">{node.label}</div>
              <div className="text-xs text-gray-500">{node.description}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FormNodePanel;
