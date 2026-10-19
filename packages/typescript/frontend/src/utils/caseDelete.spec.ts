import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { isCaseNotFoundError, pollUntilCaseDeleted } from './caseDelete';

describe('isCaseNotFoundError', () => {
  it('recognizes Error messages about missing cases', () => {
    expect(isCaseNotFoundError(new Error('Case not found'))).toBe(true);
    expect(isCaseNotFoundError(new Error('Not Found'))).toBe(true);
    expect(isCaseNotFoundError(new Error('Forbidden'))).toBe(false);
  });
});

describe('pollUntilCaseDeleted', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('resolves when getCase starts returning not found', async () => {
    const api = {
      getCase: vi
        .fn()
        .mockRejectedValueOnce(new Error('Case not found'))
        .mockRejectedValue(new Error('should not be called again')),
    };

    const pending = pollUntilCaseDeleted(api as never, 'CLM-1', {
      intervalMs: 100,
      maxWaitMs: 5000,
    });

    await pending;
    expect(api.getCase).toHaveBeenCalledTimes(1);
  });

  it('polls until case disappears', async () => {
    const api = {
      getCase: vi
        .fn()
        .mockResolvedValueOnce({ case_id: 'CLM-1' })
        .mockRejectedValueOnce(new Error('Case not found')),
    };

    const pending = pollUntilCaseDeleted(api as never, 'CLM-1', {
      intervalMs: 100,
      maxWaitMs: 5000,
    });

    await vi.advanceTimersByTimeAsync(100);
    await pending;
    expect(api.getCase).toHaveBeenCalledTimes(2);
  });
});
