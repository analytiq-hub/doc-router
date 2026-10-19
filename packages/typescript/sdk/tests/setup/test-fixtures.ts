import { ObjectId } from 'mongodb';
import jwt from 'jsonwebtoken';

export class TestFixtures {
  static async createOrgAndUsers(testDb: { collection: (name: string) => { findOne: (query: unknown) => Promise<unknown>; insertMany: (docs: unknown[]) => Promise<unknown>; insertOne: (doc: unknown) => Promise<unknown> } }, baseURL: string): Promise<{
    org_id: string;
    admin: { id: string; token: string; account_token: string };
    member: { id: string; token: string; account_token: string };
    outsider: { id: string; token: string; account_token: string };
  }> {
    const uniqueSuffix = `${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

    const adminEmail = process.env.ADMIN_EMAIL;
    if (!adminEmail) {
      throw new Error('ADMIN_EMAIL environment variable is not set');
    }
    const adminUser = await testDb.collection('users').findOne({ email: adminEmail }) as { _id: { toString(): string } } | null;

    if (!adminUser) {
      throw new Error('System admin user not found - server may not have started correctly');
    }

    const adminId = adminUser._id.toString();

    const memberId = new ObjectId().toString();
    const outsiderId = new ObjectId().toString();

    await testDb.collection('users').insertMany([
      {
        _id: new ObjectId(memberId),
        email: `member-${uniqueSuffix}@example.com`,
        name: 'Org Member',
        role: 'user',
        email_verified: true,
        has_password: true,
        created_at: new Date()
      },
      {
        _id: new ObjectId(outsiderId),
        email: `outsider-${uniqueSuffix}@example.com`,
        name: 'Not In Org',
        role: 'user',
        email_verified: true,
        has_password: true,
        created_at: new Date()
      }
    ]);

    const orgId = new ObjectId().toString();
    await testDb.collection('organizations').insertOne({
      _id: new ObjectId(orgId),
      name: `Test Org ${uniqueSuffix}`,
      members: [
        { user_id: memberId, permission_group_ids: ['admin'] }
      ],
      type: 'team',
      created_at: new Date(),
      updated_at: new Date()
    });

    await testDb.collection('payments_customers').insertOne({
      organization_id: orgId,
      stripe_customer_id: `cus_test_${uniqueSuffix}`,
      created_at: new Date()
    });

    const adminToken = await this.createJWTTokenFromAPI(adminId, 'System Administrator', adminEmail, baseURL);
    const memberToken = await this.createJWTTokenFromAPI(memberId, 'Org Member', `member-${uniqueSuffix}@example.com`, baseURL);
    const outsiderToken = await this.createJWTTokenFromAPI(outsiderId, 'Not In Org', `outsider-${uniqueSuffix}@example.com`, baseURL);
    
    const adminAccountToken = adminToken;
    const memberAccountToken = memberToken;
    const outsiderAccountToken = outsiderToken;

    return {
      org_id: orgId,
      admin: { id: adminId, token: adminToken, account_token: adminAccountToken },
      member: { id: memberId, token: memberToken, account_token: memberAccountToken },
      outsider: { id: outsiderId, token: outsiderToken, account_token: outsiderAccountToken }
    };
  }

  /** Mint the same session JWT shape as FastAPI ``mint_session_jwt`` (integration tests). */
  static createSessionJwt(userId: string, userName: string, email: string): string {
    const secret = process.env.APP_SECRET || 'test_secret_key_for_tests_32bytes_min!!';
    return jwt.sign({ userId, userName, email }, secret, { algorithm: 'HS256' });
  }

  static async createJWTTokenFromAPI(userId: string, userName: string, email: string, _baseURL: string): Promise<string> {
    return this.createSessionJwt(userId, userName, email);
  }
}
