# DocRouter TypeScript SDK

A TypeScript SDK for the DocRouter API, providing type-safe access to document processing, OCR, LLM, and organization management features.

## Publishing to npm

### Prerequisites

1. **Create npm account and organization:**
   ```bash
   # Login to npm
   npm login
   
   # Create the @docrouter organization (via npm website or CLI)
   # Visit: https://www.npmjs.com/org/create
   ```

2. **Verify organization access:**
   ```bash
   npm org ls docrouter
   ```

### Publishing Steps

1. **Build the package:**
   ```bash
   cd packages/typescript/sdk
   npm run build
   ```

2. **Run tests and linting:**
   ```bash
   npm run test:unit
   npm run lint
   npm run type-check
   ```

3. **Update version (if needed):**
   ```bash
   # For patch version (0.1.0 → 0.1.1)
   npm version patch
   
   # For minor version (0.1.0 → 0.2.0)
   npm version minor
   
   # For major version (0.1.0 → 1.0.0)
   npm version major
   ```

4. **Publish to npm:**
   ```bash
   npm publish
   ```

### Publishing Scripts

The package includes convenient publishing scripts:

```bash
# Publish to public registry
npm run publish:public

# Publish beta version
npm run publish:beta
```

### Configuration Files

- **`.npmrc`**: Registry and access configuration
- **`package.json`**: Package metadata and scripts
- **`publishConfig`**: Ensures public access for scoped package

## Installation

```bash
npm install @docrouter/sdk
```

## Quick Start

### Using Account Token (Server-to-Server)

```typescript
import { DocRouterAccount } from '@docrouter/sdk';

const client = new DocRouterAccount({
  baseURL: 'https://api.docrouter.com',
  accountToken: 'your-account-token-here'
});

// List organizations
const orgs = await client.organizations.list();

// Create organization tokens
const token = await client.tokens.createOrganizationToken({
  name: 'My App Token',
  lifetime: 86400 // 24 hours
}, 'org-123');
```

### Using Organization Token

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-org-token-here',
  organizationId: 'org-123'
});

// Upload documents (organizationId is automatically included)
const result = await client.documents.upload({
  organizationId: 'org-123',
  documents: [
    {
      name: 'document.pdf',
      content: fileBuffer,
      type: 'application/pdf'
    }
  ]
});

// List documents
const documents = await client.documents.list();
```

### Using JWT Token (Browser)

```typescript
import { DocRouterOrg } from '@docrouter/sdk';

const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-jwt-token-here',
  organizationId: 'your-org-id'
});

// Run LLM chat with streaming
await client.llm.chatStream({
  messages: [{ role: 'user', content: 'Hello' }],
  model: 'gpt-4'
}, (chunk) => {
  console.log('Received chunk:', chunk);
});
```

## Features

- **Type-safe**: Full TypeScript support with generated types
- **Multiple auth strategies**: Support for account, organization, and JWT tokens
- **Streaming support**: Real-time LLM chat streaming with fetch streams
- **Node.js & Browser**: Works in both environments with proper polyfills
- **Error handling**: Comprehensive error handling with retry logic and auth callbacks
- **Modular**: Import only what you need, or use the full SDK
- **Two client types**: `DocRouterAccount` and `DocRouterOrg` for different use cases

## API Reference

### DocRouterAccount (Server-to-Server)
Use for account-level operations with account tokens.

```typescript
const client = new DocRouterAccount({
  baseURL: 'https://api.docrouter.com',
  accountToken: 'your-account-token'
});

// Available APIs:
client.organizations.* // Full organization management
client.llm.*          // Account-level LLM operations
client.tokens.*       // Token management
client.users.*        // User management
```

### DocRouterOrg (Organization-Scoped)
Use when you have an organization token and want to work within that org.

```typescript
const client = new DocRouterOrg({
  baseURL: 'https://api.docrouter.com',
  orgToken: 'your-org-token',
  organizationId: 'org-123'
});

// Available APIs:
client.documents.*    // Document management (scoped to org)
client.llm.*          // LLM operations (scoped to org)
client.ocr.*          // OCR operations (scoped to org)
client.tags.*         // Tag management (scoped to org)
```

### Core APIs

#### Documents
- `upload(params)` - Upload documents with metadata
- `list(params?)` - List documents with filtering
- `get(params)` - Get document details and content
- `update(params)` - Update document metadata
- `delete(params)` - Delete document

#### LLM
- `chat(request)` - Run LLM chat
- `chatStream(request, onChunk, onError?, abortSignal?)` - Stream LLM responses
- `run(params)` - Run LLM on document
- `getResult(params)` - Get LLM result
- `updateResult(params)` - Update LLM result
- `deleteResult(params)` - Delete LLM result

#### Organizations
- `list(params?)` - List organizations
- `get(id)` - Get organization details
- `create(request)` - Create organization
- `update(id, request)` - Update organization
- `delete(id)` - Delete organization

#### OCR
- `getBlocks(params)` - Get OCR blocks
- `getText(params)` - Get OCR text
- `getMetadata(params)` - Get OCR metadata

#### Tags
- `create(params)` - Create tag
- `get(params)` - Get tag details
- `list(params)` - List tags
- `update(params)` - Update tag
- `delete(params)` - Delete tag

#### Tokens
- `createAccountToken(request)` - Create account token
- `getAccountTokens()` - List account tokens
- `deleteAccountToken(id)` - Delete account token
- `createOrganizationToken(request, orgId)` - Create org token
- `getOrganizationTokens(orgId)` - List org tokens
- `deleteOrganizationToken(id, orgId)` - Delete org token

#### Users
- `list(params?)` - List users
- `get(id)` - Get user details
- `create(request)` - Create user
- `update(id, request)` - Update user
- `delete(id)` - Delete user

## Error Handling

```typescript
try {
  const result = await client.documents.upload(params);
} catch (error) {
  if (error.status === 401) {
    // Handle authentication error
  } else if (error.status === 402) {
    // Handle payment required
  }
}
```

## License

MIT
