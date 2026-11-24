/**
 * DERMAPAT-FE-002 (owner registry #4063; review-group audit comment
 * 6693119519) — dermatologist search drops valid matches beyond the
 * server's first result page.
 *
 * `searchPatients(query)` sends only `{q}` — no `skip`/`limit` — so the
 * backend default of 100 results silently truncates the search set, and
 * `DermaPatientsTab` renders that single response as if it were
 * complete, with no pagination and no truncation indication. A broad
 * 2-character fragment matching 120 accessible patients makes patients
 * beyond the first page unselectable from that query.
 *
 * Contract after the repair (per the red-first: search pagination):
 * - the first page requests the explicit server page size (100);
 * - a visible "Load more" button requests the NEXT page with
 *   `skip = loaded count` and merges it without duplicates, so patient
 *   120 becomes selectable from the same query;
 * - the button disappears once a short (last) page proves the list is
 *   exhausted; a rejected page load shows a visible alert;
 * - callers predating the fix (Search, AppointmentWizardV2) keep the
 *   single-argument call signature (options are optional).
 *
 * Red-first: on the pre-fix source the load-more button never appears
 * (the truncation is invisible) and patient 120 is unreachable — both
 * RED; the short-result control stays green on main.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

const apiMock = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../../api/client', () => ({ api: { get: apiMock.get } }));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock('../../ui/macos', () => ({
  Badge: ({ children }: { children?: ReactNode }) => <span>{children}</span>,
  Button: ({ children, ...props }: { children?: ReactNode } & Record<string, unknown>) => (
    <button type="button" {...props}>{children}</button>
  ),
  Card: ({ children }: { children?: ReactNode }) => <section>{children}</section>,
  Input: ({ icon: _icon, ...props }: Record<string, unknown> & { icon?: unknown }) => (
    <input {...props} />
  ),
}));

import DermaPatientsTab from '../DermaPatientsTab';

const patientDto = (i: number) => ({
  id: i,
  last_name: 'Фамилия',
  first_name: `Пациент ${i}`,
  created_at: '2026-01-01T00:00:00Z',
});

const PAGE_SIZE = 100;

type Responder = (q: string | undefined, skip: number | undefined, limit: number | undefined) => Promise<{ data: unknown }>;
let responder: Responder = async () => ({ data: [] });

apiMock.get.mockImplementation((url: string, config?: { params?: { q?: string; skip?: number; limit?: number } }) => {
  return responder(config?.params?.q, config?.params?.skip, config?.params?.limit);
});

beforeEach(() => {
  apiMock.get.mockClear();
  responder = async () => ({ data: [] });
});

function renderTab() {
  return render(
    <DermaPatientsTab
      selectedPatient={null}
      onSelectPatient={() => undefined}
      appointments={[]}
      skinExaminations={[]}
      cosmeticProcedures={[]}
      skinExaminationsTotal={0}
      cosmeticProceduresTotal={0}
      hasMoreExaminations={false}
      hasMoreProcedures={false}
      loadingMoreExaminations={false}
      loadingMoreProcedures={false}
      onLoadMoreExaminations={() => undefined}
      onLoadMoreProcedures={() => undefined}
      historyLoading={false}
      historyReady={false}
      historyError={false}
    />,
  );
}

async function search(query = 'ab') {
  fireEvent.change(screen.getByLabelText('derma.derma_panel_patients_search_label'), {
    target: { value: query },
  });
}

describe('DERMAPAT-FE-002 — search reaches matches beyond the first result page', () => {
  it('the first page is truncated at the explicit server page size with a visible Load more', async () => {
    responder = (q, skip) => Promise.resolve({
      data: Array.from({ length: PAGE_SIZE }, (_, i) => patientDto((skip ?? 0) + i)),
    });

    renderTab();
    await search();
    await waitFor(() => expect(screen.getByText('Фамилия Пациент 0')).toBeTruthy());

    // The truncation is visible: a Load more affordance exists.
    expect(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' })).toBeTruthy();
    // Patient 120 is not on the first page — it must be reachable, not dropped.
    expect(screen.queryByText('Фамилия Пациент 119')).toBeNull();
  });

  it('Load more requests the next page with skip=loaded and reaches patient 120', async () => {
    const requests: Array<{ skip?: number; limit?: number }> = [];
    responder = (q, skip, limit) => {
      requests.push({ skip, limit });
      return Promise.resolve({
        data: Array.from({ length: PAGE_SIZE }, (_, i) => patientDto((skip ?? 0) + i)),
      });
    };

    renderTab();
    await search();
    await waitFor(() => expect(screen.getByText('Фамилия Пациент 0')).toBeTruthy());

    const loadMore = screen.getByRole('button', { name: 'derma.derma_gallery_load_more' });
    responder = (q, skip, limit) => {
      requests.push({ skip, limit });
      return Promise.resolve({
        data: Array.from({ length: 20 }, (_, i) => patientDto((skip ?? 0) + i)),
      });
    };
    fireEvent.click(loadMore);

    await waitFor(() => expect(screen.getByText('Фамилия Пациент 119')).toBeTruthy());
    // The next-page request paginates explicitly.
    expect(requests[1]).toEqual({ skip: PAGE_SIZE, limit: PAGE_SIZE });
    // 120 total rendered; the last page (20 < 100) proves exhaustion.
    expect(screen.getByText('Фамилия Пациент 99')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'derma.derma_gallery_load_more' })).toBeNull();
  });

  it('a rejected page load shows a visible alert instead of a silent re-enable', async () => {
    responder = (_q, skip) => Promise.resolve({
      data: Array.from({ length: PAGE_SIZE }, (_, i) => patientDto((skip ?? 0) + i)),
    });

    renderTab();
    await search();
    await waitFor(() => expect(screen.getByText('Фамилия Пациент 0')).toBeTruthy());

    responder = () => Promise.reject(new Error('page-2 unavailable'));
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' }));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent)
        .toContain('derma.derma_panel_patients_search_load_more_failed');
    });
    // The retry affordance stays available.
    expect(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' })).toBeTruthy();
  });

  it('control: a result set shorter than the page size shows no Load more', async () => {
    responder = () => Promise.resolve({
      data: Array.from({ length: 50 }, (_, i) => patientDto(i)),
    });

    renderTab();
    await search();
    await waitFor(() => expect(screen.getByText('Фамилия Пациент 0')).toBeTruthy());

    expect(screen.queryByRole('button', { name: 'derma.derma_gallery_load_more' })).toBeNull();
  });
});
