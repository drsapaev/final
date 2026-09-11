/**
 * RQ-19 — registrar worklist tabpanel wiring.
 *
 * The registrar worklist region (WorklistView) is the ARIA tabpanel
 * controlled by the department Tabs strip. The tabs publish their button
 * ids via the shared tabButtonIdFor contract (percent-encoded keys —
 * backend queue-profile keys may contain whitespace); the panel's
 * aria-labelledby MUST reference the SAME id.
 *
 * Before RQ-19 the panel pointed at `${activeTab}-tab`, an id no button
 * carried — a dangling IDREF that left the tabpanel unlabelled for screen
 * readers (and, for whitespace-bearing profile keys, an INVALID IDREF).
 * These tests pin the resolved wiring (plan §RQ-19, S-16).
 */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../../api/client', () => ({
  api: {
    get: vi.fn().mockRejectedValue(new Error('offline — fallback tabs expected')),
  },
}));

vi.mock('../../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('../../../../components/tables/EnhancedAppointmentsTable', () => ({
  default: () => <div data-testid="appointments-stub" />,
}));

vi.mock('../../../../components/ui', () => ({
  AnimatedLoader: { TableSkeleton: () => <div /> },
}));

vi.mock('../../../../components/ui/macos', () => ({
  Button: (props: Record<string, unknown>) => <button {...props} />,
  Badge: (props: Record<string, unknown>) => <span {...props} />,
}));

import WorklistView from '../WorklistView';
import Tabs, { tabButtonIdFor } from '../../../../components/navigation/Tabs';

afterEach(() => cleanup());

const baseProps = {
  activeTab: 'cardiology' as string | null,
  currentWorklistLabel: 'Синтетическая кардиология',
  statusFilterLabel: null,
  showCalendar: false,
  historyDate: '2026-09-11',
  language: 'ru-RU',
  legacyLanguage: 'ru',
  isMobile: false,
  services: {},
  filteredAppointments: [] as Record<string, unknown>[],
  appointmentsLoading: false,
  dataSource: 'api',
  paginationInfo: { total: 0, hasMore: false, loadingMore: false },
  onActionClick: vi.fn(),
  loadMoreAppointments: vi.fn(),
  onNewAppointment: vi.fn(),
  onEmptyStateCta: vi.fn(),
  tI18n: (key: string) => key,
};

describe('RQ-19 — worklist tabpanel wiring', () => {
  it('panel is the main-content tabpanel; aria-labelledby matches the shared tab-id contract', () => {
    render(<WorklistView {...baseProps} activeTab="cardiology" />);

    const panel = screen.getByRole('tabpanel');
    expect(panel).toHaveAttribute('id', 'main-content');
    expect(panel.getAttribute('aria-labelledby')).toBe(tabButtonIdFor('cardiology'));
    // Clean keys keep the pre-existing `${key}-tab` format.
    expect(panel.getAttribute('aria-labelledby')).toBe('cardiology-tab');
  });

  it('whitespace-bearing tab keys: the labelledby reference stays a valid (whitespace-free) IDREF', () => {
    render(<WorklistView {...baseProps} activeTab="general medicine" />);

    const panel = screen.getByRole('tabpanel');
    const labelledby = panel.getAttribute('aria-labelledby');
    expect(labelledby).toBe(tabButtonIdFor('general medicine'));
    // Defect guard: before RQ-19 this was 'general medicine-tab' — an
    // INVALID IDREF (IDREF values must not contain whitespace).
    expect(labelledby).not.toMatch(/\s/);
  });

  it('Tabs + WorklistView agree: the panel labelledby resolves to the actual selected tab button', async () => {
    render(
      <>
        <Tabs activeTab="ecg" />
        <WorklistView {...baseProps} activeTab="ecg" />
      </>,
    );

    // Fallback set mounts after the mocked api rejection (6 departments).
    await waitFor(() => {
      expect(document.querySelectorAll('.tab-button.department').length).toBe(6);
    });

    const panel = screen.getByRole('tabpanel');
    const labelledby = panel.getAttribute('aria-labelledby') as string;
    const owner = document.getElementById(labelledby);

    // THE RQ-19 assertion: before the fix no element carried this id —
    // the dangling reference left the panel unlabelled.
    expect(owner).not.toBeNull();
    expect(owner).toHaveAttribute('role', 'tab');
    expect(owner).toHaveAttribute('data-tab', 'ecg');
    expect(owner).toHaveAttribute('aria-selected', 'true');
  });

  it('no selection (all-departments view): the panel renders no dangling aria-labelledby', () => {
    render(<WorklistView {...baseProps} activeTab={null} />);

    const panel = screen.getByRole('tabpanel');
    expect(panel.getAttribute('aria-labelledby')).toBeNull();
  });
});

// RQ-20.b (child slice): the active status filter is visible as a badge but
// had NO explicit reset control on the worklist itself (only the Welcome
// quick cards or a manual URL edit cleared it — plan §RQ-20 "действующие
// фильтры видны и сбрасываются явно"). The badge tail hosts a keyboard-
// accessible clear button wired by the panel to the URL-state owner.
describe('RQ-20.b — worklist status filter explicit reset', () => {
  const withFilterProps = {
    ...baseProps,
    statusFilterLabel: 'Ожидает оплаты' as string | null,
  };

  it('active status filter badge exposes an explicit clear control that fires the callback', () => {
    const onClearStatusFilter = vi.fn();
    render(<WorklistView {...withFilterProps} onClearStatusFilter={onClearStatusFilter} />);

    const clearButton = screen.getByRole('button', { name: /common\.reset/ });
    expect(clearButton).toHaveAttribute('aria-label', 'common.reset: Ожидает оплаты');
    clearButton.click();
    expect(onClearStatusFilter).toHaveBeenCalledTimes(1);
  });

  it('no status filter → no clear control', () => {
    render(<WorklistView {...baseProps} statusFilterLabel={null} onClearStatusFilter={vi.fn()} />);

    expect(screen.queryByRole('button', { name: /common\.reset/ })).toBeNull();
  });

  it('no callback provided → no clear control (optional prop compat)', () => {
    render(<WorklistView {...withFilterProps} />);

    expect(screen.queryByRole('button', { name: /common\.reset/ })).toBeNull();
  });
});

// RQ-22 (child slice, F-18): a failed refresh must not silently become a
// "successfully empty" answer. Two display contracts:
// 1) kept rows + stale flag → explicit staleness banner with a retry;
// 2) primary failure (nothing loaded) → error state, NOT the "no matches"
//    empty state that masked the failure before.
describe('RQ-22 — worklist failed-refresh display (S-19)', () => {
  const staleProps = {
    ...baseProps,
    filteredAppointments: [
      { id: 'synthetic-1', patient_fio: 'SYNTHETIC-DEMO' },
    ] as Record<string, unknown>[],
    dataSource: 'api',
    stale: true,
    onRetry: vi.fn(),
  };

  it('stale rows stay visible under an explicit staleness banner with a retry control', () => {
    render(<WorklistView {...staleProps} />);

    // Rows are still rendered (table stub), NOT wiped into an empty state.
    expect(screen.getByTestId('appointments-stub')).toBeInTheDocument();
    // Banner is explicit and retry fires the callback.
    const retry = screen.getByRole('button', { name: /ds_retry/ });
    retry.click();
    expect(staleProps.onRetry).toHaveBeenCalledTimes(1);
  });

  it('no stale flag → no staleness banner (fresh data keeps the clean look)', () => {
    render(<WorklistView {...staleProps} stale={false} />);

    expect(screen.queryByRole('button', { name: /ds_retry/ })).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('loading overrides the banner (a retry is already in flight)', () => {
    render(<WorklistView {...staleProps} appointmentsLoading />);

    expect(screen.queryByRole('status')).toBeNull();
  });

  it('primary failure: error state with retry instead of the misleading "no matches" empty state', () => {
    render(
      <WorklistView
        {...baseProps}
        filteredAppointments={[]}
        dataSource="error"
        onRetry={vi.fn()}
      />,
    );

    // Before RQ-22 this branch rendered the generic filtered-empty state.
    expect(screen.getByText(/ds_error_message/)).toBeInTheDocument();
    expect(screen.queryByText(/rp_empty_filter_desc/)).toBeNull();
    expect(screen.queryByText(/rp_empty_queue_title/)).toBeNull();
    const retry = screen.getByRole('button', { name: /ds_retry/ });
    retry.click();
  });

  it('empty API answer (dataSource=api, no rows) still shows the genuine empty-queue state', () => {
    render(
      <WorklistView
        {...baseProps}
        filteredAppointments={[]}
        dataSource="api"
        onRetry={vi.fn()}
      />,
    );

    // QW-04 empty state must remain for a REAL empty answer — not the error.
    expect(screen.getByText(/rp_empty_queue_title/)).toBeInTheDocument();
    expect(screen.queryByText(/ds_error_message/)).toBeNull();
  });
});
