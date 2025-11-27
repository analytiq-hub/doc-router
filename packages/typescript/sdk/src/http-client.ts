import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, isAxiosError } from 'axios';
import { DocRouterConfig, ApiError, LLMChatStreamChunk, LLMChatStreamError } from './types';

export class HttpClient {
  private axios: AxiosInstance;
  private config: DocRouterConfig;
  private isRefreshing = false;
  private failedQueue: Array<{
    resolve: (value?: unknown) => void;
    reject: (error: Error) => void;
  }> = [];

  constructor(config: DocRouterConfig) {
    this.config = config;
    this.axios = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // Request interceptor for auth
    this.axios.interceptors.request.use(
      async (config) => {
        const token = await this.getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        // Handle 401 errors (unauthorized)
        if (error.response?.status === 401 && !originalRequest._retry) {
          if (this.isRefreshing) {
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            })
              .then(() => this.axios(originalRequest))
              .catch((err) => {
                this.handleAuthError(err);
                return Promise.reject(err);
              });
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            // Try to get a new token
            const newToken = await this.getToken();
            if (newToken) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              this.processQueue();
              return this.axios(originalRequest);
            } else {
              this.handleAuthError(error);
              return Promise.reject(this.createApiError(error));
            }
          } catch (refreshError) {
            this.processQueue(refreshError instanceof Error ? refreshError : new Error('Token refresh failed'));
            this.handleAuthError(error);
            return Promise.reject(this.createApiError(error));
          } finally {
            this.isRefreshing = false;
          }
        }

        return Promise.reject(this.createApiError(error));
      }
    );
  }

  private async getToken(): Promise<string | null> {
    if (this.config.token) {
      return this.config.token;
    }
    
    if (this.config.tokenProvider) {
      try {
        return await this.config.tokenProvider();
      } catch (error) {
        console.warn('Token provider failed:', error);
        return null;
      }
    }

    return null;
  }

  private processQueue(error: Error | null = null): void {
    this.failedQueue.forEach(prom => {
      if (error) {
        prom.reject(error);
      } else {
        prom.resolve();
      }
    });
    this.failedQueue = [];
  }

  private handleAuthError(error: unknown): void {
    if (this.config.onAuthError) {
      this.config.onAuthError(error instanceof Error ? error : new Error('Authentication failed'));
    }
  }

  private createApiError(error: unknown): ApiError {
    if (isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message || 'Request failed';
      const apiError: ApiError = new Error(message);
      apiError.status = error.response?.status;
      apiError.code = error.code;
      apiError.details = error.response?.data;
      return apiError;
    }

    if (error instanceof Error) {
      const apiError: ApiError = error;
      return apiError;
    }

    return new Error('Unknown error occurred');
  }

  // Public methods
  async get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.get(url, config);
    return response.data;
  }

  async post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.post(url, data, config);
    return response.data;
  }

  async put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.put(url, data, config);
    return response.data;
  }

  async delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.delete(url, config);
    return response.data;
  }

  async request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.request(config);
    return response.data;
  }

  // For streaming requests
  async stream(
    url: string,
    data: unknown,
    onChunk: (chunk: LLMChatStreamChunk | LLMChatStreamError) => void,
    onError?: (error: Error) => void,
    abortSignal?: AbortSignal
  ): Promise<void> {
    try {
      const token = await this.getToken();
      if (!token) {
        throw new Error('No token available for streaming request');
      }

      const response = await fetch(`${this.config.baseURL}${url}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/plain',
          'Cache-Control': 'no-cache',
        },
        body: JSON.stringify(data),
        signal: abortSignal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Response body is not available for streaming');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            break;
          }

          // Decode the chunk and add to buffer
          buffer += decoder.decode(value, { stream: true });
          
          // Process complete lines from buffer
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const chunkData = JSON.parse(line.slice(6));
                onChunk(chunkData);
                
                // Stop if we're done
                if (chunkData.done) {
                  return;
                }
              } catch (parseError) {
                console.warn('Failed to parse streaming chunk:', parseError);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      if (onError) {
        onError(error instanceof Error ? error : new Error('Streaming request failed'));
      } else {
        throw error;
      }
    }
  }

  // Update token
  updateToken(token: string): void {
    this.config.token = token;
  }

  // Update token provider
  updateTokenProvider(provider: () => Promise<string>): void {
    this.config.tokenProvider = provider;
  }
}
