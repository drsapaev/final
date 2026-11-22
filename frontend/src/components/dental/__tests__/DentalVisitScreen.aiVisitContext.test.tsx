import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../../api/client';
import DentalVisitScreen from '../DentalVisitScreen';

const assistant = vi.hoisted(() => ({ select: undefined as ((type: string, value: string) => void) | undefined }));
vi.mock('../../../api/client', () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../../../services/notify', () => ({ default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));
vi.mock('../../../utils/logger', () => ({ default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() } }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../../contexts/ThemeContext', () => ({ useTheme: () => ({}) }));
vi.mock('../TeethChart', () => ({ default: () => null }));
vi.mock('../ToothModal', () => ({ default: () => null }));
vi.mock('../../ai/AIAssistant', () => ({
  default: ({ onSuggestionSelect }: { onSuggestionSelect: (type: string, value: string) => void }) => {
    assistant.select = onSuggestionSelect;
    return <span>synthetic-assistant</span>;
  },
}));

const patient = (visitId: number, patientId: number) => ({ visit_id: visitId, patient_id: patientId });

beforeEach(() => {
  vi.clearAllMocks();
  assistant.select = undefined;
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url.includes('/patient/')) return Promise.resolve({ status: 404, data: null }) as never;
    const visitId = Number(url.split('/').pop());
    return Promise.resolve({ status: 200, data: {
      data: { anamnesis_morbi: 'SYNTHETIC SAME', icd10_code: '' },
      visit_id: visitId, patient_id: visitId === 41 ? 7 : 8, row_version: 1,
    } }) as never;
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('dental assistant visit ownership', () => {
  it('drops a delayed old-visit suggestion when the new visit has identical input', async () => {
    const view = render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'dental.dental_dvs_aria_ai_icd10' }));
    await screen.findByText('synthetic-assistant');
    const lateSelect = assistant.select;
    expect(lateSelect).toBeDefined();

    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={vi.fn()} />);
    await waitFor(() => expect(screen.queryByText('synthetic-assistant')).not.toBeInTheDocument());
    await screen.findByDisplayValue('SYNTHETIC SAME');
    act(() => lateSelect?.('icd10', 'SYNTHETIC STALE CODE'));
    expect(screen.queryByDisplayValue('SYNTHETIC STALE CODE')).not.toBeInTheDocument();
    expect(vi.mocked(apiClient.post).mock.calls.some(([url, body]) =>
      url === '/v2/emr/42' && JSON.stringify(body).includes('SYNTHETIC STALE CODE'))).toBe(false);
  });

  it('allows a suggestion for the currently loaded visit', async () => {
    render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'dental.dental_dvs_aria_ai_icd10' }));
    await screen.findByText('synthetic-assistant');
    act(() => assistant.select?.('icd10', 'SYNTHETIC CURRENT CODE'));
    expect(await screen.findByDisplayValue('SYNTHETIC CURRENT CODE')).toBeInTheDocument();
  });

  it('rejects a callback from a closed dialog when the same visit is reopened', async () => {
    render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={vi.fn()} />);
    const trigger = await screen.findByRole('button', { name: 'dental.dental_dvs_aria_ai_icd10' });
    fireEvent.click(trigger);
    await screen.findByText('synthetic-assistant');
    const oldSelect = assistant.select;
    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_dvs_close' }));
    await waitFor(() => expect(screen.queryByText('synthetic-assistant')).not.toBeInTheDocument());
    fireEvent.click(trigger);
    await screen.findByText('synthetic-assistant');
    act(() => oldSelect?.('icd10', 'SYNTHETIC EXPIRED'));
    expect(screen.queryByDisplayValue('SYNTHETIC EXPIRED')).not.toBeInTheDocument();
    act(() => assistant.select?.('icd10', 'SYNTHETIC CURRENT'));
    expect(await screen.findByDisplayValue('SYNTHETIC CURRENT')).toBeInTheDocument();
  });
});
