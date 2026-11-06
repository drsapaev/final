/**
 * QAPI-FE-001 (audit 3886, ledger group 2): queueService.callNextWaiting
 * must treat the backend's canonical `next_call_entry_id` as the SSOT:
 * - an EXPLICIT null means «no callable entry» — the client must NOT
 *   re-derive its own candidate via the local `entries.find(can_call)`
 *   fallback and must not POST a call;
 * - a MISSING field is a contract failure — fail closed with an explicit
 *   message instead of silently guessing the first entry;
 * - a valid canonical id is the only thing that may be called.
 *
 * Red-first: on pre-fix source cases 1 and 2 fail (the local fallback
 * POSTs the self-derived entry 17).
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

const CALLABLE_ENTRY = {
  id: 17,
  number: 'A017',
  patient_name: 'Синтетический Пациент',
  status: 'waiting',
  available_actions: ['call'],
  can_call: true,
};

function queueResponse(queue: Record<string, unknown>) {
  return {
    ok: true,
    json: async () => queue,
  };
}

function postedCallUrls(): string[] {
  return fetchMock.mock.calls
    .filter(([input, init]) => String((init as RequestInit | undefined)?.method ?? 'GET').toUpperCase() === 'POST')
    .map(([input]) => String(input));
}

beforeEach(() => {
  fetchMock.mockReset();
  global.fetch = fetchMock as never;
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('QAPI-FE-001: the server null choice is not second-guessed', () => {
  it('explicit next_call_entry_id: null with a can_call entry — NO call POST', async () => {
    fetchMock.mockImplementation(async () =>
      queueResponse({ next_call_entry_id: null, entries: [CALLABLE_ENTRY] }),
    );

    const result = await queueService.callNextWaiting('cardiology');

    expect(result.success).toBe(false);
    expect(postedCallUrls()).toEqual([]);
    // Only the GET ever happened.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('missing next_call_entry_id is a contract failure — no POST, explicit message', async () => {
    fetchMock.mockImplementation(async () => queueResponse({ entries: [CALLABLE_ENTRY] }));

    const result = await queueService.callNextWaiting('cardiology');

    expect(result.success).toBe(false);
    expect(typeof (result as { message?: unknown }).message).toBe('string');
    expect((result as { message?: string }).message).toMatch(/next_call_entry_id/i);
    expect(postedCallUrls()).toEqual([]);
  });

  it('a valid canonical id is the only entry called', async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/queue/today')) {
        return queueResponse({ next_call_entry_id: 17, entries: [CALLABLE_ENTRY] });
      }
      // DOCFLOW-FE-003 (audit 3886): the call POST ack is authoritative —
      // the canonical backend contract (_queue_ops.py) answers a committed
      // call with `{success: true, entry: <updated>}`. The old test mocked a
      // success-less `{message:'called'}` body because the pre-DOCFLOW code
      // ignored the POST response entirely.
      return { ok: true, json: async () => ({ success: true, entry: { id: 17, number: 'A017', status: 'called' } }) };
    });

    const result = await queueService.callNextWaiting('cardiology');

    expect(result.success).toBe(true);
    const posts = postedCallUrls();
    expect(posts).toHaveLength(1);
    expect(posts[0]).toContain('/doctor/queue/17/call');
  });
});
