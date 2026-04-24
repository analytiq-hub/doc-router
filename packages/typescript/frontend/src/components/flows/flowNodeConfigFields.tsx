import React, { useMemo } from 'react';
import { Box, FormControlLabel, MenuItem, Switch, TextField } from '@mui/material';
import Editor from '@monaco-editor/react';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';

function getSchemaProps(schema: unknown): Record<string, unknown> {
  const props = (schema as { properties?: unknown } | null | undefined)?.properties;
  return props && typeof props === 'object' ? (props as Record<string, unknown>) : {};
}

export const FlowNodeSettingsFields: React.FC<{
  node: FlowNode;
  onChange: (patch: Partial<FlowNode>) => void;
  readOnly?: boolean;
}> = ({ node, onChange, readOnly = false }) => {
  if (readOnly) {
    return (
      <>
        <TextField label="Name" value={node.name} fullWidth size="small" className="mb-3" InputProps={{ readOnly: true }} />
        <TextField
          label="Disabled"
          value={node.disabled ? 'yes' : 'no'}
          fullWidth
          size="small"
          className="mb-3"
          InputProps={{ readOnly: true }}
        />
        <TextField
          label="On error"
          value={node.on_error ?? 'stop'}
          fullWidth
          size="small"
          className="mb-4"
          InputProps={{ readOnly: true }}
        />
      </>
    );
  }
  return (
    <>
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
    </>
  );
};

export const FlowNodeParameterFields: React.FC<{
  node: FlowNode;
  nodeType: FlowNodeType | null;
  onChange: (patch: Partial<FlowNode>) => void;
  readOnly?: boolean;
}> = ({ node, nodeType, onChange, readOnly = false }) => {
  const schemaProps = useMemo(() => getSchemaProps(nodeType?.parameter_schema), [nodeType]);
  const params = node.parameters || {};

  const renderParamField = (key: string, subschema: { type?: string; enum?: unknown[] } & Record<string, unknown>) => {
    const t = subschema?.type;
    const v = (params as Record<string, unknown>)[key];
    const isCode = key === 'python_code' || key === 'js_code' || key === 'ts_code';

    if (isCode || t === 'object' || t === 'array') {
      const lang = key === 'python_code' ? 'python' : key === 'ts_code' ? 'typescript' : key === 'js_code' ? 'javascript' : 'json';
      const textValue =
        typeof v === 'string'
          ? v
          : v == null
            ? t === 'object' || t === 'array'
              ? JSON.stringify(v ?? (t === 'array' ? [] : {}), null, 2)
              : ''
            : JSON.stringify(v, null, 2);
      return (
        <Box key={key} className="min-h-0 flex-1">
          <div className="text-xs font-semibold text-gray-600 mb-1">{key}</div>
          <Editor
            height="400px"
            language={lang}
            value={textValue}
            onChange={(val) => {
              if (readOnly) return;
              if (isCode) {
                onChange({ parameters: { ...params, [key]: val ?? '' } });
                return;
              }
              try {
                const parsed = JSON.parse(val ?? 'null');
                onChange({ parameters: { ...params, [key]: parsed } });
              } catch {
                // ignore until valid
              }
            }}
            options={{
              minimap: { enabled: false },
              fontSize: 12,
              scrollBeyondLastLine: false,
              readOnly,
            }}
          />
        </Box>
      );
    }

    if (t === 'boolean') {
      return readOnly ? (
        <TextField
          key={key}
          label={key}
          value={Boolean(v) ? 'true' : 'false'}
          fullWidth
          size="small"
          className="mb-3"
          InputProps={{ readOnly: true }}
        />
      ) : (
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
      if (readOnly) {
        return (
          <TextField
            key={key}
            label={key}
            value={v == null || v === '' ? '' : String(v)}
            fullWidth
            size="small"
            className="mb-3"
            InputProps={{ readOnly: true }}
          />
        );
      }
      return (
        <TextField
          key={key}
          label={key}
          type="number"
          value={typeof v === 'number' ? v : (v as number | '') ?? ''}
          onChange={(e) => onChange({ parameters: { ...params, [key]: Number(e.target.value) } })}
          fullWidth
          size="small"
          className="mb-3"
        />
      );
    }

    if (subschema?.enum && Array.isArray(subschema.enum)) {
      return readOnly ? (
        <TextField
          key={key}
          label={key}
          value={v == null ? '' : String(v)}
          fullWidth
          size="small"
          className="mb-3"
          InputProps={{ readOnly: true }}
        />
      ) : (
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
          {subschema.enum.map((opt: unknown) => (
            <MenuItem key={String(opt)} value={opt as string | number}>
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
        value={typeof v === 'string' ? v : (v as string) ?? ''}
        onChange={(e) => onChange({ parameters: { ...params, [key]: e.target.value } })}
        fullWidth
        size="small"
        className="mb-3"
        InputProps={readOnly ? { readOnly: true } : undefined}
      />
    );
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1">
      {Object.entries(schemaProps).map(([k, subschema]) => renderParamField(k, subschema as { type?: string; enum?: unknown[] }))}
      {Object.keys(schemaProps).length === 0 && (
        <div className="text-sm text-[#6b7280]">No parameters for this node type.</div>
      )}
    </div>
  );
};
