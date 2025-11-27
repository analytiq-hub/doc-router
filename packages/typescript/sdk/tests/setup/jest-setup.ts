import { TEST_USER_ID, TEST_ORG_ID } from './mongodb-setup';
import { TestFixtures } from './test-fixtures';

// Environment variables are set in global-setup.ts before the test server starts

// Lazy-load MongoDB client for workers
let cachedMongoClient: any = null;

async function getMongoClient() {
  if (!cachedMongoClient) {
    const { MongoClient } = await import('mongodb');
    const fs = await import('fs');
    const path = await import('path');

    const configPath = path.join(__dirname, '.test-server-config.json');
    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));

    cachedMongoClient = new MongoClient(config.mongodbUri);
    await cachedMongoClient.connect();
  }
  return cachedMongoClient;
}

// Close MongoDB connections when worker exits
afterAll(async () => {
  if (cachedMongoClient) {
    await cachedMongoClient.close();
    cachedMongoClient = null;
  }
});

// Also close on process exit to ensure cleanup
if (process.env.TEST_TYPE === 'integration') {
  const closeConnections = async () => {
    if (cachedMongoClient) {
      await cachedMongoClient.close().catch(() => {});
      cachedMongoClient = null;
    }
  };

  process.on('beforeExit', closeConnections);
}

// Helper function to get test database (no circular refs returned)
// Reads server config from file created by globalSetup
export function getTestDatabase(): any {
  const env = process.env.ENV || 'pytest_ts';
  return {
    collection: (name: string) => {
      // Return a proxy that lazily connects
      return new Proxy({}, {
        get: (target, prop) => {
          return async (...args: any[]) => {
            const client = await getMongoClient();
            const collection = client.db(env).collection(name);
            return (collection as any)[prop](...args);
          };
        }
      });
    }
  };
}

export function getBaseUrl(): string {
  const fs = require('fs');
  const path = require('path');
  const configPath = path.join(__dirname, '.test-server-config.json');

  if (!fs.existsSync(configPath)) {
    throw new Error('Test server config not found. Global setup may have failed.');
  }

  const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  return config.baseUrl;
}

// Helper function to create test fixtures (users, orgs, tokens)
export async function createTestFixtures(testDb: any, baseUrl: string) {
  return await TestFixtures.createOrgAndUsers(testDb, baseUrl);
}

// Export test constants
export { TEST_USER_ID, TEST_ORG_ID };