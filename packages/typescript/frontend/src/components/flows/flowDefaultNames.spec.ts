import { describe, expect, it } from 'vitest';
import { defaultCredentialAccountName } from './flowDefaultNames';

describe('defaultCredentialAccountName', () => {
  it('strips OAuth2 API suffix like n8n', () => {
    expect(defaultCredentialAccountName('Gmail OAuth2 API')).toBe('Gmail account');
  });

  it('strips generic API suffix', () => {
    expect(defaultCredentialAccountName('Slack API')).toBe('Slack account');
  });
});
