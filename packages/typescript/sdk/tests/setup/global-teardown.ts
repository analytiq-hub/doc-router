import * as fs from 'fs';
import * as path from 'path';

export default async function globalTeardown() {
  console.log('Stopping shared test server...');

  const testServer = (global as any).__TEST_SERVER__;
  const mongoSetup = (global as any).__MONGO_SETUP__;

  // Stop test server
  if (testServer) {
    await testServer.stop();
  }

  // Cleanup MongoDB
  if (mongoSetup) {
    await mongoSetup.cleanup();
  }

  // Clean up config file
  const configPath = path.join(__dirname, '.test-server-config.json');
  if (fs.existsSync(configPath)) {
    fs.unlinkSync(configPath);
  }

  console.log('Test server stopped');

  // Give a small delay to ensure all connections are closed
  await new Promise(resolve => setTimeout(resolve, 100));
}
