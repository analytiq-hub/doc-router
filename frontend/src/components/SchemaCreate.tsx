import React, { useState, useEffect, useCallback } from 'react';
import { createSchemaApi, updateSchemaApi } from '@/utils/api';
import { SchemaField, SchemaConfig, ResponseFormat, JsonSchemaProperty } from '@/types/index';
import { getApiErrorMsg } from '@/utils/api';

import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import Editor from "@monaco-editor/react";
import InfoTooltip from '@/components/InfoTooltip';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useSchemaContext } from '@/contexts/SchemaContext';

interface SchemaPreviewProps {
  schema: ResponseFormat;
}

const SchemaPreview: React.FC<SchemaPreviewProps> = ({ schema }) => (
  <div className="space-y-2">
    <h3 className="text-lg font-semibold mb-2">JSON Schema</h3>
    <div className="h-[300px] border rounded">
      <Editor
        height="100%"
        defaultLanguage="json"
        value={JSON.stringify(schema, null, 2)}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          wordWrap: "on",
          wrappingIndent: "indent",
          lineNumbers: "off",
          folding: true,
          renderValidationDecorations: "off"
        }}
        theme="vs-light"
      />
    </div>
  </div>
);

interface NestedFieldsEditorProps {
  fields: SchemaField[];
  onChange: (fields: SchemaField[]) => void;
  isLoading: boolean;
}

const NestedFieldsEditor: React.FC<NestedFieldsEditorProps> = ({ fields, onChange, isLoading }) => {
  const [expandedFields, setExpandedFields] = useState<Record<number, boolean>>({});
  
  const toggleExpansion = (index: number) => {
    setExpandedFields(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };
  
  const addNestedField = (afterIndex?: number) => {
    const newFields = [...fields];
    const newIndex = afterIndex !== undefined ? afterIndex + 1 : fields.length;
    
    newFields.splice(newIndex, 0, { name: '', type: 'str' });
    
    // Automatically expand if it's an object type
    if (afterIndex !== undefined && fields[afterIndex].type === 'object') {
      setExpandedFields(prev => ({
        ...prev,
        [newIndex]: true
      }));
    }
    
    onChange(newFields);
  };

  const removeNestedField = (index: number) => {
    const newFields = fields.filter((_, i) => i !== index);
    onChange(newFields);
  };

  const updateNestedField = (index: number, field: Partial<SchemaField>) => {
    const newFields = fields.map((f, i) => 
      i === index ? { ...f, ...field } as SchemaField : f
    );
    
    // If changing to object type, automatically expand
    if (field.type === 'object' && newFields[index].type === 'object') {
      setExpandedFields(prev => ({
        ...prev,
        [index]: true
      }));
    }
    
    onChange(newFields);
  };

  const handleNestedFieldsChange = (parentIndex: number, nestedFields: SchemaField[]) => {
    const updatedFields = [...fields];
    updatedFields[parentIndex] = {
      ...updatedFields[parentIndex],
      nestedFields
    };
    onChange(updatedFields);
  };

  return (
    <div className="space-y-2">
      {fields.map((field, index) => (
        <div key={index} className="border rounded p-2 bg-white">
          <div className="flex items-center gap-2 mb-2">
            <input
              type="text"
              className="flex-1 p-1.5 border rounded text-sm"
              value={field.name}
              onChange={e => updateNestedField(index, { name: e.target.value })}
              placeholder="field_name"
              disabled={isLoading}
            />
            <select
              className="p-1.5 border rounded text-sm w-24"
              value={field.type}
              onChange={e => updateNestedField(index, { type: e.target.value as SchemaField['type'] })}
              disabled={isLoading}
            >
              <option value="str">String</option>
              <option value="int">Integer</option>
              <option value="float">Float</option>
              <option value="bool">Boolean</option>
              <option value="object">Object</option>
            </select>
            <button
              type="button"
              onClick={() => removeNestedField(index)}
              className="p-1 bg-red-50 text-red-600 rounded hover:bg-red-100 disabled:opacity-50 text-sm h-8 w-8 flex items-center justify-center"
              disabled={isLoading}
              aria-label="Remove field"
            >
              <span className="inline-block leading-none translate-y-[1px]">✕</span>
            </button>
            <button
              type="button"
              onClick={() => addNestedField(index)}
              className="p-1 bg-green-50 text-green-600 rounded hover:bg-green-100 disabled:opacity-50 text-xl h-8 w-8 flex items-center justify-center"
              disabled={isLoading}
              aria-label="Add field after this one"
            >
              <span className="inline-block leading-none">+</span>
            </button>
          </div>
          
          <textarea
            className="w-full p-1.5 border rounded text-sm min-h-[30px] resize-y"
            value={field.description || ''}
            onChange={e => updateNestedField(index, { description: e.target.value })}
            placeholder="Description of this field"
            disabled={isLoading}
          />
          
          {/* Recursive rendering for nested objects */}
          {field.type === 'object' && (
            <div className="mt-2 pl-4 border-l-2 border-blue-200">
              <div 
                className="flex items-center text-sm font-medium text-blue-600 mb-2 cursor-pointer"
                onClick={() => toggleExpansion(index)}
              >
                <span className="mr-1 inline-flex items-center justify-center w-4">
                  {expandedFields[index] ? 
                    <ExpandMoreIcon fontSize="small" /> : 
                    <ChevronRightIcon fontSize="small" />
                  }
                </span>
                <span>Nested Fields</span>
              </div>
              
              {expandedFields[index] && (
                <NestedFieldsEditor 
                  fields={field.nestedFields || [{ name: '', type: 'str' }]}
                  onChange={(nestedFields) => handleNestedFieldsChange(index, nestedFields)}
                  isLoading={isLoading}
                />
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

const SchemaCreate: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const { editingSchema, setEditingSchema } = useSchemaContext();
  
  const [currentSchemaId, setCurrentSchemaId] = useState<string | null>(null);
  const [currentSchema, setCurrentSchema] = useState<SchemaConfig>({
    name: '',
    response_format: {
      type: 'json_schema',
      json_schema: {
        name: 'document_extraction',
        schema: {
          type: 'object',
          properties: {},
          required: [],
          additionalProperties: false
        },
        strict: true
      }
    }
  });
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [fields, setFields] = useState<SchemaField[]>([{ name: '', type: 'str' }]);
  const [expandedNestedFields, setExpandedNestedFields] = useState<Record<number, boolean>>({});
  const [expandedArrayFields, setExpandedArrayFields] = useState<Record<number, boolean>>({});

  // Define jsonSchemaToFields with useCallback
  const jsonSchemaToFields = useCallback((responseFormat: ResponseFormat): SchemaField[] => {
    const fields: SchemaField[] = [];
    const properties = responseFormat.json_schema.schema.properties;

    const processProperty = (name: string, prop: JsonSchemaProperty): SchemaField => {
      let fieldType: SchemaField['type'];
      let nestedFields: SchemaField[] | undefined;
      let arrayItemType: 'str' | 'int' | 'float' | 'bool' | 'object' | undefined;
      let arrayObjectFields: SchemaField[] | undefined;

      switch (prop.type) {
        case 'string':
          fieldType = 'str';
          break;
        case 'integer':
          fieldType = 'int';
          break;
        case 'number':
          fieldType = 'float';
          break;
        case 'boolean':
          fieldType = 'bool';
          break;
        case 'array':
          fieldType = 'array';
          if (prop.items) {
            const itemType = prop.items.type;
            switch (itemType) {
              case 'string':
                arrayItemType = 'str';
                break;
              case 'integer':
                arrayItemType = 'int';
                break;
              case 'number':
                arrayItemType = 'float';
                break;
              case 'boolean':
                arrayItemType = 'bool';
                break;
              case 'object':
                arrayItemType = 'object';
                if (prop.items.properties) {
                  arrayObjectFields = Object.entries(prop.items.properties).map(
                    ([objName, objProp]) => processProperty(objName, objProp)
                  );
                }
                break;
              default:
                arrayItemType = 'str';
            }
          }
          break;
        case 'object':
          fieldType = 'object';
          if (prop.properties) {
            nestedFields = Object.entries(prop.properties).map(
              ([nestedName, nestedProp]) => processProperty(nestedName, nestedProp)
            );
          }
          break;
        default:
          fieldType = 'str';
      }

      return { 
        name, 
        type: fieldType,
        description: prop.description,
        nestedFields,
        arrayItemType,
        arrayObjectFields
      };
    };

    Object.entries(properties).forEach(([name, prop]) => {
      fields.push(processProperty(name, prop));
    });

    return fields;
  }, []);

  // Load editing schema if available
  useEffect(() => {
    if (editingSchema) {
      setCurrentSchemaId(editingSchema.id);
      setCurrentSchema({
        name: editingSchema.name,
        response_format: editingSchema.response_format
      });
      setFields(jsonSchemaToFields(editingSchema.response_format));
      
      // Clear the editing schema after loading
      setEditingSchema(null);
    }
  }, [editingSchema, setEditingSchema, jsonSchemaToFields]);

  const saveSchema = async (schema: SchemaConfig) => {
    try {
      setIsLoading(true);
      
      if (currentSchemaId) {
        await updateSchemaApi({organizationId: organizationId, schemaId: currentSchemaId, schema});
      } else {
        await createSchemaApi({organizationId: organizationId, ...schema });
      }

      setMessage('Schema saved successfully');
      
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving schema';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const addField = () => {
    const newFields = [...fields, { name: '', type: 'str' as const }];
    setFields(newFields);
    setCurrentSchema(prev => ({
      ...prev,
      response_format: fieldsToJsonSchema(newFields)
    }));
  };

  const removeField = (index: number) => {
    const newFields = fields.filter((_, i) => i !== index);
    setFields(newFields);
    setCurrentSchema(prev => ({
      ...prev,
      response_format: fieldsToJsonSchema(newFields)
    }));
  };

  const updateField = (index: number, field: Partial<SchemaField>) => {
    const newFields = fields.map((f, i) => 
      i === index ? { ...f, ...field } as SchemaField : f
    );
    
    // If changing to object type, automatically expand
    if (field.type === 'object' && newFields[index].type === 'object') {
      setExpandedNestedFields(prev => ({
        ...prev,
        [index]: true
      }));
    }
    
    // If changing to array type, automatically expand
    if (field.type === 'array' && newFields[index].type === 'array') {
      setExpandedArrayFields(prev => ({
        ...prev,
        [index]: true
      }));
    }
    
    setFields(newFields);
    setCurrentSchema(prev => ({
      ...prev,
      response_format: fieldsToJsonSchema(newFields)
    }));
  };

  // Toggle expansion state for nested fields
  const toggleNestedFieldExpansion = (index: number) => {
    setExpandedNestedFields(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  // Toggle expansion state for array fields
  const toggleArrayFieldExpansion = (index: number) => {
    setExpandedArrayFields(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  // Add this function to handle nested object fields
  const handleNestedFieldsChange = (parentIndex: number, nestedFields: SchemaField[]) => {
    const updatedFields = [...fields];
    updatedFields[parentIndex] = {
      ...updatedFields[parentIndex],
      nestedFields
    };
    setFields(updatedFields);
    setCurrentSchema(prev => ({
      ...prev,
      response_format: fieldsToJsonSchema(updatedFields)
    }));
  };

  // Add this function to handle array item type changes
  const handleArrayItemTypeChange = (index: number, itemType: SchemaField['type']) => {
    const newFields = [...fields];
    // Only assign valid types to arrayItemType
    const validArrayItemType = (itemType === 'str' || itemType === 'int' || 
                               itemType === 'float' || itemType === 'bool' || 
                               itemType === 'object') ? itemType : 'str';
    newFields[index] = {
      ...newFields[index],
      arrayItemType: validArrayItemType,
      // Initialize nested fields for array of objects
      arrayObjectFields: validArrayItemType === 'object' ? [{ name: '', type: 'str' }] : undefined
    };
    setFields(newFields);
    setCurrentSchema(prev => ({
      ...prev,
      response_format: fieldsToJsonSchema(newFields)
    }));
  };

  // Add this function to handle array object fields changes
  const handleArrayObjectFieldsChange = (parentIndex: number, objectFields: SchemaField[]) => {
    const updatedFields = [...fields];
    updatedFields[parentIndex] = {
      ...updatedFields[parentIndex],
      arrayObjectFields: objectFields
    };
    setFields(updatedFields);
    setCurrentSchema(prev => ({
      ...prev,
      response_format: fieldsToJsonSchema(updatedFields)
    }));
  };

  const validateFields = (fields: SchemaField[]): string | null => {
    const fieldNames = fields.map(f => f.name.toLowerCase());
    const duplicates = fieldNames.filter((name, index) => fieldNames.indexOf(name) !== index);
    
    if (duplicates.length > 0) {
      return `Duplicate field name: ${duplicates[0]}`;
    }
    
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentSchema.name || fields.some(f => !f.name)) {
      setMessage('Please fill in all fields');
      return;
    }

    const fieldError = validateFields(fields);
    if (fieldError) {
      setMessage(`Error: ${fieldError}`);
      return;
    }

    saveSchema(currentSchema);
    setFields([{ name: '', type: 'str' }]);
    setCurrentSchema({
      name: '',
      response_format: {
        type: 'json_schema',
        json_schema: {
          name: 'document_extraction',
          schema: {
            type: 'object',
            properties: {},
            required: [],
            additionalProperties: false
          },
          strict: true
        }
      }
    });
    setCurrentSchemaId(null);
  };

  // Update fieldsToJsonSchema to handle arrays
  const fieldsToJsonSchema = (fields: SchemaField[]): ResponseFormat => {
    const responseFormat = {
      type: 'json_schema' as const,
      json_schema: {
        name: 'document_extraction',
        schema: {
          type: 'object' as const,
          properties: {} as Record<string, JsonSchemaProperty>,
          required: [] as string[],
          additionalProperties: false
        },
        strict: true
      }
    };

    const processField = (field: SchemaField): JsonSchemaProperty => {
      let property: JsonSchemaProperty;

      switch (field.type) {
        case 'str':
          property = { type: 'string' };
          break;
        case 'int':
          property = { type: 'integer' };
          break;
        case 'float':
          property = { type: 'number' };
          break;
        case 'bool':
          property = { type: 'boolean' };
          break;
        case 'array':
          property = {
            type: 'array',
            items: field.arrayItemType ? processArrayItemType(field) : { type: 'string' }
          };
          break;
        case 'object':
          property = {
            type: 'object',
            properties: {},
            additionalProperties: false,
            required: []
          };
          
          // Process nested fields if they exist
          if (field.nestedFields && field.nestedFields.length > 0) {
            field.nestedFields.forEach(nestedField => {
              if (property.type === 'object' && property.properties && nestedField.name) {
                property.properties[nestedField.name] = processField(nestedField);
                // Add all fields as required by default
                if (property.required) {
                  property.required.push(nestedField.name);
                }
              }
            });
          }
          break;
        default:
          property = { type: 'string' };
      }

      if (field.description) {
        property.description = field.description;
      } else {
        property.description = field.name.replace(/_/g, ' ');
      }

      return property;
    };

    // Helper function to process array item types
    const processArrayItemType = (field: SchemaField): JsonSchemaProperty => {
      if (!field.arrayItemType) return { type: 'string' };

      switch (field.arrayItemType) {
        case 'str':
          return { type: 'string' };
        case 'int':
          return { type: 'integer' };
        case 'float':
          return { type: 'number' };
        case 'bool':
          return { type: 'boolean' };
        case 'object':
          const objectProperty: JsonSchemaProperty = {
            type: 'object',
            properties: {},
            additionalProperties: false,
            required: []
          };
          
          // Process array object fields
          if (field.arrayObjectFields && field.arrayObjectFields.length > 0) {
            field.arrayObjectFields.forEach(objField => {
              if (objField.name && objectProperty.properties) {
                objectProperty.properties[objField.name] = processField(objField);
                // Add all fields as required by default
                if (objectProperty.required) {
                  objectProperty.required.push(objField.name);
                }
              }
            });
          }
          
          return objectProperty;
        default:
          return { type: 'string' };
      }
    };

    fields.forEach(field => {
      if (field.name) {
        responseFormat.json_schema.schema.properties[field.name] = processField(field);
        responseFormat.json_schema.schema.required.push(field.name);
      }
    });

    return responseFormat;
  };

  // Handle drag end event
  const handleDragEnd = (result: DropResult) => {
    // Dropped outside the list
    if (!result.destination) {
      return;
    }

    const reorderedFields = reorderFields(
      fields,
      result.source.index,
      result.destination.index
    );

    setFields(reorderedFields);
    setCurrentSchema(prev => ({
      ...prev,
      response_format: fieldsToJsonSchema(reorderedFields)
    }));
  };

  // Helper function to reorder fields
  const reorderFields = (list: SchemaField[], startIndex: number, endIndex: number): SchemaField[] => {
    const result = Array.from(list);
    const [removed] = result.splice(startIndex, 1);
    result.splice(endIndex, 0, removed);
    return result;
  };

  return (
    <div className="p-4 mx-auto">
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="text-xl font-bold" data-tour="schemas">
            {currentSchemaId ? 'Edit Schema' : 'Create Schema'}
          </h2>
          <InfoTooltip 
            title="About Schemas"
            content={
              <>
                <p className="mb-2">
                  When linked to a prompt, schemas enforce structured output.
                </p>
                <ul className="list-disc list-inside space-y-1 mb-2">
                  <li>Use descriptive field names</li>
                  <li>Choose appropriate data types for each field</li>
                  <li>All fields defined in a schema are required by default</li>
                </ul>
              </>
            }
          />
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Schema Name Input */}
          <div className="mb-4">
            <input
              type="text"
              className="w-full p-2 border rounded"
              value={currentSchema.name}
              onChange={e => setCurrentSchema({ ...currentSchema, name: e.target.value })}
              placeholder="Schema Name"
              disabled={isLoading}
            />
          </div>

          {/* Grid Container */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Fields Editor - Left Column */}
            <div className="space-y-2">
              <h3 className="text-lg font-semibold mb-2">Fields Editor</h3>
              <div className="space-y-2 max-h-[300px] overflow-y-auto p-2 border rounded">
                <DragDropContext onDragEnd={handleDragEnd}>
                  <Droppable droppableId="fields">
                    {(provided) => (
                      <div
                        {...provided.droppableProps}
                        ref={provided.innerRef}
                        className="space-y-2"
                      >
                        {fields.map((field, index) => (
                          <Draggable key={index} draggableId={`field-${index}`} index={index}>
                            {(provided) => (
                              <div
                                ref={provided.innerRef}
                                {...provided.draggableProps}
                                className="mb-2 border rounded p-3 bg-gray-50"
                              >
                                <div className="flex items-center gap-2 mb-2">
                                  <div 
                                    {...provided.dragHandleProps}
                                    className="flex items-center text-gray-400 cursor-grab p-1"
                                  >
                                    <DragIndicatorIcon fontSize="small" />
                                  </div>
                                  <input
                                    type="text"
                                    className="flex-1 p-1.5 border rounded text-sm"
                                    value={field.name}
                                    onChange={e => updateField(index, { name: e.target.value })}
                                    placeholder="field_name"
                                    disabled={isLoading}
                                  />
                                  <select
                                    className="p-1.5 border rounded text-sm w-24"
                                    value={field.type}
                                    onChange={e => updateField(index, { type: e.target.value as SchemaField['type'] })}
                                    disabled={isLoading}
                                  >
                                    <option value="str">String</option>
                                    <option value="int">Integer</option>
                                    <option value="float">Float</option>
                                    <option value="bool">Boolean</option>
                                    <option value="object">Object</option>
                                    <option value="array">Array</option>
                                  </select>
                                  <button
                                    type="button"
                                    onClick={() => removeField(index)}
                                    className="p-1 bg-red-50 text-red-600 rounded hover:bg-red-100 disabled:opacity-50 text-sm h-8 w-8 flex items-center justify-center"
                                    disabled={isLoading}
                                    aria-label="Remove field"
                                  >
                                    <span className="inline-block leading-none translate-y-[1px]">✕</span>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      const newFields = [...fields];
                                      newFields.splice(index + 1, 0, { name: '', type: 'str' });
                                      setFields(newFields);
                                      setCurrentSchema(prev => ({
                                        ...prev,
                                        response_format: fieldsToJsonSchema(newFields)
                                      }));
                                    }}
                                    className="p-1 bg-green-50 text-green-600 rounded hover:bg-green-100 disabled:opacity-50 text-xl h-8 w-8 flex items-center justify-center"
                                    disabled={isLoading}
                                    aria-label="Add field after this one"
                                  >
                                    <span className="inline-block leading-none">+</span>
                                  </button>
                                </div>
                                <textarea
                                  className="w-full p-1.5 border rounded text-sm min-h-[30px] resize-y"
                                  value={field.description || ''}
                                  onChange={e => updateField(index, { description: e.target.value })}
                                  placeholder="Description of this field"
                                  disabled={isLoading}
                                  onKeyDown={e => {
                                    // Allow Shift+Enter for new lines, but prevent form submission
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                      e.preventDefault();
                                    }
                                  }}
                                />
                                
                                {/* Nested fields for object type */}
                                {field.type === 'object' && (
                                  <div className="mt-2 pl-4 border-l-2 border-blue-200">
                                    <div 
                                      className="flex items-center text-sm font-medium text-blue-600 mb-2 cursor-pointer"
                                      onClick={() => toggleNestedFieldExpansion(index)}
                                    >
                                      <span className="mr-1 inline-flex items-center justify-center w-4">
                                        {expandedNestedFields[index] ? 
                                          <ExpandMoreIcon fontSize="small" /> : 
                                          <ChevronRightIcon fontSize="small" />
                                        }
                                      </span>
                                      <span>Nested Fields</span>
                                    </div>
                                    
                                    {expandedNestedFields[index] && (
                                      <NestedFieldsEditor 
                                        fields={field.nestedFields || [{ name: '', type: 'str' }]}
                                        onChange={(nestedFields) => handleNestedFieldsChange(index, nestedFields)}
                                        isLoading={isLoading}
                                      />
                                    )}
                                  </div>
                                )}

                                {/* Array type configuration */}
                                {field.type === 'array' && (
                                  <div className="mt-2 pl-4 border-l-2 border-green-200">
                                    <div 
                                      className="flex items-center text-sm font-medium text-green-600 mb-2 cursor-pointer"
                                      onClick={() => toggleArrayFieldExpansion(index)}
                                    >
                                      <span className="mr-1 inline-flex items-center justify-center w-4">
                                        {expandedArrayFields[index] ? 
                                          <ExpandMoreIcon fontSize="small" /> : 
                                          <ChevronRightIcon fontSize="small" />
                                        }
                                      </span>
                                      <span>Array Item Type</span>
                                    </div>
                                    
                                    {expandedArrayFields[index] && (
                                      <>
                                        <div className="flex items-center gap-2 mb-2">
                                          <select
                                            className="p-1.5 border rounded text-sm"
                                            value={field.arrayItemType || 'str'}
                                            onChange={e => handleArrayItemTypeChange(index, e.target.value as SchemaField['type'])}
                                            disabled={isLoading}
                                          >
                                            <option value="str">String</option>
                                            <option value="int">Integer</option>
                                            <option value="float">Float</option>
                                            <option value="bool">Boolean</option>
                                            <option value="object">Object</option>
                                          </select>
                                        </div>
                                        
                                        {/* For array of objects, show object field editor */}
                                        {field.arrayItemType === 'object' && (
                                          <div className="mt-2">
                                            <div className="text-sm font-medium text-blue-600 mb-2">Array Object Fields</div>
                                            <NestedFieldsEditor 
                                              fields={field.arrayObjectFields || [{ name: '', type: 'str' }]}
                                              onChange={(objectFields) => handleArrayObjectFieldsChange(index, objectFields)}
                                              isLoading={isLoading}
                                            />
                                          </div>
                                        )}
                                      </>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </Draggable>
                        ))}
                        {provided.placeholder}
                      </div>
                    )}
                  </Droppable>
                </DragDropContext>
              </div>
              <button
                type="button"
                onClick={addField}
                className="w-full p-1.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 disabled:opacity-50 text-sm"
                disabled={isLoading}
              >
                Add Field
              </button>
            </div>

            {/* JSON Schema Preview - Right Column */}
            <SchemaPreview schema={currentSchema.response_format} />
          </div>

          {/* Save Button */}
          <div className="flex justify-end pt-4">
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={isLoading}
            >
              {currentSchemaId ? 'Update Schema' : 'Save Schema'}
            </button>
          </div>
        </form>

        {/* Message */}
        {message && (
          <div className={`mt-4 p-3 rounded ${
            message.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
          }`}>
            {message}
          </div>
        )}
      </div>
    </div>
  );
};

export default SchemaCreate;