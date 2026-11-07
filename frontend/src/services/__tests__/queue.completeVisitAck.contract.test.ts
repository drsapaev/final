/**
 * DOCFLOW-FE-001 / DOCFLOW-FE-003 (audit 3886, ledger group «specialty
 * visit completion and auto-call»): a doctor-queue write is CONFIRMED only
 * by an explicit `success: true` DTO in a parseable 2xx body.
 *
 * - completeVisit: a 2xx body that fails to parse (apiRequest → null) is
 *   AMBIGUOUS (the server may have committed); a `success:false` body is an
 *   explicit rejection. Neither may fire the optimistic `queueUpdated`
 *   refresh event nor be returned as a confirmed completion.
 * - callNextWaiting: the POST result is authoritative — the old code ignored
 *   it and always fabricated `{success:true, entry:<GET snapshot>}`. Only a
 *   confirmed success may notify; the backend-returned entry is canonical.
 *
 * Red-first: on pre-fix source cases 1, 2, 4, 5 fail (event fired and/or
 * fabricated success) and case 6 fails on the stale GET entry identity.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { fetchMock } = vi.hoisted(() => ({ fetchMock: vi.fn() }));

vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../utils/tokenManager', () => ({
  tokenManager: { getAccessToken: () => 'doctor-token' },
}));

import { queueService } from '../queue';

function jsonResponse(body: unknown, opts: { jsonThrows?: boolean } = {}) {
  return {
    ok: true,
    status: 200,
    json: async () => {
      if (opts.jsonThrows) throw new SyntaxError('Unexpected end of JSON input');
      return body;
    },
  };
}

function postedCallUrls(): string[] {
  return fetchMock.mock.calls
    .filter(([input, init]) => String((init as RequestInit | undefined)?.method ?? 'GET').toUpperCase() === 'POST')
    .map(([input]) => String(input));
}

function queueUpdatedEvents(): Array<Record<string, unknown>> {
  const events: Array<Record<string, unknown>> = [];
  vi.spyOn(window, 'dispatchEvent').mockImplementation((event: Event) => {
    if (event instanceof CustomEvent && event.type === 'queueUpdated') {
      events.push(event.detail as Record<string, unknown>);
    }
    return true;
  });
  return events;
}

beforeEach(() => {
  fetchMock.mockReset();
  global.fetch = fetchMock as never;
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe('DOCFLOW-FE-001: completeVisit is confirmed only by success:true', () => {
  it('a 2xx body that fails to parse is AMBIGUOUS — no success, no queueUpdated event', async () => {
    const events = queueUpdatedEvents();
    fetchMock.mockImplementation(async () => jsonResponse(null, { jsonThrows: true }));

    const result = (await queueService.completeVisit(91, {})) as Record<string, unknown>;

    expect(result.success).toBe(false);
    expect(result.unknown).toBe(true);
    expect(typeof result.message).toBe('string');
    expect(events).toEqual([]);
  });

  it('an explicit success:false body is a rejection — no success, no queueUpdated event', async () => {
    const events = queueUpdatedEvents();
    fetchMock.mockImplementation(async () =>
      jsonResponse({ success: false, detail: 'visit already completed' }),
    );

    const result = (await queueService.completeVisit(91, {})) as Record<string, unknown>;

    expect(result.success).toBe(false);
    expect(String(result.message)).toContain('visit already completed');
    expect(events).toEqual([]);
  });

  it('positive control: success:true confirms the completion and fires exactly one visitCompleted event', async () => {
    const events = queueUpdatedEvents();
    fetchMock.mockImplementation(async () => jsonResponse({ success: true, visit_id: 77 }));

    const result = (await queueService.completeVisit(91, {})) as Record<string, unknown>;

    expect(result.success).toBe(true);
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ action: 'visitCompleted' });
  });
});

describe('DOCFLOW-FE-003: callNextWaiting does not fabricate success', () => {
  const QUEUE = {
    next_call_entry_id: 17,
    entries: [
      { id: 17, number: 'A017', status: 'waiting', can_call: true },
    ],
  };

  it('POST 200 with success:false — no fabricated success, no queueUpdated event', async () => {
    const events = queueUpdatedEvents();
    fetchMock.mockImplementation(async (input: unknown) => {
      const url = String(input);
      if (url.includes('/call')) return jsonResponse({ success: false, detail: 'entry already called' });
      return jsonResponse(QUEUE);
    });

    const result = (await queueService.callNextWaiting('cardiology')) as Record<string, unknown>;

    expect(result.success).toBe(false);
    expect(String(result.message)).toContain('entry already called');
    expect(events).toEqual([]);
    expect(postedCallUrls()).toEqual([expect.stringContaining('/doctor/queue/17/call')]);
  });

  it('POST 200 with an unparseable body is AMBIGUOUS — no success, no queueUpdated event', async () => {
    const events = queueUpdatedEvents();
    fetchMock.mockImplementation(async (input: unknown) => {
      const url = String(input);
      if (url.includes('/call')) return jsonResponse(null, { jsonThrows: true });
      return jsonResponse(QUEUE);
    });

    const result = (await queueService.callNextWaiting('cardiology')) as Record<string, unknown>;

    expect(result.success).toBe(false);
    expect(result.unknown).toBe(true);
    expect(events).toEqual([]);
  });

  it('positive control: success:true returns the BACKEND entry as canonical and fires exactly one event', async () => {
    const events = queueUpdatedEvents();
    const backendEntry = { id: 17, number: 'A018', status: 'called' };
    fetchMock.mockImplementation(async (input: unknown) => {
      const url = String(input);
      if (url.includes('/call')) return jsonResponse({ success: true, entry: backendEntry });
      return jsonResponse(QUEUE);
    });

    const result = (await queueService.callNextWaiting('cardiology')) as { success: boolean; entry?: Record<string, unknown> };

    expect(result.success).toBe(true);
    // Canonical entry comes from the POST response, not the pre-call GET snapshot.
    expect(result.entry).toEqual(backendEntry);
    expect((result.entry as Record<string, unknown>).number).toBe('A018');
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ action: 'nextPatientCalled' });
  });
});
