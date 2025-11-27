# DocRouter TypeScript SDK Installation and Usage Guide

## Overview

The DocRouter TypeScript SDK provides type-safe access to the DocRouter API, enabling developers to integrate document processing, OCR, LLM operations, and organization management into their applications. The SDK supports both Node.js and browser environments with comprehensive TypeScript support.

## Installation

### Prerequisites

- **Node.js 16+** (for Node.js usage)
- **TypeScript 4.9+** (recommended for type safety)
- **DocRouter API access** with appropriate tokens

### Install the Package

```bash
npm install @docrouter/sdk
```

### TypeScript Configuration

For optimal TypeScript support, ensure your `tsconfig.json` includes:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

## Authentication Methods

The SDK supports three authentication strategies:

### 1. Account Token (Server-to-Server)

Use `DocRouterAccount` for account-level operations with account tokens:

```typescript
import { DocRouterAccount } from '@docrouter/sdk';

const client = new DocRouterAccount({
  baseURL: 'https://api.docrouter.com',
  accountToken: 'your-account-token-here'
});
```

**Use cases:**
- Server-to-server applications
- Organization management
- Token creation and management
- User management

### 2. Organization Token

Use `DocRouterOrg` for organization-scoped operations:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-org-token-here',
  organizationId: 'org-123'
});
```

**Use cases:**
- Document processing within an organization
- OCR operations
- LLM operations
- Tag management

### 3. JWT Token (Browser)

Use `DocRouterOrg` with JWT tokens for browser applications:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-jwt-token-here',
  organizationId: 'your-org-id'
});
```

**Use cases:**
- Browser-based applications
- Client-side document processing
- Real-time chat interfaces

## Quick Start Examples

### Basic Account Operations

```typescript
import { DocRouterAccount } from '@docrouter/sdk';

const client = new DocRouterAccount({
  baseURL: 'https://api.docrouter.com',
  accountToken: 'your-account-token'
});

// List organizations
const orgs = await client.listOrganizations();

// Create organization token
const token = await client.createOrganizationToken({
  name: 'My App Token',
  lifetime: 86400 // 24 hours
}, 'org-123');
```

### Document Processing

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-org-token',
  organizationId: 'org-123'
});

// Upload documents
const result = await client.uploadDocuments({
  documents: [
    {
      name: 'document.pdf',
      content: fileBuffer,
      type: 'application/pdf'
    }
  ]
});

// List documents
const documents = await client.listDocuments();

// Get document details
const document = await client.getDocument({
  documentId: 'doc-123',
  fileType: 'pdf'
});
```

## API Reference

### DocRouterAccount Client

The `DocRouterAccount` client provides account-level operations:

```typescript
const client = new DocRouterAccount({
  baseURL: 'https://api.docrouter.com',
  accountToken: 'your-account-token'
});

// Available methods:
client.listOrganizations()     // List organizations
client.getOrganization()       // Get organization details
client.createOrganization()    // Create organization
client.updateOrganization()    // Update organization
client.deleteOrganization()    // Delete organization
client.createAccountToken()    // Create account token
client.getAccountTokens()      // List account tokens
client.deleteAccountToken()    // Delete account token
client.createOrganizationToken() // Create organization token
client.listLLMModels()         // List LLM models
client.listLLMProviders()      // List LLM providers
client.setLLMProviderConfig()  // Configure LLM provider
client.listUsers()             // List users
client.getUser()               // Get user details
client.createUser()            // Create user
client.updateUser()            // Update user
client.deleteUser()            // Delete user
```

#### Organization Management

```typescript
// List all organizations
const orgs = await client.listOrganizations();

// Get organization details
const org = await client.getOrganization('org-123');

// Create new organization
const newOrg = await client.createOrganization({
  name: 'My Organization',
  description: 'Organization description'
});

// Update organization
await client.updateOrganization('org-123', {
  name: 'Updated Name'
});

// Delete organization
await client.deleteOrganization('org-123');
```

#### Token Management

```typescript
// Create account token
const accountToken = await client.createAccountToken({
  name: 'My Account Token',
  lifetime: 86400
});

// List account tokens
const tokens = await client.getAccountTokens();

// Create organization token
const orgToken = await client.createOrganizationToken({
  name: 'My Org Token',
  lifetime: 86400
}, 'org-123');

// Delete token
await client.deleteAccountToken('token-id');
```

#### User Management

```typescript
// List users
const users = await client.listUsers();

// Get user details
const user = await client.getUser('user-123');

// Create user
const newUser = await client.createUser({
  email: 'user@example.com',
  name: 'John Doe'
});

// Update user
await client.updateUser('user-123', {
  name: 'John Smith'
});
```

### DocRouterOrg Client

The `DocRouterOrg` client provides organization-scoped operations:

```typescript
const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-org-token',
  organizationId: 'org-123'
});

// Available methods:
client.uploadDocuments()       // Upload documents
client.listDocuments()         // List documents
client.getDocument()           // Get document details
client.updateDocument()        // Update document
client.deleteDocument()        // Delete document
client.getOCRBlocks()          // Get OCR blocks
client.getOCRText()            // Get OCR text
client.getOCRMetadata()        // Get OCR metadata
client.runLLM()                // Run LLM on document
client.getLLMResult()          // Get LLM result
client.updateLLMResult()       // Update LLM result
client.deleteLLMResult()       // Delete LLM result
client.runLLMChat()            // Run LLM chat
client.runLLMChatStream()      // Stream LLM chat
client.createTag()             // Create tag
client.getTag()                // Get tag details
client.listTags()              // List tags
client.updateTag()             // Update tag
client.deleteTag()             // Delete tag
client.createForm()            // Create form
client.listForms()             // List forms
client.getForm()               // Get form details
client.updateForm()            // Update form
client.deleteForm()            // Delete form
client.submitForm()            // Submit form
client.createPrompt()          // Create prompt
client.listPrompts()           // List prompts
client.getPrompt()             // Get prompt details
client.updatePrompt()          // Update prompt
client.deletePrompt()          // Delete prompt
client.createSchema()          // Create schema
client.listSchemas()           // List schemas
client.getSchema()             // Get schema details
client.updateSchema()          // Update schema
client.deleteSchema()          // Delete schema
client.validateAgainstSchema() // Validate data against schema
client.getCustomerPortal()     // Get customer portal
client.getSubscription()       // Get subscription
client.activateSubscription()  // Activate subscription
client.cancelSubscription()    // Cancel subscription
client.getCurrentUsage()       // Get current usage
client.addCredits()            // Add credits
client.getCreditConfig()       // Get credit configuration
client.purchaseCredits()       // Purchase credits
client.getUsageRange()         // Get usage range
client.createCheckoutSession() // Create checkout session
```

#### Document Management

```typescript
// Upload documents
const uploadResult = await client.uploadDocuments({
  documents: [
    {
      name: 'invoice.pdf',
      content: fileBuffer,
      type: 'application/pdf'
    }
  ]
});

// List documents with filtering
const documents = await client.listDocuments({
  limit: 10,
  skip: 0,
  tagIds: 'tag1,tag2'
});

// Get document details and content
const document = await client.getDocument({
  documentId: 'doc-123',
  fileType: 'pdf'
});

// Update document metadata
await client.updateDocument({
  documentId: 'doc-123',
  documentName: 'Updated Document Name',
  tagIds: ['tag1', 'tag2']
});

// Delete document
await client.deleteDocument({
  documentId: 'doc-123'
});
```

#### OCR Operations

```typescript
// Get OCR blocks (structured text data)
const ocrBlocks = await client.getOCRBlocks({
  documentId: 'doc-123'
});

// Get OCR text (plain text)
const ocrText = await client.getOCRText({
  documentId: 'doc-123'
});

// Get OCR metadata
const ocrMetadata = await client.getOCRMetadata({
  documentId: 'doc-123'
});
```

#### LLM Operations

```typescript
// Run LLM chat
const chatResponse = await client.runLLMChat({
  messages: [
    { role: 'user', content: 'Extract key information from this document' }
  ],
  model: 'gpt-4'
});

// Run LLM on document
const llmResult = await client.runLLM({
  documentId: 'doc-123',
  promptRevId: 'prompt-123'
});

// Get LLM result
const result = await client.getLLMResult({
  documentId: 'doc-123',
  promptRevId: 'prompt-123'
});

// Update LLM result
await client.updateLLMResult({
  documentId: 'doc-123',
  promptRevId: 'prompt-123',
  content: 'Updated result content'
});

// Delete LLM result
await client.deleteLLMResult({
  documentId: 'doc-123',
  promptId: 'prompt-123'
});
```

#### Tag Management

```typescript
// Create tag
const tag = await client.createTag({
  tag: {
    name: 'invoice',
    color: '#ff0000',
    description: 'Invoice documents'
  }
});

// Get tag details
const tagDetails = await client.getTag({
  tagId: 'tag-123'
});

// List tags
const tags = await client.listTags({
  limit: 20,
  skip: 0
});

// Update tag
await client.updateTag({
  tagId: 'tag-123',
  tag: {
    name: 'Updated Tag Name',
    color: '#00ff00'
  }
});

// Delete tag
await client.deleteTag({
  tagId: 'tag-123'
});
```

#### Form Management

```typescript
// Create form
const form = await client.createForm({
  name: 'Invoice Form',
  description: 'Form for invoice data extraction',
  jsonFormio: formioDefinition,
  jsonFormioMapping: mappingDefinition
});

// List forms
const forms = await client.listForms({
  limit: 10,
  skip: 0
});

// Get form details
const formDetails = await client.getForm({
  formId: 'form-123'
});

// Update form
await client.updateForm({
  formId: 'form-123',
  name: 'Updated Form Name'
});

// Submit form
const submission = await client.submitForm({
  formId: 'form-123',
  documentId: 'doc-123',
  data: formData
});

// Delete form
await client.deleteForm({
  formId: 'form-123'
});
```

#### Prompt Management

```typescript
// Create prompt
const prompt = await client.prompts.create({
  name: 'Invoice Extraction',
  content: 'Extract invoice number, date, and total amount',
  description: 'Prompt for extracting invoice data'
});

// List prompts
const prompts = await client.prompts.list({
  limit: 10,
  skip: 0
});

// Get prompt details
const promptDetails = await client.prompts.get({
  promptId: 'prompt-123'
});

// Update prompt
await client.prompts.update({
  promptId: 'prompt-123',
  content: 'Updated prompt content'
});

// Delete prompt
await client.prompts.delete({
  promptId: 'prompt-123'
});
```

#### Schema Management

```typescript
// Create schema
const schema = await client.schemas.create({
  name: 'Invoice Schema',
  description: 'Schema for invoice data validation',
  jsonSchema: schemaDefinition
});

// List schemas
const schemas = await client.schemas.list({
  limit: 10,
  skip: 0
});

// Get schema details
const schemaDetails = await client.schemas.get({
  schemaId: 'schema-123'
});

// Update schema
await client.schemas.update({
  schemaId: 'schema-123',
  name: 'Updated Schema Name'
});

// Delete schema
await client.schemas.delete({
  schemaId: 'schema-123'
});
```

#### Payment and Subscription Management

```typescript
// Create portal session
const portalSession = await client.payments.createPortalSession({
  returnUrl: 'https://yourapp.com/return'
});

// Get subscription details
const subscription = await client.payments.getSubscription();

// Get usage information
const usage = await client.payments.getUsage();

// Get usage for date range
const usageRange = await client.payments.getUsageRange({
  startDate: '2024-01-01',
  endDate: '2024-01-31'
});

// Update credit configuration
const creditUpdate = await client.payments.updateCreditConfig({
  credits: 1000,
  resetPeriod: 'monthly'
});
```

## Error Handling

The SDK provides comprehensive error handling with retry logic and authentication callbacks:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-org-token',
  organizationId: 'org-123',
  onAuthError: (error) => {
    console.error('Authentication error:', error);
    // Handle token refresh or re-authentication
  }
});

try {
  const documents = await client.documents.list();
} catch (error) {
  if (error.status === 401) {
    // Handle authentication error
    console.error('Unauthorized access');
  } else if (error.status === 429) {
    // Handle rate limiting
    console.error('Rate limited, retrying...');
  } else {
    // Handle other errors
    console.error('API error:', error.message);
  }
}
```

## Streaming Support

The SDK supports real-time streaming for LLM operations:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-jwt-token',
  organizationId: 'your-org-id'
});

// Stream LLM responses
const abortController = new AbortController();

await client.runLLMChatStream({
  messages: [
    { role: 'user', content: 'Analyze this document step by step' }
  ],
  model: 'gpt-4'
}, (chunk) => {
  // Handle each chunk of the response
  console.log('Chunk received:', chunk);
  
  // You can abort the stream if needed
  if (shouldAbort) {
    abortController.abort();
  }
}, (error) => {
  // Handle stream errors
  console.error('Stream error:', error);
}, abortController.signal);
```

## Browser Usage

The SDK works in browser environments with proper polyfills:

```typescript
// In a browser environment
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-jwt-token',
  organizationId: 'your-org-id'
});

// File upload from browser
const fileInput = document.getElementById('fileInput') as HTMLInputElement;
const file = fileInput.files[0];

if (file) {
  const fileBuffer = await file.arrayBuffer();
  
  const result = await client.uploadDocuments({
    documents: [
      {
        name: file.name,
        content: fileBuffer,
        type: file.type
      }
    ]
  });
}
```

## Advanced Configuration

### Custom HTTP Client

You can provide custom configuration for the underlying HTTP client:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-org-token',
  organizationId: 'org-123',
  timeout: 30000, // 30 seconds
  retries: 3,
  retryDelay: 1000 // 1 second
});
```

### Environment-Specific Configuration

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const config = {
  development: {
    baseURL: 'http://localhost:8000',
    orgToken: process.env.DOCROUTER_DEV_TOKEN,
    organizationId: process.env.DOCROUTER_DEV_ORG_ID
  },
  production: {
    baseURL: 'https://api.docrouter.com',
    orgToken: process.env.DOCROUTER_PROD_TOKEN,
    organizationId: process.env.DOCROUTER_PROD_ORG_ID
  }
};

const environment = process.env.NODE_ENV || 'development';
const client = new DocRouterOrg(config[environment]);
```

## Testing

The SDK includes comprehensive testing utilities:

```typescript
// Unit tests
npm run test:unit

// Integration tests
npm run test:integration

// All tests
npm run test:all
```

### Mocking for Tests

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

// Mock the client for testing
jest.mock('@docrouter/sdk');

const mockClient = {
  documents: {
    list: jest.fn().mockResolvedValue({
      documents: [],
      total: 0,
      skip: 0,
      limit: 10
    })
  }
};

(DocRouterOrg as jest.Mock).mockImplementation(() => mockClient);
```

## Best Practices

### 1. Error Handling

Always implement proper error handling:

```typescript
try {
  const result = await client.uploadDocuments(params);
  return result;
} catch (error) {
  if (error.status === 401) {
    // Handle authentication
    throw new Error('Authentication failed');
  } else if (error.status === 429) {
    // Handle rate limiting
    await new Promise(resolve => setTimeout(resolve, 1000));
    return client.uploadDocuments(params); // Retry
  } else {
    // Handle other errors
    throw new Error(`API error: ${error.message}`);
  }
}
```

### 2. Type Safety

Leverage TypeScript for type safety:

```typescript
import { DocRouterOrg, Document, UploadDocumentsParams } from '@docrouter/sdk';

const client = new DocRouterOrg(config);

// Type-safe parameters
const uploadParams: UploadDocumentsParams = {
  organizationId: 'org-123',
  documents: [
    {
      name: 'document.pdf',
      content: fileBuffer,
      type: 'application/pdf'
    }
  ]
};

// Type-safe response
const result = await client.uploadDocuments(uploadParams);
const documents: Document[] = result.documents;
```

### 3. Resource Management

Properly manage resources and connections:

```typescript
class DocumentService {
  private client: DocRouterOrg;
  
  constructor(config: DocRouterOrgConfig) {
    this.client = new DocRouterOrg(config);
  }
  
  async uploadDocument(file: File): Promise<Document> {
    const fileBuffer = await file.arrayBuffer();
    
    const result = await this.client.uploadDocuments({
      documents: [{
        name: file.name,
        content: fileBuffer,
        type: file.type
      }]
    });
    
    return result.documents[0];
  }
  
  // Cleanup method
  destroy() {
    // Clean up any resources if needed
  }
}
```

### 4. Environment Variables

Use environment variables for configuration:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: process.env.DOCROUTER_API_URL || 'https://api.docrouter.com',
  orgToken: process.env.DOCROUTER_ORG_TOKEN!,
  organizationId: process.env.DOCROUTER_ORG_ID!
});
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**Problem**: 401 Unauthorized errors

**Solutions**:
- Verify your token is valid and not expired
- Check that you're using the correct token type for your client
- Ensure the organization ID is correct for `DocRouterOrg`

#### 2. TypeScript Errors

**Problem**: Type errors or missing types

**Solutions**:
- Ensure you're using TypeScript 4.9+
- Check that all imports are correct
- Verify your `tsconfig.json` configuration

#### 3. Network Errors

**Problem**: Connection timeouts or network errors

**Solutions**:
- Check your network connection
- Verify the API URL is correct
- Increase timeout values if needed
- Check for firewall or proxy issues

#### 4. Rate Limiting

**Problem**: 429 Too Many Requests errors

**Solutions**:
- Implement exponential backoff
- Reduce request frequency
- Use streaming for large operations
- Contact support for rate limit increases

### Debug Mode

Enable debug logging:

```typescript
const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-org-token',
  organizationId: 'org-123',
  debug: true // Enable debug logging
});
```

## Package Information

- **Package Name**: `@docrouter/sdk`
- **Current Version**: 0.1.0
- **Node.js Requirement**: >=16.0.0
- **TypeScript Requirement**: >=4.9.0
- **License**: MIT
- **Repository**: Available on npm registry

### Dependencies

- **axios**: HTTP client for API requests
- **TypeScript**: Type definitions and compilation

### Development Dependencies

- **Jest**: Testing framework
- **ESLint**: Code linting
- **tsup**: Build tool
- **Various type definitions**: For enhanced TypeScript support

## Support and Resources

### Getting Help

1. **Check the API documentation** for detailed endpoint information
2. **Review the examples** in the package repository
3. **Check the troubleshooting section** above
4. **Enable debug mode** for detailed logging
5. **Contact support** for API-specific issues

### Package Management

```bash
# Update to latest version
npm update @docrouter/sdk

# Check current version
npm list @docrouter/sdk

# Install specific version
npm install @docrouter/sdk@0.1.0
```

### Development

For developers working on the SDK:

```bash
# Clone the repository
git clone <repository-url>
cd packages/typescript/sdk

# Install dependencies
npm install

# Build the package
npm run build

# Run tests
npm run test:all

# Development mode
npm run dev
```

The DocRouter TypeScript SDK provides a powerful, type-safe way to integrate DocRouter's document processing capabilities into your applications. With comprehensive API coverage, streaming support, and excellent TypeScript integration, it's the ideal choice for building document processing applications.
