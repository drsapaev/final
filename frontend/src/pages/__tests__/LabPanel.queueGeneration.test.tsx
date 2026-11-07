/**
 * LABQ-FE-001 / LABQ-FE-002 (audit 3886, ledger group «laboratory queue
 * pagination and card interaction») — fail-first regressions for the
 * LabPanel queue pagination ownership:
 *
 * **LABQ-FE-001 (P1):** a load-more page launched against queue snapshot A
 * (offset = A's page size) must not append into a snapshot B that a
 * refresh installed while A's page was still in flight. The guard is an
 * epoch/generation check — the request mock resolves despite `abort()`,
 * so AbortController cancellation alone cannot enforce ownership.
 *
 * **LABQ-FE-002 (P2):** the aborted/outdated request's `finally` must not
 * clear the newer request's loading state — while the newer refresh is
 * still pending, the skeleton must stay visible.
 *
 * Red-first: on the pre-fix source the stale page is appended into the
 * refreshed snapshot (duplicated/foreign rows, offset no longer describes
 * a coherent page), and the aborted request's finally clears the newer
 * request's loading flag.
 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { LabDirtyGuardProvider } from '../../components/laboratory/LabDirtyGuardContext';

const listQueueTodayMock = vi.hoisted(() => vi.fn());
const forceRefreshTokenMock = vi.hoisted(() => vi.fn());

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return {
    ...actual,
    forceRefreshToken: forceRefreshTokenMock,
  };
});

vi.mock('../../api/labReporting', () => ({
  labReportingApi: {
    listQueueToday: listQueueTodayMock,
    listTemplates: vi.fn(async () => ({ entries: [{ id: 5, name: 'Rule Demo' }], total: 1 })),
    resolveTemplateOptions: vi.fn(async () => ({
      visit_id: 601,
      service_codes: ['svc-101'],
      allowed_templates: [],
      default_template: null,
      unmapped_service_codes: [],
      resolution_mode: 'mapped',
    })),
    listInstances: vi.fn(async () => ({ entries: [], total: 0 })),
    getInstance: vi.fn(async () => ({})),
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    finalize: vi.fn(),
    revise: vi.fn(),
    markPrinted: vi.fn(),
    downloadPdf: vi.fn(async () => ({ blob: new Blob(), url: '' })),
  },
}));

vi.mock('../../services/print', () => ({
  printService: { printLabResults: vi.fn() },
}));

// Test double: plain cards (the real virtualizer measures through rAF) with
// an explicit load-more trigger; ownership assertions do not depend on it.
vi.mock('../../components/laboratory/VirtualizedQueueList', () => ({
  default: ({ appointments, onOpenAppointment, onLoadMore }: {
    appointments: Array<Record<string, unknown>>;
    onOpenAppointment: (appointment: Record<string, unknown>) => void;
    onLoadMore?: () => void;
  }) => (
    <div className="lqw-virtualized-list" data-testid="vql">
      {appointments.map((appointment) => (
        <div
          key={String(appointment.id)}
          data-testid={`vql-row-${appointment.id}`}
          role="button"
          tabIndex={0}
          onClick={() => onOpenAppointment(appointment)}
          onKeyDown={() => undefined}
        >
          {String(appointment.patient_fio ?? '')}
        </div>
      ))}
      {typeof onLoadMore === 'function' && (
        <button data-testid="vql-load-more" type="button" onClick={() => onLoadMore()}>
          load more
        </button>
      )}
    </div>
  ),
}));

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as Record<string, unknown>).ResizeObserver = ResizeObserverStub;

import LabPanel from '../LabPanel';

const rows = (prefix: string, from: number, count: number) =>
  Array.from({ length: count }, (_, i) => ({
    id: from + i,
    appointment_id: `appt-${from + i}`,
    patient_id: from + i,
    patient_fio: `${prefix}-ROW-${i + 1}`,
    patient_phone: '',
    status: 'waiting',
    report_instance_id: null,
    services: [],
    service_codes: [],
    service_details: [],
  }));

// Snapshot B: 10 rows, more available (total 25).
const SNAP_B_PAGE1 = rows('B', 1001, 10);
// A's second page (launched at offset 10 against snapshot B's list length).
const STALE_PAGE = rows('A', 3001, 5);
// Snapshot C (after refresh): 8 rows, nothing more (total 8).
const SNAP_C = rows('C', 2001, 8);

function abortLikeError(): Error {
  return Object.assign(new Error('The operation was aborted'), { name: 'AbortError' });
}

const settle = async () => {
  for (let i = 0; i < 10; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
};

const skeletonVisible = () => document.querySelector('.lqw-skeleton') !== null;

describe('LABQ-FE-001 — a load-more page is owned by the queue generation it was launched in', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listQueueTodayMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not append the stale page into the refreshed snapshot (mock resolves despite abort)', async () => {
    let releaseStalePage: (mode: 'data' | 'abort') => void = () => {
      throw new Error('stale page release not armed');
    };
    const callLog: string[] = [];
    listQueueTodayMock.mockImplementation(async (_date: unknown, params: { offset?: number; signal?: AbortSignal } & Record<string, unknown>) => {
      const offset = Number(params?.offset ?? 0);
      callLog.push(`offset=${offset}`);
      if (offset === 0) {
        // Generation 1's page 1, then generation 2 (refresh) — both resolve
        // immediately; the refreshed snapshot has completely different rows.
        return { entries: callLog.filter((c) => c === 'offset=0').length === 1 ? SNAP_B_PAGE1 : SNAP_C, total: callLog.filter((c) => c === 'offset=0').length === 1 ? 25 : 8 };
      }
      // offset=10: the stale load-more page hangs until the test releases it.
      return new Promise((resolve, reject) => {
        releaseStalePage = (mode) => {
          if (mode === 'abort') {
            reject(abortLikeError());
          } else {
            // resolve DESPITE the abort() the refresh issued — the epoch
            // guard, not cancellation, must enforce ownership.
            resolve({ entries: STALE_PAGE, total: 25 });
          }
        };
      });
    });

    render(
      <MemoryRouter initialEntries={['/lab?tab=queue']}>
        <ThemeProvider>
          <LabDirtyGuardProvider>
            <LabPanel />
          </LabDirtyGuardProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );
    await settle();

    // Snapshot B page 1 is rendered.
    expect(screen.getByTestId('vql-row-1001')).toBeInTheDocument();
    expect(screen.getByTestId('vql-row-1010')).toBeInTheDocument();

    // Page 2 for snapshot B starts (offset 10) and hangs.
    fireEvent.click(screen.getByTestId('vql-load-more'));
    await settle();

    // Refresh installs snapshot C while the page is in flight.
    fireEvent.click(screen.getByRole('button', { name: /Yangilash|Обновить|Refresh/i }));
    await settle();

    // Only C's rows are present — B's page 1 is replaced, no A rows yet.
    for (const row of SNAP_C) {
      expect(screen.getByTestId(`vql-row-${row.id}`)).toBeInTheDocument();
    }
    expect(screen.queryByTestId('vql-row-1001')).toBeNull();
    expect(screen.queryByTestId('vql-row-3001')).toBeNull();

    // The stale page resolves despite its abort() — it must be ignored.
    releaseStalePage('data');
    await settle();

    // Pre-fix: A's rows were appended into C's snapshot. Post-fix: absent.
    for (const row of STALE_PAGE) {
      expect(screen.queryByTestId(`vql-row-${row.id}`)).toBeNull();
    }
    for (const row of SNAP_C) {
      expect(screen.getByTestId(`vql-row-${row.id}`)).toBeInTheDocument();
    }
    // No duplicate ids in the visible list.
    const visibleIds = screen.getAllByRole('button').map((el) => el.getAttribute('data-testid') || '');
    const rowIds = visibleIds.filter((id) => id.startsWith('vql-row-'));
    expect(new Set(rowIds).size).toBe(rowIds.length);
    // Snapshot C is complete (total 8) — no further page was requested.
    expect(callLog.filter((c) => c === 'offset=10')).toHaveLength(1);
    expect(callLog.filter((c) => c === 'offset=0')).toHaveLength(2);
  });

  it('the aborted request must not clear the newer request\'s loading state (LABQ-FE-002)', async () => {
    // Two overlapping REFRESH requests (the finding is about
    // loadLabAppointments' own loading flag, not the incremental one):
    // generation 1 hangs, generation 2 aborts it and stays pending.
    let releaseFirst: (mode: 'data' | 'abort') => void = () => {
      throw new Error('first release not armed');
    };
    let releaseSecond: () => void = () => {
      throw new Error('second release not armed');
    };
    listQueueTodayMock.mockImplementation(async (_date: unknown, params: { offset?: number } & Record<string, unknown>) => {
      const offset = Number(params?.offset ?? 0);
      expect(offset).toBe(0);
      const calls = listQueueTodayMock.mock.calls.filter(([, p]) => Number((p as { offset?: number })?.offset ?? 0) === 0);
      if (calls.length === 1) {
        return new Promise((resolve, reject) => {
          releaseFirst = (mode) => {
            if (mode === 'abort') {
              reject(abortLikeError());
            } else {
              resolve({ entries: SNAP_B_PAGE1, total: 25 });
            }
          };
        });
      }
      return new Promise((resolve) => {
        releaseSecond = () => resolve({ entries: SNAP_C, total: 8 });
      });
    });

    render(
      <MemoryRouter initialEntries={['/lab?tab=queue']}>
        <ThemeProvider>
          <LabDirtyGuardProvider>
            <LabPanel />
          </LabDirtyGuardProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );
    await settle();

    // Generation 1 is in flight — the skeleton is visible.
    expect(skeletonVisible()).toBe(true);

    // A refresh opens generation 2 (the F5 hotkey — the refresh button is
    // disabled while generation 1 is loading): it aborts generation 1 and
    // stays pending.
    fireEvent.keyDown(document.body, { key: 'F5' });
    await settle();

    // Generation 1 completes with an AbortError-like rejection while
    // generation 2 is STILL pending.
    releaseFirst('abort');
    await settle();

    // Pre-fix: the outdated finally cleared the loading state here and the
    // skeleton disappeared while generation 2 was still in flight.
    // Post-fix: generation 2 still owns the loading flag.
    expect(skeletonVisible()).toBe(true);

    // Generation 2 completes and may clear the loading state.
    releaseSecond();
    await settle();
    expect(skeletonVisible()).toBe(false);
    expect(screen.getByTestId('vql-row-2001')).toBeInTheDocument();
    // No stale page ever appeared.
    expect(screen.queryByTestId('vql-row-3001')).toBeNull();
  });

});
