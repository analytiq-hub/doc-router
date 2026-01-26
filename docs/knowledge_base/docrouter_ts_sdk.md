# DocRouter TypeScript SDK Installation and Usage Guide

## Overview

The DocRouter TypeScript SDK provides type-safe access to the DocRouter API, enabling developers to integrate document processing, OCR, LLM operations, knowledge bases, forms, schemas, and organization management into their applications. The SDK supports both Node.js and browser environments with comprehensive TypeScript support.

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

The SDK supports two main authentication strategies:

### 1. Account Token (Server-to-Server)

Use `DocRouterAccount` for account-level operations with account tokens:

```typescript
import { DocRouterAccount } from '@docrouter/sdk';

const client = new DocRouterAccount({
  baseURL: 'https://app.docrouter.ai/fastapi',
  accountToken: 'your-account-token-here'
});
```

**Use cases:**
- Server-to-server applications
- Organization management
- Token creation and management
- User management
- Account-level LLM operations

### 2. Organization Token

Use `DocRouterOrg` for organization-scoped operations:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://app.docrouter.ai/fastapi',
  orgToken: 'your-org-token-here',
  organizationId: 'org-123'
});
```

**Use cases:**
- Document processing within an organization
- OCR operations
- LLM operations
- Tag, prompt, schema, and form management
- Knowledge base operations
- Payment and subscription management

**Note**: The organization ID can be resolved from the token using `DocRouterAccount.getOrganizationFromToken()`.

## Quick Start Examples

### Basic Account Operations

```typescript
import { DocRouterAccount } from '@docrouter/sdk';

const client = new DocRouterAccount({
  baseURL: 'https://app.docrouter.ai/fastapi',
  accountToken: 'your-account-token'
});

// List organizations
const orgs = await client.listOrganizations();

// Get organization from token
const orgInfo = await client.getOrganizationFromToken('org-token');

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
  baseURL: 'https://app.docrouter.ai/fastapi',
  orgToken: 'your-org-token',
  organizationId: 'org-123'
});

// Upload documents (content should be base64 encoded)
const result = await client.uploadDocuments({
  documents: [
    {
      name: 'document.pdf',
      content: base64Content, // Base64 string or data URL
      tag_ids: ['tag-1', 'tag-2'],
      metadata: { category: 'invoice' }
    }
  ]
});

// List documents with filtering
const documents = await client.listDocuments({
  skip: 0,
  limit: 10,
  tagIds: 'tag-1,tag-2',
  nameSearch: 'invoice',
  metadataSearch: 'category=invoice'
});

// Get document details and content
const document = await client.getDocument({
  documentId: 'doc-123',
  fileType: 'pdf' // or 'original'
});

// Update document metadata
await client.updateDocument({
  documentId: 'doc-123',
  documentName: 'Updated Document Name',
  tagIds: ['tag-1', 'tag-2'],
  metadata: { category: 'updated' }
});

// Delete document
await client.deleteDocument({
  documentId: 'doc-123'
});
```

## API Reference

### DocRouterAccount Client

The `DocRouterAccount` client provides account-level operations:

```typescript
const client = new DocRouterAccount({
  baseURL: 'https://app.docrouter.ai/fastapi',
  accountToken: 'your-account-token'
});
```

#### Organization Management

```typescript
// List organizations with optional filters
const orgs = await client.listOrganizations({
  userId: 'user-123',
  organizationId: 'org-123',
  nameSearch: 'My Org',
  memberSearch: 'user@example.com',
  skip: 0,
  limit: 10
});

// Get organization details
const org = await client.getOrganization('org-123');

// Create new organization
const newOrg = await client.createOrganization({
  name: 'My Organization',
  type: 'team' // or 'personal'
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
  lifetime: 86400 // seconds
});

// List account tokens
const tokens = await client.getAccountTokens();

// Delete account token
await client.deleteAccountToken('token-id');

// Create organization token
const orgToken = await client.createOrganizationToken({
  name: 'My Org Token',
  lifetime: 86400
}, 'org-123');

// List organization tokens
const orgTokens = await client.getOrganizationTokens('org-123');

// Delete organization token
await client.deleteOrganizationToken('token-id', 'org-123');

// Get organization from token
const orgInfo = await client.getOrganizationFromToken('org-token');
```

#### User Management

```typescript
// List users with optional filters
const users = await client.listUsers({
  skip: 0,
  limit: 10,
  organization_id: 'org-123',
  user_id: 'user-123',
  search_name: 'John'
});

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

// Delete user
await client.deleteUser('user-123');
```

#### Email Verification

```typescript
// Send verification email
await client.sendVerificationEmail('user-123');

// Send registration verification email
await client.sendRegistrationVerificationEmail('user-123');

// Verify email with token
await client.verifyEmail('verification-token');
```

#### AWS Configuration

```typescript
// Create AWS config
const awsConfig = await client.createAWSConfig({
  access_key_id: 'key',
  secret_access_key: 'secret',
  region: 'us-east-1'
});

// Get AWS config
const config = await client.getAWSConfig();

// Delete AWS config
await client.deleteAWSConfig();
```

#### Invitations

```typescript
// Create invitation
const invitation = await client.createInvitation({
  email: 'user@example.com',
  organization_id: 'org-123',
  role: 'member'
});

// List invitations
const invitations = await client.getInvitations({
  skip: 0,
  limit: 10
});

// Get invitation by token
const inv = await client.getInvitation('invitation-token');

// Accept invitation
await client.acceptInvitation('invitation-token', {
  name: 'John Doe'
});
```

#### LLM Operations (Account Level)

```typescript
// List LLM models
const models = await client.listLLMModels({
  providerName: 'openai',
  providerEnabled: true,
  llmEnabled: true
});

// List LLM providers
const providers = await client.listLLMProviders();

// Set LLM provider config
await client.setLLMProviderConfig('openai', {
  api_key: 'key',
  enabled: true
});

// Run LLM chat
const response = await client.runLLMChat({
  messages: [
    { role: 'user', content: 'Hello' }
  ],
  model: 'gpt-4'
});

// Run LLM chat with streaming
await client.runLLMChatStream(
  {
    messages: [{ role: 'user', content: 'Hello' }],
    model: 'gpt-4'
  },
  (chunk) => {
    console.log('Chunk:', chunk);
  },
  (error) => {
    console.error('Error:', error);
  }
);

// Test embedding model
const testResult = await client.testEmbeddingModel({
  model: 'text-embedding-ada-002',
  text: 'Test text'
});
```

#### Payment and Subscription Management (Account Level)

```typescript
// Get customer portal
const portal = await client.getCustomerPortal('org-123');

// Get subscription
const subscription = await client.getSubscription('org-123');

// Activate subscription
await client.activateSubscription('org-123');

// Cancel subscription
await client.cancelSubscription('org-123');

// Get current usage
const usage = await client.getCurrentUsage('org-123');

// Add credits
await client.addCredits('org-123', 1000);

// Get credit config
const creditConfig = await client.getCreditConfig('org-123');

// Purchase credits
const purchase = await client.purchaseCredits('org-123', {
  credits: 1000,
  success_url: 'https://example.com/success',
  cancel_url: 'https://example.com/cancel'
});

// Get usage range
const usageRange = await client.getUsageRange('org-123', {
  start_date: '2024-01-01',
  end_date: '2024-01-31'
});

// Create checkout session
const checkout = await client.createCheckoutSession('org-123', 'plan-id');
```

### DocRouterOrg Client

The `DocRouterOrg` client provides organization-scoped operations:

```typescript
const client = new DocRouterOrg({
  baseURL: 'https://app.docrouter.ai/fastapi',
  orgToken: 'your-org-token',
  organizationId: 'org-123'
});
```

#### Document Management

```typescript
// Upload documents
const uploadResult = await client.uploadDocuments({
  documents: [
    {
      name: 'invoice.pdf',
      content: base64Content, // Base64 string or data URL
      tag_ids: ['tag-1'],
      metadata: { category: 'invoice' }
    }
  ]
});

// List documents with filtering
const documents = await client.listDocuments({
  skip: 0,
  limit: 10,
  tagIds: 'tag-1,tag-2',
  nameSearch: 'invoice',
  metadataSearch: 'category=invoice'
});

// Get document details and content
const document = await client.getDocument({
  documentId: 'doc-123',
  fileType: 'pdf' // or 'original'
});

// Update document metadata
await client.updateDocument({
  documentId: 'doc-123',
  documentName: 'Updated Name',
  tagIds: ['tag-1'],
  metadata: { category: 'updated' }
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
  documentId: 'doc-123',
  pageNum: 1 // Optional: specific page number
});

// Get OCR metadata
const ocrMetadata = await client.getOCRMetadata({
  documentId: 'doc-123'
});
```

#### LLM Operations

```typescript
// Run LLM on document
const llmResult = await client.runLLM({
  documentId: 'doc-123',
  promptRevId: 'prompt-123',
  force: false // Force re-extraction
});

// Get LLM result
const result = await client.getLLMResult({
  documentId: 'doc-123',
  promptRevId: 'prompt-123',
  fallback: false // Use fallback results
});

// Update LLM result
await client.updateLLMResult({
  documentId: 'doc-123',
  promptId: 'prompt-123',
  result: { key: 'value' },
  isVerified: false
});

// Delete LLM result
await client.deleteLLMResult({
  documentId: 'doc-123',
  promptId: 'prompt-123'
});

// Download all LLM results
const results = await client.downloadAllLLMResults({
  documentId: 'doc-123'
});

// Run LLM chat
const chatResponse = await client.runLLMChat({
  messages: [
    { role: 'user', content: 'Extract key information' }
  ],
  model: 'gpt-4',
  temperature: 0.7,
  max_tokens: 1000
});

// Run LLM chat with streaming
await client.runLLMChatStream(
  {
    messages: [{ role: 'user', content: 'Hello' }],
    model: 'gpt-4'
  },
  (chunk) => {
    console.log('Chunk:', chunk);
  },
  (error) => {
    console.error('Error:', error);
  },
  abortSignal // Optional AbortSignal
);

// List LLM models
const models = await client.listLLMModels();
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

// List tags with optional search
const tags = await client.listTags({
  skip: 0,
  limit: 20,
  nameSearch: 'invoice'
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

#### Prompt Management

```typescript
// Create prompt
const prompt = await client.createPrompt({
  prompt: {
    name: 'Invoice Extraction',
    content: 'Extract invoice number, date, and total amount',
    schema_id: 'schema-123',
    schema_version: 1,
    tag_ids: ['tag-1'],
    model: 'gpt-4o-mini',
    kb_id: 'kb-123' // Optional: knowledge base ID for RAG
  }
});

// List prompts with optional filters
const prompts = await client.listPrompts({
  skip: 0,
  limit: 10,
  document_id: 'doc-123',
  tag_ids: 'tag-1,tag-2',
  nameSearch: 'invoice'
});

// Get prompt details
const promptDetails = await client.getPrompt({
  promptRevId: 'prompt-rev-123'
});

// Update prompt
await client.updatePrompt({
  promptId: 'prompt-123',
  prompt: {
    name: 'Updated Prompt',
    content: 'Updated content',
    schema_id: 'schema-123',
    schema_version: 1,
    tag_ids: ['tag-1'],
    model: 'gpt-4o-mini'
  }
});

// Delete prompt
await client.deletePrompt({
  promptId: 'prompt-123'
});

// List prompt versions
const versions = await client.listPromptVersions({
  promptId: 'prompt-123'
});
```

#### Schema Management

```typescript
// Create schema
const schema = await client.createSchema({
  name: 'Invoice Schema',
  response_format: {
    type: 'json_schema',
    json_schema: {
      name: 'invoice_extraction',
      schema: {
        type: 'object',
        properties: {
          invoice_date: { type: 'string', description: 'invoice date' }
        },
        required: ['invoice_date'],
        additionalProperties: false
      },
      strict: true
    }
  }
});

// List schemas with optional search
const schemas = await client.listSchemas({
  skip: 0,
  limit: 10,
  nameSearch: 'invoice'
});

// Get schema details
const schemaDetails = await client.getSchema({
  schemaRevId: 'schema-rev-123'
});

// Update schema
await client.updateSchema({
  schemaId: 'schema-123',
  schema: {
    name: 'Updated Schema',
    response_format: { /* ... */ }
  }
});

// Delete schema
await client.deleteSchema({
  schemaId: 'schema-123'
});

// Validate data against schema
const validation = await client.validateAgainstSchema({
  schemaRevId: 'schema-rev-123',
  data: { invoice_date: '2024-01-01' }
});

// List schema versions
const versions = await client.listSchemaVersions({
  schemaId: 'schema-123'
});
```

#### Form Management

```typescript
// Create form
const form = await client.createForm({
  name: 'Invoice Form',
  response_format: {
    type: 'formio',
    formio: {
      json_formio: [
        {
          type: 'textfield',
          key: 'invoice_number',
          label: 'Invoice Number',
          input: true
        }
      ],
      json_formio_mapping: {
        invoice_number: {
          sources: [
            {
              promptId: 'prompt-123',
              schemaFieldPath: 'invoice_number'
            }
          ],
          mappingType: 'direct'
        }
      }
    }
  }
});

// List forms with optional tag filter
const forms = await client.listForms({
  skip: 0,
  limit: 10,
  tag_ids: 'tag-1,tag-2'
});

// Get form details
const formDetails = await client.getForm({
  formRevId: 'form-rev-123'
});

// Update form
await client.updateForm({
  formId: 'form-123',
  form: {
    name: 'Updated Form',
    response_format: { /* ... */ }
  }
});

// Delete form
await client.deleteForm({
  formId: 'form-123'
});

// List form versions
const versions = await client.listFormVersions({
  formId: 'form-123'
});

// Submit form
const submission = await client.submitForm({
  documentId: 'doc-123',
  formRevId: 'form-rev-123',
  submission_data: {
    invoice_number: 'INV-123'
  },
  submitted_by: 'user@example.com'
});

// Get form submission
const formSubmission = await client.getFormSubmission({
  documentId: 'doc-123',
  formRevId: 'form-rev-123'
});

// Delete form submission
await client.deleteFormSubmission({
  documentId: 'doc-123',
  formRevId: 'form-rev-123'
});
```

#### Knowledge Base Management

```typescript
// Create knowledge base
const kb = await client.createKnowledgeBase({
  kb: {
    name: 'Invoice Knowledge Base',
    description: 'KB for invoice processing'
  }
});

// List knowledge bases
const kbs = await client.listKnowledgeBases({
  skip: 0,
  limit: 10,
  name_search: 'invoice'
});

// Get knowledge base details
const kbDetails = await client.getKnowledgeBase({
  kbId: 'kb-123'
});

// Update knowledge base
await client.updateKnowledgeBase({
  kbId: 'kb-123',
  update: {
    name: 'Updated KB',
    description: 'Updated description'
  }
});

// Delete knowledge base
await client.deleteKnowledgeBase({
  kbId: 'kb-123'
});

// List KB documents
const kbDocuments = await client.listKBDocuments({
  kbId: 'kb-123',
  skip: 0,
  limit: 10
});

// Get KB document chunks
const chunks = await client.getKBDocumentChunks({
  kbId: 'kb-123',
  documentId: 'doc-123',
  skip: 0,
  limit: 100
});

// Search knowledge base
const searchResults = await client.searchKnowledgeBase({
  kbId: 'kb-123',
  search: {
    query: 'invoice date',
    top_k: 5
  }
});

// Reconcile knowledge base
const reconcileResult = await client.reconcileKnowledgeBase({
  kbId: 'kb-123',
  dry_run: false
});

// Reconcile all knowledge bases
const reconcileAllResult = await client.reconcileAllKnowledgeBases({
  dry_run: false
});

// Run KB chat with streaming
await client.runKBChatStream(
  'kb-123',
  {
    messages: [{ role: 'user', content: 'What is the invoice date?' }],
    model: 'gpt-4'
  },
  (chunk) => {
    console.log('Chunk:', chunk);
  },
  (error) => {
    console.error('Error:', error);
  },
  abortSignal
);
```

#### Payment and Subscription Management (Org Level)

```typescript
// Get customer portal
const portal = await client.getCustomerPortal();

// Get subscription
const subscription = await client.getSubscription();

// Activate subscription
await client.activateSubscription();

// Cancel subscription
await client.cancelSubscription();

// Get current usage
const usage = await client.getCurrentUsage();

// Add credits
await client.addCredits(1000);

// Get credit config
const creditConfig = await client.getCreditConfig();

// Purchase credits
const purchase = await client.purchaseCredits({
  credits: 1000,
  success_url: 'https://example.com/success',
  cancel_url: 'https://example.com/cancel'
});

// Get usage range
const usageRange = await client.getUsageRange({
  start_date: '2024-01-01',
  end_date: '2024-01-31'
});

// Create checkout session
const checkout = await client.createCheckoutSession('plan-id');
```

## Error Handling

The SDK provides comprehensive error handling with retry logic and authentication callbacks:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://app.docrouter.ai/fastapi',
  orgToken: 'your-org-token',
  organizationId: 'org-123',
  timeout: 30000, // 30 seconds
  retries: 3,
  onAuthError: (error) => {
    console.error('Authentication error:', error);
    // Handle token refresh or re-authentication
  }
});

try {
  const documents = await client.listDocuments();
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
  baseURL: 'https://app.docrouter.ai/fastapi',
  orgToken: 'your-org-token',
  organizationId: 'org-123'
});

// Stream LLM responses
const abortController = new AbortController();

await client.runLLMChatStream(
  {
    messages: [
      { role: 'user', content: 'Analyze this document step by step' }
    ],
    model: 'gpt-4'
  },
  (chunk) => {
    // Handle each chunk of the response
    console.log('Chunk received:', chunk);
    
    // You can abort the stream if needed
    if (shouldAbort) {
      abortController.abort();
    }
  },
  (error) => {
    // Handle stream errors
    console.error('Stream error:', error);
  },
  abortController.signal
);
```

## Browser Usage

The SDK works in browser environments with proper polyfills:

```typescript
// In a browser environment
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://app.docrouter.ai/fastapi',
  orgToken: 'your-jwt-token',
  organizationId: 'your-org-id'
});

// File upload from browser
const fileInput = document.getElementById('fileInput') as HTMLInputElement;
const file = fileInput.files[0];

if (file) {
  // Convert file to base64
  const reader = new FileReader();
  reader.onload = async () => {
    const base64Content = reader.result as string;
    
    const result = await client.uploadDocuments({
      documents: [
        {
          name: file.name,
          content: base64Content,
          metadata: { source: 'browser' }
        }
      ]
    });
  };
  reader.readAsDataURL(file);
}
```

## Advanced Configuration

### Custom HTTP Client Configuration

You can provide custom configuration for the underlying HTTP client:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://app.docrouter.ai/fastapi',
  orgToken: 'your-org-token',
  organizationId: 'org-123',
  timeout: 30000, // 30 seconds
  retries: 3,
  onAuthError: (error) => {
    // Handle authentication errors
  }
});
```

### Environment-Specific Configuration

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const config = {
  development: {
    baseURL: 'http://localhost:8000',
    orgToken: process.env.DOCROUTER_DEV_TOKEN!,
    organizationId: process.env.DOCROUTER_DEV_ORG_ID!
  },
  production: {
    baseURL: 'https://app.docrouter.ai/fastapi',
    orgToken: process.env.DOCROUTER_PROD_TOKEN!,
    organizationId: process.env.DOCROUTER_PROD_ORG_ID!
  }
};

const environment = process.env.NODE_ENV || 'development';
const client = new DocRouterOrg(config[environment]);
```

### Token Updates

You can update the token for an existing client:

```typescript
// Update organization token
client.updateToken('new-org-token');

// For account client
accountClient.updateToken('new-account-token');
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
import { DocRouterOrg, UploadDocumentsResponse } from '@docrouter/sdk';

const client = new DocRouterOrg(config);

// Type-safe response
const result: UploadDocumentsResponse = await client.uploadDocuments({
  documents: [
    {
      name: 'document.pdf',
      content: base64Content
    }
  ]
});
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
    const base64Content = await this.fileToBase64(file);
    
    const result = await this.client.uploadDocuments({
      documents: [{
        name: file.name,
        content: base64Content
      }]
    });
    
    return result.documents[0];
  }
  
  private async fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }
}
```

### 4. Environment Variables

Use environment variables for configuration:

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: process.env.DOCROUTER_API_URL || 'https://app.docrouter.ai/fastapi',
  orgToken: process.env.DOCROUTER_ORG_TOKEN!,
  organizationId: process.env.DOCROUTER_ORG_ID!
});
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**Problem**: 401 Unauthorized errors

**Solutions:**
- Verify your token is valid and not expired
- Check that you're using the correct token type for your client
- Ensure the organization ID is correct for `DocRouterOrg`
- Use `getOrganizationFromToken()` to resolve organization ID from token

#### 2. TypeScript Errors

**Problem**: Type errors or missing types

**Solutions:**
- Ensure you're using TypeScript 4.9+
- Check that all imports are correct
- Verify your `tsconfig.json` configuration

#### 3. Network Errors

**Problem**: Connection timeouts or network errors

**Solutions:**
- Check your network connection
- Verify the API URL is correct (`https://app.docrouter.ai/fastapi`)
- Increase timeout values if needed
- Check for firewall or proxy issues

#### 4. Rate Limiting

**Problem**: 429 Too Many Requests errors

**Solutions:**
- Implement exponential backoff
- Reduce request frequency
- Use streaming for large operations
- Contact support for rate limit increases

## Package Information

- **Package Name**: `@docrouter/sdk`
- **Current Version**: 1.0.0
- **Node.js Requirement**: >=16.0.0
- **TypeScript Requirement**: >=4.9.0
- **License**: MIT
- **Repository**: https://github.com/analytiq/doc-router

### Dependencies

- **axios**: HTTP client for API requests
- **bson**: BSON serialization
- **jsonwebtoken**: JWT handling
- **mongodb**: MongoDB client

### Development Dependencies

- **Jest**: Testing framework
- **ESLint**: Code linting
- **tsup**: Build tool
- **TypeScript**: Type definitions and compilation

## Support and Resources

### Getting Help

1. **Check the API documentation** for detailed endpoint information
2. **Review the examples** in the package repository
3. **Check the troubleshooting section** above
4. **Contact support** for API-specific issues

### Package Management

```bash
# Update to latest version
npm update @docrouter/sdk

# Check current version
npm list @docrouter/sdk

# Install specific version
npm install @docrouter/sdk@1.0.0
```

### Development

For developers working on the SDK:

```bash
# Clone the repository
git clone https://github.com/analytiq/doc-router
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

The DocRouter TypeScript SDK provides a powerful, type-safe way to integrate DocRouter's document processing capabilities into your applications. With comprehensive API coverage, streaming support, knowledge base integration, and excellent TypeScript integration, it's the ideal choice for building document processing applications.
