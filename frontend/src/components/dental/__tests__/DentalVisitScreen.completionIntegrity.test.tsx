/**
 * Audit 3892 round 3 — fail-first regressions for the dental visit screen
 * completion-integrity cluster:
 *
 *  - DENTVISIT-FE-001: a signed EMR must render read-only with a visible
 *    signed badge; draft records stay editable (positive control).
 *  - DENTVISIT-FE-002: a failed queue-completion callback (rejected promise
 *    or an explicit `false` ack) surfaces a persistent, visible error with a
 *    completion-only retry that never re-POSTs the already-saved EMR draft.
 *  - DENTVISIT-FE-004: retrying a 409 conflict revalidates the canonical
 *    server version and offers an explicit server-vs-local resolution path
 *    instead of blindly re-submitting the stale row_version.
 *  - DENTHIST-FE-001: the visit-history widget renders the summary DTO's
 *    `diagnosis_main` field, not the absent `diagnosis` key.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
vi.mock('../TeethChart', () => ({ default: () => null }));
vi.mock('../ToothModal', () => ({ default: () => null }));
vi.mock('../../ai/AIAssistant', () => ({ default: () => null }));

type EmrResponse = { status: number; data: Record<string, unknown> };

const patient = (visitId: number, patientId = 7) => ({ visit_id: visitId, patient_id: patientId });

const loadedEMR = (
  data: Record<string, unknown> = {},
  rowVersion = 1,
  emrStatus = 'draft',
): EmrResponse => ({
  status: 200,
  data: { data, row_version: rowVersion, status: emrStatus },
});

const TEXTAREA_NAME = 'dental.dental_dvs_anamnesis_aria';
const COMPLETE_BUTTON_NAME = 'dental.dental_dvs_aria_complete';
const RETRY_BUTTON_NAME = 'doctor.btn_retry';
const getTextarea = () => screen.getByRole('textbox', { name: TEXTAREA_NAME });
const getCompleteButton = () => screen.getByRole('button', { name: COMPLETE_BUTTON_NAME });
const getRetryButton = () => screen.getByRole('button', { name: RETRY_BUTTON_NAME });

const renderVisit = (visitId = 41, onCompleteVisit = vi.fn()) => {
  const result = render(
    <DentalVisitScreen patient={patient(visitId)} onCompleteVisit={onCompleteVisit} />,
  );
  return { ...result, onCompleteVisit };
};

const patientHistory = (url: string): boolean => url.includes('/patient/');

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
    patientHistory(url)
      ? { status: 404, data: null }
      : loadedEMR(),
  ) as never);
  vi.mocked(apiClient.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('DentalVisitScreen completion integrity (audit 3892 round 3)', () => {
  it('DENTVISIT-FE-001: a signed EMR renders read-only with a visible signed state and no autosave', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      patientHistory(url)
        ? { status: 404, data: null }
        : loadedEMR({ anamnesis_morbi: 'signed anamnesis' }, 3, 'signed'),
    ) as never);
    renderVisit();

    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    expect(textarea).toHaveProperty('disabled', true);
    expect(screen.getByText('dental2.visit_emr_signed_readonly')).toBeTruthy();
    expect(screen.getByText('dental2.visit_emr_status_signed')).toBeTruthy();
    expect(getCompleteButton()).toHaveProperty('disabled', true);
    // No clinical mutation is possible, so no autosave may ever be dispatched.
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('DENTVISIT-FE-001 (control): a draft EMR keeps the clinical editors enabled', async () => {
    renderVisit();
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    expect(textarea).toHaveProperty('disabled', false);
    expect(screen.queryByText('dental2.visit_emr_signed_readonly')).toBeNull();
  });

  it('DENTVISIT-FE-002: an explicitly failed completion callback surfaces a visible error with a completion-only retry', async () => {
    const onCompleteVisit = vi.fn(async () => false);
    renderVisit(41, onCompleteVisit);

    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    fireEvent.change(textarea, { target: { value: 'completion failure case' } });
    fireEvent.click(getCompleteButton());

    await waitFor(() => expect(onCompleteVisit).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('dental2.visit_completion_failed')).toBeTruthy();
    // The EMR draft was persisted exactly once before the callback failed.
    expect(apiClient.post).toHaveBeenCalledTimes(1);

    // The retry re-runs ONLY the queue completion — never a duplicate EMR POST.
    onCompleteVisit.mockResolvedValue(true);
    fireEvent.click(getRetryButton());
    await waitFor(() => expect(onCompleteVisit).toHaveBeenCalledTimes(2));
    expect(apiClient.post).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByText('dental2.visit_completion_failed')).toBeNull());
  });

  it('DENTVISIT-FE-002 (throw): a rejecting completion callback surfaces the same failure state', async () => {
    const onCompleteVisit = vi.fn(async () => {
      throw new Error('queue completion network failure');
    });
    renderVisit(41, onCompleteVisit);

    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    fireEvent.change(textarea, { target: { value: 'rejecting callback case' } });
    fireEvent.click(getCompleteButton());

    expect(await screen.findByText('dental2.visit_completion_failed')).toBeTruthy();
    expect(apiClient.post).toHaveBeenCalledTimes(1);
    expect(onCompleteVisit).toHaveBeenCalledTimes(1);
  });

  it('DENTVISIT-FE-004: retrying a 409 revalidates the server version and resolves the conflict explicitly (local wins)', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      patientHistory(url)
        ? { status: 404, data: null }
        : { status: 200, data: { data: { anamnesis_morbi: 'server version' }, row_version: 4 } },
    ) as never);
    vi.mocked(apiClient.post)
      .mockRejectedValueOnce({ response: { status: 409 } })
      .mockResolvedValue({ data: { row_version: 5 } } as never);

    const { onCompleteVisit } = renderVisit();
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    fireEvent.change(textarea, { target: { value: 'local conflicting edit' } });
    fireEvent.click(getCompleteButton());

    // A 409 surfaces the conflict explanation (not the generic save error).
    expect(await screen.findByText('dental2.visit_conflict_description')).toBeTruthy();

    // Retry must NOT blindly re-POST the stale row_version — it revalidates.
    fireEvent.click(getRetryButton());
    expect(await screen.findByText('dental2.visit_conflict_title')).toBeTruthy();
    expect(screen.getByText('server version')).toBeTruthy();
    // The local draft stays visible (both in the editor and the review).
    expect(screen.getAllByText('local conflicting edit').length).toBeGreaterThan(1);
    expect(apiClient.post).toHaveBeenCalledTimes(1);

    // Explicitly keeping the local version submits with the SERVER's row_version.
    fireEvent.click(screen.getByRole('button', { name: 'dental2.visit_conflict_keep_local' }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(2));
    expect(apiClient.post).toHaveBeenLastCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 4,
      data: expect.objectContaining({ anamnesis_morbi: 'local conflicting edit' }),
    }));
    await waitFor(() => expect(screen.queryByText('dental2.visit_conflict_title')).toBeNull());
    // The queue completion was never faked through the failed attempt.
    expect(onCompleteVisit).not.toHaveBeenCalled();
  });

  it('DENTVISIT-FE-004 (server wins): loading the canonical server version replaces the draft and adopts its row_version', async () => {
    let reads = 0;
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (patientHistory(url)) return Promise.resolve({ status: 404, data: null }) as never;
      reads += 1;
      return Promise.resolve(reads <= 1
        ? { status: 200, data: { data: { anamnesis_morbi: 'stale local base' }, row_version: 1 } }
        : { status: 200, data: { data: { anamnesis_morbi: 'server version' }, row_version: 4 } }) as never;
    });
    vi.mocked(apiClient.post)
      .mockRejectedValueOnce({ response: { status: 409 } })
      .mockResolvedValue({ data: { row_version: 5 } } as never);

    renderVisit();
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    fireEvent.change(textarea, { target: { value: 'doomed local edit' } });
    fireEvent.click(getCompleteButton());

    expect(await screen.findByText('dental2.visit_conflict_description')).toBeTruthy();
    fireEvent.click(getRetryButton());
    expect(await screen.findByText('dental2.visit_conflict_title')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'dental2.visit_conflict_use_server' }));
    await waitFor(() => expect(screen.queryByText('dental2.visit_conflict_title')).toBeNull());
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'server version'));

    // The next autosave continues from the server-adopted row_version.
    fireEvent.change(getTextarea(), { target: { value: 'edit after resolution' } });
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(2), { timeout: 2500 });
    expect(apiClient.post).toHaveBeenLastCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 4,
      data: expect.objectContaining({ anamnesis_morbi: 'edit after resolution' }),
    }));
  });

  it('DENTHIST-FE-001: history rows render the summary DTO diagnosis_main', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      patientHistory(url)
        ? {
            status: 200,
            data: [{
              visit_id: 40,
              diagnosis_main: 'chronic apical periodontitis',
              icd10_code: 'K05.3',
              created_at: '2026-11-01T09:30:00Z',
              status: 'signed',
            }],
          }
        : loadedEMR(),
    ) as never);
    renderVisit();

    expect(await screen.findByText('chronic apical periodontitis')).toBeTruthy();
    expect(screen.getByText(/K05\.3/)).toBeTruthy();
  });
});
