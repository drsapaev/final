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

// An in-progress entry: start-visit and complete are the offered commands.
const QUEUE_IN_PROGRESS = {
  data: {
    queue_exists: true,
    opened_at: '2026-03-30T00:00:00Z',
    stats: { total: 1, waiting: 0, served: 0, online_entries: 0 },
    doctor: { name: 'Dr. Test', specialty: 'cardiology', cabinet: '101' },
    next_call_entry_id: 12,
    entries: [
      {
        id: 12,
        number: 'A002',
        patient_name: 'Синтетический Пациент Два',
        status: 'in_progress',
        available_actions: ['start_visit', 'complete'],
        can_call: false,
        can_start_visit: true,
        can_complete: true,
        source: 'desk',
        phone: '+998901234568',
        created_at: '2026-03-30T08:00:00Z',
        called_at: '2026-03-30T08:05:00Z',
      },
    ],
  },
};

const setupInProgressQueue = () => {
  apiGet.mockImplementation(async (url: string) => {
    if (url === '/doctor/my-info') return MY_INFO;
    if (url === '/doctor/cardiology/queue/today') return QUEUE_IN_PROGRESS;
    throw new Error(`Unexpected api.get URL: ${url}`);
  });
};

describe('DOCQ-FE-004 write-ACK: a resolved 2xx without an explicit success ack is never a confirmed command', () => {
  // Post-merge review of #3905 (P1): the panel reported a clinical visit
  // completed on ANY resolved 2xx. The #3902 queue contract (DOCFLOW-FE-001)
  // fail-closes on rejected/ambiguous bodies — the panel must apply the
  // same contract to call/start-visit/complete.
  it('complete: a 2xx body with success:false is a rejection, not «Успешно» (pre-fix: success toast)', async () => {
    setupInProgressQueue();
    apiPost.mockResolvedValue({ data: { success: false, detail: 'Прием уже завершен другим врачом' } });

    render(<DoctorQueuePanel specialty="cardiology" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Завершить/ }));

    await waitFor(() => {
      expect(screen.getByText(/Прием уже завершен другим врачом/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Успешно/)).toBeNull();
  });

  it('complete: an unreadable 2xx body is reported as an unconfirmed operation, not a success', async () => {
    setupInProgressQueue();
    apiPost.mockResolvedValue({ data: null });

    render(<DoctorQueuePanel specialty="cardiology" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Завершить/ }));

    await waitFor(() => {
      expect(screen.getByText(/не подтверждена|NOT confirmed/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Успешно/)).toBeNull();
  });

  it('start-visit: a 2xx body with success:false is a rejection, not «Успешно»', async () => {
    setupInProgressQueue();
    apiPost.mockResolvedValue({ data: { success: false, message: 'Визит уже начат' } });

    render(<DoctorQueuePanel specialty="cardiology" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Начать/ }));

    await waitFor(() => {
      expect(screen.getByText(/Визит уже начат/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Успешно/)).toBeNull();
  });

  it('call: a 2xx body with success:false is a rejection, not «Успешно»', async () => {
    apiGet.mockImplementation(async (url: string) => {
      if (url === '/doctor/my-info') return MY_INFO;
      if (url === '/doctor/cardiology/queue/today') return QUEUE;
      throw new Error(`Unexpected api.get URL: ${url}`);
    });
    apiPost.mockResolvedValue({ data: { success: false, detail: 'Пациент уже вызван' } });

    render(<DoctorQueuePanel specialty="cardiology" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Вызвать/ }));

    await waitFor(() => {
      expect(screen.getByText(/Пациент уже вызван/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Успешно/)).toBeNull();
  });

  it('control: an explicit success:true ack confirms the command', async () => {
    setupInProgressQueue();
    apiPost.mockResolvedValue({ data: { success: true, message: 'Прием пациента завершен' } });

    render(<DoctorQueuePanel specialty="cardiology" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Завершить/ }));

    await waitFor(() => {
      expect(screen.getByText(/Успешно/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Прием пациента завершен/)).toBeInTheDocument();
  });
});
