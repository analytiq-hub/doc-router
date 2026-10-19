'use client';

import { useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  TextField,
} from '@mui/material';
import type { Case } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { toastActionError } from '@/utils/toastActionError';
import { toast } from 'react-toastify';
import { caseDisplayName } from '@/utils/caseDisplayName';
import { deleteCaseAndWait, type CaseDeleteMode } from '@/utils/caseDelete';

type CaseDeleteDialogProps = {
  open: boolean;
  organizationId: string;
  caseRow: Case | null;
  /** Same as documents.write — required for cascade delete per API. */
  canCascadeDelete: boolean;
  onClose: () => void;
  onDeleted: () => void | Promise<void>;
};

export default function CaseDeleteDialog({
  open,
  organizationId,
  caseRow,
  canCascadeDelete,
  onClose,
  onDeleted,
}: CaseDeleteDialogProps) {
  const [mode, setMode] = useState<CaseDeleteMode>('unassign');
  const [confirmId, setConfirmId] = useState('');
  const [busy, setBusy] = useState(false);

  const docCount = caseRow?.document_count ?? 0;
  const caseId = caseRow?.case_id ?? '';

  const cascadeConfirmOk = confirmId.trim() === caseId;
  const canSubmit = useMemo(() => {
    if (!caseRow || busy) return false;
    if (mode === 'cascade') {
      return canCascadeDelete && cascadeConfirmOk;
    }
    return true;
  }, [busy, canCascadeDelete, cascadeConfirmOk, caseRow, mode]);

  const resetForm = () => {
    setMode('unassign');
    setConfirmId('');
    setBusy(false);
  };

  const handleClose = () => {
    if (busy) return;
    resetForm();
    onClose();
  };

  const handleSubmit = async () => {
    if (!caseRow || !canSubmit) return;
    const api = new DocRouterOrgApi(organizationId);
    setBusy(true);
    try {
      if (mode === 'cascade') {
        toast.info('Deleting case and documents…', { autoClose: 3000 });
      }
      const result = await deleteCaseAndWait(api, caseRow.case_id, mode);
      if (result.cascade && result.polled) {
        toast.success(
          docCount > 0
            ? `Case and ${docCount} document(s) deleted.`
            : 'Case deleted.',
        );
      } else {
        toast.success(
          docCount > 0
            ? `Case deleted. ${docCount} document(s) were unassigned and kept.`
            : 'Case deleted.',
        );
      }
      resetForm();
      onClose();
      await onDeleted();
    } catch (error) {
      toastActionError('Failed to delete case', error);
    } finally {
      setBusy(false);
    }
  };

  if (!caseRow) {
    return null;
  }

  const title = caseDisplayName(caseRow);

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Delete case</DialogTitle>
      <DialogContent className="flex flex-col gap-4 pt-2">
        <p className="text-sm text-gray-700">
          <span className="font-medium">{title}</span>
          {title !== caseRow.case_id && (
            <span className="block font-mono text-gray-500 text-xs mt-1">{caseRow.case_id}</span>
          )}
        </p>
        <p className="text-sm text-gray-600">
          This case contains{' '}
          <strong>{docCount}</strong> document{docCount === 1 ? '' : 's'}.
        </p>

        <FormControl component="fieldset" disabled={busy}>
          <RadioGroup
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as CaseDeleteMode);
              setConfirmId('');
            }}
          >
            <FormControlLabel
              value="unassign"
              control={<Radio size="small" />}
              label={
                <span className="text-sm">
                  Remove case only — documents stay in the org and are unassigned from this case.
                </span>
              }
            />
            {canCascadeDelete && (
              <FormControlLabel
                value="cascade"
                control={<Radio size="small" />}
                label={
                  <span className="text-sm">
                    Delete case and all member documents
                  </span>
                }
              />
            )}
          </RadioGroup>
        </FormControl>

        {mode === 'cascade' && (
          <>
            <Alert severity="error" variant="outlined">
              This permanently deletes every document in the case (files, OCR, extractions, and
              related data). This cannot be undone.
            </Alert>
            <TextField
              label={`Type case id "${caseRow.case_id}" to confirm`}
              value={confirmId}
              onChange={(e) => setConfirmId(e.target.value)}
              disabled={busy}
              fullWidth
              size="small"
              autoComplete="off"
              inputProps={{ className: 'font-mono' }}
            />
          </>
        )}
      </DialogContent>
      <DialogActions className="px-6 pb-4">
        <Button onClick={handleClose} disabled={busy}>
          Cancel
        </Button>
        <Button
          color="error"
          variant="contained"
          disabled={!canSubmit}
          onClick={() => void handleSubmit()}
        >
          {busy ? 'Deleting…' : mode === 'cascade' ? 'Delete case and documents' : 'Delete case'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
