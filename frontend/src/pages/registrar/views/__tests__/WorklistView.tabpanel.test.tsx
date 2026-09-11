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
