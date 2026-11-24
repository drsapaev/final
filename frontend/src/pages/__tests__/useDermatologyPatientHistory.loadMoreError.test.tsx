/**
 * DERMAHIST-FE-002 (owner registry #4063; review-group audit comment
 * 6693119519) — failure of "Load more" is invisible to the clinician.
 *
 * `useDermatologyPatientHistory` catches a rejected pagination request,
 * logs a warning and merely resets `loadingMore…` — no user-visible
 * error state, no failed-page indicator. `DermaHistoryTab` then silently
 * re-enables the identical "Load more" button, and the patient tab's
 * alert covers only `historyError` (initial request failures). A
 * clinician seeing 20 of 40 records gets no indication that page 2 is
 * currently unavailable.
 *
 * Contract after the repair:
 * - a rejected load-more request surfaces a dedicated
 *   `loadMoreExaminationsError` / `loadMoreProceduresError` state;
 * - the history tab renders a visible alert (`role="alert"`) with a
 *   retry hint next to the (still-enabled) Load more button;
 * - the error clears on a successful retry and on a patient reload.
 *
 * Red-first: on the pre-fix source the error state is never set (hook
 * assertions fail) and the alert text is never rendered (UI assertions
 * fail); the no-error control stays green on main.
 */
import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

const apiMock = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../api/client', () => ({ api: { get: apiMock.get } }));
vi.mock('../../utils/logger', () => ({ default: { warn: vi.fn() } }));
vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock('../../components/ui/macos', () => ({
  Badge: ({ children }: { children?: ReactNode }) => <span>{children}</span>,
  Card: ({ children }: { children?: ReactNode }) => <section>{children}</section>,
}));

import { useDermatologyPatientHistory } from '../../pages/useDermatologyPatientHistory';
import DermaHistoryTab from '../../components/dermatology/DermaHistoryTab';

const envelope = (items: unknown[], total: number) => ({
  data: { items, total, page: 1, size: 20, pages: Math.ceil(total / 20) },
});

const exam = (i: number) => ({ id: `ex-${i}`, examination_date: '2026-11-16', diagnosis: `dx-${i}` });
const procedure = (i: number) => ({ id: `pr-${i}`, procedure_date: '2026-11-16', name: `proc-${i}` });

type Responder = (url: string, page: number | undefined) => Promise<{ data: unknown }>;
let responder: Responder = async () => ({ data: { items: [], total: 0 } });

apiMock.get.mockImplementation((url: string, config?: { params?: { page?: number } }) => {
  return responder(url, config?.params?.page);
});

beforeEach(() => {
  apiMock.get.mockClear();
  responder = async () => ({ data: { items: [], total: 0 } });
});

async function loadFirstPage(patientId: string) {
  const { result } = renderHook(() => useDermatologyPatientHistory(patientId));
  await waitFor(() => expect(result.current.ready).toBe(true));
  return result;
}

describe('DERMAHIST-FE-002 — a failed history page load is visible to the clinician', () => {
  it('a rejected load-more examination request raises a dedicated error state', async () => {
    responder = (url, page) => {
      if (url === '/patients/7/appointments') return Promise.resolve({ data: [] });
      if (url === '/derma/examinations') {
        return page === 2
          ? Promise.reject(new Error('page-2 unavailable'))
          : Promise.resolve(envelope(Array.from({ length: 20 }, (_, i) => exam(i)), 40));
      }
      return Promise.resolve(envelope([], 0));
    };

    const result = await loadFirstPage('7');
    expect(result.current.skinExaminations).toHaveLength(20);
    expect(result.current.hasMoreExaminations).toBe(true);

    act(() => { result.current.loadMoreExaminations(); });
    await waitFor(() => expect(result.current.loadMoreExaminationsError).toBe(true));
  });

  it('a successful retry clears the error and completes the page merge', async () => {
    responder = (url, page) => {
      if (url === '/patients/7/appointments') return Promise.resolve({ data: [] });
      if (url === '/derma/examinations') {
        return page === 2
          ? Promise.reject(new Error('page-2 unavailable'))
          : Promise.resolve(envelope(Array.from({ length: 20 }, (_, i) => exam(i)), 40));
      }
      return Promise.resolve(envelope([], 0));
    };

    const result = await loadFirstPage('7');
    act(() => { result.current.loadMoreExaminations(); });
    await waitFor(() => expect(result.current.loadMoreExaminationsError).toBe(true));

    responder = (url, page) => {
      if (url === '/patients/7/appointments') return Promise.resolve({ data: [] });
      if (url === '/derma/examinations') {
        const items = page === 2
          ? Array.from({ length: 20 }, (_, i) => exam(100 + i))
          : Array.from({ length: 20 }, (_, i) => exam(i));
        return Promise.resolve(envelope(items, 40));
      }
      return Promise.resolve(envelope([], 0));
    };

    act(() => { result.current.loadMoreExaminations(); });
    await waitFor(() => expect(result.current.loadMoreExaminationsError).toBe(false));
    await waitFor(() => expect(result.current.skinExaminations).toHaveLength(40));
  });

  it('the same contract holds for procedures', async () => {
    responder = (url, page) => {
      if (url === '/patients/7/appointments') return Promise.resolve({ data: [] });
      if (url === '/derma/procedures') {
        return page === 2
          ? Promise.reject(new Error('page-2 unavailable'))
          : Promise.resolve(envelope(Array.from({ length: 20 }, (_, i) => procedure(i)), 40));
      }
      return Promise.resolve(envelope([], 0));
    };

    const result = await loadFirstPage('7');
    act(() => { result.current.loadMoreProcedures(); });
    await waitFor(() => expect(result.current.loadMoreProceduresError).toBe(true));
  });

  it('the history tab renders a visible alert next to the retry button when a page fails', () => {
    render(
      <DermaHistoryTab
        skinExaminations={Array.from({ length: 20 }, (_, i) => exam(i) as never)}
        skinExaminationsTotal={40}
        hasMoreExaminations
        loadMoreExaminationsError
        onLoadMoreExaminations={() => undefined}
      />,
    );

    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('derma.derma_panel_patient_history_load_more_failed');
    // The retry button stays available.
    expect(screen.getByText('derma.derma_gallery_load_more')).toBeTruthy();
  });

  it('control: no alert is rendered while no page failure is recorded', () => {
    render(
      <DermaHistoryTab
        skinExaminations={Array.from({ length: 20 }, (_, i) => exam(i) as never)}
        skinExaminationsTotal={40}
        hasMoreExaminations
        onLoadMoreExaminations={() => undefined}
      />,
    );

    expect(screen.queryByRole('alert')).toBeNull();
  });
});
