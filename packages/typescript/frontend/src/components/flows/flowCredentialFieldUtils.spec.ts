import { describe, expect, it } from 'vitest';
import type { FlowCredentialKindSummary } from '@docrouter/sdk';
import {
  credentialFieldRowVisible,
  credentialFormSnapshotsEqual,
  credentialKindShowsTestButton,
  credentialOAuthHintAppName,
  formatCredentialTestDetail,
  parseCredentialBooleanField,
  type CredentialFieldRow,
} from './flowCredentialFieldUtils';

describe('credentialFormSnapshotsEqual', () => {
  it('detects name and field changes', () => {
    const base = { name: 'Gmail account', fields: { clientId: 'a' } };
    expect(credentialFormSnapshotsEqual(base, base)).toBe(true);
    expect(credentialFormSnapshotsEqual(base, { ...base, name: 'Other' })).toBe(false);
    expect(
      credentialFormSnapshotsEqual(base, { name: 'Gmail account', fields: { clientId: 'b' } }),
    ).toBe(false);
  });
});

describe('credentialOAuthHintAppName', () => {
  it('strips OAuth API suffix from display names', () => {
    expect(credentialOAuthHintAppName('Gmail OAuth2 API')).toBe('Gmail');
    expect(credentialOAuthHintAppName('Google OAuth2 API')).toBe('Google');
    expect(credentialOAuthHintAppName('Custom')).toBe('Custom');
  });
});

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

describe('credentialFieldRowVisible', () => {
  const domainField: CredentialFieldRow = {
    name: 'allowedDomains',
    showWhen: { field: 'allowedHttpRequestDomains', equals: 'domains' },
  };

  it('hides allowedDomains unless restriction mode is domains', () => {
    expect(
      credentialFieldRowVisible(domainField, { allowedHttpRequestDomains: 'all' }, [domainField]),
    ).toBe(false);
    expect(
      credentialFieldRowVisible(
        domainField,
        { allowedHttpRequestDomains: 'domains', allowedDomains: 'example.com' },
        [domainField],
      ),
    ).toBe(true);
  });
});

describe('parseCredentialBooleanField', () => {
  it('parses common boolean string forms', () => {
    expect(parseCredentialBooleanField('true')).toBe(true);
    expect(parseCredentialBooleanField('false')).toBe(false);
    expect(parseCredentialBooleanField('')).toBe(false);
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
