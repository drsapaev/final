/* eslint-disable react/prop-types */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

const { fetchMock, loggerInfo, loggerError, tokenGetAccessToken } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
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

const {
  DoctorQueuePanelTestMacOSCard,
  DoctorQueuePanelTestMacOSButton,
  DoctorQueuePanelTestMacOSBadge,
  DoctorQueuePanelTestMacOSLoadingSkeleton,
  DoctorQueuePanelTestMacOSEmptyState,
  DoctorQueuePanelTestMacOSAlert,
} = vi.hoisted(() => {
  const DoctorQueuePanelTestMacOSCard = ({ children }) => <div>{children}</div>;

  const DoctorQueuePanelTestMacOSButton = ({ children, ...props }) => <button {...props}>{children}</button>;

  const DoctorQueuePanelTestMacOSBadge = ({ children }) => <span>{children}</span>;

  const DoctorQueuePanelTestMacOSLoadingSkeleton = () => <div>loading</div>;

  const DoctorQueuePanelTestMacOSEmptyState = ({ title }) => <div>{title}</div>;

  const DoctorQueuePanelTestMacOSAlert = ({ title, description }) => (
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
    DoctorQueuePanelTestMacOSEmptyState,
    DoctorQueuePanelTestMacOSAlert,
  };
});

vi.mock('../../ui/macos', () => ({
  MacOSCard: DoctorQueuePanelTestMacOSCard,
  Button: DoctorQueuePanelTestMacOSButton,
  Badge: DoctorQueuePanelTestMacOSBadge,
  Skeleton: DoctorQueuePanelTestMacOSLoadingSkeleton,
  MacOSEmptyState: DoctorQueuePanelTestMacOSEmptyState,
  Alert: DoctorQueuePanelTestMacOSAlert,
}));

import DoctorQueuePanel from '../DoctorQueuePanel.tsx';

describe('DoctorQueuePanel', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    loggerInfo.mockReset();
    loggerError.mockReset();
    tokenGetAccessToken.mockReturnValue('doctor-token');

    fetchMock.mockImplementation(async (input) => {
      const url = String(input);

      if (url.includes('/doctor/my-info')) {
        return {
          ok: true,
          json: async () => ({
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
          }),
        };
      }

      if (url.includes('/doctor/cardiology/queue/today')) {
        return {
          ok: true,
          json: async () => ({
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
          }),
        };
      }

      throw new Error(`Unexpected fetch URL: ${url}`);
    });

    global.fetch = fetchMock;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('uses the canonical backend origin instead of legacy port 8000', async () => {
    render(<DoctorQueuePanel specialty="cardiology" />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    const requestedUrls = fetchMock.mock.calls.map(([url]) => String(url));

    expect(requestedUrls).toEqual([
      expect.stringMatching(/^http:\/\/(?:localhost|127\.0\.0\.1):18000\/api\/v1\/doctor\/my-info$/),
      expect.stringMatching(/^http:\/\/(?:localhost|127\.0\.0\.1):18000\/api\/v1\/doctor\/cardiology\/queue\/today$/),
    ]);
    expect(requestedUrls.some((url) => url.includes(':8000'))).toBe(false);
    expect(loggerInfo).toHaveBeenCalledWith(
      '[FIX:DOCTOR_QUEUE_PANEL] Loading doctor info from canonical API origin',
      expect.objectContaining({
        url: expect.stringMatching(/^http:\/\/(?:localhost|127\.0\.0\.1):18000\/api\/v1\/doctor\/my-info$/),
      }),
    );
  });

  it('does not render queue command buttons from status alone', async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);

      if (url.includes('/doctor/my-info')) {
        return {
          ok: true,
          json: async () => ({
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
          }),
        };
      }

      if (url.includes('/doctor/cardiology/queue/today')) {
        return {
          ok: true,
          json: async () => ({
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
          }),
        };
      }

      throw new Error(`Unexpected fetch URL: ${url}`);
    });

    const { container } = render(<DoctorQueuePanel specialty="cardiology" />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/doctor\/cardiology\/queue\/today$/),
        expect.any(Object),
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
