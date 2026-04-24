import React from 'react';
import { Button } from '@mui/material';
import FlowStatusBadge from './FlowStatusBadge';

const FlowToolbar: React.FC<{
  name: string;
  active: boolean;
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onRun: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
}> = ({ name, active, isDirty, isSaving, onSave, onRun, onActivate, onDeactivate }) => {
  return (
    <div className="flex items-center justify-between border-b border-gray-200 bg-white px-3 py-2">
      <div className="flex items-center gap-3">
        <div className="text-sm font-semibold text-gray-900">{name}</div>
        <FlowStatusBadge active={active} />
        {isDirty && <div className="text-xs text-amber-700">Unsaved changes</div>}
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outlined" onClick={onSave} disabled={!isDirty || isSaving}>
          {isSaving ? 'Saving…' : 'Save'}
        </Button>
        <Button variant="contained" onClick={onRun}>
          Run
        </Button>
        {active ? (
          <Button variant="outlined" onClick={onDeactivate}>
            Deactivate
          </Button>
        ) : (
          <Button variant="outlined" onClick={onActivate} disabled={isDirty}>
            Activate
          </Button>
        )}
      </div>
    </div>
  );
};

export default FlowToolbar;

