import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';

import { useQueueManager } from '../useQueueManager';

/**
 * QD-2C (Codex round-17 P1): the queue manager adapter must match the
 * resource ownership axis. A pure registry queue (lab/ECG) carries
 * specialist_id = null — before the fix, pickQueueForDoctor accepted
 * only an exact non-null specialist id, so selecting the legacy lab/ECG
 * specialist discarded the valid resource queue returned by
 * /registrar/queues/today and substituted an empty queue, hiding all
 * waiting patients. The payload now carries queue_resource_id +
 * routing_specialists (the legacy specialists whose specialty routes to
 * the registry tag) and the adapter matches the selection against that
 * axis.
 */

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

const todayQueuesResponse = {
  data: {
    queues: [
      {
        queue_id: 1,
        specialist_id: null,
        specialty: 'laboratory',
        queue_resource_id: 5,
        routing_specialists: [LAB_SPECIALIST_ID],
        specialist_name: 'Ресурс очереди',
        cabinet: '7',
        entries: [
          {
            id: 101,
            status: 'waiting',
            patient_name: 'Пациент Лаборатории',
          },
        ],
        stats: { total_entries: 1, waiting: 1, completed: 0 },
      },
      {
        queue_id: 2,
        specialist_id: CARDIO_DOCTOR_ID,
        specialty: 'cardiology',
        queue_resource_id: null,
        routing_specialists: [],
        entries: [],
        stats: { total_entries: 0, waiting: 0, completed: 0 },
      },
    ],
    total_queues: 2,
    date: '2026-09-10',
    timezone: 'Asia/Tashkent',
  },
};

const specialistsResponse = {
  data: {
    specialists: [
      {
        id: LAB_SPECIALIST_ID,
        specialty: 'lab',
        doctor_name: 'Лаборатория',
        cabinet: '7',
      },
      {
        id: CARDIO_DOCTOR_ID,
        specialty: 'cardiology',
        doctor_name: 'dr_cardio',
        cabinet: '2',
      },
    ],
    total: 2,
  },
};

describe('useQueueManager resource-axis queue matching (QD-2C round-17 P1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.get.mockImplementation(async (url: string) => {
      if (url === '/queue/available-specialists') {
        return specialistsResponse;
      }
      if (url === '/registrar/queues/today') {
        return todayQueuesResponse;
      }
      throw new Error(`unexpected api.get url: ${url}`);
    });
  });

  it('picks the resource queue through routing_specialists for the legacy lab specialist', async () => {
    const { result } = renderHook(() => useQueueManager());

    let picked: unknown = null;
    await act(async () => {
      picked = await result.current.loadQueueSnapshot({
        specialistId: LAB_SPECIALIST_ID,
        targetDate: '2026-09-10',
      });
    });

    // the REAL resource queue is picked — not the empty substitution
    expect(picked).not.toBeNull();
    const queue = picked as { entries?: Array<{ id: number }>; queue_resource_id?: number };
    expect(queue.queue_resource_id).toBe(5);
    expect(queue.entries).toHaveLength(1);
    expect(queue.entries?.[0].id).toBe(101);
    expect(result.current.queueData?.entries).toHaveLength(1);
    expect(result.current.statistics?.waiting).toBe(1);
  });

  it('still substitutes an empty queue for an id on neither ownership axis', async () => {
    const { result } = renderHook(() => useQueueManager());

    let picked: unknown = null;
    await act(async () => {
      picked = await result.current.loadQueueSnapshot({
        specialistId: 999,
        targetDate: '2026-09-10',
      });
    });

    const queue = picked as { entries?: unknown[]; id?: number };
    expect(queue.id).toBe(999);
    expect(queue.entries).toHaveLength(0);
    expect(result.current.statistics?.waiting).toBe(0);
  });

  it('keeps the exact specialist_id match for doctor-owned queues', async () => {
    const { result } = renderHook(() => useQueueManager());

    let picked: unknown = null;
    await act(async () => {
      picked = await result.current.loadQueueSnapshot({
        specialistId: CARDIO_DOCTOR_ID,
        targetDate: '2026-09-10',
      });
    });

    const queue = picked as { specialist_id?: number; queue_resource_id?: null };
    expect(queue.specialist_id).toBe(CARDIO_DOCTOR_ID);
    expect(queue.queue_resource_id).toBeNull();
  });
});
