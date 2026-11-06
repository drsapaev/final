import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api, apiClient } from '../../../api/client';
import DentalVisitScreen from '../DentalVisitScreen';
import { TOOTH_PROCEDURES } from '../dentalConstants';

/**
 * DENTMODAL-FE-001 / DENTMODAL-FE-002 (audit 2026-11-06, PR 3892):
 * the tooth modal must be a controlled editor inside the visit screen —
 * DentalVisitScreen is the sole EMR writer — and an open tooth modal must
 * not survive a visit/patient identity switch.
 *
 * The real ToothModal is rendered here (only TeethChart is mocked) so the
 * modal's own save path is exercised.
 */
vi.mock('../../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
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
vi.mock('../TeethChart', () => ({
  default: ({ onToothClick }: { onToothClick?: (n: number, d: Record<string, unknown> | null) => void }) => (
    <button
      type="button"
      onClick={() => onToothClick?.(11, null)}
    >
      mock-tooth-11
    </button>
  ),
}));
vi.mock('../../ai/AIAssistant', () => ({ default: () => null }));

const patient = (visitId: number, patientId = 7) => ({ visit_id: visitId, patient_id: patientId });

const loadedEMR = (data: Record<string, unknown> = {}, rowVersion = 1) => ({
  status: 200,
  data: { data, row_version: rowVersion },
});

const COMPLETE_BUTTON_NAME = 'dental.dental_dvs_aria_complete';

const openToothModal = async () => {
  fireEvent.click(await screen.findByText('mock-tooth-11'));
  await screen.findByRole('button', { name: 'dental.dental_tm_save' });
};

const fillProcedureInModal = () => {
  const firstProcedureName = Object.values(TOOTH_PROCEDURES)[0].name;
  fireEvent.click(screen.getByRole('button', { name: new RegExp(firstProcedureName) }));
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
    url.includes('/patient/')
      ? { status: 404, data: null }
      : loadedEMR(),
  ) as never);
  vi.mocked(apiClient.post).mockResolvedValue({ data: { row_version: 2 } } as never);
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { data: {}, row_version: 1 } } as never);
  vi.mocked(api.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('DentalVisitScreen tooth modal — single EMR writer (DENTMODAL-FE-001)', () => {
  it('persists a tooth save through the parent writer only, without a modal-owned GET/POST', async () => {
    render(
      <DentalVisitScreen patient={patient(41)} onCompleteVisit={vi.fn()} />,
    );
    await openToothModal();
    fillProcedureInModal();
    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tm_save' }));

    // The modal must not perform its own read/write pair.
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledTimes(1);
    });
    expect(api.post).not.toHaveBeenCalled();
    expect(api.get).not.toHaveBeenCalledWith('/v2/emr/41', expect.anything());

    // The single authoritative write comes from the parent writer and carries
    // the parent's row_version plus the tooth change.
    expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 1,
      is_draft: true,
      data: expect.objectContaining({
        specialty_data: expect.objectContaining({
          tooth_status: expect.objectContaining({
            11: expect.objectContaining({ toothNumber: 11 }),
          }),
        }),
      }),
    }));
  });

  it('reports a tooth save failure through the parent save-error path instead of a silent modal success', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({ response: { status: 409 } });
    render(
      <DentalVisitScreen patient={patient(41)} onCompleteVisit={vi.fn()} />,
    );
    await openToothModal();
    fillProcedureInModal();
    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tm_save' }));

    expect(await screen.findByText('dental2.visit_protocol_save_failed')).toBeTruthy();
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe('DentalVisitScreen tooth modal — visit switch isolation (DENTMODAL-FE-002)', () => {
  it('closes the open tooth modal when the visit identity switches and keeps patient A tooth data out of visit B', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      url.includes('/patient/')
        ? { status: 404, data: null }
        : Promise.resolve(url.endsWith('/41')
          ? loadedEMR({ anamnesis_morbi: 'patient A draft' }, 1)
          : loadedEMR({ anamnesis_morbi: 'patient B draft' }, 5)),
    ) as never);
    const onCompleteVisit = vi.fn();
    const view = render(
      <DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={onCompleteVisit} />,
    );
    await openToothModal();
    fillProcedureInModal();

    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={onCompleteVisit} />);
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'dental.dental_dvs_anamnesis_aria' })).toHaveProperty('value', 'patient B draft'));

    // The modal (and its Save control) must be gone after the switch.
    expect(screen.queryByRole('button', { name: 'dental.dental_tm_save' })).toBeNull();

    // Completing visit B must not carry patient A's tooth form.
    fireEvent.click(screen.getByRole('button', { name: COMPLETE_BUTTON_NAME }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/42', expect.objectContaining({
      row_version: 5,
      data: expect.objectContaining({
        specialty_data: expect.objectContaining({
          tooth_status: {},
        }),
      }),
    })));
    expect(onCompleteVisit).toHaveBeenCalledWith(
      expect.objectContaining({ anamnesis_morbi: 'patient B draft' }),
    );
  });
});
