'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { createTableApi, updateTableApi, listTagsApi, getTableApi } from '@/utils/api';
import { TableConfig, TableColumn, TableResponseFormat } from '@/types/tables';
import { Tag } from '@/types/index';
import { getApiErrorMsg } from '@/utils/api';
import TagSelector from './TagSelector';
import { toast } from 'react-toastify';
import { useRouter } from 'next/navigation';
import Editor from '@monaco-editor/react';
import InfoTooltip from '@/components/InfoTooltip';
import TableMapper from '@/components/TableMapper';

const defaultResponseFormat: TableResponseFormat = {
  columns: [],
  row_schema: {},
  column_mapping: {}
};

const TableCreate: React.FC<{ organizationId: string; tableId?: string }> = ({
  organizationId,
  tableId
}) => {
  const router = useRouter();
  const [currentTableId, setCurrentTableId] = useState<string | null>(null);
  const [currentTable, setCurrentTable] = useState<TableConfig>({
    name: '',
    response_format: defaultResponseFormat,
    tag_ids: []
  });
  const [isLoading, setIsLoading] = useState(false);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'columns' | 'mapper' | 'json'>('columns');
  const [jsonConfig, setJsonConfig] = useState('');

  // Load editing table if available (tableId is a table revision id)
  useEffect(() => {
    const loadTable = async () => {
      if (tableId) {
        try {
          setIsLoading(true);
          const table = await getTableApi({ organizationId, tableRevId: tableId });
          setCurrentTableId(table.table_id);
          setCurrentTable({
            name: table.name,
            response_format: {
              columns: table.response_format?.columns || [],
              row_schema: table.response_format?.row_schema || {},
              column_mapping: table.response_format?.column_mapping || {}
            },
            tag_ids: table.tag_ids || []
          });
          setSelectedTagIds(table.tag_ids || []);
        } catch (error) {
          toast.error(`Error loading table for editing: ${getApiErrorMsg(error)}`);
        } finally {
          setIsLoading(false);
        }
      }
    };
    loadTable();
  }, [tableId, organizationId]);

  const loadTags = useCallback(async () => {
    try {
      const response = await listTagsApi({ organizationId });
      setAvailableTags(response.tags);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading tags';
      toast.error('Error: ' + errorMsg);
    }
  }, [organizationId]);

  useEffect(() => {
    loadTags();
  }, [loadTags]);

  // Keep JSON editor in sync
  useEffect(() => {
    setJsonConfig(JSON.stringify(currentTable.response_format, null, 2));
  }, [currentTable]);

  // Prune column mappings if columns changed (remove orphaned mappings)
  useEffect(() => {
    const colKeys = new Set((currentTable.response_format.columns || []).map(c => c.key));
    const mappings = currentTable.response_format.column_mapping || {};
    const pruned = Object.fromEntries(Object.entries(mappings).filter(([k]) => colKeys.has(k)));
    if (Object.keys(pruned).length !== Object.keys(mappings).length) {
      setCurrentTable(prev => ({
        ...prev,
        response_format: {
          ...prev.response_format,
          column_mapping: pruned
        }
      }));
    }
  }, [currentTable.response_format.columns]);

  const handleJsonChange = (value: string | undefined) => {
    if (!value) return;
    try {
      const parsed = JSON.parse(value) as TableResponseFormat;

      // Basic validation
      if (parsed.columns && !Array.isArray(parsed.columns)) {
        toast.error('Error: response_format.columns must be an array');
        return;
      }

      setCurrentTable(prev => ({
        ...prev,
        response_format: {
          columns: parsed.columns || [],
          row_schema: parsed.row_schema || {},
          column_mapping: parsed.column_mapping || {}
        }
      }));
    } catch (error) {
      toast.error(`Error: Invalid JSON syntax: ${error}`);
    }
  };

  const saveTable = async () => {
    try {
      setIsLoading(true);

      const tableToSave: TableConfig = {
        ...currentTable,
        tag_ids: selectedTagIds
      };

      if (currentTableId) {
        await updateTableApi({
          organizationId,
          tableId: currentTableId,
          table: tableToSave
        });
      } else {
        await createTableApi({
          organizationId,
          ...tableToSave
        });
      }

      // Reset form
      setCurrentTable({
        name: '',
        response_format: defaultResponseFormat,
        tag_ids: []
      });
      setCurrentTableId(null);
      setSelectedTagIds([]);

      router.push(`/orgs/${organizationId}/tables`);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving table';
      toast.error('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  // Columns builder UI handlers
  const addColumn = () => {
    const newCol: TableColumn = {
      key: `col_${Date.now()}`,
      name: 'New Column',
      width: 150,
      editable: true
    };
    setCurrentTable(prev => ({
      ...prev,
      response_format: {
        ...prev.response_format,
        columns: [...(prev.response_format.columns || []), newCol]
      }
    }));
  };

  const updateColumn = (index: number, updates: Partial<TableColumn>) => {
    setCurrentTable(prev => {
      const cols = [...(prev.response_format.columns || [])];
      cols[index] = { ...cols[index], ...updates };
      return {
        ...prev,
        response_format: { ...prev.response_format, columns: cols }
      };
    });
  };

  const deleteColumn = (index: number) => {
    setCurrentTable(prev => {
      const cols = [...(prev.response_format.columns || [])];
      cols.splice(index, 1);
      return {
        ...prev,
        response_format: { ...prev.response_format, columns: cols }
      };
    });
  };

  return (
    <div className="p-4 w-full">
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="hidden md:flex items-center gap-2 mb-4">
          <h2 className="text-xl font-bold">
            {currentTableId ? 'Edit Table' : 'Create Table'}
          </h2>
          <InfoTooltip
            title="About Tables"
            content={
              <>
                <p className="mb-2">
                  Tables define columnar outputs and row schema for structured document data.
                </p>
                <ul className="list-disc list-inside space-y-1 mb-2">
                  <li>Define clear keys and labels for each column</li>
                  <li>Mark columns editable when they should be user-correctable</li>
                  <li>Use JSON editor for advanced row schema and mappings</li>
                </ul>
              </>
            }
          />
        </div>

        <div className="space-y-4">
          {/* Table Name + Actions */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1 md:w-1/2 md:max-w-[calc(50%-1rem)]">
              <input
                type="text"
                className="w-full p-2 border rounded"
                value={currentTable.name}
                onChange={e => setCurrentTable({ ...currentTable, name: e.target.value })}
                placeholder="Table Name"
                disabled={isLoading}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setCurrentTableId(null);
                  setCurrentTable({
                    name: '',
                    response_format: defaultResponseFormat,
                    tag_ids: []
                  });
                  setSelectedTagIds([]);
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
                disabled={isLoading}
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!currentTable.name) {
                    toast.error('Please fill in the table name');
                    return;
                  }
                  saveTable();
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={isLoading}
              >
                {currentTableId ? 'Update Table' : 'Save Table'}
              </button>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="border-b border-gray-200 mb-4">
            <div className="flex gap-8">
              <button
                type="button"
                onClick={() => setActiveTab('columns')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  activeTab === 'columns'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Columns Builder
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('mapper')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  activeTab === 'mapper'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Mapper
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('json')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  activeTab === 'json'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                JSON Config
              </button>
            </div>
          </div>

          {/* Tab Content */}
          <div className="space-y-4">
            {activeTab === 'columns' ? (
              <div className="border rounded-lg bg-white p-4">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="font-semibold">Columns</h3>
                  <button
                    type="button"
                    onClick={addColumn}
                    className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Add Column
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-600 border-b">
                        <th className="py-2 pr-4">Key</th>
                        <th className="py-2 pr-4">Label</th>
                        <th className="py-2 pr-4">Width</th>
                        <th className="py-2 pr-4">Editable</th>
                        <th className="py-2 pr-4 w-24">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(currentTable.response_format.columns || []).map((col, idx) => (
                        <tr key={col.key} className="border-b">
                          <td className="py-2 pr-4">
                            <input
                              type="text"
                              value={col.key}
                              onChange={e => updateColumn(idx, { key: e.target.value })}
                              className="w-full p-2 border rounded"
                            />
                          </td>
                          <td className="py-2 pr-4">
                            <input
                              type="text"
                              value={col.name}
                              onChange={e => updateColumn(idx, { name: e.target.value })}
                              className="w-full p-2 border rounded"
                            />
                          </td>
                          <td className="py-2 pr-4">
                            <input
                              type="number"
                              value={col.width ?? 150}
                              onChange={e => updateColumn(idx, { width: Number(e.target.value) })}
                              className="w-24 p-2 border rounded"
                              min={50}
                            />
                          </td>
                          <td className="py-2 pr-4">
                            <input
                              type="checkbox"
                              checked={!!col.editable}
                              onChange={e => updateColumn(idx, { editable: e.target.checked })}
                            />
                          </td>
                          <td className="py-2 pr-4">
                            <button
                              type="button"
                              onClick={() => deleteColumn(idx)}
                              className="px-3 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100"
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                      {(!currentTable.response_format.columns ||
                        currentTable.response_format.columns.length === 0) && (
                        <tr>
                          <td colSpan={5} className="py-6 text-center text-gray-500">
                            No columns defined. Click &quot;Add Column&quot; to create your first column.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 text-xs text-gray-600">
                  Tip: Use the JSON Config tab to edit row_schema and column_mapping.
                </div>
              </div>
            ) : activeTab === 'mapper' ? (
              <TableMapper
                organizationId={organizationId}
                selectedTagIds={selectedTagIds}
                columns={currentTable.response_format.columns || []}
                columnMappings={currentTable.response_format.column_mapping || {}}
                onMappingChange={(mappings) => {
                  setCurrentTable(prev => ({
                    ...prev,
                    response_format: {
                      ...prev.response_format,
                      column_mapping: mappings
                    }
                  }));
                }}
              />
            ) : (
              <div className="h-[calc(100vh-300px)] border rounded">
                <Editor
                  height="100%"
                  defaultLanguage="json"
                  value={jsonConfig}
                  onChange={handleJsonChange}
                  options={{
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    wordWrap: 'on',
                    lineNumbers: 'on',
                    folding: true,
                    renderValidationDecorations: 'on'
                  }}
                  theme="vs-light"
                />
              </div>
            )}
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Tags</label>
            <div className="w-full md:w-1/4">
              <TagSelector
                availableTags={availableTags}
                selectedTagIds={selectedTagIds}
                onChange={setSelectedTagIds}
                disabled={isLoading}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TableCreate;