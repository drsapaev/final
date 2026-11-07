/**
 * DOCQ-FE-002 (audit 3886, ledger group «doctor queue API/client paths»):
 * the doctor queue panel's reads and commands must route through the
 * canonical `api/client.ts` axios instance — the shared client owns the
 * expired-JWT single-flight refresh + 401 retry, CSRF and rate-limit
 * handling. The raw fetch bypassed all of it: an expired staff JWT could
 * 401 without the shared refresh/retry, failing commands until a manual
 * re-auth.
 *
 * The 401 refresh/retry semantics themselves are the client's own pinned
 * surface (src/api/__tests__/client.401.test.ts: exactly one single-flight
 * refresh + one retry, session-replacement guard). These tests pin the
 * PANEL side of the contract:
 *  - reads and commands go through api.get/api.post with the canonical
 *    relative paths — global.fetch is NEVER called;
 *  - a 401 that still surfaces after the client's own refresh/retry
 *    (dead session) renders the honest load-error state, never the
 *    misleading «Очередь не создана» empty state;
 *  - a command POST carries the queue entry id and surfaces the server's
 *    detail on rejection.
 *
 * Red-first: on pre-fix source every test below fails — the panel issued
 * raw fetch() calls, so the api mocks are never invoked and the fetch spy
 * IS invoked.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

const MY_INFO = {
  data: {
    id: 7,
    name: 'Dr. Test',
    specialty: 'cardiology',
    queue_settings: { start_number: 'A001', max_per_day: 20, timezone: 'Asia/Tashkent' },
    doctor: { cabinet: '101' },
  },
};

const QUEUE = {
  data: {
    queue_exists: true,
    opened_at: '2026-03-30T00:00:00Z',
    stats: { total: 1, waiting: 1, served: 0, online_entries: 1 },
    doctor: { name: 'Dr. Test', specialty: 'cardiology', cabinet: '101' },
    next_call_entry_id: 11,
    entries: [
      {
        id: 11,
        number: 'A001',
        patient_name: 'Синтетический Пациент',
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

/** Axios-shaped rejection the way the canonical client surfaces non-2xx. */
const axiosReject = (status: number, data: unknown) =>
  Object.assign(new Error(`Request failed with status code ${status}`), {
    isAxiosError: true,
    response: { status, statusText: '', data },
  });

let fetchSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  apiGet.mockReset();
  apiPost.mockReset();
  loggerInfo.mockReset();
  loggerError.mockReset();
  tokenGetAccessToken.mockReturnValue('doctor-token');
  fetchSpy = vi.fn();
  global.fetch = fetchSpy as never;
});

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('DOCQ-FE-002 transport: the panel never issues a raw fetch', () => {
  it('reads (my-info, today queue) go through the canonical api client', async () => {
    apiGet.mockImplementation(async (url: string) => {
      if (url === '/doctor/my-info') return MY_INFO;
      if (url === '/doctor/cardiology/queue/today') return QUEUE;
      throw new Error(`Unexpected api.get URL: ${url}`);
    });

    render(<DoctorQueuePanel specialty="cardiology" />);

    expect(await screen.findByText('Синтетический Пациент')).toBeInTheDocument();
    expect(apiGet.mock.calls.map(([url]) => String(url))).toEqual([
      '/doctor/my-info',
      '/doctor/cardiology/queue/today',
    ]);
    // DOCQ-FE-002: zero raw fetch — the refresh/retry machinery cannot be
    // bypassed anymore.
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('the call command POSTs through the canonical client with the canonical entry id', async () => {
    apiGet.mockImplementation(async (url: string) => {
      if (url === '/doctor/my-info') return MY_INFO;
      if (url === '/doctor/cardiology/queue/today') return QUEUE;
      throw new Error(`Unexpected api.get URL: ${url}`);
    });
    apiPost.mockResolvedValue({ data: { success: true, message: 'Пациент вызван' } });

    render(<DoctorQueuePanel specialty="cardiology" />);
    const user = userEvent.setup();
    const callButton = await screen.findByRole('button', { name: /Вызвать/ });
    await user.click(callButton);

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith('/doctor/queue/11/call');
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('a command rejection surfaces the server-provided detail through the client error shape', async () => {
    apiGet.mockImplementation(async (url: string) => {
      if (url === '/doctor/my-info') return MY_INFO;
      if (url === '/doctor/cardiology/queue/today') return QUEUE;
      throw new Error(`Unexpected api.get URL: ${url}`);
    });
    apiPost.mockRejectedValue(axiosReject(409, { detail: 'Пациент уже вызван' }));

    render(<DoctorQueuePanel specialty="cardiology" />);
    const user = userEvent.setup();
    const callButton = await screen.findByRole('button', { name: /Вызвать/ });
    await user.click(callButton);

    await waitFor(() => {
      expect(screen.getByText(/Пациент уже вызван/)).toBeInTheDocument();
    });
  });
});

describe('DOCQ-FE-002 401-after-refresh: a dead session renders the honest error state', () => {
  it('a 401 that still surfaces after the client refresh/retry is a load error, not «Очередь не создана»', async () => {
    apiGet.mockImplementation(async (url: string) => {
      if (url === '/doctor/my-info') return MY_INFO;
      // The canonical client already performed its single-flight refresh +
      // retry (pinned in client.401.test.ts); the 401 that still reaches
      // the panel means the session is dead — surface it honestly.
      if (url === '/doctor/cardiology/queue/today') throw axiosReject(401, { detail: 'Не авторизован' });
      throw new Error(`Unexpected api.get URL: ${url}`);
    });

    render(<DoctorQueuePanel specialty="cardiology" />);

    await waitFor(() => {
      expect(screen.getByText(/очередь недоступна/i)).toBeInTheDocument();
    });
    expect(screen.queryByText('Очередь не создана')).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
