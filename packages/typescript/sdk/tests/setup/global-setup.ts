import { TestServer, defaultTestConfig } from './test-server';
import { MongoDBTestSetup } from './mongodb-setup';
import * as fs from 'fs';
import * as path from 'path';

export default async function globalSetup() {
  console.log('Starting shared test server...');

  // Set test environment variables BEFORE starting the server
  // NOTE: When ENV starts with 'pytest', the .env file will NOT be loaded (see analytiq_data/common/setup.py)
  // All required environment variables must be set here
  process.env.ENV = 'pytest_ts';
  process.env.NEXTAUTH_SECRET = 'test_secret_key_for_tests';
  process.env.NEXTAUTH_URL = 'http://127.0.0.1:3000';
  process.env.MONGODB_URI = 'mongodb://localhost:27017';
  process.env.FASTAPI_ROOT_PATH = '/';
  process.env.ADMIN_EMAIL = 'test-admin@example.com';
  process.env.ADMIN_PASSWORD = 'test-admin-password-123';
  process.env.SES_FROM_EMAIL = 'test@example.com';

  // Start MongoDB setup
  const mongoSetup = new MongoDBTestSetup();
  await mongoSetup.connect(defaultTestConfig.mongodbUri);

  // Clean up database from previous test runs
  await mongoSetup.cleanDatabase(defaultTestConfig.env);

  // Start test server
  const testServer = new TestServer(defaultTestConfig);
  await testServer.start();

  console.log(`Test server ready at ${testServer.getBaseUrl()}`);

  // Store references in global for teardown
  (global as any).__TEST_SERVER__ = testServer;
  (global as any).__MONGO_SETUP__ = mongoSetup;

  // Write server info to a file that workers can read
  const configPath = path.join(__dirname, '.test-server-config.json');
  fs.writeFileSync(configPath, JSON.stringify({
    baseUrl: testServer.getBaseUrl(),
    port: defaultTestConfig.port,
    mongodbUri: defaultTestConfig.mongodbUri
  }));
}
