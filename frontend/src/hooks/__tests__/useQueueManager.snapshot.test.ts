/**
 * REG-FE-035 + REG-FE-042 (registrar audit ledger 3803) — queue manager
 * snapshot lifecycle.
 *
 * REG-FE-035: loadQueueSnapshot had no request epoch, so an older
 * doctor/date snapshot resolving late overwrote the currently selected
 * one (entries + statistics), and a late older `finally` cleared the
 * shared loading flag while the newer request was still pending.
 *
 * REG-FE-042: a doctor with no matching queue got a fabricated
 * { id: specialistId, entries: [], stats: null } queue, erasing the
 * distinction between "Очередь не найдена" (queueData = null) and a real
 * "Очередь пуста" (queue with zero entries) that QueueTable renders.
 *
 * Contract:
 * - the latest selected doctor/date snapshot wins; a superseded response
 *   (success, failure or finally) must not touch newer state
 * - a doctor absent from the payload keeps queueData = null and zeroes
 *   the statistics — the not-found UI, never a fake empty queue
 * - a real empty queue stays a real queue object (distinction preserved)
 */
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useQueueManager } from '../useQueueManager';

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../../api/client', () => ({ api }));

vi.mock('../../utils/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    log: vi.fn(),
    debug: vi.fn(),
  },
}));

const apiMock = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

const LAB_SPECIALIST_ID = 7;
const CARDIO_DOCTOR_ID = 3;

const labQueue = {
  queue_id: 1,
  specialist_id: null,
  specialty: 'laboratory',
  queue_resource_id: 5,
  routing_specialists: [LAB_SPECIALIST_ID],
  specialist_name: 'Ресурс очереди',
  cabinet: '7',
  entries: [
    { id: 101, status: 'waiting', patient_name: 'Синтетов С.' },
    { id: 102, status: 'waiting', patient_name: 'Синтетова С.' },
  ],
  stats: { total_entries: 2, waiting: 2, completed: 0 },
};

const cardioQueue = {
  queue_id: 2,
  specialist_id: CARDIO_DOCTOR_ID,
  specialty: 'cardiology',
  queue_resource_id: null,
  routing_specialists: [],
  entries: [],
  stats: { total_entries: 0, waiting: 0, completed: 0 },
};

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

/**
 * The hook auto-loads /queue/available-specialists on mount, so the mock
 * must be URL-aware: only /registrar/queues/today draws from the
 * per-test deferred queue.
 */
function mockTodayQueue(calls: Array<Promise<{ data: { queues: unknown[] } }>>) {
  apiMock.get.mockImplementation(async (url: string) => {
    if (url === '/queue/available-specialists') {
      return { data: { specialists: [] } };
    }
    if (url === '/registrar/queues/today') {
      const next = calls.shift();
      if (!next) throw new Error('unexpected /registrar/queues/today call');
      return next;
    }
    throw new Error(`unexpected api.get url: ${url}`);
  });
}

describe('useQueueManager snapshot lifecycle (REG-FE-035 / REG-FE-042)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('REG-FE-042: a doctor absent from the payload keeps queueData null with zeroed stats — no fabricated empty queue', async () => {
    apiMock.get.mockResolvedValue({ data: { queues: [labQueue, cardioQueue] } });
    const { result } = renderHook(() => useQueueManager());

    let picked: unknown = 'sentinel';
    await act(async () => {
      picked = await result.current.loadQueueSnapshot({
        specialistId: 999,
        targetDate: '2026-11-03',
      });
    });

    expect(picked).toBeNull();
    expect(result.current.queueData).toBeNull();
    expect(result.current.statistics).toEqual({ total_entries: 0, waiting: 0, completed: 0 });
  });

  it('REG-FE-042: a real empty queue stays a real queue object (not-found vs empty distinction preserved)', async () => {
    apiMock.get.mockResolvedValue({ data: { queues: [labQueue, cardioQueue] } });
    const { result } = renderHook(() => useQueueManager());

    let picked: unknown = null;
    await act(async () => {
      picked = await result.current.loadQueueSnapshot({
        specialistId: CARDIO_DOCTOR_ID,
        targetDate: '2026-11-03',
      });
    });

    const queue = picked as { queue_id?: number; entries?: unknown[] };
    expect(queue.queue_id).toBe(2);
    expect(queue.entries).toEqual([]);
    expect(result.current.queueData?.queue_id).toBe(2);
  });

  it('REG-FE-035: a late older snapshot must not overwrite the newer selection', async () => {
    const lateA = deferred<{ data: { queues: unknown[] } }>();
    const freshB = deferred<{ data: { queues: unknown[] } }>();
    mockTodayQueue([lateA.promise, freshB.promise]);

    const { result } = renderHook(() => useQueueManager());

    // Request A (lab) starts and hangs.
    let aPromise: Promise<unknown> | null = null;
    await act(async () => {
      aPromise = result.current.loadQueueSnapshot({ specialistId: LAB_SPECIALIST_ID, targetDate: '2026-11-03' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // Request B (cardio) starts and resolves first.
    await act(async () => {
      void result.current.loadQueueSnapshot({ specialistId: CARDIO_DOCTOR_ID, targetDate: '2026-11-03' });
      freshB.resolve({ data: { queues: [labQueue, cardioQueue] } });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.queueData?.queue_id).toBe(2);

    // A resolves LATE: the newer cardio selection must win.
    await act(async () => {
      lateA.resolve({ data: { queues: [labQueue] } });
      await aPromise;
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(result.current.queueData?.queue_id).toBe(2);
    expect(result.current.statistics?.waiting).toBe(0);
    expect(result.current.loading).toBe(false);
  });

  it('REG-FE-035: a superseded request resolving early does not clear loading while the newer request is pending', async () => {
    const earlyA = deferred<{ data: { queues: unknown[] } }>();
    const pendingB = deferred<{ data: { queues: unknown[] } }>();
    mockTodayQueue([earlyA.promise, pendingB.promise]);

    const { result } = renderHook(() => useQueueManager());

    let aPromise: Promise<unknown> | null = null;
    await act(async () => {
      aPromise = result.current.loadQueueSnapshot({ specialistId: LAB_SPECIALIST_ID, targetDate: '2026-11-03' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    await act(async () => {
      void result.current.loadQueueSnapshot({ specialistId: CARDIO_DOCTOR_ID, targetDate: '2026-11-03' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // A (superseded) resolves while B is still pending: loading must stay true.
    await act(async () => {
      earlyA.resolve({ data: { queues: [labQueue] } });
      await aPromise;
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.loading).toBe(true);

    await act(async () => {
      pendingB.resolve({ data: { queues: [cardioQueue] } });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.loading).toBe(false);
    expect(result.current.queueData?.queue_id).toBe(2);
  });

  it('REG-FE-035: a superseded request failing late resolves null and does not disturb the newer state', async () => {
    const lateA = deferred<{ data: { queues: unknown[] } }>();
    const freshB = deferred<{ data: { queues: unknown[] } }>();
    mockTodayQueue([lateA.promise, freshB.promise]);

    const { result } = renderHook(() => useQueueManager());

    let aPromise: Promise<unknown> | null = null;
    await act(async () => {
      aPromise = result.current.loadQueueSnapshot({ specialistId: LAB_SPECIALIST_ID, targetDate: '2026-11-03' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    await act(async () => {
      void result.current.loadQueueSnapshot({ specialistId: CARDIO_DOCTOR_ID, targetDate: '2026-11-03' });
      freshB.resolve({ data: { queues: [cardioQueue] } });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // The superseded request rejects late: resolves null (no unhandled throw
    // into the newer caller's UI), cardio state untouched.
    let lateOutcome: unknown = 'sentinel';
    await act(async () => {
      lateA.reject(new Error('late failure'));
      lateOutcome = await aPromise!.then(
        (value) => value,
        () => 'rejected',
      );
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(lateOutcome).toBeNull();
    expect(result.current.queueData?.queue_id).toBe(2);
    expect(result.current.loading).toBe(false);
  });

  // REG-FE-068: deselecting the doctor is a snapshot lifecycle transition —
  // the epoch bump must happen BEFORE the no-specialist early return, the
  // previous doctor's queue/statistics must be cleared, and a late response
  // of the in-flight request must not resurrect the deselected queue.
  it('REG-FE-068: deselecting the doctor invalidates an in-flight snapshot — the late response cannot resurrect it', async () => {
    const lateA = deferred<{ data: { queues: unknown[] } }>();
    mockTodayQueue([lateA.promise]);

    const { result } = renderHook(() => useQueueManager());

    // Doctor A (lab) is selected — the request hangs in flight.
    let aPromise: Promise<unknown> | null = null;
    await act(async () => {
      aPromise = result.current.loadQueueSnapshot({ specialistId: LAB_SPECIALIST_ID, targetDate: '2026-11-03' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // The user deselects the doctor while A is still in flight.
    let deselected: unknown = 'sentinel';
    await act(async () => {
      deselected = await result.current.loadQueueSnapshot({ specialistId: '', targetDate: '2026-11-03' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(deselected).toBeNull();
    // The deselected state is explicit: no queue, no statistics (null — not
    // misleading zeroed cards; see the #3856 review follow-up), no spinner.
    expect(result.current.queueData).toBeNull();
    expect(result.current.statistics).toBeNull();
    expect(result.current.loading).toBe(false);

    // A's late response arrives after the deselection — it must NOT
    // resurrect the deselected doctor's queue (pre-fix: the untouched epoch
    // let it pass the staleness check and setQueueData(labQueue)).
    await act(async () => {
      lateA.resolve({ data: { queues: [labQueue] } });
      await aPromise;
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.queueData).toBeNull();
    expect(result.current.statistics).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('REG-FE-068: a deselection followed by a new selection keeps the new selection authoritative', async () => {
    const lateA = deferred<{ data: { queues: unknown[] } }>();
    const freshB = deferred<{ data: { queues: unknown[] } }>();
    mockTodayQueue([lateA.promise, freshB.promise]);

    const { result } = renderHook(() => useQueueManager());

    let aPromise: Promise<unknown> | null = null;
    await act(async () => {
      aPromise = result.current.loadQueueSnapshot({ specialistId: LAB_SPECIALIST_ID, targetDate: '2026-11-03' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // Deselect, then immediately pick another doctor.
    await act(async () => {
      void result.current.loadQueueSnapshot({ specialistId: '', targetDate: '2026-11-03' });
      void result.current.loadQueueSnapshot({ specialistId: CARDIO_DOCTOR_ID, targetDate: '2026-11-03' });
      freshB.resolve({ data: { queues: [cardioQueue] } });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.queueData?.queue_id).toBe(2);

    await act(async () => {
      lateA.resolve({ data: { queues: [labQueue] } });
      await aPromise;
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.queueData?.queue_id).toBe(2);
    expect(result.current.loading).toBe(false);
  });
});

describe('QMAN-FE-001 (audit 3886): failed current-selection load is fail-closed', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('a failed CURRENT selection load clears the previous selection\'s queue and stats — no stale doctor data', async () => {
    // Doctor A (lab) loads successfully; the switch to doctor B (cardio)
    // FAILS. The hook must not leave A's queue/statistics on screen as if
    // they were B's current queue.
    // Lazy rejection: the failure is created at call time (an eagerly
    // created Promise.reject would surface as an unhandled rejection
    // before the hook attaches its handler).
    let todayCallCount = 0;
    apiMock.get.mockImplementation(async (url: string) => {
      if (url === '/queue/available-specialists') {
        return { data: { specialists: [] } };
      }
      if (url === '/registrar/queues/today') {
        todayCallCount += 1;
        if (todayCallCount === 1) return { data: { queues: [labQueue] } };
        throw new Error('network down');
      }
      throw new Error(`unexpected api.get url: ${url}`);
    });

    const { result } = renderHook(() => useQueueManager());

    await act(async () => {
      await result.current.loadQueueSnapshot({
        specialistId: LAB_SPECIALIST_ID,
        targetDate: '2026-11-03',
      });
    });
    expect(result.current.queueData?.queue_id).toBe(1);
    expect(result.current.statistics?.total_entries).toBe(2);

    await act(async () => {
      await expect(
        result.current.loadQueueSnapshot({
          specialistId: CARDIO_DOCTOR_ID,
          targetDate: '2026-11-03',
        }),
      ).rejects.toThrow('network down');
    });

    // Fail-closed: the failed current selection owns NO data — the previous
    // doctor's rows/is_open decisions must not be presented as current.
    expect(result.current.queueData).toBeNull();
    expect(result.current.statistics).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('positive control: a successful switch still replaces the queue with the new selection', async () => {
    mockTodayQueue([
      Promise.resolve({ data: { queues: [labQueue] } }),
      Promise.resolve({ data: { queues: [cardioQueue] } }),
    ]);

    const { result } = renderHook(() => useQueueManager());

    await act(async () => {
      await result.current.loadQueueSnapshot({ specialistId: LAB_SPECIALIST_ID, targetDate: '2026-11-03' });
    });
    expect(result.current.queueData?.queue_id).toBe(1);

    await act(async () => {
      await result.current.loadQueueSnapshot({ specialistId: CARDIO_DOCTOR_ID, targetDate: '2026-11-03' });
    });
    expect(result.current.queueData?.queue_id).toBe(2);
    expect(result.current.statistics).toEqual({ total_entries: 0, waiting: 0, completed: 0 });
  });
});
