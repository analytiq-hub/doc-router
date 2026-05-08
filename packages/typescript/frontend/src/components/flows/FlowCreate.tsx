import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NEW_FLOW_URL_SEGMENT } from './flowDefaultNames';
import { flowInputClass, flowLabelClass } from './flowUiClasses';

const FlowCreate: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const [name, setName] = useState('');
  const [message, setMessage] = useState('');

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');
    if (!name.trim()) {
      setMessage('Flow name is required');
      return;
    }
    const q = new URLSearchParams();
    q.set('proposedName', name.trim());
    router.push(`/orgs/${organizationId}/flows/${NEW_FLOW_URL_SEGMENT}?${q.toString()}`);
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
            className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Create Flow
          </button>
          {message && <span className="text-sm text-red-600">{message}</span>}
        </div>
      </form>
    </div>
  );
};

export default FlowCreate;
