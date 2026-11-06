/**
 * Audit 3892 round 1 — fail-first regressions for DentalVisitScreen
 * patient-context isolation and EMR write integrity.
 *
 * Covers (IDs from docs/audits/2026-11-06-dental-dermatology-visit-source-review.md):
 *  - DENTMODAL-FE-002: a tooth modal opened for patient A must not write its
 *    still-open form to patient B after the selected visit changes.
 *  - DENTIDENT-FE-001: the returned EMR patient_id/visit_id must match the
 *    selected patient header before any clinical editor hydration (fail-closed
 *    identity mismatch state otherwise; number/string normalization accepted).
 *  - DENTVISIT-FE-005: switching patients before the debounce must flush the
 *    unsaved draft to the OLD visit instead of silently discarding it.
 *  - DENTMODAL-FE-001: the row_version returned by ToothModal's independent
 *    POST must propagate into the parent's rowVersionRef so the next parent
 *    save does not reuse the stale version.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import DentalVisitScreen from '../DentalVisitScreen';

vi.mock('../../../api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../../services/notify', () => ({
  default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../i18n/useTranslation', () => {
  return {
    useTranslation: () => ({ t: (key: string) => key }),
    TranslationProvider: ({ children }: { children: unknown }) => children,
  };
});
vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({}),
}));

// TeethChart stand-in: a single button that opens the tooth modal for tooth 16.
vi.mock('../TeethChart', () => ({
  default: ({ onToothClick }: { onToothClick?: (n: number, d: Record<string, unknown>) => void }) => (
    <button type="button" onClick={() => onToothClick?.(16, { status: 'filled' })}>mock-teeth-chart</button>
  ),
}));

// ToothModal stand-in: exposes the Save control that invokes onSave with the
// payload and (post-fix) the row_version returned by the modal's own POST.
vi.mock('../ToothModal', () => ({
  default: ({ onSave }: { onSave?: (data: unknown, rowVersion?: number) => void }) => (
    <button
      type="button"
      onClick={() => onSave?.({ status: 'filled', procedures: [{ id: 'p1', name: 'SYNTHETIC filling', price: 1000 }] }, 2)}
    >
      mock-tooth-save
    </button>
  ),
}));

vi.mock('../../ai/AIAssistant', () => ({ default: () => null }));

const patient = (visitId: number, patientId = 7) => ({ visit_id: visitId, patient_id: patientId });

const loadedEMR = (
  data: Record<string, unknown> = {},
  rowVersion = 1,
  identity: { patient_id?: number | string; visit_id?: number | string } = { patient_id: 7, visit_id: 41 },
) => ({
  status: 200,
  data: { data, row_version: rowVersion, patient_id: identity.patient_id, visit_id: identity.visit_id },
});

const TEXTAREA_NAME = 'dental.dental_dvs_anamnesis_aria';
const COMPLETE_BUTTON_NAME = 'dental.dental_dvs_aria_complete';

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
    url.includes('/patient/')
      ? { status: 404, data: null }
      : loadedEMR(),
  ) as never);
  vi.mocked(apiClient.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('DentalVisitScreen patient-context isolation (audit 3892 round 1)', () => {
  it('DENTMODAL-FE-002: closes the open tooth modal when the selected visit changes', async () => {
    const view = render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={vi.fn()} />);
    fireEvent.click(await screen.findByText('mock-teeth-chart'));
    expect(screen.getByText('mock-tooth-save')).toBeTruthy();

    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={vi.fn()} />);
    await waitFor(() => expect(screen.queryByText('mock-tooth-save')).toBeNull());
    // A's still-open tooth form must not be savable against B's visit.
    expect(apiClient.post).not.toHaveBeenCalledWith('/v2/emr/42', expect.anything());
  });

  it('DENTIDENT-FE-001: fails closed when the returned EMR patient_id mismatches the selected patient', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      url.includes('/patient/')
        ? { status: 404, data: null }
        : loadedEMR({}, 1, { patient_id: 42, visit_id: 77 }),
    ) as never);
    const onCompleteVisit = vi.fn();
    render(<DentalVisitScreen patient={{ visit_id: 77, patient_id: 23 }} onCompleteVisit={onCompleteVisit} />);

    expect(await screen.findByText('dental2.visit_identity_mismatch')).toBeTruthy();
    expect(screen.queryByRole('textbox', { name: TEXTAREA_NAME })).toBeNull();
    expect(apiClient.post).not.toHaveBeenCalled();
    expect(onCompleteVisit).not.toHaveBeenCalled();
  });

  it('DENTIDENT-FE-001 control: string/number patient_id normalization still loads the editor', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      url.includes('/patient/')
        ? { status: 404, data: null }
        : loadedEMR({ anamnesis_morbi: 'ok' }, 1, { patient_id: '23', visit_id: '77' }),
    ) as never);
    render(<DentalVisitScreen patient={{ visit_id: 77, patient_id: 23 }} onCompleteVisit={vi.fn()} />);

    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    await waitFor(() => expect(textarea).toHaveProperty('value', 'ok'));
    expect(screen.queryByText('dental2.visit_identity_mismatch')).toBeNull();
  });

  it('DENTVISIT-FE-005: flushes patient A\'s unsaved draft to A\'s visit before switching to B', async () => {
    const onCompleteVisit = vi.fn();
    const view = render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={onCompleteVisit} />);
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    fireEvent.change(textarea, { target: { value: 'unsaved patient A edit' } });

    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={onCompleteVisit} />);

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 1,
      is_draft: true,
      data: expect.objectContaining({ anamnesis_morbi: 'unsaved patient A edit' }),
    })));
    // The flushed write is attributed to A's visit only — B's visit is never
    // touched with A's draft.
    const postsToB = vi.mocked(apiClient.post).mock.calls.filter(([url]) => url === '/v2/emr/42');
    expect(postsToB).toHaveLength(0);
  });

  it('DENTMODAL-FE-001: the tooth modal\'s returned row_version feeds the next parent save', async () => {
    const onCompleteVisit = vi.fn();
    render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={onCompleteVisit} />);

    fireEvent.click(await screen.findByText('mock-teeth-chart'));
    fireEvent.click(screen.getByText('mock-tooth-save'));
    await waitFor(() => expect(screen.queryByText('mock-tooth-save')).toBeNull());

    // Explicit save-and-complete: must reuse the version returned by the
    // modal's independent POST (2), not the stale load-time version (1).
    fireEvent.click(screen.getByRole('button', { name: COMPLETE_BUTTON_NAME }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 2,
      is_draft: true,
      data: expect.objectContaining({
        specialty_data: expect.objectContaining({
          tooth_status: expect.objectContaining({ 16: expect.objectContaining({ status: 'filled' }) }),
        }),
      }),
    })));
  });
});
