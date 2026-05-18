import { describe, expect, it } from 'vitest';
import type { FlowCredentialKindSummary } from '@docrouter/sdk';
import {
  credentialKindShowsTestButton,
  formatCredentialTestDetail,
} from './flowCredentialFieldUtils';

describe('credentialKindShowsTestButton', () => {
  it('hides test for OAuth browser-flow kinds (n8n: isCredentialTestable false when isOAuthType)', () => {
    const gmail = {
      key: 'gmailOAuth2',
      has_test_request: true,
      supports_oauth_browser_flow: true,
    } as FlowCredentialKindSummary;
    expect(credentialKindShowsTestButton(gmail)).toBe(false);
  });

  it('shows test for non-OAuth kinds with test_request', () => {
    const header = {
      key: 'httpHeaderAuth',
      has_test_request: true,
      supports_oauth_browser_flow: false,
    } as FlowCredentialKindSummary;
    expect(credentialKindShowsTestButton(header)).toBe(true);
  });
});

describe('formatCredentialTestDetail', () => {
  it('extracts Google API error message from JSON body', () => {
    const detail = formatCredentialTestDetail({
      ok: false,
      status_code: 403,
      error: JSON.stringify({
        error: {
          code: 403,
          message: 'Gmail API has not been used in project before',
        },
      }),
    });
    expect(detail).toBe('Gmail API has not been used in project before');
  });
});
