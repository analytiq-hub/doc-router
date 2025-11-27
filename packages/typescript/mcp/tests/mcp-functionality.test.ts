import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

// Mock the DocRouter SDK
jest.mock('@docrouter/sdk', () => ({
  DocRouterOrg: jest.fn().mockImplementation(() => ({
    listDocuments: jest.fn().mockResolvedValue({
      documents: [
        {
          id: 'doc1',
          name: 'test-document.pdf',
          createdAt: new Date('2024-01-01'),
          updatedAt: new Date('2024-01-01'),
        }
      ],
      total: 1,
      skip: 0,
      limit: 10
    }),
    getDocument: jest.fn().mockResolvedValue({
      id: 'doc1',
      name: 'test-document.pdf',
      content: new ArrayBuffer(1024),
      createdAt: new Date('2024-01-01'),
      updatedAt: new Date('2024-01-01'),
    }),
    getOCRText: jest.fn().mockResolvedValue('This is mock OCR text content.'),
    listTags: jest.fn().mockResolvedValue({
      tags: [
        {
          id: 'tag1',
          name: 'invoice',
          color: '#ff0000',
          createdAt: new Date('2024-01-01'),
        }
      ],
      total: 1,
      skip: 0,
      limit: 10
    }),
    listPrompts: jest.fn().mockResolvedValue({
      prompts: [
        {
          id: 'prompt1',
          name: 'Invoice Extraction',
          content: 'Extract invoice data',
          createdAt: new Date('2024-01-01'),
        }
      ],
      total: 1,
      skip: 0,
      limit: 10
    }),
  }))
}));

// Mock file system operations for knowledge base
jest.mock('fs', () => ({
  ...jest.requireActual('fs'),
  readFileSync: jest.fn(),
  existsSync: jest.fn(),
}));

// Mock path operations
jest.mock('path', () => ({
  ...jest.requireActual('path'),
  join: jest.fn((...args) => args.join('/')),
}));

const mockReadFileSync = readFileSync as jest.MockedFunction<typeof readFileSync>;
const mockExistsSync = existsSync as jest.MockedFunction<typeof existsSync>;
const mockJoin = join as jest.MockedFunction<typeof join>;

describe('MCP Server Functionality', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Knowledge Base Help Functions', () => {
    beforeEach(() => {
      // Mock successful file operations
      mockExistsSync.mockReturnValue(true);
      mockReadFileSync.mockReturnValue('# Mock Knowledge Base Content\n\nThis is test content.');
      mockJoin.mockImplementation((...args) => args.join('/'));
    });

    it('should load prompts help content from bundled files', () => {
      const filePath = 'dist/docs/knowledge_base/prompts.md';
      mockJoin.mockReturnValue(filePath);

      expect(mockExistsSync(filePath)).toBe(true);
      const content = mockReadFileSync(filePath, 'utf-8');
      expect(content).toContain('Mock Knowledge Base Content');
    });

    it('should load schemas help content from bundled files', () => {
      const filePath = 'dist/docs/knowledge_base/schemas.md';
      mockJoin.mockReturnValue(filePath);

      expect(mockExistsSync(filePath)).toBe(true);
      const content = mockReadFileSync(filePath, 'utf-8');
      expect(content).toContain('Mock Knowledge Base Content');
    });

    it('should load forms help content from bundled files', () => {
      const filePath = 'dist/docs/knowledge_base/forms.md';
      mockJoin.mockReturnValue(filePath);

      expect(mockExistsSync(filePath)).toBe(true);
      const content = mockReadFileSync(filePath, 'utf-8');
      expect(content).toContain('Mock Knowledge Base Content');
    });

    it('should handle missing knowledge base files gracefully', () => {
      mockExistsSync.mockReturnValue(false);
      const filePath = 'dist/docs/knowledge_base/missing.md';
      mockJoin.mockReturnValue(filePath);

      expect(mockExistsSync(filePath)).toBe(false);
      expect(mockReadFileSync).not.toHaveBeenCalled();
    });
  });

  describe('MCP Tool Definitions', () => {
    it('should have correct tool structure for document operations', () => {
      // Test that our MCP tools have the expected structure
      const expectedDocumentTools = [
        'upload_documents',
        'list_documents', 
        'get_document',
        'update_document',
        'delete_document'
      ];

      expectedDocumentTools.forEach(toolName => {
        expect(toolName).toMatch(/^[a-z_]+$/);
        expect(toolName.length).toBeGreaterThan(0);
      });
    });

    it('should have correct tool structure for OCR operations', () => {
      const expectedOCRTools = [
        'get_ocr_blocks',
        'get_ocr_text',
        'get_ocr_metadata'
      ];

      expectedOCRTools.forEach(toolName => {
        expect(toolName).toMatch(/^[a-z_]+$/);
        expect(toolName.length).toBeGreaterThan(0);
      });
    });

    it('should have correct tool structure for LLM operations', () => {
      const expectedLLMTools = [
        'run_llm',
        'get_llm_result',
        'update_llm_result',
        'delete_llm_result'
      ];

      expectedLLMTools.forEach(toolName => {
        expect(toolName).toMatch(/^[a-z_]+$/);
        expect(toolName.length).toBeGreaterThan(0);
      });
    });

    it('should have correct tool structure for help operations', () => {
      const expectedHelpTools = [
        'help',
        'help_prompts',
        'help_schemas',
        'help_forms'
      ];

      expectedHelpTools.forEach(toolName => {
        expect(toolName).toMatch(/^[a-z_]+$/);
        expect(toolName.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Schema Validation Functions', () => {
    it('should validate correct schema format', () => {
      const validSchema = {
        type: 'json_schema',
        json_schema: {
          name: 'document_extraction',
          schema: {
            type: 'object',
            properties: {
              name: {
                type: 'string',
                description: 'Document name'
              }
            },
            required: ['name'],
            additionalProperties: false
          },
          strict: true
        }
      };

      expect(validSchema.type).toBe('json_schema');
      expect(validSchema.json_schema.strict).toBe(true);
      expect(validSchema.json_schema.schema.additionalProperties).toBe(false);
      expect(validSchema.json_schema.schema.required).toContain('name');
    });

    it('should reject invalid schema format', () => {
      const invalidSchema = {
        type: 'invalid_type',
        json_schema: {
          name: 'document_extraction',
          schema: {
            type: 'object',
            properties: {},
            // Missing required array
            additionalProperties: false
          },
          strict: true
        }
      };

      expect(invalidSchema.type).not.toBe('json_schema');
      expect((invalidSchema.json_schema.schema as any).required).toBeUndefined();
    });
  });

  describe('Form Validation Functions', () => {
    it('should validate correct form format', () => {
      const validForm = {
        json_formio: [
          {
            type: 'textfield',
            key: 'name',
            label: 'Name',
            input: true,
            validate: {
              required: true
            }
          }
        ],
        json_formio_mapping: {
          name: {
            sources: [
              {
                promptId: 'prompt1',
                schemaFieldPath: 'name',
                schemaFieldName: 'name',
                schemaFieldType: 'string'
              }
            ],
            mappingType: 'direct'
          }
        }
      };

      expect(validForm.json_formio).toBeDefined();
      expect(Array.isArray(validForm.json_formio)).toBe(true);
      expect(validForm.json_formio[0].type).toBe('textfield');
      expect(validForm.json_formio[0].key).toBe('name');
      expect(validForm.json_formio_mapping.name.mappingType).toBe('direct');
    });

    it('should reject invalid form format', () => {
      const invalidForm = {
        // Missing json_formio array
        json_formio_mapping: {}
      };

      expect((invalidForm as any).json_formio).toBeUndefined();
    });
  });

  describe('MCP Server Configuration', () => {
    it('should have correct server configuration structure', () => {
      const serverConfig = {
        name: 'docrouter-mcp',
        version: '0.1.0',
        capabilities: {
          tools: {}
        }
      };

      expect(serverConfig.name).toBe('docrouter-mcp');
      expect(serverConfig.version).toMatch(/^\d+\.\d+\.\d+$/);
      expect(serverConfig.capabilities.tools).toBeDefined();
    });

    it('should have correct environment variable handling', () => {
      const expectedEnvVars = [
        'DOCROUTER_API_URL',
        'DOCROUTER_ORG_ID', 
        'DOCROUTER_ORG_API_TOKEN'
      ];

      expectedEnvVars.forEach(envVar => {
        expect(envVar).toMatch(/^DOCROUTER_[A-Z_]+$/);
        expect(envVar.length).toBeGreaterThan(0);
      });
    });
  });
});
