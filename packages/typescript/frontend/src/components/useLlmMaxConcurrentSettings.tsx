import { useCallback, useEffect, useRef, useState } from 'react';
import TextField from '@mui/material/TextField';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { DocRouterAccountApi } from '@/utils/api';

export const MIN_LLM_MAX_CONCURRENT = 0;
export const MAX_LLM_MAX_CONCURRENT = 1024;

type MaxConcurrentColumnOptions = {
  getModelName: (row: Record<string, unknown>) => string;
  isEnabled: (row: Record<string, unknown>) => boolean;
};

type MaxConcurrentCellProps = {
  modelName: string;
  savedValue?: number;
  enabled: boolean;
  saving: boolean;
  onPersist: (modelName: string, rawValue: string) => void;
};

function MaxConcurrentCell({
  modelName,
  savedValue,
  enabled,
  saving,
  onPersist,
}: MaxConcurrentCellProps) {
  const [draft, setDraft] = useState(savedValue !== undefined ? String(savedValue) : '');

  useEffect(() => {
    setDraft(savedValue !== undefined ? String(savedValue) : '');
  }, [savedValue, modelName]);

  const commit = () => {
    onPersist(modelName, draft);
  };

  return (
    <TextField
      type="number"
      size="small"
      placeholder="0"
      value={draft}
      disabled={!enabled || saving}
      inputProps={{ min: MIN_LLM_MAX_CONCURRENT, max: MAX_LLM_MAX_CONCURRENT, step: 1 }}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          commit();
          (e.target as HTMLInputElement).blur();
        }
      }}
      sx={{ width: 88 }}
    />
  );
}

export function useLlmMaxConcurrentSettings(docRouterAccountApi: DocRouterAccountApi) {
  const [llmMaxConcurrentByModel, setLlmMaxConcurrentByModel] = useState<Record<string, number>>({});
  const [savingModel, setSavingModel] = useState<string | null>(null);
  const mapRef = useRef(llmMaxConcurrentByModel);

  useEffect(() => {
    mapRef.current = llmMaxConcurrentByModel;
  }, [llmMaxConcurrentByModel]);

  const loadMaxConcurrentSettings = useCallback(async () => {
    const settings = await docRouterAccountApi.getSystemSettings();
    setLlmMaxConcurrentByModel(settings.llm_max_concurrent_by_model ?? {});
  }, [docRouterAccountApi]);

  const persistMaxConcurrent = useCallback(
    async (modelName: string, rawValue: string) => {
      const parsed = rawValue.trim() === '' ? 0 : Number.parseInt(rawValue, 10);
      const clamped = Number.isFinite(parsed)
        ? Math.min(MAX_LLM_MAX_CONCURRENT, Math.max(MIN_LLM_MAX_CONCURRENT, Math.trunc(parsed)))
        : 0;

      const prev = mapRef.current;
      const next = { ...prev };
      if (clamped <= 0) {
        delete next[modelName];
      } else {
        next[modelName] = clamped;
      }

      const prevValue = prev[modelName] ?? 0;
      const nextValue = clamped <= 0 ? 0 : clamped;
      if (prevValue === nextValue) {
        return;
      }

      setSavingModel(modelName);
      try {
        const updated = await docRouterAccountApi.updateSystemSettings({
          llm_max_concurrent_by_model: next,
        });
        setLlmMaxConcurrentByModel(updated.llm_max_concurrent_by_model ?? {});
      } finally {
        setSavingModel(null);
      }
    },
    [docRouterAccountApi],
  );

  const createMaxConcurrentColumn = useCallback(
    ({ getModelName, isEnabled }: MaxConcurrentColumnOptions): GridColDef => ({
      field: 'max_concurrent',
      headerName: 'Max concurrent',
      width: 130,
      minWidth: 130,
      renderCell: (params: GridRenderCellParams) => {
        const modelName = getModelName(params.row);
        return (
          <MaxConcurrentCell
            modelName={modelName}
            savedValue={llmMaxConcurrentByModel[modelName]}
            enabled={isEnabled(params.row)}
            saving={savingModel === modelName}
            onPersist={persistMaxConcurrent}
          />
        );
      },
    }),
    [llmMaxConcurrentByModel, persistMaxConcurrent, savingModel],
  );

  return {
    loadMaxConcurrentSettings,
    createMaxConcurrentColumn,
  };
}
