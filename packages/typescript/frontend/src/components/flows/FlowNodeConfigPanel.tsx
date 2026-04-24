import React, { useMemo } from 'react';
import { Box, Switch, TextField, FormControlLabel, MenuItem } from '@mui/material';
import Editor from '@monaco-editor/react';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';

function getSchemaProps(schema: any): Record<string, any> {
  const props = schema?.properties;
  return props && typeof props === 'object' ? props : {};
}

const FlowNodeConfigPanel: React.FC<{
  node: FlowNode | null;
  nodeType: FlowNodeType | null;
  onChange: (patch: Partial<FlowNode>) => void;
}> = ({ node, nodeType, onChange }) => {
  const schemaProps = useMemo(() => getSchemaProps(nodeType?.parameter_schema), [nodeType]);

  if (!node) {
    return (
      <div className="h-full border-l border-gray-200 bg-white p-3">
        <div className="text-sm text-gray-500">Select a node to configure.</div>
      </div>
    );
  }

  const params = node.parameters || {};

  const renderParamField = (key: string, subschema: any) => {
    const t = subschema?.type;
    const v = (params as any)[key];
    const isCode = key === 'python_code' || key === 'js_code' || key === 'ts_code';

    if (isCode || t === 'object' || t === 'array') {
      const lang = key === 'python_code' ? 'python' : key === 'ts_code' ? 'typescript' : key === 'js_code' ? 'javascript' : 'json';
      const textValue =
        typeof v === 'string'
          ? v
          : v == null
            ? (t === 'object' || t === 'array' ? JSON.stringify(v ?? (t === 'array' ? [] : {}), null, 2) : '')
            : JSON.stringify(v, null, 2);
      return (
        <Box key={key} className="mb-4">
          <div className="text-xs font-semibold text-gray-600 mb-1">{key}</div>
          <Editor
            height="300px"
            language={lang}
            value={textValue}
            onChange={(val) => {
              if (isCode) {
                onChange({ parameters: { ...params, [key]: val ?? '' } });
                return;
              }
              try {
                const parsed = JSON.parse(val ?? 'null');
                onChange({ parameters: { ...params, [key]: parsed } });
              } catch {
                // ignore invalid JSON until user fixes it
              }
            }}
            options={{
              minimap: { enabled: false },
              fontSize: 12,
              scrollBeyondLastLine: false,
            }}
          />
        </Box>
      );
    }

    if (t === 'boolean') {
      return (
        <FormControlLabel
          key={key}
          control={
            <Switch
              checked={Boolean(v)}
              onChange={(e) => onChange({ parameters: { ...params, [key]: e.target.checked } })}
            />
          }
          label={key}
        />
      );
    }

    if (t === 'number' || t === 'integer') {
      return (
        <TextField
          key={key}
          label={key}
          type="number"
          value={typeof v === 'number' ? v : v ?? ''}
          onChange={(e) => onChange({ parameters: { ...params, [key]: Number(e.target.value) } })}
          fullWidth
          size="small"
          className="mb-3"
        />
      );
    }

    if (subschema?.enum && Array.isArray(subschema.enum)) {
      return (
        <TextField
          key={key}
          select
          label={key}
          value={v ?? ''}
          onChange={(e) => onChange({ parameters: { ...params, [key]: e.target.value } })}
          fullWidth
          size="small"
          className="mb-3"
        >
          {subschema.enum.map((opt: any) => (
            <MenuItem key={String(opt)} value={opt}>
              {String(opt)}
            </MenuItem>
          ))}
        </TextField>
      );
    }

    return (
      <TextField
        key={key}
        label={key}
        value={typeof v === 'string' ? v : v ?? ''}
        onChange={(e) => onChange({ parameters: { ...params, [key]: e.target.value } })}
        fullWidth
        size="small"
        className="mb-3"
      />
    );
  };

  return (
    <div className="h-full overflow-auto border-l border-gray-200 bg-white p-3">
      <div className="text-xs text-gray-500">{nodeType?.label ?? node.type}</div>
      <div className="text-sm font-semibold text-gray-900 mb-3">Node config</div>

      <TextField
        label="Name"
        value={node.name}
        onChange={(e) => onChange({ name: e.target.value })}
        fullWidth
        size="small"
        className="mb-3"
      />

      <FormControlLabel
        control={<Switch checked={Boolean(node.disabled)} onChange={(e) => onChange({ disabled: e.target.checked })} />}
        label="Disabled"
      />

      <TextField
        select
        label="On error"
        value={node.on_error ?? 'stop'}
        onChange={(e) => onChange({ on_error: e.target.value as 'stop' | 'continue' })}
        fullWidth
        size="small"
        className="mb-4"
      >
        <MenuItem value="stop">stop</MenuItem>
        <MenuItem value="continue">continue</MenuItem>
      </TextField>

      <div className="mt-2">
        <div className="text-xs font-semibold text-gray-600 mb-2">Parameters</div>
        {Object.entries(schemaProps).map(([k, subschema]) => renderParamField(k, subschema))}
        {Object.keys(schemaProps).length === 0 && (
          <div className="text-sm text-gray-500">No parameters for this node.</div>
        )}
      </div>
    </div>
  );
};

export default FlowNodeConfigPanel;

