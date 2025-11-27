import { ObjectId } from 'mongodb';
import * as crypto from 'crypto';
import axios from 'axios';

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
        { user_id: memberId, role: 'admin' }
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

  static createRequestSignature(jsonString: string): string {
    const secret = process.env.NEXTAUTH_SECRET || 'test_secret_key_for_tests';
    const hmac = crypto.createHmac('sha256', secret);
    hmac.update(jsonString);
    return hmac.digest('hex');
  }

  static async createJWTTokenFromAPI(userId: string, userName: string, email: string, baseURL: string): Promise<string> {
    if (!baseURL) {
      throw new Error('baseURL is required for createJWTTokenFromAPI');
    }

    const payload = { id: userId, name: userName, email };
    const payloadJson = JSON.stringify(payload);
    const signature = this.createRequestSignature(payloadJson);

    const url = `${baseURL}/v0/account/auth/token`;
    const response = await axios.post(url, payloadJson, {
      headers: {
        'Content-Type': 'application/json',
        'X-Request-Signature': signature
      }
    });

    return response.data.token;
  }
}
