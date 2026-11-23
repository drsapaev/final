/*  */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

const { apiGet, apiPost, loggerInfo, loggerError, tokenGetAccessToken } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  loggerInfo: vi.fn(),
  loggerError: vi.fn(),
  tokenGetAccessToken: vi.fn(() => 'doctor-token'),
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    log: vi.fn(),
    info: loggerInfo,
    warn: vi.fn(),
    error: loggerError,
  },
}));

vi.mock('../../../utils/tokenManager', () => ({
  default: {
    getAccessToken: tokenGetAccessToken,
  },
}));

// DOCQ-FE-002 (audit 3886): the panel routes through the canonical api
// client (refresh/retry/CSRF are the client's own tested surface —
// api/__tests__/client.401.test.ts); these tests mock that boundary.
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

  const DoctorQueuePanelTestMacOSButton = ({ children, ...props }: { children?: React.ReactNode; [key: string]: unknown }) => <button {...props as Record<string, unknown>}>{children}</button>;

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

describe('DoctorQueuePanel', () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiPost.mockReset();
    loggerInfo.mockReset();
    loggerError.mockReset();
    tokenGetAccessToken.mockReturnValue('doctor-token');

    apiGet.mockImplementation(async (url: string) => {
      if (url.includes('/doctor/my-info')) {
        return {
          data: {
            id: 7,
            name: 'Dr. Test',
            specialty: 'cardiology',
            queue_settings: {
              start_number: 'A001',
              max_per_day: 20,
              timezone: 'Asia/Tashkent',
            },
            doctor: {
              cabinet: '101',
            },
          },
        };
      }

      if (url.includes('/doctor/cardiology/queue/today')) {
        return {
          data: {
            queue_exists: true,
            opened_at: '2026-03-30T00:00:00Z',
            stats: {
              total: 1,
              waiting: 1,
              served: 0,
              online_entries: 1,
            },
            doctor: {
              name: 'Dr. Test',
              specialty: 'cardiology',
              cabinet: '101',
            },
            entries: [
              {
                id: 11,
                number: 'A001',
                patient_name: 'Ivan Ivanov',
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

      throw new Error(`Unexpected api.get URL: ${url}`);
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('routes reads through the canonical api client instead of raw fetch', async () => {
    const fetchSpy = vi.fn();
    global.fetch = fetchSpy as never;

    render(<DoctorQueuePanel specialty="cardiology" />);

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalled();
    });

    // DOCQ-FE-002: the client owns the API origin (baseURL) and the
    // JWT refresh/retry machinery — the panel never issues a raw fetch.
    const requestedUrls = apiGet.mock.calls.map(([url]) => String(url));
    expect(requestedUrls).toEqual([
      '/doctor/my-info',
      '/doctor/cardiology/queue/today',
    ]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('does not render queue command buttons from status alone', async () => {
    apiGet.mockImplementation(async (url: string) => {

      if (url.includes('/doctor/my-info')) {
        return {
          data: {
            id: 7,
            name: 'Dr. Test',
            specialty: 'cardiology',
            queue_settings: {
              start_number: 'A001',
              max_per_day: 20,
              timezone: 'Asia/Tashkent',
            },
            doctor: {
              cabinet: '101',
            },
          },
        };
      }

      if (url.includes('/doctor/cardiology/queue/today')) {
        return {
          data: {
            queue_exists: true,
            opened_at: '2026-03-30T00:00:00Z',
            stats: {
              total: 3,
              waiting: 1,
              called: 1,
              served: 0,
              online_entries: 0,
            },
            doctor: {
              name: 'Dr. Test',
              specialty: 'cardiology',
              cabinet: '101',
            },
            entries: [
              {
                id: 11,
                number: 'A001',
                patient_name: 'Waiting Patient',
                status: 'waiting',
                available_actions: [],
                can_call: false,
                source: 'desk',
                phone: '+998901234567',
                created_at: '2026-03-30T08:00:00Z',
              },
              {
                id: 12,
                number: 'A002',
                patient_name: 'Called Patient',
                status: 'called',
                available_actions: [],
                can_start_visit: false,
                source: 'desk',
                phone: '+998901234568',
                created_at: '2026-03-30T08:05:00Z',
              },
              {
                id: 13,
                number: 'A003',
                patient_name: 'Progress Patient',
                status: 'in_progress',
                available_actions: [],
                can_complete: false,
                source: 'desk',
                phone: '+998901234569',
                created_at: '2026-03-30T08:10:00Z',
              },
            ],
          },
        };
      }

      throw new Error(`Unexpected api.get URL: ${url}`);
    });

    const { container } = render(<DoctorQueuePanel specialty="cardiology" />);

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith(
        expect.stringMatching(/\/doctor\/cardiology\/queue\/today$/),
      );
    });

    expect(container.querySelectorAll('button')).toHaveLength(1);
  });

  it('keeps queue command visibility behind backend actions and flags', () => {
    const source = readFileSync(
      join(process.cwd(), 'src/components/doctor/DoctorQueuePanel.tsx'),
      'utf8',
    );

    expect(source).toContain('hasBackendQueueAction(entry, \'call\', \'can_call\')');
    expect(source).toContain('hasBackendQueueAction(entry, \'start_visit\', \'can_start_visit\')');
    expect(source).toContain('hasBackendQueueAction(entry, \'complete\', \'can_complete\')');
    expect(source).not.toContain('entry.status === \'waiting\' &&');
    expect(source).not.toContain('entry.status === \'called\' &&');
    expect(source).not.toContain('entry.status === \'in_progress\' &&');
  });
});
