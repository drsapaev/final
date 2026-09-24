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
  const t = (key: string) => key;
  return {
    useTranslation: () => ({ t }),
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
type SaveResponse = { data: { row_version: number } };

const patient = (visitId: number, patientId = 7) => ({ visit_id: visitId, patient_id: patientId });

const loadedEMR = (data: Record<string, unknown> = {}, rowVersion = 1): EmrResponse => ({
  status: 200,
  data: { data, row_version: rowVersion },
});

const TEXTAREA_NAME = 'dental.dental_dvs_anamnesis_aria';
const COMPLETE_BUTTON_NAME = 'dental.dental_dvs_aria_complete';
const getTextarea = () => screen.getByRole('textbox', { name: TEXTAREA_NAME });
const getCompleteButton = () => screen.getByRole('button', { name: COMPLETE_BUTTON_NAME });

const renderVisit = (visitId = 41, onCompleteVisit = vi.fn()) => {
  const result = render(
    <DentalVisitScreen patient={patient(visitId)} onCompleteVisit={onCompleteVisit} />,
  );
  return { ...result, onCompleteVisit };
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
    url.includes('/patient/')
      ? { status: 404, data: null }
      : loadedEMR(),
  ) as never);
  vi.mocked(apiClient.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('DentalVisitScreen EMR persistence', () => {
  it('keeps completion unavailable without a visit id and offers retry', async () => {
    const onCompleteVisit = vi.fn();
    render(<DentalVisitScreen patient={{ patient_id: 7 }} onCompleteVisit={onCompleteVisit} />);

    expect(await screen.findByText('dental.protocol_needs_visit_id')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'doctor.btn_retry' })).toBeTruthy();
    expect(getCompleteButton()).toHaveProperty('disabled', true);
    expect(apiClient.get).not.toHaveBeenCalledWith('/v2/emr/undefined', expect.anything());
    expect(onCompleteVisit).not.toHaveBeenCalled();
  });

  it('waits for the latest draft save before queue completion', async () => {
    let resolveSave: ((response: SaveResponse) => void) | undefined;
    vi.mocked(apiClient.post).mockReturnValueOnce(new Promise((resolve) => {
      resolveSave = resolve;
    }) as never);

    const { onCompleteVisit } = renderVisit();
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    fireEvent.change(textarea, { target: { value: 'latest complaint' } });
    fireEvent.click(getCompleteButton());

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1));
    expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 1,
      is_draft: true,
      data: expect.objectContaining({ anamnesis_morbi: 'latest complaint' }),
    }));
    expect(onCompleteVisit).not.toHaveBeenCalled();

    await act(async () => {
      resolveSave?.({ data: { row_version: 2 } });
    });
    await waitFor(() => expect(onCompleteVisit).toHaveBeenCalledWith(
      expect.objectContaining({ anamnesis_morbi: 'latest complaint' }),
    ));
  });

  it('keeps the visit open on a load failure and retries the EMR read', async () => {
    let visitReads = 0;
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.includes('/patient/')) return Promise.resolve({ status: 404, data: null }) as never;
      visitReads += 1;
      return visitReads === 1
        ? Promise.reject(new Error('network unavailable')) as never
        : Promise.resolve(loadedEMR({ anamnesis_morbi: 'loaded after retry' })) as never;
    });
    const { onCompleteVisit } = renderVisit();

    expect(await screen.findByText('dental2.visit_map_load_failed')).toBeTruthy();
    expect(screen.queryByRole('textbox', { name: TEXTAREA_NAME })).toBeNull();
    expect(onCompleteVisit).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'doctor.btn_retry' }));
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'loaded after retry'));
    expect(visitReads).toBe(2);
  });

  it('blocks queue completion after a 409 save conflict and exposes retry', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({ response: { status: 409 } });
    const { onCompleteVisit } = renderVisit();
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    fireEvent.change(textarea, { target: { value: 'unsaved change' } });
    fireEvent.click(getCompleteButton());

    expect(await screen.findByText('dental2.visit_protocol_save_failed')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'doctor.btn_retry' })).toBeTruthy();
    expect(onCompleteVisit).not.toHaveBeenCalled();
  });

  it('blocks queue completion after a save failure and retries the completion flow', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce(new Error('network unavailable'));
    const { onCompleteVisit } = renderVisit();
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    fireEvent.change(textarea, { target: { value: 'unsaved change' } });
    fireEvent.click(getCompleteButton());

    expect(await screen.findByText('dental2.visit_protocol_save_failed')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'doctor.btn_retry' })).toBeTruthy();
    expect(onCompleteVisit).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'doctor.btn_retry' }));
    await waitFor(() => expect(onCompleteVisit).toHaveBeenCalledWith(
      expect.objectContaining({ anamnesis_morbi: 'unsaved change' }),
    ));
    expect(apiClient.post).toHaveBeenCalledTimes(2);
  });

  it('uses the row_version returned by each sequential autosave', async () => {
    let resolveFirst: ((response: SaveResponse) => void) | undefined;
    let resolveSecond: ((response: SaveResponse) => void) | undefined;
    vi.mocked(apiClient.post)
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve; }) as never)
      .mockReturnValueOnce(new Promise((resolve) => { resolveSecond = resolve; }) as never);
    renderVisit();
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });

    fireEvent.change(textarea, { target: { value: 'first edit' } });
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1), { timeout: 2500 });

    fireEvent.change(textarea, { target: { value: 'second edit' } });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1600)); });
    expect(apiClient.post).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFirst?.({ data: { row_version: 2 } });
      await Promise.resolve();
    });
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(2));
    expect(apiClient.post).toHaveBeenLastCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 2,
      data: expect.objectContaining({ anamnesis_morbi: 'second edit' }),
    }));
    await act(async () => { resolveSecond?.({ data: { row_version: 3 } }); });
  }, 10000);

  it('does not carry a previous patient draft across a patient switch', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.includes('/patient/')) return Promise.resolve({ status: 404, data: null }) as never;
      return Promise.resolve(url.endsWith('/41')
        ? loadedEMR({ anamnesis_morbi: 'patient A draft' }, 1)
        : loadedEMR({ anamnesis_morbi: 'patient B draft' }, 5)) as never;
    });
    const onCompleteVisit = vi.fn();
    const view = render(
      <DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={onCompleteVisit} />,
    );
    const textarea = await screen.findByRole('textbox', { name: TEXTAREA_NAME });
    await waitFor(() => expect(textarea).toHaveProperty('value', 'patient A draft'));
    fireEvent.change(textarea, { target: { value: 'unsaved patient A edit' } });

    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={onCompleteVisit} />);
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'patient B draft'));
    expect(apiClient.post).not.toHaveBeenCalled();

    fireEvent.click(getCompleteButton());
    await waitFor(() => expect(onCompleteVisit).toHaveBeenCalledWith(
      expect.objectContaining({ anamnesis_morbi: 'patient B draft' }),
    ));
    expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/42', expect.objectContaining({
      row_version: 5,
      data: expect.objectContaining({ anamnesis_morbi: 'patient B draft' }),
    }));
  });
});
