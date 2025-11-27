import { MongoClient, Db } from 'mongodb';
import { ObjectId } from 'mongodb';

export interface TestDatabase {
  db: Db;
  client: MongoClient;
  cleanup: () => Promise<void>;
}

export class MongoDBTestSetup {
  private client: MongoClient | null = null;
  private databases: Db[] = [];

  async connect(mongodbUri: string): Promise<void> {
    this.client = new MongoClient(mongodbUri);
    await this.client.connect();
  }

  async cleanDatabase(env: string): Promise<void> {
    if (!this.client) {
      throw new Error('MongoDB client not connected. Call connect() first.');
    }

    console.log(`Cleaning database: ${env}`);
    const db = this.client.db(env);

    // Drop the entire database to ensure a clean state
    await db.dropDatabase().catch(() => {
      // Ignore error if database doesn't exist
    });
  }

  async createTestDatabase(env: string): Promise<TestDatabase> {
    if (!this.client) {
      throw new Error('MongoDB client not connected. Call connect() first.');
    }

    const db = this.client.db(env);

    // Only add to databases list once (for cleanup in afterAll)
    if (!this.databases.includes(db)) {
      this.databases.push(db);
    }

    // Initialize payments system indexes (idempotent)
    await this.initPayments(db);

    return {
      db,
      client: this.client,
      cleanup: async () => {
        // No cleanup between tests - only in afterAll
      }
    };
  }

  async cleanup(): Promise<void> {
    // Clean up all test databases (only called in afterAll)
    // We drop the database at the start of tests anyway, so just close the connection
    this.databases = [];

    if (this.client) {
      await this.client.close();
      this.client = null;
    }
  }

  private async initPayments(db: Db): Promise<void> {
    // Initialize payments collections indexes (idempotent - won't fail if already exists)
    await db.collection('payments_customers').createIndex(
      { organization_id: 1 },
      { unique: true, sparse: true }
    ).catch(() => {}); // Ignore if already exists

    await db.collection('payments_subscriptions').createIndex(
      { organization_id: 1 },
      { unique: true, sparse: true }
    ).catch(() => {});

    await db.collection('payments_usage').createIndex(
      { organization_id: 1, date: 1 },
      { unique: true, sparse: true }
    ).catch(() => {});
  }
}

// Test data constants (matching Python tests)
export const TEST_USER_ID = '6579a94b1f1d8f5a8e9c0124';
export const TEST_ORG_ID = '6579a94b1f1d8f5a8e9c0123';

export interface TestUser {
  user_id: string;
  user_name: string;
  token_type: string;
}

export const TEST_USER: TestUser = {
  user_id: TEST_USER_ID,
  user_name: 'test@example.com',
  token_type: 'jwt'
};
