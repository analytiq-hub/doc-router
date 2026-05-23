import { describe, expect, it } from 'vitest';
import {
  filterTraceEvents,
  hasNodeTraceContent,
  matchesTraceFilter,
  traceEventCount,
  type FlowTraceEvent,
} from './flowNodeTracePanel';

describe('traceEventCount', () => {
  it('returns 0 for null, undefined, and non-arrays', () => {
    expect(traceEventCount(null)).toBe(0);
    expect(traceEventCount(undefined)).toBe(0);
    expect(traceEventCount({})).toBe(0);
  });

  it('counts valid trace events', () => {
    expect(
      traceEventCount([
        { ts: '2026-05-23T09:25:44.984948+00:00', level: 'debug', kind: 'http', message: 'GET … → 200' },
        { ts: '2026-05-23T09:25:46.157368+00:00', level: 'debug', kind: 'http', message: 'GET … → 200' },
      ]),
    ).toBe(2);
  });

  it('skips invalid entries', () => {
    expect(traceEventCount([null, 'x', { message: 'only message' }])).toBe(1);
  });
});

describe('hasNodeTraceContent', () => {
  it('is false when there is nothing to show', () => {
    expect(hasNodeTraceContent({})).toBe(false);
    expect(hasNodeTraceContent({ traceEvents: [] })).toBe(false);
  });

  it('is true when trace events exist', () => {
    expect(hasNodeTraceContent({ traceEvents: [{ message: 'GET → 200' }] })).toBe(true);
  });

  it('is true for node errors and code logs', () => {
    expect(hasNodeTraceContent({ nodeError: { message: 'failed' } })).toBe(true);
    expect(hasNodeTraceContent({ codeLogs: ['line 1'] })).toBe(true);
  });
});

describe('matchesTraceFilter', () => {
  const okHttp: FlowTraceEvent = {
    level: 'debug',
    kind: 'http',
    message: 'GET https://example.com → 200',
    detail: { status_code: 200 },
  };
  const failHttp: FlowTraceEvent = {
    level: 'error',
    kind: 'http',
    message: 'POST https://example.com → 404',
    detail: { status_code: 404 },
  };
  const warnEvent: FlowTraceEvent = { level: 'warn', kind: 'log', message: 'slow' };

  it('shows all events for All', () => {
    expect(matchesTraceFilter(okHttp, 'all')).toBe(true);
    expect(matchesTraceFilter(failHttp, 'all')).toBe(true);
  });

  it('shows only HTTP kind for Http', () => {
    expect(matchesTraceFilter(okHttp, 'http')).toBe(true);
    expect(matchesTraceFilter(warnEvent, 'http')).toBe(false);
  });

  it('shows errors/warns and failed HTTP for Errors, not successful HTTP', () => {
    expect(matchesTraceFilter(okHttp, 'errors')).toBe(false);
    expect(matchesTraceFilter(failHttp, 'errors')).toBe(true);
    expect(matchesTraceFilter(warnEvent, 'errors')).toBe(true);
    expect(filterTraceEvents([okHttp, failHttp, warnEvent], 'errors')).toEqual([failHttp, warnEvent]);
  });
});
