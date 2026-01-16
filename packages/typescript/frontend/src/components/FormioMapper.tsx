'use client';

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Prompt } from '@docrouter/sdk';
import { FieldMapping, FieldMappingSource } from '@docrouter/sdk';

import { FormComponent, FormField } from '@/types/ui';
import { getApiErrorMsg } from '@/utils/api';
import { toast } from 'react-toastify';
import { 
  ChevronDownIcon, 
  ChevronRightIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
  LinkIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';

interface FormioMapperProps {
  organizationId: string;
  selectedTagIds: string[];
  formComponents: FormComponent[];
  fieldMappings: Record<string, FieldMapping>;
  onMappingChange: (mappings: Record<string, FieldMapping>) => void;
  readOnly?: boolean;
}

interface MappedSchemaField {
  name: string;
  path: string;
  type: string;
  description?: string;
  promptRevId: string;
  promptName: string;
  depth: number; // Nesting level for indentation
  isExpandable: boolean; // Whether this field has children (object/array)
  parentPath?: string; // Path of parent field for hierarchy
}

// Add interface for schema field definition (for JSON Schema parsing)
interface JsonSchemaFieldDefinition {
  type: string;
  properties?: Record<string, JsonSchemaFieldDefinition>;
  items?: {
    type: string;
    properties?: Record<string, JsonSchemaFieldDefinition>;
  };
  description?: string;
}

const FormioMapper: React.FC<FormioMapperProps> = ({
  readOnly = false,
  organizationId,
  selectedTagIds,
  formComponents,
  fieldMappings,
  onMappingChange
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [schemaFields, setSchemaFields] = useState<MappedSchemaField[]>([]);
  const [formFields, setFormFields] = useState<FormField[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set());
  const [expandedFields, setExpandedFields] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [draggedField, setDraggedField] = useState<MappedSchemaField | null>(null);
  const previousFormFieldsRef = useRef<FormField[]>([]);

  // Load prompts and schemas based on selected tags
  const loadPromptsAndSchemas = useCallback(async () => {
    if (selectedTagIds.length === 0) {
      setSchemaFields([]);
      return;
    }

    setLoading(true);
    try {
      // First, fetch all schemas to get schema_revid mappings
      const allSchemasResponse = await docRouterOrgApi.listSchemas({
        limit: 100
      });

      // Fetch prompts for each tag individually and merge results
      // This is needed because backend uses $all (requires ALL tags) but we want ANY tags
      const allPrompts = new Map<string, Prompt>();
      
      for (const tagId of selectedTagIds) {
        try {
          const promptsResponse = await docRouterOrgApi.listPrompts({
            tag_ids: tagId, // Single tag ID
            limit: 100
          });
          
          // Add prompts to map to avoid duplicates
          promptsResponse.prompts.forEach(prompt => {
            allPrompts.set(prompt.prompt_revid, prompt);
          });
        } catch (error) {
          console.error(`Error fetching prompts for tag ${tagId}:`, error);
        }
      }
      
      // Also fetch prompts without tag filtering to include untagged prompts if needed
      if (selectedTagIds.length === 0) {
        const promptsResponse = await docRouterOrgApi.listPrompts({
          limit: 100
        });
        promptsResponse.prompts.forEach(prompt => {
          allPrompts.set(prompt.prompt_revid, prompt);
        });
      }

      const uniquePrompts = Array.from(allPrompts.values());

      // Fetch schemas for prompts that have schema_id
      const schemaPromises = uniquePrompts
        .filter(prompt => prompt.schema_id)
        .map(async (prompt) => {
          try {
            // Find the matching schema with the latest version
            const matchingSchemas = allSchemasResponse.schemas.filter(s => 
              s.schema_id === prompt.schema_id
            );
            
            if (matchingSchemas.length === 0) {
              console.warn(`No schema found with id ${prompt.schema_id}`);
              return {};
            }

            // Fetch the full schema using schema_revid
            const schema = await docRouterOrgApi.getSchema({
              schemaRevId: matchingSchemas[0].schema_revid
            });
            return { [prompt.schema_id!]: schema };
          } catch (error) {
            console.error(`Error loading schema ${prompt.schema_id}:`, error);
            return {};
          }
        });

      const schemaResults = await Promise.all(schemaPromises);
      const combinedSchemas = schemaResults.reduce((acc, curr) => ({ ...acc, ...curr }), {});

      // Parse schema fields recursively
      const allSchemaFields: MappedSchemaField[] = [];
      uniquePrompts.forEach(prompt => {
        if (prompt.schema_id && combinedSchemas[prompt.schema_id]) {
          const schema = combinedSchemas[prompt.schema_id];
          const properties = schema.response_format.json_schema.schema.properties;
          
          // Recursive function to parse nested properties
          const parseProperties = (props: Record<string, JsonSchemaFieldDefinition>, basePath: string = '', depth: number = 0, parentPath?: string) => {
            Object.entries(props).forEach(([fieldName, fieldDef]) => {
              const fullPath = basePath ? `${basePath}.${fieldName}` : fieldName;
              const displayName = fieldName; // Show only the field name, not the full path
              
              // Check if this field is expandable (has children)
              const hasObjectChildren = fieldDef.type === 'object' && fieldDef.properties;
              const hasArrayChildren = fieldDef.type === 'array' && fieldDef.items?.type === 'object' && fieldDef.items.properties;
              const isExpandable = Boolean(hasObjectChildren || hasArrayChildren);
              
              // Add the current field
              allSchemaFields.push({
                name: displayName,
                path: fullPath,
                type: fieldDef.type,
                description: fieldDef.description,
                promptRevId: prompt.prompt_revid,
                promptName: prompt.name,
                depth: depth,
                isExpandable: isExpandable,
                parentPath: parentPath
              });

              // Recursively handle nested object properties
              if (hasObjectChildren && fieldDef.properties) {
                parseProperties(fieldDef.properties, fullPath, depth + 1, fullPath);
              }

              // Handle array of objects
              if (hasArrayChildren && fieldDef.items?.properties) {
                // Add array item properties with [n] notation
                parseProperties(fieldDef.items.properties, `${fullPath}[0]`, depth + 1, fullPath);
              }
            });
          };

          if (properties) {
            parseProperties(properties);
          }
        }
      });

      setSchemaFields(allSchemaFields);
    } catch (error) {
      console.error('Error loading prompts and schemas:', error);
      toast.error(`Error loading data: ${getApiErrorMsg(error)}`);
    } finally {
      setLoading(false);
    }
  }, [docRouterOrgApi, selectedTagIds]);

  // Parse form components into flat field list
  const parseFormFields = useCallback((components: FormComponent[], path: string[] = []): FormField[] => {
    const fields: FormField[] = [];

    components.forEach(component => {
      if (component.key && component.type) {
        // Skip layout components without data
        if (!['panel', 'fieldset', 'columns', 'tabs', 'well'].includes(component.type)) {
          fields.push({
            key: component.key,
            label: component.label || component.key,
            type: component.type,
            path: [...path, component.key]
          });
        }
      }

      // Recursively parse nested components
      if (component.components) {
        fields.push(...parseFormFields(component.components, [...path, component.key || '']));
      }
      if (component.columns) {
        component.columns.forEach((column: FormComponent) => {
          if (column.components) {
            fields.push(...parseFormFields(column.components, [...path, component.key || '']));
          }
        });
      }
      if (component.tabs) {
        component.tabs.forEach((tab: FormComponent) => {
          if (tab.components) {
            fields.push(...parseFormFields(tab.components, [...path, component.key || '']));
          }
        });
      }
    });

    return fields;
  }, []);

  // Update form fields when components change
  useEffect(() => {
    const newFormFields = parseFormFields(formComponents);
    setFormFields(newFormFields);
  }, [formComponents, parseFormFields]);

  // Detect potentially renamed fields by comparing labels and types
  const detectRenamedFields = useCallback((oldFields: FormField[], newFields: FormField[], orphanedMappings: string[]): Map<string, string> => {
    const renamedFields = new Map<string, string>(); // Maps old key to new key
    
    // Only consider orphaned mappings that might be renamed fields
    const orphanedFields = oldFields.filter(field => orphanedMappings.includes(field.key));
    
    orphanedFields.forEach(orphanedField => {
      // Look for new fields with similar labels or types that weren't previously mapped
      const candidates = newFields.filter(newField => 
        !Object.keys(fieldMappings).includes(newField.key) && // Not already mapped
        (
          // Same label (exact match)
          newField.label === orphanedField.label ||
          // Same type and similar label (fuzzy match)
          (newField.type === orphanedField.type && 
           newField.label.toLowerCase().includes(orphanedField.label.toLowerCase()) ||
           orphanedField.label.toLowerCase().includes(newField.label.toLowerCase()))
        )
      );
      
      // If we found exactly one candidate, it's likely a rename
      if (candidates.length === 1) {
        renamedFields.set(orphanedField.key, candidates[0].key);
      }
    });
    
    return renamedFields;
  }, [fieldMappings]);

  // Clean up orphaned mappings when form fields change (separate effect to avoid infinite loops)
  useEffect(() => {
    const currentFormFields = formFields;
    const previousFormFields = previousFormFieldsRef.current;
    
    // Update the ref for next time
    previousFormFieldsRef.current = currentFormFields;
    
    // Only process mapping cleanup if we have existing mappings and both current and previous fields
    if (Object.keys(fieldMappings).length === 0 || previousFormFields.length === 0 || currentFormFields.length === 0) {
      return;
    }
    
    // Check if form structure actually changed
    const previousKeys = new Set(previousFormFields.map(field => field.key));
    const currentKeys = new Set(currentFormFields.map(field => field.key));
    const keysChanged = previousKeys.size !== currentKeys.size || 
      Array.from(previousKeys).some(key => !currentKeys.has(key)) ||
      Array.from(currentKeys).some(key => !previousKeys.has(key));
    
    if (!keysChanged) {
      return; // No structural changes
    }
    
    // Clean up orphaned mappings when form fields are removed or renamed
    const mappedFieldKeys = Object.keys(fieldMappings);
    const orphanedMappings = mappedFieldKeys.filter(key => !currentKeys.has(key));
    
    if (orphanedMappings.length > 0) {
      console.log('Found orphaned mappings for removed/renamed fields:', orphanedMappings);
      
      // Try to detect renamed fields
      const renamedFields = detectRenamedFields(previousFormFields, currentFormFields, orphanedMappings);
      
      const cleanedMappings = { ...fieldMappings };
      let removedCount = 0;
      let renamedCount = 0;
      
      orphanedMappings.forEach(oldKey => {
        const newKey = renamedFields.get(oldKey);
        
        if (newKey) {
          // Field was renamed - migrate the mapping
          cleanedMappings[newKey] = cleanedMappings[oldKey];
          delete cleanedMappings[oldKey];
          renamedCount++;
          console.log(`Migrated mapping from '${oldKey}' to '${newKey}'`);
        } else {
          // Field was deleted - remove the mapping
          delete cleanedMappings[oldKey];
          removedCount++;
          console.log(`Removed mapping for deleted field '${oldKey}'`);
        }
      });
      
      // Update the mappings
      onMappingChange(cleanedMappings);
      
      // Notify user about the changes
      let message = '';
      if (renamedCount > 0 && removedCount > 0) {
        message = `Updated ${renamedCount} renamed field mapping(s) and removed ${removedCount} deleted field mapping(s)`;
      } else if (renamedCount > 0) {
        message = renamedCount === 1 
          ? 'Updated mapping for renamed field' 
          : `Updated mappings for ${renamedCount} renamed fields`;
      } else if (removedCount > 0) {
        message = removedCount === 1 
          ? 'Removed mapping for deleted field' 
          : `Removed mappings for ${removedCount} deleted fields`;
      }
      
      if (message) {
        toast.info(message);
      }
    }
  }, [formFields, fieldMappings, onMappingChange, detectRenamedFields]);

  // Load data when tags change
  useEffect(() => {
    loadPromptsAndSchemas();
  }, [loadPromptsAndSchemas]);

  // Filter schema fields based on search
  const filteredSchemaFields = schemaFields.filter(field =>
    field.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    field.promptName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    field.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Group schema fields by prompt
  const groupedSchemaFields = filteredSchemaFields.reduce((acc, field) => {
    if (!acc[field.promptRevId]) {
      acc[field.promptRevId] = {
        promptName: field.promptName,
        fields: []
      };
    }
    acc[field.promptRevId].fields.push(field);
    return acc;
  }, {} as Record<string, { promptName: string; fields: MappedSchemaField[] }>);

  // Handle drag start
  const handleDragStart = (e: React.DragEvent, field: MappedSchemaField) => {
    setDraggedField(field);
    e.dataTransfer.setData('text/plain', JSON.stringify({
      type: 'schema-field',
      field
    }));
    e.dataTransfer.effectAllowed = 'copy';
  };

  // Handle drop on form field
  const handleDrop = (e: React.DragEvent, formField: FormField) => {
    e.preventDefault();
    const data = JSON.parse(e.dataTransfer.getData('text/plain'));
    
    if (data.type === 'schema-field') {
      const schemaField = data.field as MappedSchemaField;
      
      // Check type compatibility for string fields (most flexible for concatenation)
      if (!isCompatibleType(schemaField.type, formField.type)) {
        toast.error(`Cannot map ${schemaField.type} field to ${formField.type} component`);
        return;
      }

      // Create new source
      const newSource: FieldMappingSource = {
        promptRevId: schemaField.promptRevId,
        promptName: schemaField.promptName,
        schemaFieldPath: schemaField.path,
        schemaFieldName: schemaField.name,
        schemaFieldType: schemaField.type
      };

      // Get existing mapping or create new one
      const existingMapping = fieldMappings[formField.key];
      
      if (existingMapping) {
        // Add to existing mapping (concatenation)
        const updatedMapping: FieldMapping = {
          ...existingMapping,
          sources: [...existingMapping.sources, newSource],
          mappingType: existingMapping.sources.length > 0 ? 'concatenated' : 'direct',
          concatenationSeparator: existingMapping.concatenationSeparator || ' '
        };
        
        onMappingChange({
          ...fieldMappings,
          [formField.key]: updatedMapping
        });
        
        toast.success(`Added ${schemaField.name} to ${formField.label} (${existingMapping.sources.length + 1} fields)`);
      } else {
        // Create new mapping
        const newMapping: FieldMapping = {
          sources: [newSource],
          mappingType: 'direct',
          concatenationSeparator: ' '
        };

        onMappingChange({
          ...fieldMappings,
          [formField.key]: newMapping
        });

        toast.success(`Mapped ${schemaField.name} to ${formField.label}`);
      }
    }
    setDraggedField(null);
  };

  // Handle drag over
  const handleDragOver = (e: React.DragEvent, formField: FormField) => {
    e.preventDefault();
    if (draggedField && isCompatibleType(draggedField.type, formField.type)) {
      e.dataTransfer.dropEffect = 'copy';
    } else {
      e.dataTransfer.dropEffect = 'none';
    }
  };

  // Remove entire mapping
  const removeMapping = (formFieldKey: string) => {
    const newMappings = { ...fieldMappings };
    delete newMappings[formFieldKey];
    onMappingChange(newMappings);
    toast.success('Mapping removed');
  };

  // Remove specific source from mapping
  const removeSource = (formFieldKey: string, sourceIndex: number) => {
    const mapping = fieldMappings[formFieldKey];
    if (!mapping) return;

    const newSources = mapping.sources.filter((_, index) => index !== sourceIndex);
    
    if (newSources.length === 0) {
      // Remove entire mapping if no sources left
      removeMapping(formFieldKey);
    } else {
      // Update mapping with remaining sources
      const updatedMapping: FieldMapping = {
        ...mapping,
        sources: newSources,
        mappingType: newSources.length === 1 ? 'direct' : 'concatenated'
      };
      
      onMappingChange({
        ...fieldMappings,
        [formFieldKey]: updatedMapping
      });
      
      toast.success('Source removed from mapping');
    }
  };

  // Check type compatibility
  const isCompatibleType = (schemaType: string, formType: string): boolean => {
    const typeMapping: Record<string, string[]> = {
      'string': ['textfield', 'textarea', 'email', 'url', 'phoneNumber', 'select', 'radio', 'selectboxes'],
      'number': ['number', 'currency'],
      'integer': ['number', 'currency'],
      'boolean': ['checkbox', 'radio'],
      'array': ['select', 'selectboxes', 'datagrid', 'editgrid'],
      'object': ['container', 'datagrid', 'editgrid']
    };

    return typeMapping[schemaType]?.includes(formType) || false;
  };

  // Check if field should be visible based on parent expansion state
  const isFieldVisible = (field: MappedSchemaField): boolean => {
    if (!field.parentPath) return true; // Root level fields are always visible
    
    // Check if all parent paths are expanded
    const pathParts = field.parentPath.split('.');
    for (let i = 1; i <= pathParts.length; i++) {
      const parentPath = pathParts.slice(0, i).join('.');
      if (!expandedFields.has(`${field.promptRevId}-${parentPath}`)) {
        return false;
      }
    }
    return true;
  };

  // Toggle field expansion
  const toggleFieldExpansion = (field: MappedSchemaField) => {
    const fieldKey = `${field.promptRevId}-${field.path}`;
    setExpandedFields(prev => {
      const newSet = new Set(prev);
      if (newSet.has(fieldKey)) {
        newSet.delete(fieldKey);
      } else {
        newSet.add(fieldKey);
      }
      return newSet;
    });
  };

  // Get type badge color
  const getTypeBadgeColor = (type: string): string => {
    const colors: Record<string, string> = {
      'string': 'bg-blue-100 text-blue-800',
      'number': 'bg-green-100 text-green-800',
      'integer': 'bg-green-100 text-green-800',
      'boolean': 'bg-purple-100 text-purple-800',
      'array': 'bg-orange-100 text-orange-800',
      'object': 'bg-gray-100 text-gray-800'
    };
    return colors[type] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="h-[calc(100vh-300px)] flex gap-4">
      {/* Left Panel - Schema Fields */}
      <div className="w-1/2 border rounded-lg bg-white overflow-hidden flex flex-col">
        <div className="p-4 border-b bg-gray-50 flex-shrink-0">
          <h3 className="font-semibold text-gray-900 mb-3">Schema Fields</h3>
          
          {/* Search */}
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search fields..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 min-h-0">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <ArrowPathIcon className="h-6 w-6 animate-spin text-gray-500" />
              <span className="ml-2 text-gray-500">Loading schemas...</span>
            </div>
          ) : selectedTagIds.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p>Select tags in the form to see available schema fields</p>
            </div>
          ) : Object.keys(groupedSchemaFields).length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p>No prompts with schemas found for selected tags</p>
            </div>
          ) : (
            <div className="space-y-2">
              {Object.entries(groupedSchemaFields).map(([promptRevId, { promptName, fields }]) => (
                <div key={promptRevId} className="border rounded-lg">
                  <button
                    onClick={() => setExpandedPrompts(prev => 
                      prev.has(promptRevId) 
                        ? new Set(Array.from(prev).filter(id => id !== promptRevId))
                        : new Set([...Array.from(prev), promptRevId])
                    )}
                    className="w-full px-3 py-2 flex items-center justify-between bg-gray-50 hover:bg-gray-100 text-left"
                  >
                    <span className="font-medium text-sm">{promptName}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">{fields.length} fields</span>
                      {expandedPrompts.has(promptRevId) ? (
                        <ChevronDownIcon className="h-4 w-4" />
                      ) : (
                        <ChevronRightIcon className="h-4 w-4" />
                      )}
                    </div>
                  </button>
                  
                  {expandedPrompts.has(promptRevId) && (
                    <div className="p-2 space-y-1">
                      {fields.filter(field => isFieldVisible(field)).map((field) => (
                        <div
                          key={field.path}
                          className="flex items-center justify-between p-2 bg-white border rounded transition-colors"
                          style={{ marginLeft: `${field.depth * 16}px` }} // 16px per depth level
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              {/* Expand/Collapse button for expandable fields */}
                              {field.isExpandable && (
                                <button
                                  onClick={() => toggleFieldExpansion(field)}
                                  className="text-gray-500 hover:text-gray-700 p-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
                                  title={expandedFields.has(`${field.promptRevId}-${field.path}`) ? 'Collapse' : 'Expand'}
                                  disabled={readOnly}
                                >
                                  {expandedFields.has(`${field.promptRevId}-${field.path}`) ? (
                                    <ChevronDownIcon className="h-3 w-3" />
                                  ) : (
                                    <ChevronRightIcon className="h-3 w-3" />
                                  )}
                                </button>
                              )}
                              
                              <span 
                                className={`font-medium text-sm ${readOnly ? 'cursor-default' : (field.isExpandable ? 'cursor-pointer' : 'cursor-move')}`}
                                onClick={!readOnly && field.isExpandable ? () => toggleFieldExpansion(field) : undefined}
                                draggable={!readOnly && !field.isExpandable}
                                onDragStart={!readOnly && !field.isExpandable ? (e) => handleDragStart(e, field) : undefined}
                              >
                                {field.name}
                              </span>
                              
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${getTypeBadgeColor(field.type)}`}>
                                {field.type}
                              </span>
                              
                              {/* Drag handle for leaf fields only */}
                              {!field.isExpandable && (
                                <div 
                                  className="cursor-move text-gray-400 hover:text-gray-600 ml-auto"
                                  draggable
                                  onDragStart={(e) => handleDragStart(e, field)}
                                  title="Drag to map this field"
                                >
                                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z"/>
                                  </svg>
                                </div>
                              )}
                            </div>
                            {field.description && (
                              <p className="text-xs text-gray-500 mt-1 truncate">
                                {field.description}
                              </p>
                            )}
                          </div>
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

      {/* Right Panel - Form Fields */}
      <div className="w-1/2 border rounded-lg bg-white overflow-hidden flex flex-col">
        <div className="p-4 border-b bg-gray-50 flex-shrink-0">
          <h3 className="font-semibold text-gray-900">Form Fields</h3>
          <p className="text-sm text-gray-500 mt-1">Drop schema fields here to create mappings</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 min-h-0">
          {formFields.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p>No form fields available</p>
              <p className="text-sm mt-1">Create fields in the Form Builder tab</p>
            </div>
          ) : (
            <div className="space-y-2">
              {formFields.map((formField) => {
                const mapping = fieldMappings[formField.key];
                const isDropTarget = draggedField && isCompatibleType(draggedField.type, formField.type);
                
                return (
                  <div
                    key={formField.key}
                    onDrop={!readOnly ? (e) => handleDrop(e, formField) : undefined}
                    onDragOver={!readOnly ? (e) => handleDragOver(e, formField) : undefined}
                    className={`p-3 border-2 border-dashed rounded-lg transition-colors ${
                      mapping 
                        ? 'border-green-300 bg-green-50' 
                        : isDropTarget 
                        ? 'border-blue-300 bg-blue-50'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{formField.label}</span>
                          <span className="text-xs text-gray-500">({formField.type})</span>
                          {mapping && <LinkIcon className="h-4 w-4 text-green-600" />}
                        </div>
                        
                        {mapping && (
                          <div className="mt-2 p-2 bg-white border rounded text-xs">
                            {mapping.sources.length > 1 && (
                              <div className="mb-2 flex items-center justify-between">
                                <span className="text-blue-600 font-medium">
                                  {mapping.mappingType === 'concatenated' ? 'Concatenated' : 'Multiple'} mapping
                                </span>
                                <button
                                  onClick={() => removeMapping(formField.key)}
                                  className="text-red-500 hover:text-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                  title="Remove all mappings"
                                  disabled={readOnly}
                                >
                                  <XMarkIcon className="h-4 w-4" />
                                </button>
                              </div>
                            )}
                            
                            <div className="space-y-1">
                              {mapping.sources.map((source, index) => (
                                <div key={index} className="flex items-center justify-between">
                                  <div className="flex-1">
                                    <span className="font-medium text-green-700">
                                      {source.schemaFieldName}
                                    </span>
                                    <span className="text-gray-500 ml-2">
                                      from {source.promptName}
                                    </span>
                                  </div>
                                  <button
                                    onClick={() => mapping.sources.length === 1 
                                      ? removeMapping(formField.key) 
                                      : removeSource(formField.key, index)
                                    }
                                    className="text-red-500 hover:text-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    title={mapping.sources.length === 1 ? "Remove mapping" : "Remove this source"}
                                    disabled={readOnly}
                                  >
                                    <XMarkIcon className="h-3 w-3" />
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
                    </div>
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

export default FormioMapper;