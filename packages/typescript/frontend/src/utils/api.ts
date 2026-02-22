import axios, { isAxiosError } from 'axios';
import { getSession } from 'next-auth/react';
import { AppSession } from '@/types/AppSession';
import { DocRouterOrg, DocRouterAccount } from '@docrouter/sdk';
import type { ListOrganizationsResponse } from '@docrouter/sdk';

// Session cache to avoid repeated calls
let sessionCache: { session: AppSession | null; timestamp: number } | null = null;
const SESSION_CACHE_DURATION = 30000; // 30 seconds

// Global session reference for context-based access
let globalSession: AppSession | null = null;

export function setGlobalSession(session: AppSession | null): void {
  globalSession = session;
}

export function getGlobalSession(): AppSession | null {
  return globalSession;
}

export async function getCachedSession(): Promise<AppSession | null> {
  // First try to use global session from context
  if (globalSession) {
    return globalSession;
  }
  
  const now = Date.now();
  
  if (sessionCache && (now - sessionCache.timestamp) < SESSION_CACHE_DURATION) {
    return sessionCache.session;
  }
  
  const session = await getSession() as AppSession | null;
  sessionCache = { session, timestamp: now };
  return session;
}

// Function to invalidate session cache
export function invalidateSessionCache(): void {
  sessionCache = null;
  globalSession = null;
}

import { toast } from 'react-toastify';

// These APIs execute from the frontend
const NEXT_PUBLIC_FASTAPI_FRONTEND_URL = process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: NEXT_PUBLIC_FASTAPI_FRONTEND_URL, 
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Export for custom (non-SDK) backend endpoints.
export const apiClient = api;

// Add authorization header to all requests
api.interceptors.request.use(async (config) => {
  // First try to use global session (pre-fetched from context)
  let session = getGlobalSession();
  
  // Fallback to cached session if global session is not available
  if (!session) {
    session = await getCachedSession();
  }
  
  if (session?.apiAccessToken) {
    config.headers.Authorization = `Bearer ${session.apiAccessToken}`;
  } else {
    console.warn('No API token found in session');
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Add a request queue to handle concurrent requests during token refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (error: Error) => void;
}> = [];

const processQueue = (error: Error | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve();
    }
  });
  failedQueue = [];
};

// Store the toast ID outside the interceptor
let sessionExpiredToastId: React.ReactText | null = null;

// Add a response interceptor that handles all errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 402 errors (payment required)
    if (error.response?.status === 402) {
      toast.error('Insufficient credits. Please upgrade your plan to continue using AI features.', {
        toastId: 'payment-required', // Prevent duplicate toasts
        autoClose: 8000
      });
      return Promise.reject(error);
    }

    // Handle 401 errors (unauthorized)
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => api(originalRequest))
          .catch(() => {
            // Only show session expiration toast once
            if (!sessionExpiredToastId || !toast.isActive(sessionExpiredToastId)) {
              sessionExpiredToastId = toast.error('Your session has expired. Please login again.');
            }
            return Promise.reject(new Error('Session expired'));
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Invalidate cache and get fresh session on 401
        invalidateSessionCache();
        const session = await getCachedSession();
        if (session?.apiAccessToken) {
          originalRequest.headers.Authorization = `Bearer ${session.apiAccessToken}`;
          processQueue();
          return api(originalRequest);
        } else {
          if (!sessionExpiredToastId || !toast.isActive(sessionExpiredToastId)) {
            sessionExpiredToastId = toast.error('Your session has expired. Please login again.');
          }
          return Promise.reject(new Error('Session expired'));
        }
      } catch (refreshError) {
        processQueue(refreshError instanceof Error ? refreshError : new Error('Token refresh failed'));
        if (!sessionExpiredToastId || !toast.isActive(sessionExpiredToastId)) {
          sessionExpiredToastId = toast.error('Your session has expired. Please login again.');
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // For all other errors, just pass through the error without showing toast
    if (isAxiosError(error)) {
      const responseData = error.response?.data as { detail?: string };
      if (responseData?.detail) {
        return Promise.reject(new Error(responseData.detail));
      }
    }

    return Promise.reject(error);
  }
);

export class DocRouterOrgApi extends DocRouterOrg {
 constructor(organizationId: string) {
    super({
      baseURL: NEXT_PUBLIC_FASTAPI_FRONTEND_URL,
      orgToken: '', // Empty token so tokenProvider will be used
      organizationId: organizationId,
    });
    
    // Set up token provider that gets called on every request
    this.getHttpClient().updateTokenProvider(async () => {
      // First try to use global session (pre-fetched from context)
      let session = getGlobalSession();
      
      // Fallback to cached session if global session is not available
      if (!session) {
        session = await getCachedSession();
      }
      
      return session?.apiAccessToken || '';
    });
  }
}

// In-flight promise cache for listOrganizations to avoid duplicate concurrent requests
// (e.g. from OrganizationProvider and dashboard redirect or React Strict Mode)
const listOrgsCache = new Map<string, Promise<ListOrganizationsResponse>>();

function listOrgsCacheKey(params?: {
  userId?: string;
  organizationId?: string;
  nameSearch?: string;
  memberSearch?: string;
  skip?: number;
  limit?: number;
}): string {
  if (!params) return 'default';
  const p = params;
  return [
    p.userId ?? '',
    p.organizationId ?? '',
    p.nameSearch ?? '',
    p.memberSearch ?? '',
    p.skip ?? 0,
    p.limit ?? 10,
  ].join('|');
}

export class DocRouterAccountApi extends DocRouterAccount {
  constructor() {
    super({
      baseURL: NEXT_PUBLIC_FASTAPI_FRONTEND_URL,
      accountToken: '', // Empty token so tokenProvider will be used
    });

    // Set up token provider that gets called on every request
    this.getHttpClient().updateTokenProvider(async () => {
      // First try to use global session (pre-fetched from context)
      let session = getGlobalSession();

      // Fallback to cached session if global session is not available
      if (!session) {
        session = await getCachedSession();
      }

      return session?.apiAccessToken || '';
    });
  }

  /**
   * Override to deduplicate concurrent identical listOrganizations requests.
   * Reuses the in-flight promise so only one network call is made.
   */
  override async listOrganizations(params?: Parameters<DocRouterAccount['listOrganizations']>[0]): Promise<ListOrganizationsResponse> {
    const key = listOrgsCacheKey(params);
    const existing = listOrgsCache.get(key);
    if (existing) return existing;

    const promise = super.listOrganizations(params).finally(() => {
      listOrgsCache.delete(key);
    });
    listOrgsCache.set(key, promise);
    return promise;
  }
}

export function getApiErrorMsg(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  
  if (isAxiosError(error)) {
    const responseData = error.response?.data as { detail?: string };
    if (responseData?.detail) {
      return responseData.detail;
    }
    if (error.message) {
      return error.message;
    }
  }

  // Fallback for unknown error types
  return 'An unexpected error occurred. Please try again.';
}



// Helper function to get session token for direct fetch calls (for FormIO)
export const getSessionToken = async (): Promise<string | null> => {
  const session = await getCachedSession();
  return session?.apiAccessToken || null;
};