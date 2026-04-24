import React from 'react';
import { Button, TextField } from '@mui/material';
import FlowStatusBadge from './FlowStatusBadge';

const FlowToolbar: React.FC<{
  name: string;
  onNameChange: (name: string) => void;
  active: boolean;
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onRun: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
}> = ({ name, onNameChange, active, isDirty, isSaving, onSave, onRun, onActivate, onDeactivate }) => {
  return (
    <div className="flex items-center justify-between border-b border-gray-200 bg-white px-3 py-2">
      <div className="flex items-center gap-3 flex-1 min-w-0 pr-2">
        <TextField
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          size="small"
          label="Flow name"
          className="min-w-[200px] max-w-md"
        />
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

