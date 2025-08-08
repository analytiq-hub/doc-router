'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { listPromptsApi, listSchemasApi, getSchemaApi } from '@/utils/api';
import { TableColumn } from '@/types/tables';
import { FieldMapping, FieldMappingSource } from '@/types/forms';
import { toast } from 'react-toastify';
import { getApiErrorMsg } from '@/utils/api';

type SchemaField = {
  name: string;
  path: string;
  type: string;
  description?: string;
  promptRevId: string;
  promptName: string;
  depth: number;
  isExpandable: boolean;
  parentPath?: string;
};

type SchemaFieldDef = {
  type: string;
  properties?: Record<string, SchemaFieldDef>;
  items?: {
    type: string;
    properties?: Record<string, SchemaFieldDef>;
  };
  description?: string;
};

interface TableMapperProps {
  organizationId: string;
  selectedTagIds: string[];
  columns: TableColumn[];
  columnMappings: Record<string, FieldMapping>;
  onMappingChange: (mappings: Record<string, FieldMapping>) => void;
}

const TableMapper: React.FC<TableMapperProps> = ({
  organizationId,
  selectedTagIds,
  columns,
  columnMappings,
  onMappingChange
}) => {
  const [schemaFields, setSchemaFields] = useState<SchemaField[]>([]);
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set());
  const [expandedFields, setExpandedFields] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);

  // Load LLM schemas (via prompts) matching ANY of the selected tags
  const loadSchemasByTags = useCallback(async () => {
    if (selectedTagIds.length === 0) {
      setSchemaFields([]);
      return;
    }
    setLoading(true);
    try {
      const allSchemas = await listSchemasApi({ organizationId, limit: 200 });

      const promptsMap = new Map<string, { prompt_revid: string; name: string; schema_id?: string }>();
      for (const tagId of selectedTagIds) {
        try {
          const resp = await listPromptsApi({ organizationId, tag_ids: tagId, limit: 200 });
          resp.prompts.forEach(p => promptsMap.set(p.prompt_revid, p));
        } catch {
          // ignore per-tag errors
        }
      }

      const prompts = Array.from(promptsMap.values()).filter(p => p.schema_id);
      const schemaById: Record<string, any> = {};
      await Promise.all(
        prompts.map(async (p) => {
          const match = allSchemas.schemas.find(s => s.schema_id === p.schema_id);
          if (!match) return;
          try {
            const full = await getSchemaApi({ organizationId, schemaId: match.schema_revid });
            schemaById[p.schema_id!] = full;
          } catch {
            // ignore
          }
        })
      );

      const out: SchemaField[] = [];
      prompts.forEach(p => {
        const schema = p.schema_id ? schemaById[p.schema_id] : null;
        const props = schema?.response_format?.json_schema?.schema?.properties || {};
        const parse = (defs: Record<string, SchemaFieldDef>, basePath = '', depth = 0, parentPath?: string) => {
          Object.entries(defs).forEach(([fieldName, def]) => {
            const fullPath = basePath ? `${basePath}.${fieldName}` : fieldName;
            const hasObj = def.type === 'object' && def.properties;
            const hasArrayObj = def.type === 'array' && def.items?.type === 'object' && def.items.properties;
            const isExpandable = Boolean(hasObj || hasArrayObj);

            out.push({
              name: fieldName,
              path: fullPath,
              type: def.type,
              description: def.description,
              promptRevId: p.prompt_revid,
              promptName: p.name,
              depth,
              isExpandable,
              parentPath
            });

            if (hasObj && def.properties) parse(def.properties, fullPath, depth + 1, fullPath);
            if (hasArrayObj && def.items?.properties) parse(def.items.properties, `${fullPath}[0]`, depth + 1, fullPath);
          });
        };
        parse(props);
      });

      setSchemaFields(out);
    } catch (error) {
      toast.error(`Error loading schemas: ${getApiErrorMsg(error)}`);
    } finally {
      setLoading(false);
    }
  }, [organizationId, selectedTagIds]);

  useEffect(() => {
    loadSchemasByTags();
  }, [loadSchemasByTags]);

  const grouped = useMemo(() => {
    return schemaFields
      .filter(f =>
        f.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        f.promptName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (f.description || '').toLowerCase().includes(searchTerm.toLowerCase())
      )
      .reduce((acc, f) => {
        (acc[f.promptRevId] ||= { promptName: f.promptName, fields: [] as SchemaField[] }).fields.push(f);
        return acc;
      }, {} as Record<string, { promptName: string; fields: SchemaField[] }>);
  }, [schemaFields, searchTerm]);

  const toggleFieldExpansion = (f: SchemaField) => {
    const key = `${f.promptRevId}-${f.path}`;
    setExpandedFields(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const isFieldVisible = (f: SchemaField): boolean => {
    if (!f.parentPath) return true;
    const parts = f.parentPath.split('.');
    for (let i = 1; i <= parts.length; i++) {
      const parentPath = parts.slice(0, i).join('.');
      if (!expandedFields.has(`${f.promptRevId}-${parentPath}`)) return false;
    }
    return true;
  };

  // Drop handlers for mapping schema fields to table columns
  const handleDrop = (e: React.DragEvent, colKey: string) => {
    e.preventDefault();
    const raw = e.dataTransfer.getData('text/plain');
    if (!raw) return;
    let data: any;
    try { data = JSON.parse(raw); } catch { return; }
    if (data?.type !== 'schema-field') return;
    const field = data.field as SchemaField;

    const newSource: FieldMappingSource = {
      promptRevId: field.promptRevId,
      promptName: field.promptName,
      schemaFieldPath: field.path,
      schemaFieldName: field.name,
      schemaFieldType: field.type
    };

    const existing = columnMappings[colKey];
    if (existing) {
      const updated: FieldMapping = {
        ...existing,
        sources: [...existing.sources, newSource],
        mappingType: existing.sources.length > 0 ? 'concatenated' : 'direct',
        concatenationSeparator: existing.concatenationSeparator || ' '
      };
      onMappingChange({ ...columnMappings, [colKey]: updated });
      toast.success(`Added ${field.name} to ${colKey}`);
    } else {
      const mapping: FieldMapping = {
        sources: [newSource],
        mappingType: 'direct',
        concatenationSeparator: ' '
      };
      onMappingChange({ ...columnMappings, [colKey]: mapping });
      toast.success(`Mapped ${field.name} to ${colKey}`);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  const removeMapping = (colKey: string) => {
    const next = { ...columnMappings };
    delete next[colKey];
    onMappingChange(next);
    toast.success('Mapping removed');
  };

  const removeSource = (colKey: string, index: number) => {
    const m = columnMappings[colKey];
    if (!m) return;
    const nextSources = m.sources.filter((_, i) => i !== index);
    if (nextSources.length === 0) {
      removeMapping(colKey);
    } else {
      onMappingChange({
        ...columnMappings,
        [colKey]: {
          ...m,
          sources: nextSources,
          mappingType: nextSources.length === 1 ? 'direct' : 'concatenated'
        }
      });
    }
  };

  return (
    <div className="h-[calc(100vh-300px)] flex gap-4">
      {/* Left: Schema fields */}
      <div className="w-1/2 border rounded-lg bg-white overflow-hidden flex flex-col">
        <div className="p-4 border-b bg-gray-50">
          <h3 className="font-semibold text-gray-900 mb-3">LLM Schema Fields</h3>
          <input
            type="text"
            placeholder="Search fields..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          {loading ? (
            <div className="text-center text-gray-500 py-8">Loading schemas…</div>
          ) : selectedTagIds.length === 0 ? (
            <div className="text-center text-gray-500 py-8">Select tags to see available schemas</div>
          ) : Object.keys(grouped).length === 0 ? (
            <div className="text-center text-gray-500 py-8">No prompts with schemas found for selected tags</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(grouped).map(([promptRevId, { promptName, fields }]) => (
                <div key={promptRevId} className="border rounded">
                  <button
                    onClick={() =>
                      setExpandedPrompts(prev =>
                        prev.has(promptRevId)
                          ? new Set([...prev].filter(x => x !== promptRevId))
                          : new Set([...prev, promptRevId])
                      )
                    }
                    className="w-full px-3 py-2 flex items-center justify-between bg-gray-50 hover:bg-gray-100 text-left"
                  >
                    <span className="font-medium text-sm">{promptName}</span>
                    <span className="text-xs text-gray-500">{fields.length} fields</span>
                  </button>
                  {expandedPrompts.has(promptRevId) && (
                    <div className="p-2 space-y-1">
                      {fields.filter(isFieldVisible).map(field => (
                        <div
                          key={field.path}
                          className="p-2 bg-white border rounded flex items-center gap-2"
                          style={{ marginLeft: `${field.depth * 16}px` }}
                          draggable={!field.isExpandable}
                          onDragStart={(e) => {
                            if (field.isExpandable) return;
                            e.dataTransfer.setData('text/plain', JSON.stringify({ type: 'schema-field', field }));
                            e.dataTransfer.effectAllowed = 'copy';
                          }}
                        >
                          <button
                            className="text-gray-500"
                            onClick={() => toggleFieldExpansion(field)}
                            disabled={!field.isExpandable}
                            title={field.isExpandable ? 'Expand/Collapse' : ''}
                          >
                            {field.isExpandable ? (expandedFields.has(`${field.promptRevId}-${field.path}`) ? '▾' : '▸') : '•'}
                          </button>
                          <span className="font-medium text-sm">{field.name}</span>
                          <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-800">{field.type}</span>
                          {field.description && <span className="text-xs text-gray-500 truncate">{field.description}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right: Table columns */}
      <div className="w-1/2 border rounded-lg bg-white overflow-hidden flex flex-col">
        <div className="p-4 border-b bg-gray-50">
          <h3 className="font-semibold text-gray-900">Table Columns</h3>
          <p className="text-sm text-gray-500 mt-1">Drop schema fields onto columns to map</p>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {columns.length === 0 ? (
            <div className="text-center py-8 text-gray-500">Add columns in the Columns Builder tab</div>
          ) : (
            <div className="space-y-2">
              {columns.map((col) => {
                const mapping = columnMappings[col.key];
                return (
                  <div
                    key={col.key}
                    className={`p-3 border-2 border-dashed rounded-lg ${mapping ? 'border-green-300 bg-green-50' : 'border-gray-300 hover:border-gray-400'}`}
                    onDrop={(e) => handleDrop(e, col.key)}
                    onDragOver={handleDragOver}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{col.name}</span>
                        <span className="text-xs text-gray-500">({col.key})</span>
                        {mapping && <span className="text-green-600 text-xs font-medium">mapped</span>}
                      </div>
                      {mapping && (
                        <button
                          onClick={() => removeMapping(col.key)}
                          className="text-red-600 text-sm"
                          title="Remove all mappings"
                        >
                          Remove
                        </button>
                      )}
                    </div>

                    {mapping && (
                      <div className="mt-2 p-2 bg-white border rounded text-xs">
                        <div className="space-y-1">
                          {mapping.sources.map((s, idx) => (
                            <div key={idx} className="flex items-center justify-between">
                              <div className="flex-1">
                                <span className="font-medium text-green-700">{s.schemaFieldName}</span>
                                <span className="text-gray-500 ml-2">from {s.promptName}</span>
                              </div>
                              <button
                                onClick={() => removeSource(col.key, idx)}
                                className="text-red-500 hover:text-red-700"
                                title="Remove this source"
                              >
                                ✕
                              </button>
                            </div>
                          ))}
                        </div>
                        {mapping.mappingType === 'concatenated' && (
                          <div className="mt-2 pt-2 border-t">
                            <span className="text-gray-600">
                              Separator: &quot;{mapping.concatenationSeparator || ' '}&quot;
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TableMapper;
