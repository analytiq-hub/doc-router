import { DocRouter, DocRouterAccount, DocRouterOrg } from '../src';

// Example 1: Using DocRouterAccount for server-to-server operations
async function accountExample() {
  const client = new DocRouterAccount({
    baseURL: 'https://api.docrouter.com',
    accountToken: 'your-account-token-here'
  });

  // List all organizations
  const orgs = await client.organizations.list();
  console.log('Organizations:', orgs);

  // Create a new organization
  const newOrg = await client.organizations.create({
    name: 'My New Organization',
    type: 'team'
  });
  console.log('Created organization:', newOrg);

  // Create an organization token
  const token = await client.tokens.createOrganizationToken({
    name: 'My App Token',
    lifetime: 86400 // 24 hours
  }, newOrg.id);
  console.log('Created token:', token);
}

// Example 2: Using DocRouterOrg for organization-scoped operations
async function orgExample() {
  const client = new DocRouterOrg({
    baseURL: 'https://api.docrouter.com',
    orgToken: 'your-org-token-here',
    organizationId: 'org-123'
  });

  // Upload a document
  const fileBuffer = new ArrayBuffer(1024); // Your file content
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
  console.log('Uploaded documents:', result);

  // List documents
  const documents = await client.documents.list();
  console.log('Documents:', documents);

  // Run LLM on a document
  const llmResult = await client.llm.run({
    organizationId: 'org-123',
    documentId: result.documents[0].id,
    promptRevId: 'prompt-123',
    force: false
  });
  console.log('LLM result:', llmResult);
}

// Example 3: Using DocRouter for browser applications
async function browserExample() {
  const client = new DocRouter({
    baseURL: 'https://api.docrouter.com',
    token: 'your-jwt-token-here'
  });

  // Run LLM chat with streaming
  await client.llm.chatStream({
    messages: [
      { role: 'user', content: 'Hello, how are you?' }
    ],
    model: 'gpt-4',
    stream: true
  }, (chunk) => {
    if (chunk.type === 'chunk') {
      console.log('Received chunk:', chunk.content);
    } else if (chunk.type === 'error') {
      console.error('Stream error:', chunk.error);
    }
  });

  // List organizations
  const orgs = await client.organizations.list();
  console.log('Organizations:', orgs);
}

// Example 4: Error handling
async function errorHandlingExample() {
  const client = new DocRouter({
    baseURL: 'https://api.docrouter.com',
    token: 'invalid-token',
    onAuthError: (error) => {
      console.error('Authentication failed:', error.message);
      // Handle auth error (e.g., redirect to login)
    }
  });

  try {
    await client.organizations.list();
  } catch (error) {
    if (error.status === 401) {
      console.log('Unauthorized - token may be invalid');
    } else if (error.status === 402) {
      console.log('Payment required - insufficient credits');
    } else {
      console.error('Unexpected error:', error.message);
    }
  }
}

// Example 5: Token provider for dynamic tokens
async function tokenProviderExample() {
  const client = new DocRouter({
    baseURL: 'https://api.docrouter.com',
    tokenProvider: async () => {
      // Fetch fresh token from your auth service
      const response = await fetch('/api/auth/token');
      const data = await response.json();
      return data.token;
    }
  });

  // The client will automatically use the token provider for each request
  const orgs = await client.organizations.list();
  console.log('Organizations:', orgs);
}

// Run examples
if (require.main === module) {
  // Uncomment to run specific examples
  // accountExample().catch(console.error);
  // orgExample().catch(console.error);
  // browserExample().catch(console.error);
  // errorHandlingExample().catch(console.error);
  // tokenProviderExample().catch(console.error);
}
