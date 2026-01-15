import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Schema, SchemaResponseFormat, SchemaProperty } from '@docrouter/sdk';
import { SchemaField } from '@/types/ui';

// Type alias for schema creation/update (without id and timestamps)
type SchemaConfig = Omit<Schema, 'schema_revid' | 'schema_id' | 'schema_version' | 'created_at' | 'created_by'>;
import { getApiErrorMsg } from '@/utils/api';

import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import Editor from "@monaco-editor/react";
import InfoTooltip from '@/components/InfoTooltip';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import InfoIcon from '@mui/icons-material/Info';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import { toast } from 'react-toastify';
import { useRouter } from 'next/navigation';
import SchemaInfoModal from './SchemaInfoModal';
import SchemaVersionSelector from './SchemaVersionSelector';
import SchemaVersionCompareModal from './SchemaVersionCompareModal';
import SchemaDiffView from './SchemaDiffView';

interface NestedFieldsEditorProps {
  fields: SchemaField[];
  onChange: (fields: SchemaField[]) => void;
  isLoading: boolean;
  isReadOnly?: boolean;
}

const NestedFieldsEditor: React.FC<NestedFieldsEditorProps> = ({ fields, onChange, isLoading, isReadOnly = false }) => {
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
              disabled={isLoading || isReadOnly}
            />
            <select
              className="p-1.5 border rounded text-sm w-24"
              value={field.type}
              onChange={e => updateNestedField(index, { type: e.target.value as SchemaField['type'] })}
              disabled={isLoading || isReadOnly}
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
              disabled={isLoading || isReadOnly}
              aria-label="Remove field"
            >
              <span className="inline-block leading-none translate-y-[1px]">✕</span>
            </button>
            <button
              type="button"
              onClick={() => addNestedField(index)}
              className="p-1 bg-green-50 text-green-600 rounded hover:bg-green-100 disabled:opacity-50 text-xl h-8 w-8 flex items-center justify-center"
              disabled={isLoading || isReadOnly}
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
            disabled={isLoading || isReadOnly}
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

const SchemaCreate: React.FC<{ organizationId: string, schemaRevId?: string }> = ({ organizationId, schemaRevId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [currentSchemaId, setCurrentSchemaId] = useState<string | null>(null);
  const [currentSchemaFull, setCurrentSchemaFull] = useState<Schema | null>(null);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [viewingVersion, setViewingVersion] = useState<number | null>(null);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);
  const [diffSchemas, setDiffSchemas] = useState<{ left: Schema | null; right: Schema | null }>({ left: null, right: null });
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
  const [isLoading, setIsLoading] = useState(false);
  const [fields, setFields] = useState<SchemaField[]>([{ name: '', type: 'str' }]);
  const [expandedNestedFields, setExpandedNestedFields] = useState<Record<number, boolean>>({});
  const [expandedArrayFields, setExpandedArrayFields] = useState<Record<number, boolean>>({});
  const [activeTab, setActiveTab] = useState<'fields' | 'json'>('fields');
  const [jsonSchema, setJsonSchema] = useState('');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Define jsonSchemaToFields with useCallback
  const jsonSchemaToFields = useCallback((responseFormat: SchemaResponseFormat): SchemaField[] => {
    const fields: SchemaField[] = [];
    const properties = responseFormat.json_schema.schema.properties;

    const processProperty = (name: string, prop: SchemaProperty): SchemaField => {
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
    async function loadSchema() {
      if (schemaRevId) {
        setIsLoading(true);
        try {
          const schema = await docRouterOrgApi.getSchema({ schemaRevId });
          setCurrentSchemaId(schema.schema_id);
          setCurrentSchemaFull(schema);
          setViewingVersion(schema.schema_version);
          // Check if this is the latest version
          const versionsResponse = await docRouterOrgApi.listSchemaVersions({ schemaId: schema.schema_id });
          const latestVersion = versionsResponse.schemas.sort((a, b) => b.schema_version - a.schema_version)[0];
          setIsReadOnly(schema.schema_version !== latestVersion.schema_version);
          setCurrentSchema({
            name: schema.name,
            response_format: schema.response_format
          });
          setFields(jsonSchemaToFields(schema.response_format));
        } catch (error) {
          toast.error(`Error loading schema: ${getApiErrorMsg(error)}`);
        } finally {
          setIsLoading(false);
        }
      } else {
        setCurrentSchemaId(null);
        setCurrentSchemaFull(null);
        setViewingVersion(null);
        setIsReadOnly(false);
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
        setFields([{ name: '', type: 'str' }]);
      }
    }
    loadSchema();
    // Only run when schemaId or organizationId changes
  }, [schemaRevId, docRouterOrgApi, jsonSchemaToFields]);

  // Update jsonSchema when currentSchema changes
  useEffect(() => {
    setJsonSchema(JSON.stringify(currentSchema.response_format, null, 2));
  }, [currentSchema]);

  // Custom JSON parser that tracks line numbers using WeakMap
  const parseJsonWithLineNumbers = (jsonString: string) => {
    let currentLine = 1;
    let currentColumn = 1;
    let index = 0;
    
    // Use WeakMap to store line numbers separately from parsed objects
    const lineNumbers = new WeakMap<object, number>();
    const propertyLineNumbers = new WeakMap<object, Map<string, number>>();

    const skipWhitespace = () => {
      while (index < jsonString.length && /\s/.test(jsonString[index])) {
        if (jsonString[index] === '\n') {
          currentLine++;
          currentColumn = 1;
        } else {
          currentColumn++;
        }
        index++;
      }
    };

    const parseValue = (): unknown => {
      skipWhitespace();
      
      if (index >= jsonString.length) {
        throw new Error(`Unexpected end of input at line ${currentLine}, column ${currentColumn}`);
      }

      const char = jsonString[index];

      if (char === '{') {
        return parseObject();
      } else if (char === '[') {
        return parseArray();
      } else if (char === '"') {
        return parseString();
      } else if (char === 't' || char === 'f') {
        return parseBoolean();
      } else if (char === 'n') {
        return parseNull();
      } else if (char === '-' || /\d/.test(char)) {
        return parseNumber();
      } else {
        throw new Error(`Unexpected character '${char}' at line ${currentLine}, column ${currentColumn}`);
      }
    };

      const parseObject = (): Record<string, unknown> => {
        const obj: Record<string, unknown> = {};
        lineNumbers.set(obj, currentLine);
        propertyLineNumbers.set(obj, new Map());
      index++; // consume '{'
      currentColumn++;
      
      skipWhitespace();
      
      if (jsonString[index] === '}') {
        index++;
        currentColumn++;
        return obj;
      }

      while (true) {
        skipWhitespace();
        
        if (jsonString[index] !== '"') {
          throw new Error(`Expected string key at line ${currentLine}, column ${currentColumn}`);
        }
        
        const key = parseString();
        skipWhitespace();
        
        if (jsonString[index] !== ':') {
          throw new Error(`Expected ':' at line ${currentLine}, column ${currentColumn}`);
        }
        index++;
        currentColumn++;
        
        const value = parseValue();
        
        // Store the property
        obj[key] = value;
        // Store line number for this property in WeakMap
        const propMap = propertyLineNumbers.get(obj);
        if (propMap) {
          propMap.set(key, currentLine);
        }
        
        skipWhitespace();
        
        if (jsonString[index] === '}') {
          index++;
          currentColumn++;
          break;
        } else if (jsonString[index] === ',') {
          index++;
          currentColumn++;
        } else {
          throw new Error(`Expected ',' or '}' at line ${currentLine}, column ${currentColumn}`);
        }
      }
      
      return obj;
    };

      const parseArray = (): unknown[] => {
        const arr: unknown[] = [];
        lineNumbers.set(arr, currentLine);
      index++; // consume '['
      currentColumn++;
      
      skipWhitespace();
      
      if (jsonString[index] === ']') {
        index++;
        currentColumn++;
        return arr;
      }

      while (true) {
        const value = parseValue();
        arr.push(value);
        
        skipWhitespace();
        
        if (jsonString[index] === ']') {
          index++;
          currentColumn++;
          break;
        } else if (jsonString[index] === ',') {
          index++;
          currentColumn++;
        } else {
          throw new Error(`Expected ',' or ']' at line ${currentLine}, column ${currentColumn}`);
        }
      }
      
      return arr;
    };

    const parseString = (): string => {
      let result = '';
      index++; // consume opening quote
      currentColumn++;
      
      while (index < jsonString.length && jsonString[index] !== '"') {
        if (jsonString[index] === '\\') {
          index++;
          currentColumn++;
          if (index >= jsonString.length) {
            throw new Error(`Unexpected end of string at line ${currentLine}, column ${currentColumn}`);
          }
          
          const escapeChar = jsonString[index];
          switch (escapeChar) {
            case '"': result += '"'; break;
            case '\\': result += '\\'; break;
            case '/': result += '/'; break;
            case 'b': result += '\b'; break;
            case 'f': result += '\f'; break;
            case 'n': result += '\n'; break;
            case 'r': result += '\r'; break;
            case 't': result += '\t'; break;
            case 'u':
              // Simple unicode handling - just skip 4 characters
              index += 4;
              currentColumn += 4;
              result += '\\u';
              break;
            default:
              result += escapeChar;
          }
        } else {
          if (jsonString[index] === '\n') {
            currentLine++;
            currentColumn = 1;
          } else {
            currentColumn++;
          }
          result += jsonString[index];
        }
        index++;
      }
      
      if (index >= jsonString.length) {
        throw new Error(`Unterminated string at line ${currentLine}, column ${currentColumn}`);
      }
      
      index++; // consume closing quote
      currentColumn++;
      return result;
    };

    const parseNumber = (): number => {
      let result = '';
      
      if (jsonString[index] === '-') {
        result += jsonString[index];
        index++;
        currentColumn++;
      }
      
      while (index < jsonString.length && /\d/.test(jsonString[index])) {
        result += jsonString[index];
        index++;
        currentColumn++;
      }
      
      if (index < jsonString.length && jsonString[index] === '.') {
        result += jsonString[index];
        index++;
        currentColumn++;
        
        while (index < jsonString.length && /\d/.test(jsonString[index])) {
          result += jsonString[index];
          index++;
          currentColumn++;
        }
      }
      
      if (index < jsonString.length && /[eE]/.test(jsonString[index])) {
        result += jsonString[index];
        index++;
        currentColumn++;
        
        if (index < jsonString.length && /[+-]/.test(jsonString[index])) {
          result += jsonString[index];
          index++;
          currentColumn++;
        }
        
        while (index < jsonString.length && /\d/.test(jsonString[index])) {
          result += jsonString[index];
          index++;
          currentColumn++;
        }
      }
      
      const num = parseFloat(result);
      if (isNaN(num)) {
        throw new Error(`Invalid number '${result}' at line ${currentLine}, column ${currentColumn}`);
      }
      
      return num;
    };

    const parseBoolean = (): boolean => {
      if (jsonString.substr(index, 4) === 'true') {
        index += 4;
        currentColumn += 4;
        return true;
      } else if (jsonString.substr(index, 5) === 'false') {
        index += 5;
        currentColumn += 5;
        return false;
      } else {
        throw new Error(`Invalid boolean at line ${currentLine}, column ${currentColumn}`);
      }
    };

    const parseNull = (): null => {
      if (jsonString.substr(index, 4) === 'null') {
        index += 4;
        currentColumn += 4;
        return null;
      } else {
        throw new Error(`Invalid null at line ${currentLine}, column ${currentColumn}`);
      }
    };

    try {
      const result = parseValue();
      skipWhitespace();
      
      if (index < jsonString.length) {
        throw new Error(`Unexpected character '${jsonString[index]}' at line ${currentLine}, column ${currentColumn}`);
      }
      
      return { result, lineNumbers, propertyLineNumbers };
    } catch (error) {
      throw new Error(`JSON parse error at line ${currentLine}, column ${currentColumn}: ${error}`);
    }
  };

  // Recursive validation function for nested objects with line number tracking
  const validateNestedObject = (
    obj: Record<string, unknown>, 
    path: string = 'root',
    lineNumbers: WeakMap<object, number>,
    propertyLineNumbers: WeakMap<object, Map<string, number>>
  ): Array<{message: string, line: number}> => {
    const errors: Array<{message: string, line: number}> = [];
    
    // Helper function to get line number for an object
    const getLineNumber = (obj: object, fallback: number = 1): number => {
      return lineNumbers.get(obj) || fallback;
    };
    
    // Helper function to get line number for a property
    const getPropertyLineNumber = (obj: object, propertyName: string, fallback: number = 1): number => {
      const propMap = propertyLineNumbers.get(obj);
      return propMap?.get(propertyName) || getLineNumber(obj, fallback);
    };
    
    // Check if this is an object type
    if (obj.type === 'object') {
      // Check additionalProperties
      if (typeof obj.additionalProperties !== 'boolean') {
        errors.push({
          message: `${path} must have additionalProperties as a boolean`,
          line: getPropertyLineNumber(obj, 'additionalProperties')
        });
      }
      
      if (obj.additionalProperties !== false) {
        errors.push({
          message: `${path} must have additionalProperties = false`,
          line: getPropertyLineNumber(obj, 'additionalProperties')
        });
      }
      
      // Check properties exist
      if (!obj.properties || typeof obj.properties !== 'object') {
        errors.push({
          message: `${path} must have properties object`,
          line: getPropertyLineNumber(obj, 'properties')
        });
      }
      
      // Check required array exists
      if (!Array.isArray(obj.required)) {
        errors.push({
          message: `${path} must have required array`,
          line: getPropertyLineNumber(obj, 'required')
        });
      }
      
      // Check that all properties are required
      if (obj.properties && typeof obj.properties === 'object' && obj.required && Array.isArray(obj.required)) {
        const propertyNames = Object.keys(obj.properties as Record<string, unknown>);
        const missingRequired = propertyNames.filter(name => !(obj.required as string[]).includes(name));
        if (missingRequired.length > 0) {
          errors.push({
            message: `${path} has properties that are not required: ${missingRequired.join(', ')}`,
            line: getLineNumber(obj)
          });
        }
      }
      
      // Recursively validate nested objects
      if (obj.properties && typeof obj.properties === 'object') {
        for (const [propName, propValue] of Object.entries(obj.properties as Record<string, unknown>)) {
          
          const nestedPath = `${path}.${propName}`;
          const prop = propValue as Record<string, unknown>;
        
        // Check that each property has a type
        if (!prop.type) {
          errors.push({
            message: `${nestedPath} must have a type`,
            line: getLineNumber(prop)
          });
        }
        
        // Check that type is one of the allowed values
        const allowedTypes = ['string', 'integer', 'number', 'boolean', 'array', 'object'];
        if (!allowedTypes.includes(prop.type as string)) {
          errors.push({
            message: `${nestedPath} type must be one of: ${allowedTypes.join(', ')}`,
            line: getLineNumber(prop)
          });
        }
        
        // Check object type properties have properties element
        if (prop.type === 'object') {
          if (!prop.properties || typeof prop.properties !== 'object') {
            errors.push({
              message: `${nestedPath} (object type) must have a properties element`,
              line: getLineNumber(prop)
            });
          }
        }
        
        // Check array type properties have items element
        if (prop.type === 'array') {
          if (!prop.items) {
            errors.push({
              message: `${nestedPath} (array type) must have an items element`,
              line: getLineNumber(prop)
            });
          }
        }
        
        const nestedErrors = validateNestedObject(prop, nestedPath, lineNumbers, propertyLineNumbers);
        errors.push(...nestedErrors);
        
        // Check array items if it's an array type
        if (prop.type === 'array' && prop.items) {
          const arrayItemErrors = validateNestedObject(prop.items as Record<string, unknown>, `${nestedPath}.items`, lineNumbers, propertyLineNumbers);
          errors.push(...arrayItemErrors);
        }
        }
      }
    }
    
    return errors;
  };

  // Add handler for JSON schema changes
  const handleJsonSchemaChange = (value: string | undefined) => {
    if (!value) return;
    setJsonSchema(value);
    
      try {
        const { result: parsedSchema, lineNumbers, propertyLineNumbers } = parseJsonWithLineNumbers(value);
      const errors: Array<{message: string, line: number}> = [];
      
      // Helper functions for line number access
      const getLineNumber = (obj: object, fallback: number = 1): number => {
        return lineNumbers.get(obj) || fallback;
      };
      
      const getPropertyLineNumber = (obj: object, propertyName: string, fallback: number = 1): number => {
        const propMap = propertyLineNumbers.get(obj);
        return propMap?.get(propertyName) || getLineNumber(obj, fallback);
      };
      
      // Validate schema structure
      const schemaObj = parsedSchema as Record<string, unknown>;
      if (!schemaObj.json_schema || !(schemaObj.json_schema as Record<string, unknown>).schema) {
        errors.push({
          message: 'Invalid schema format. Must contain json_schema.schema',
          line: getLineNumber(schemaObj)
        });
        setValidationErrors(errors.map(e => `Line ${e.line}: ${e.message}`));
        return;
      }
      
      const schema = (schemaObj.json_schema as Record<string, unknown>).schema as Record<string, unknown>;
      
      // Validate required properties
      if (!schema.type || schema.type !== 'object') {
        errors.push({
          message: 'Schema type must be "object"',
          line: getPropertyLineNumber(schema, 'type')
        });
      }
      
      if (!schema.properties || typeof schema.properties !== 'object') {
        errors.push({
          message: 'Schema must have properties object',
          line: getPropertyLineNumber(schema, 'properties')
        });
      }
      
      if (!Array.isArray(schema.required)) {
        errors.push({
          message: 'Schema must have required array',
          line: getPropertyLineNumber(schema, 'required')
        });
      }
      
      // Check additionalProperties is present and is boolean
      if (typeof schema.additionalProperties !== 'boolean') {
        errors.push({
          message: 'additionalProperties must be a boolean',
          line: getPropertyLineNumber(schema, 'additionalProperties')
        });
      }
      
      // Validate that all properties are required at root level
      if (schema.properties && typeof schema.properties === 'object' && Array.isArray(schema.required)) {
        const propertyNames = Object.keys(schema.properties as Record<string, unknown>);
        const missingRequired = propertyNames.filter(name => !(schema.required as string[]).includes(name));
        if (missingRequired.length > 0) {
          errors.push({
            message: `Root schema has properties that are not required: ${missingRequired.join(', ')}`,
            line: getPropertyLineNumber(schema, 'required')
          });
        }
      }
      
      // Recursively validate all nested objects
      const validationErrors = validateNestedObject(schema, 'json_schema.schema', lineNumbers, propertyLineNumbers);
      errors.push(...validationErrors);
      
      setValidationErrors(errors.map(e => `Line ${e.line}: ${e.message}`));
      
      // Only update schema if no errors
      if (errors.length === 0) {
        // Use the parsed schema directly (no metadata properties to remove)
        const cleanSchema = schemaObj as unknown as SchemaResponseFormat;
        setCurrentSchema(prev => ({
          ...prev,
          response_format: cleanSchema
        }));
        
        // Update fields based on the new schema
        setFields(jsonSchemaToFields(cleanSchema));
      }
    } catch (error) {
      // Invalid JSON - extract line number from error message
      const errorStr = error instanceof Error ? error.message : String(error);
      const lineMatch = errorStr.match(/line (\d+)/);
      const line = lineMatch ? parseInt(lineMatch[1]) : 1;
      
      setValidationErrors([`Line ${line}: Invalid JSON syntax: ${errorStr}`]);
    }
  };


  const saveSchema = async (schema: SchemaConfig) => {
    try {
      setIsLoading(true);
      
      if (currentSchemaId) {
        await docRouterOrgApi.updateSchema({ schemaId: currentSchemaId, schema });
      } else {
        await docRouterOrgApi.createSchema(schema);
      }      

      router.push(`/orgs/${organizationId}/schemas`);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving schema';
      toast.error(errorMsg);
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
    
    // Check for validation errors first
    if (validationErrors.length > 0) {
      validationErrors.forEach(error => toast.error(error));
      return;
    }
    
    if (!currentSchema.name || fields.some(f => !f.name)) {
      toast.error('Please fill in all fields');
      return;
    }

    const fieldError = validateFields(fields);
    if (fieldError) {
      toast.error(fieldError);
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
  const fieldsToJsonSchema = (fields: SchemaField[]): SchemaResponseFormat => {
    const responseFormat = {
      type: 'json_schema' as const,
      json_schema: {
        name: 'document_extraction',
        schema: {
          type: 'object' as const,
          properties: {} as Record<string, SchemaProperty>,
          required: [] as string[],
          additionalProperties: false
        },
        strict: true
      }
    };

    const processField = (field: SchemaField): SchemaProperty => {
      let property: SchemaProperty;

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
    const processArrayItemType = (field: SchemaField): SchemaProperty => {
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
          const objectProperty: SchemaProperty = {
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
        <div className="hidden md:flex items-center gap-3 mb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold">
              {currentSchemaId ? 'Edit Schema' : 'Create Schema'}
            </h2>
            {currentSchemaFull && (
              <button
                onClick={() => setIsInfoModalOpen(true)}
                className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-full transition-colors"
                title="View schema information"
              >
                <InfoIcon className="text-lg" />
              </button>
            )}
          </div>
          {currentSchemaFull && currentSchemaId && (
            <div className="flex items-center gap-3">
              <SchemaVersionSelector
                organizationId={organizationId}
                schemaId={currentSchemaId}
                currentVersion={currentSchemaFull.schema_version}
                currentSchemaRevId={currentSchemaFull.schema_revid}
                onVersionSelect={async (schemaRevId, version) => {
                  try {
                    setIsLoading(true);
                    const schema = await docRouterOrgApi.getSchema({ schemaRevId });
                    setCurrentSchemaFull(schema);
                    setViewingVersion(version);
                    // Check if this is the latest version
                    const versionsResponse = await docRouterOrgApi.listSchemaVersions({ schemaId: currentSchemaId });
                    const latestVersion = versionsResponse.schemas.sort((a, b) => b.schema_version - a.schema_version)[0];
                    setIsReadOnly(version !== latestVersion.schema_version);
                    setCurrentSchema({
                      name: schema.name,
                      response_format: schema.response_format
                    });
                    setFields(jsonSchemaToFields(schema.response_format));
                    // Update URL to reflect the selected version
                    router.push(`/orgs/${organizationId}/schemas/${schemaRevId}`);
                  } catch (error) {
                    toast.error(`Error loading schema version: ${getApiErrorMsg(error)}`);
                  } finally {
                    setIsLoading(false);
                  }
                }}
              />
              <button
                onClick={() => setIsCompareModalOpen(true)}
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50 transition-colors"
              >
                <CompareArrowsIcon className="text-base" />
                <span>Compare Versions</span>
              </button>
            </div>
          )}
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
        
        {isReadOnly && currentSchemaFull && (
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-800">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                Viewing version {viewingVersion} (read-only). This is not the latest version.
              </span>
              <button
                type="button"
                onClick={async () => {
                  if (!currentSchemaId) return;
                  try {
                    setIsLoading(true);
                    const versionsResponse = await docRouterOrgApi.listSchemaVersions({ schemaId: currentSchemaId });
                    const latestVersion = versionsResponse.schemas.sort((a, b) => b.schema_version - a.schema_version)[0];
                    const schema = await docRouterOrgApi.getSchema({ schemaRevId: latestVersion.schema_revid });
                    setCurrentSchemaFull(schema);
                    setViewingVersion(schema.schema_version);
                    setIsReadOnly(false);
                    setCurrentSchema({
                      name: schema.name,
                      response_format: schema.response_format
                    });
                    setFields(jsonSchemaToFields(schema.response_format));
                    router.push(`/orgs/${organizationId}/schemas/${latestVersion.schema_revid}`);
                  } catch (error) {
                    toast.error(`Error loading latest version: ${getApiErrorMsg(error)}`);
                  } finally {
                    setIsLoading(false);
                  }
                }}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium underline"
              >
                View Latest Version
              </button>
            </div>
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Schema Name Input and Action Buttons in a flex container */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1 md:w-1/2 md:max-w-[calc(50%-1rem)]">
              <input
                type="text"
                className="w-full p-2 border rounded"
                value={currentSchema.name}
                onChange={e => setCurrentSchema({ ...currentSchema, name: e.target.value })}
                placeholder="Schema Name"
                disabled={isLoading || isReadOnly}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  // Clear the form
                  setCurrentSchemaId(null);
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
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
                disabled={isLoading || isReadOnly}
              >
                Clear
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={isLoading || isReadOnly}
              >
                {currentSchemaId ? 'Update Schema' : 'Save Schema'}
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
                JSON Schema
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
                                      disabled={isLoading || isReadOnly}
                                    />
                                    <select
                                      className="p-1.5 border rounded text-sm w-24"
                                      value={field.type}
                                      onChange={e => updateField(index, { type: e.target.value as SchemaField['type'] })}
                                      disabled={isLoading || isReadOnly}
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
                                      disabled={isLoading || isReadOnly}
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
                                      disabled={isLoading || isReadOnly}
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
                                    disabled={isLoading || isReadOnly}
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
                                          isReadOnly={isReadOnly}
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
                                              disabled={isLoading || isReadOnly}
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
                                                isReadOnly={isReadOnly}
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
                  disabled={isLoading || isReadOnly}
                >
                  Add Field
                </button>
              </div>
            ) : (
              // JSON Schema Tab
              <div className="h-[calc(100vh-300px)] border rounded">
                <Editor
                  height="100%"
                  defaultLanguage="json"
                  value={jsonSchema}
                  onChange={handleJsonSchemaChange}
                  options={{
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    wordWrap: "on",
                    wrappingIndent: "indent",
                    lineNumbers: "on",
                    folding: true,
                    renderValidationDecorations: "on",
                    readOnly: isReadOnly
                  }}
                  theme="vs-light"
                />
              </div>
            )}
          </div>
        </form>
      </div>
      
      {/* Info Modal */}
      {currentSchemaFull && (
        <>
          <SchemaInfoModal
            isOpen={isInfoModalOpen}
            onClose={() => setIsInfoModalOpen(false)}
            schema={currentSchemaFull}
          />
          
          {/* Compare Versions Modal */}
          <SchemaVersionCompareModal
            isOpen={isCompareModalOpen}
            onClose={() => setIsCompareModalOpen(false)}
            organizationId={organizationId}
            schemaId={currentSchemaId!}
            currentSchema={currentSchemaFull}
            onCompare={(leftSchema, rightSchema) => {
              setDiffSchemas({ left: leftSchema, right: rightSchema });
            }}
          />
          
          {/* Diff View */}
          {diffSchemas.left && diffSchemas.right && (
            <SchemaDiffView
              leftSchema={diffSchemas.left}
              rightSchema={diffSchemas.right}
              onClose={() => setDiffSchemas({ left: null, right: null })}
            />
          )}
        </>
      )}
    </div>
  );
};

export default SchemaCreate;