/**
 * DOCQ-FE-001/003 + QAPI-FE-001 (audit 3886, ledger group 2 — doctor queue
 * API/client paths):
 *
 * DOCQ-FE-001 (P1): the panel re-runs loading on `specialty` change but has
 *   no request-identity guard — a late response for specialty A resolves
 *   after the user switched to B and overwrites B's queue with A's patients
 *   (setQueueData after an unguarded await).
 * DOCQ-FE-003 (P2): a failed initial load renders the misleading
 *   «Очередь не создана» empty state (AppEmpty returns before the error
 *   alert), and a failed REFRESH keeps the stale rows as if they were
 *   fresh, with no stale warning.
 * QAPI-FE-001 (P2): queueService.callNextWaiting re-derives its own next
 *   patient via a local `entries.find(can_call)` fallback when the server
 *   explicitly returned `next_call_entry_id: null` — the backend SSOT said
 *   «none», the client invents a candidate anyway. A missing field is a
 *   contract failure and must not silently guess either.
 *
 * Red-first: on pre-fix source every test below fails for the documented
 * reason; see the PR body evidence table.
 */
import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { apiGet, apiPost, loggerInfo, loggerError, tokenGetAccessToken } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  loggerInfo: vi.fn(),
  loggerError: vi.fn(),
  tokenGetAccessToken: vi.fn(() => 'doctor-token'),
}));

vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), info: loggerInfo, warn: vi.fn(), error: loggerError },
}));
vi.mock('../../utils/tokenManager', () => ({
  default: { getAccessToken: tokenGetAccessToken },
}));
// DOCQ-FE-002 (audit 3886): the panel routes through the canonical api
// client — the 401 refresh/retry machinery is the client's own tested
// surface (api/__tests__/client.401.test.ts); these tests mock the client
// boundary the same way.
vi.mock('../../../api/client', () => ({
  api: { get: apiGet, post: apiPost },
}));

const {
  DoctorQueuePanelTestMacOSCard,
  DoctorQueuePanelTestMacOSButton,
  DoctorQueuePanelTestMacOSBadge,
  DoctorQueuePanelTestMacOSLoadingSkeleton,
  DoctorQueuePanelTestAppEmpty,
  DoctorQueuePanelTestMacOSAlert,
} = vi.hoisted(() => {
  const DoctorQueuePanelTestMacOSCard = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  const DoctorQueuePanelTestMacOSButton = ({ children, ...props }: { children?: React.ReactNode; [key: string]: unknown }) => (
    <button {...props as Record<string, unknown>}>{children}</button>
  );
  const DoctorQueuePanelTestMacOSBadge = ({ children }: { children?: React.ReactNode }) => <span>{children}</span>;
  const DoctorQueuePanelTestMacOSLoadingSkeleton = () => <div>loading</div>;
  const DoctorQueuePanelTestAppEmpty = ({ title }: { title?: React.ReactNode }) => <div>{title}</div>;
  const DoctorQueuePanelTestMacOSAlert = ({ title, description }: { title?: React.ReactNode; description?: React.ReactNode }) => (
    <div>
      {title}
      {description}
    </div>
  );
  return {
    DoctorQueuePanelTestMacOSCard,
    DoctorQueuePanelTestMacOSButton,
    DoctorQueuePanelTestMacOSBadge,
    DoctorQueuePanelTestMacOSLoadingSkeleton,
    DoctorQueuePanelTestAppEmpty,
    DoctorQueuePanelTestMacOSAlert,
  };
});

vi.mock('../../ui/macos', () => ({
  Card: DoctorQueuePanelTestMacOSCard,
  Button: DoctorQueuePanelTestMacOSButton,
  Badge: DoctorQueuePanelTestMacOSBadge,
  Skeleton: DoctorQueuePanelTestMacOSLoadingSkeleton,
  AppEmpty: DoctorQueuePanelTestAppEmpty,
  Alert: DoctorQueuePanelTestMacOSAlert,
}));

import DoctorQueuePanel from '../DoctorQueuePanel';

const MY_INFO_OK = {
  data: {
    id: 7,
    name: 'Dr. Test',
    specialty: 'cardiology',
    queue_settings: { start_number: 'A001', max_per_day: 20, timezone: 'Asia/Tashkent' },
    doctor: { cabinet: '101' },
  },
};

function queueOk(specialty: string, patient: string) {
  return {
    data: {
      queue_exists: true,
      opened_at: '2026-03-30T00:00:00Z',
      stats: { total: 1, waiting: 1, served: 0, online_entries: 1 },
      doctor: { name: 'Dr. Test', specialty, cabinet: '101' },
      next_call_entry_id: 11,
      entries: [
        {
          id: 11,
          number: 'A001',
          patient_name: patient,
          status: 'waiting',
          available_actions: ['call', 'no_show'],
          can_call: true,
          can_start_visit: false,
          can_complete: false,
          source: 'desk',
          phone: '+998901234567',
          created_at: '2026-03-30T08:00:00Z',
        },
      ],
    },
  };
}

// Axios-shaped rejection: the canonical client rejects non-2xx with the
// parsed body on error.response.data.
const QUEUE_LOAD_FAILED = Object.assign(
  new Error('Request failed with status code 500'),
  { isAxiosError: true, response: { status: 500, statusText: 'Internal Server Error', data: { detail: 'internal error' } } },
);

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

beforeEach(() => {
  apiGet.mockReset();
  apiPost.mockReset();
  loggerInfo.mockReset();
  loggerError.mockReset();
  tokenGetAccessToken.mockReturnValue('doctor-token');
});

afterEach(() => {
  vi.clearAllMocks();
  // custom/no-fake-timers-without-cleanup: fake timers must be restored in
  // an afterEach hook — in singleFork mode leaked timers hang the runner.
  vi.useRealTimers();
});

describe('DOCQ-FE-001: a late response of specialty A must not overwrite B', () => {
  it('deferred cardiology queue resolves after the switch to dermatology — B stays on screen', async () => {
    const cardioQueue = deferred<ReturnType<typeof queueOk>>();
    apiGet.mockImplementation(async (url: string) => {
      if (url.includes('/doctor/my-info')) return MY_INFO_OK;
      if (url.includes('/doctor/cardiology/queue/today')) return cardioQueue.promise;
      if (url.includes('/doctor/dermatology/queue/today')) return queueOk('dermatology', 'Бета-Пациент Дерма');
      throw new Error(`Unexpected api.get URL: ${url}`);
    });

    const { rerender } = render(<DoctorQueuePanel specialty="cardiology" />);

    // Switch to dermatology while cardiology's queue request is in flight.
    rerender(<DoctorQueuePanel specialty="dermatology" />);

    // B loaded and is on screen.
    expect(await screen.findByText('Бета-Пациент Дерма')).toBeInTheDocument();

    // A resolves LATE — it must not paint A's patients under B's panel.
    await act(async () => {
      cardioQueue.resolve(queueOk('cardiology', 'Альфа-Пациент Кардио'));
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText('Бета-Пациент Дерма')).toBeInTheDocument();
    expect(screen.queryByText('Альфа-Пациент Кардио')).toBeNull();
  });
});

describe('DOCQ-FE-003: a failed load must not render as «queue not created»', () => {
  it('initial 500 shows a load error, never the misleading empty state', async () => {
    apiGet.mockImplementation(async (url: string) => {
      if (url.includes('/doctor/my-info')) return MY_INFO_OK;
      if (url.includes('/doctor/cardiology/queue/today')) throw QUEUE_LOAD_FAILED;
      throw new Error(`Unexpected api.get URL: ${url}`);
    });

    render(<DoctorQueuePanel specialty="cardiology" />);

    // The failure state must surface as an error, not «Очередь не создана».
    await waitFor(() => {
      expect(screen.getByText(/очередь недоступна/i)).toBeInTheDocument();
    });
    expect(screen.queryByText('Очередь не создана')).toBeNull();
  });

  it('a failed refresh after a successful load flags the rows as stale', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    // Phase 1: both requests succeed.
    apiGet.mockImplementation(async (url: string) => {
      if (url.includes('/doctor/my-info')) return MY_INFO_OK;
      if (url.includes('/doctor/cardiology/queue/today')) return queueOk('cardiology', 'Альфа-Пациент Кардио');
      throw new Error(`Unexpected api.get URL: ${url}`);
    });

    render(<DoctorQueuePanel specialty="cardiology" />);
    expect(await screen.findByText('Альфа-Пациент Кардио')).toBeInTheDocument();

    // Phase 2: the 30s interval refresh now fails.
    apiGet.mockImplementation(async (url: string) => {
      if (url.includes('/doctor/my-info')) return MY_INFO_OK;
      if (url.includes('/doctor/cardiology/queue/today')) throw QUEUE_LOAD_FAILED;
      throw new Error(`Unexpected api.get URL: ${url}`);
    });

    await act(async () => {
      vi.advanceTimersByTime(30000);
    });

    // The stale warning must be visible next to the previously loaded rows.
    await waitFor(() => {
      expect(screen.getByText(/данные могли устареть/i)).toBeInTheDocument();
    });
    // The stale rows stay visible but the panel does not pretend they are fresh.
    expect(screen.getByText('Альфа-Пациент Кардио')).toBeInTheDocument();
  });
});
