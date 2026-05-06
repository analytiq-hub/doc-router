import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { getApiErrorMsg } from '@/utils/api';
import { useFlowApi } from './useFlowApi';
import { flowInputClass, flowLabelClass } from './flowUiClasses';

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
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div>
          <label className={flowLabelClass} htmlFor="new-flow-name">
            Flow name
          </label>
          <input
            id="new-flow-name"
            className={flowInputClass}
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="off"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? 'Creating…' : 'Create Flow'}
          </button>
          {message && <span className="text-sm text-red-600">{message}</span>}
        </div>
      </form>
    </div>
  );
};

export default FlowCreate;
