// frontend/src/components/FormAddNodeGadget.tsx
import React from 'react';

interface FormAddNodeGadgetProps {
  onOpenPanel: () => void;
  onAddStickyNote: () => void;
}

const FormAddNodeGadget: React.FC<FormAddNodeGadgetProps> = ({ onOpenPanel, onAddStickyNote }) => (
  <div className="absolute top-4 right-4 z-50 flex flex-col items-end gap-2">
    <button
      className="bg-white border border-gray-300 rounded-full w-12 h-12 flex items-center justify-center shadow hover:bg-gray-100 text-2xl"
      onClick={onOpenPanel}
      title="Open nodes panel"
    >
      +
    </button>
    <button
      className="bg-white border border-yellow-400 text-yellow-600 rounded-full w-12 h-12 flex items-center justify-center shadow hover:bg-yellow-50 text-2xl"
      onClick={onAddStickyNote}
      title="Add sticky note"
    >
      📝
    </button>
  </div>
);

export default FormAddNodeGadget;
