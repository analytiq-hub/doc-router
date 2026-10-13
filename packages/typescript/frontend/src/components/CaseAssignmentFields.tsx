'use client';

import React from 'react';
import { TextField, FormControlLabel, Checkbox } from '@mui/material';

type CaseAssignmentFieldsProps = {
  caseId: string;
  onCaseIdChange: (value: string) => void;
  createCaseIfMissing: boolean;
  onCreateCaseIfMissingChange: (value: boolean) => void;
  disabled?: boolean;
};

export function CaseAssignmentFields({
  caseId,
  onCaseIdChange,
  createCaseIfMissing,
  onCreateCaseIfMissingChange,
  disabled = false,
}: CaseAssignmentFieldsProps) {
  return (
    <div className="space-y-3">
      <TextField
        fullWidth
        size="small"
        label="Case ID"
        placeholder="e.g. CLM-123 (leave empty to skip or clear)"
        value={caseId}
        onChange={(e) => onCaseIdChange(e.target.value)}
        disabled={disabled}
        helperText="Assign this document to a case. Clear the field and save to remove from a case."
      />
      <FormControlLabel
        control={
          <Checkbox
            checked={createCaseIfMissing}
            onChange={(e) => onCreateCaseIfMissingChange(e.target.checked)}
            disabled={disabled || !caseId.trim()}
          />
        }
        label="Create case if it does not exist"
      />
    </div>
  );
}
