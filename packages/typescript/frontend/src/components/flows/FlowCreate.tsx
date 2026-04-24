import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { TextField, Button, Box } from '@mui/material';
import { getApiErrorMsg } from '@/utils/api';
import { useFlowApi } from './useFlowApi';

const FlowCreate: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const api = useFlowApi(organizationId);
  const router = useRouter();
  const [name, setName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');
    if (!name.trim()) {
      setMessage('Flow name is required');
      return;
    }
    try {
      setIsSubmitting(true);
      const res = await api.createFlow({ name: name.trim() });
      router.push(`/orgs/${organizationId}/flows/${res.flow.flow_id}`);
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to create flow');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Box className="bg-white border border-gray-200 rounded-lg p-4">
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <TextField
          label="Flow name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          fullWidth
        />
        <div className="flex items-center gap-3">
          <Button type="submit" variant="contained" disabled={isSubmitting}>
            {isSubmitting ? 'Creating…' : 'Create Flow'}
          </Button>
          {message && <span className="text-sm text-red-600">{message}</span>}
        </div>
      </form>
    </Box>
  );
};

export default FlowCreate;

