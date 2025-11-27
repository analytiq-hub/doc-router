import { DocRouterAccount } from '../../src';
import { HttpClient } from '../../src/http-client';

// Mock the HttpClient
jest.mock('../../src/http-client');
const MockedHttpClient = HttpClient as jest.MockedClass<typeof HttpClient>;

describe('DocRouterAccount New APIs Unit Tests', () => {
  let client: DocRouterAccount;
  let mockHttpClient: jest.Mocked<HttpClient>;

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();
    
    // Create mock HTTP client
    mockHttpClient = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      updateToken: jest.fn(),
    } as unknown as jest.Mocked<HttpClient>;

    // Mock the HttpClient constructor to return our mock
    MockedHttpClient.mockImplementation(() => mockHttpClient);

    // Create the client
    client = new DocRouterAccount({
      baseURL: 'https://api.example.com',
      accountToken: 'test-token'
    });
  });

  describe('Invitation APIs', () => {
    describe('createInvitation', () => {
      test('should call correct endpoint with invitation data', async () => {
        const invitationData = {
          email: 'test@example.com',
          organization_id: 'org-123',
          role: 'user'
        };

        const expectedResponse = {
          id: 'inv-123',
          email: 'test@example.com',
          organization_id: 'org-123',
          role: 'user',
          created_at: '2024-01-01T00:00:00Z',
          expires_at: '2024-01-08T00:00:00Z'
        };

        mockHttpClient.post.mockResolvedValue(expectedResponse);

        const result = await client.createInvitation(invitationData);

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          '/v0/account/email/invitations',
          invitationData
        );
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('getInvitations', () => {
      test('should call endpoint without parameters', async () => {
        const expectedResponse = {
          invitations: [
            {
              id: 'inv-123',
              email: 'test@example.com',
              organization_id: 'org-123',
              role: 'user',
              created_at: '2024-01-01T00:00:00Z',
              expires_at: '2024-01-08T00:00:00Z'
            }
          ],
          total_count: 1,
          skip: 0
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getInvitations();

        expect(mockHttpClient.get).toHaveBeenCalledWith('/v0/account/email/invitations?');
        expect(result).toEqual(expectedResponse);
      });

      test('should call endpoint with pagination parameters', async () => {
        const params = { skip: 10, limit: 5 };
        const expectedResponse = {
          invitations: [],
          total_count: 0,
          skip: 10
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getInvitations(params);

        expect(mockHttpClient.get).toHaveBeenCalledWith('/v0/account/email/invitations?skip=10&limit=5');
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('getInvitation', () => {
      test('should call endpoint with token', async () => {
        const token = 'invitation-token-123';
        const expectedResponse = {
          id: 'inv-123',
          email: 'test@example.com',
          organization_id: 'org-123',
          role: 'user',
          created_at: '2024-01-01T00:00:00Z',
          expires_at: '2024-01-08T00:00:00Z'
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getInvitation(token);

        expect(mockHttpClient.get).toHaveBeenCalledWith(`/v0/account/email/invitations/${token}`);
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('acceptInvitation', () => {
      test('should call endpoint with token and acceptance data', async () => {
        const token = 'invitation-token-123';
        const acceptanceData = {
          name: 'John Doe',
          password: 'secure-password'
        };
        const expectedResponse = { message: 'Invitation accepted successfully' };

        mockHttpClient.post.mockResolvedValue(expectedResponse);

        const result = await client.acceptInvitation(token, acceptanceData);

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          `/v0/account/email/invitations/${token}/accept`,
          acceptanceData
        );
        expect(result).toEqual(expectedResponse);
      });
    });
  });

  describe('Payment APIs', () => {
    const testOrgId = 'org-123';

    describe('getCustomerPortal', () => {
      test('should call correct endpoint', async () => {
        const expectedResponse = { url: 'https://billing.stripe.com/portal/...' };

        mockHttpClient.post.mockResolvedValue(expectedResponse);

        const result = await client.getCustomerPortal(testOrgId);

        expect(mockHttpClient.post).toHaveBeenCalledWith(`/v0/orgs/${testOrgId}/payments/customer-portal`);
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('getSubscription', () => {
      test('should call correct endpoint', async () => {
        const expectedResponse = {
          id: 'sub-123',
          status: 'active',
          current_period_start: '2024-01-01T00:00:00Z',
          current_period_end: '2024-02-01T00:00:00Z',
          plan_id: 'plan-123'
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getSubscription(testOrgId);

        expect(mockHttpClient.get).toHaveBeenCalledWith(`/v0/orgs/${testOrgId}/payments/subscription`);
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('activateSubscription', () => {
      test('should call correct endpoint', async () => {
        const expectedResponse = { status: 'activated', message: 'Subscription activated' };

        mockHttpClient.put.mockResolvedValue(expectedResponse);

        const result = await client.activateSubscription(testOrgId);

        expect(mockHttpClient.put).toHaveBeenCalledWith(`/v0/orgs/${testOrgId}/payments/subscription`);
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('cancelSubscription', () => {
      test('should call correct endpoint', async () => {
        const expectedResponse = { status: 'cancelled', message: 'Subscription cancelled' };

        mockHttpClient.delete.mockResolvedValue(expectedResponse);

        const result = await client.cancelSubscription(testOrgId);

        expect(mockHttpClient.delete).toHaveBeenCalledWith(`/v0/orgs/${testOrgId}/payments/subscription`);
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('getCurrentUsage', () => {
      test('should call correct endpoint', async () => {
        const expectedResponse = {
          credits_used: 100,
          credits_remaining: 400,
          period_start: '2024-01-01T00:00:00Z',
          period_end: '2024-02-01T00:00:00Z'
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getCurrentUsage(testOrgId);

        expect(mockHttpClient.get).toHaveBeenCalledWith(`/v0/orgs/${testOrgId}/payments/usage`);
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('addCredits', () => {
      test('should call correct endpoint with amount', async () => {
        const amount = 100;
        const expectedResponse = {
          credits_added: 100,
          new_balance: 500
        };

        mockHttpClient.post.mockResolvedValue(expectedResponse);

        const result = await client.addCredits(testOrgId, amount);

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          `/v0/orgs/${testOrgId}/payments/credits/add`,
          { amount }
        );
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('getCreditConfig', () => {
      test('should call correct endpoint', async () => {
        const expectedResponse = {
          cost_per_credit: 0.01,
          credits_per_dollar: 100
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getCreditConfig(testOrgId);

        expect(mockHttpClient.get).toHaveBeenCalledWith(`/v0/orgs/${testOrgId}/payments/credits/config`);
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('purchaseCredits', () => {
      test('should call correct endpoint with purchase data', async () => {
        const purchaseData = { credits: 50, success_url: 'https://example.com/success', cancel_url: 'https://example.com/cancel' };
        const expectedResponse = {
          checkout_url: 'https://checkout.stripe.com/...',
          session_id: 'cs_123'
        };

        mockHttpClient.post.mockResolvedValue(expectedResponse);

        const result = await client.purchaseCredits(testOrgId, purchaseData);

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          `/v0/orgs/${testOrgId}/payments/credits/purchase`,
          purchaseData
        );
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('getUsageRange', () => {
      test('should call correct endpoint with date range', async () => {
        const dateRange = {
          start_date: '2024-01-01',
          end_date: '2024-01-31'
        };
        const expectedResponse = {
          usage: [
            { date: '2024-01-01', credits_used: 10 },
            { date: '2024-01-02', credits_used: 15 }
          ]
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getUsageRange(testOrgId, dateRange);

        expect(mockHttpClient.get).toHaveBeenCalledWith(
          `/v0/orgs/${testOrgId}/payments/usage/range?start_date=2024-01-01&end_date=2024-01-31`
        );
        expect(result).toEqual(expectedResponse);
      });
    });

    describe('createCheckoutSession', () => {
      test('should call correct endpoint with plan ID', async () => {
        const planId = 'plan-123';
        const expectedResponse = { url: 'https://checkout.stripe.com/...' };

        mockHttpClient.post.mockResolvedValue(expectedResponse);

        const result = await client.createCheckoutSession(testOrgId, planId);

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          `/v0/orgs/${testOrgId}/payments/checkout-session`,
          { plan_id: planId }
        );
        expect(result).toEqual(expectedResponse);
      });
    });
  });

  describe('Token APIs', () => {
    describe('getOrganizationFromToken', () => {
      test('should call correct endpoint with token parameter', async () => {
        const token = 'test-api-token-123';
        const expectedResponse = {
          organization_id: 'org-123'
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getOrganizationFromToken(token);

        expect(mockHttpClient.get).toHaveBeenCalledWith(
          `/v0/account/token/organization?token=${encodeURIComponent(token)}`
        );
        expect(result).toEqual(expectedResponse);
      });

      test('should handle account-level token (null organization_id)', async () => {
        const token = 'account-level-token-456';
        const expectedResponse = {
          organization_id: null
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getOrganizationFromToken(token);

        expect(mockHttpClient.get).toHaveBeenCalledWith(
          `/v0/account/token/organization?token=${encodeURIComponent(token)}`
        );
        expect(result).toEqual(expectedResponse);
      });

      test('should properly encode special characters in token', async () => {
        const token = 'token with spaces & special chars!';
        const expectedResponse = {
          organization_id: 'org-789'
        };

        mockHttpClient.get.mockResolvedValue(expectedResponse);

        const result = await client.getOrganizationFromToken(token);

        expect(mockHttpClient.get).toHaveBeenCalledWith(
          `/v0/account/token/organization?token=${encodeURIComponent(token)}`
        );
        expect(result).toEqual(expectedResponse);
      });
    });
  });
});
