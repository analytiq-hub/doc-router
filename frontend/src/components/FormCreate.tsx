import React, { useState, useEffect, useCallback } from 'react';
import { createFormApi, updateFormApi, getFormApi } from '@/utils/api';
import { FormField, FormConfig, FormResponseFormat, FormProperty } from '@/types/index';
import { getApiErrorMsg } from '@/utils/api';

import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import Editor from "@monaco-editor/react";
import InfoTooltip from '@/components/InfoTooltip';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { toast } from 'react-toastify';
import { useRouter } from 'next/navigation';
import FormCanvasBuilder from '@/components/FormCanvasBuilder';

interface NestedFieldsEditorProps {
  fields: FormField[];
  onChange: (fields: FormField[]) => void;
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

  const updateNestedField = (index: number, field: Partial<FormField>) => {
    const newFields = fields.map((f, i) => 
      i === index ? { ...f, ...field } as FormField : f
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

  const handleNestedFieldsChange = (parentIndex: number, nestedFields: FormField[]) => {
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
              onChange={e => updateNestedField(index, { type: e.target.value as FormField['type'] })}
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

const FormCreate: React.FC<{ organizationId: string, formId?: string }> = ({ organizationId, formId }) => {
  const router = useRouter();
  const [currentFormId, setCurrentFormId] = useState<string | null>(null);
  const [currentForm, setCurrentForm] = useState<FormConfig>({
    name: '',
    response_format: {
      type: 'json_form',
      json_form: {
        name: 'document_extraction',
        form: {
          type: 'object',
          properties: {},
          required: [],
          additionalProperties: false
        },
        strict: true
      }
    }
  });
  const [isLoading, setIsLoading] = useState(false);
  const [fields, setFields] = useState<FormField[]>([{ name: '', type: 'str' }]);
  const [expandedNestedFields, setExpandedNestedFields] = useState<Record<number, boolean>>({});
  const [expandedArrayFields, setExpandedArrayFields] = useState<Record<number, boolean>>({});
  const [activeTab, setActiveTab] = useState<'fields' | 'json'>('fields');
  const [jsonForm, setJsonForm] = useState('');

  // Define jsonFormToFields with useCallback
  const jsonFormToFields = useCallback((responseFormat: FormResponseFormat): FormField[] => {
    const fields: FormField[] = [];
    const properties = responseFormat.json_form.form.properties;

    const processProperty = (name: string, prop: FormProperty): FormField => {
      let fieldType: FormField['type'];
      let nestedFields: FormField[] | undefined;
      let arrayItemType: 'str' | 'int' | 'float' | 'bool' | 'object' | undefined;
      let arrayObjectFields: FormField[] | undefined;

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

  // Load editing form if available
  useEffect(() => {
    async function loadForm() {
      if (formId) {
        setIsLoading(true);
        try {
          const form = await getFormApi({ organizationId, formId });
          setCurrentFormId(form.form_id);
          setCurrentForm({
            name: form.name,
            response_format: form.response_format
          });
          setFields(jsonFormToFields(form.response_format));
        } catch (error) {
          toast.error(`Error loading form: ${getApiErrorMsg(error)}`);
        } finally {
          setIsLoading(false);
        }
      } else {
        setCurrentFormId(null);
        setCurrentForm({
          name: '',
          response_format: {
            type: 'json_form',
            json_form: {
              name: 'document_extraction',
              form: {
                type: 'object',
                properties: {},
                required: [],
                additionalProperties: false
              },
              strict: true
            }
          }
        });
        setFields([{ name: '', type: 'str' }]);
      }
    }
    loadForm();
    // Only run when formId or organizationId changes
  }, [formId, organizationId, jsonFormToFields]);

  // Update jsonForm when currentForm changes
  useEffect(() => {
    setJsonForm(JSON.stringify(currentForm.response_format, null, 2));
  }, [currentForm]);

  // Add handler for JSON form changes
  const handleJsonFormChange = (value: string | undefined) => {
    if (!value) return;
    try {
      const parsedForm = JSON.parse(value);
      
      // Validate form structure
      if (!parsedForm.json_form || !parsedForm.json_form.form) {
        toast.error('Error: Invalid form format. Must contain json_form.form');
        return;
      }
      
      const form = parsedForm.json_form.form;
      
      // Validate required properties
      if (!form.type || form.type !== 'object') {
        toast.error('Error: Form type must be "object"');
        return;
      }
      
      if (!form.properties || typeof form.properties !== 'object') {
        toast.error('Error: Form must have properties object');
        return;
      }
      
      if (!Array.isArray(form.required)) {
        toast.error('Error: Form must have required array');
        return;
      }
      
      // Check additionalProperties is present and is boolean
      if (typeof form.additionalProperties !== 'boolean') {
        toast.error('Error: additionalProperties must be a boolean');
        return;
      }
      
      // Update form and fields
      setCurrentForm(prev => ({
        ...prev,
        response_format: parsedForm
      }));
      
      // Update fields based on the new form
      setFields(jsonFormToFields(parsedForm));
    } catch (error) {
      // Invalid JSON - don't update
      toast.error(`Error: Invalid JSON syntax: ${error}`);
    }
  };

  const saveForm = async (form: FormConfig) => {
    try {
      setIsLoading(true);
      
      if (currentFormId) {
        await updateFormApi({organizationId: organizationId, formId: currentFormId, form});
      } else {
        await createFormApi({organizationId: organizationId, ...form });
      }      

      router.push(`/orgs/${organizationId}/forms`);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving form';
      toast.error('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const addField = () => {
    const newFields = [...fields, { name: '', type: 'str' as const }];
    setFields(newFields);
    setCurrentForm(prev => ({
      ...prev,
      response_format: fieldsToJsonForm(newFields)
    }));
  };

  const removeField = (index: number) => {
    const newFields = fields.filter((_, i) => i !== index);
    setFields(newFields);
    setCurrentForm(prev => ({
      ...prev,
      response_format: fieldsToJsonForm(newFields)
    }));
  };

  const updateField = (index: number, field: Partial<FormField>) => {
    const newFields = fields.map((f, i) => 
      i === index ? { ...f, ...field } as FormField : f
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
    setCurrentForm(prev => ({
      ...prev,
      response_format: fieldsToJsonForm(newFields)
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
  const handleNestedFieldsChange = (parentIndex: number, nestedFields: FormField[]) => {
    const updatedFields = [...fields];
    updatedFields[parentIndex] = {
      ...updatedFields[parentIndex],
      nestedFields
    };
    setFields(updatedFields);
    setCurrentForm(prev => ({
      ...prev,
      response_format: fieldsToJsonForm(updatedFields)
    }));
  };

  // Add this function to handle array item type changes
  const handleArrayItemTypeChange = (index: number, itemType: FormField['type']) => {
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
    setCurrentForm(prev => ({
      ...prev,
      response_format: fieldsToJsonForm(newFields)
    }));
  };

  // Add this function to handle array object fields changes
  const handleArrayObjectFieldsChange = (parentIndex: number, objectFields: FormField[]) => {
    const updatedFields = [...fields];
    updatedFields[parentIndex] = {
      ...updatedFields[parentIndex],
      arrayObjectFields: objectFields
    };
    setFields(updatedFields);
    setCurrentForm(prev => ({
      ...prev,
      response_format: fieldsToJsonForm(updatedFields)
    }));
  };

  const validateFields = (fields: FormField[]): string | null => {
    const fieldNames = fields.map(f => f.name.toLowerCase());
    const duplicates = fieldNames.filter((name, index) => fieldNames.indexOf(name) !== index);
    
    if (duplicates.length > 0) {
      return `Duplicate field name: ${duplicates[0]}`;
    }
    
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentForm.name || fields.some(f => !f.name)) {
      toast.error('Please fill in all fields');
      return;
    }

    const fieldError = validateFields(fields);
    if (fieldError) {
      toast.error(`Error: ${fieldError}`);
      return;
    }

    saveForm(currentForm);
    setFields([{ name: '', type: 'str' }]);
    setCurrentForm({
      name: '',
      response_format: {
        type: 'json_form',
        json_form: {
          name: 'document_extraction',
          form: {
            type: 'object',
            properties: {},
            required: [],
            additionalProperties: false
          },
          strict: true
        }
      }
    });
    setCurrentFormId(null);
  };

  // Update fieldsToJsonForm to handle arrays
  const fieldsToJsonForm = (fields: FormField[]): FormResponseFormat => {
    const responseFormat = {
      type: 'json_form' as const,
      json_form: {
        name: 'document_extraction',
        form: {
          type: 'object' as const,
          properties: {} as Record<string, FormProperty>,
          required: [] as string[],
          additionalProperties: false
        },
        strict: true
      }
    };

    const processField = (field: FormField): FormProperty => {
      let property: FormProperty;

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
    const processArrayItemType = (field: FormField): FormProperty => {
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
          const objectProperty: FormProperty = {
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
        responseFormat.json_form.form.properties[field.name] = processField(field);
        responseFormat.json_form.form.required.push(field.name);
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
    setCurrentForm(prev => ({
      ...prev,
      response_format: fieldsToJsonForm(reorderedFields)
    }));
  };

  // Helper function to reorder fields
  const reorderFields = (list: FormField[], startIndex: number, endIndex: number): FormField[] => {
    const result = Array.from(list);
    const [removed] = result.splice(startIndex, 1);
    result.splice(endIndex, 0, removed);
    return result;
  };

  return (
    <div className="p-4 mx-auto">
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="hidden md:flex items-center gap-2 mb-4">
          <h2 className="text-xl font-bold">
            {currentFormId ? 'Edit Form' : 'Create Form'}
          </h2>
          <InfoTooltip 
            title="About Forms"
            content={
              <>
                <p className="mb-2">
                  When linked to a prompt, forms enforce structured output.
                </p>
                <ul className="list-disc list-inside space-y-1 mb-2">
                  <li>Use descriptive field names</li>
                  <li>Choose appropriate data types for each field</li>
                  <li>All fields defined in a form are required by default</li>
                </ul>
              </>
            }
          />
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Form Name Input and Action Buttons in a flex container */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1 md:w-1/2 md:max-w-[calc(50%-1rem)]">
              <input
                type="text"
                className="w-full p-2 border rounded"
                value={currentForm.name}
                onChange={e => setCurrentForm({ ...currentForm, name: e.target.value })}
                placeholder="Form Name"
                disabled={isLoading}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  // Clear the form
                  setCurrentFormId(null);
                  setFields([{ name: '', type: 'str' }]);
                  setCurrentForm({
                    name: '',
                    response_format: {
                      type: 'json_form',
                      json_form: {
                        name: 'document_extraction',
                        form: {
                          type: 'object',
                          properties: {},
                          required: [],
                          additionalProperties: false
                        },
                        strict: true
                      }
                    }
                  });
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
                disabled={isLoading}
              >
                Clear
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={isLoading}
              >
                {currentFormId ? 'Update Form' : 'Save Form'}
              </button>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="border-b border-gray-200 mb-4">
            <div className="flex gap-8">
              <button
                type="button"
                onClick={() => setActiveTab('fields')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  activeTab === 'fields'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Fields Editor
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
                JSON Form
              </button>
            </div>
          </div>

          {/* Tab Content */}
          <div className="space-y-4">
            {activeTab === 'fields' ? (
              // Fields Editor Tab
              <div className="space-y-2">
                <div className="h-[calc(100vh-300px)] overflow-y-auto p-2 border rounded">
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
                                      onChange={e => updateField(index, { type: e.target.value as FormField['type'] })}
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
                                        setCurrentForm(prev => ({
                                          ...prev,
                                          response_format: fieldsToJsonForm(newFields)
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
                                              onChange={e => handleArrayItemTypeChange(index, e.target.value as FormField['type'])}
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
            ) : (
              // JSON Form Tab
              <div className="h-[calc(100vh-300px)] border rounded">
                <Editor
                  height="100%"
                  defaultLanguage="json"
                  value={jsonForm}
                  onChange={handleJsonFormChange}
                  options={{
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    wordWrap: "on",
                    wrappingIndent: "indent",
                    lineNumbers: "on",
                    folding: true,
                    renderValidationDecorations: "on"
                  }}
                  theme="vs-light"
                />
              </div>
            )}
          </div>
        </form>
      </div>
      <FormCanvasBuilder />
    </div>
  );
};

export default FormCreate;