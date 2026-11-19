import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

const post = vi.hoisted(() => vi.fn());
const logError = vi.hoisted(() => vi.fn());
vi.mock('../../../api/client', () => ({
  api: { post, get: vi.fn(), delete: vi.fn() },
  apiClient: { post, get: vi.fn(), delete: vi.fn() },
  setSessionInvalidationListener: vi.fn(),
}));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../../utils/logger', () => ({ default: { error: logError, info: vi.fn(), warn: vi.fn() } }));
vi.mock('../../../services/notify', () => ({ default: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));
import ECGViewer from '../ECGViewer';
import { ThemeProvider } from '../../../contexts/ThemeContext';

async function loadFileAndAnalyze(envelope: unknown) {
  const file = new File(['synthetic'], 'synthetic.pdf', { type: 'application/pdf' });
  post.mockImplementation(async (url: string) => {
    if (url === '/files/upload') return { status: 201, data: {
      id: 501, original_filename: file.name, mime_type: file.type, file_size: file.size,
      created_at: '2026-11-01T00:00:00Z',
    } };
    if (url === '/ai/ecg-interpret') return { data: envelope };
    throw new Error(`unexpected endpoint ${url}`);
  });
  render(<ThemeProvider><ECGViewer patientId={7} visitId={11} /></ThemeProvider>);
  const dropzone = document.querySelector('[role="presentation"]') ?? document.body.firstElementChild!;
  await act(async () => { fireEvent.drop(dropzone, { dataTransfer: { files: [file], types: ['Files'] } }); });
  await screen.findByText('synthetic.pdf');
  fireEvent.click(screen.getByRole('button', { name: 'cardio.cardio_ecg_ai_analysis' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('/ai/ecg-interpret', expect.anything()));
}

describe('ECG medical AI safety', () => {
  beforeEach(() => { post.mockReset(); logError.mockReset(); });
  it.each([undefined, null, {}, { requires_doctor_confirmation: false },
    { requires_doctor_confirmation: 1 }, { requires_doctor_confirmation: 'true' }])(
    'never displays interpretation when nested metadata is invalid: %j', async (ai_safety_meta) => {
      await loadFileAndAnalyze({ interpretation: 'SYNTHETIC INTERPRETATION', ai_safety_meta });
      await waitFor(() => expect(logError).toHaveBeenCalled());
      expect(screen.queryByText('SYNTHETIC INTERPRETATION')).toBeNull();
      expect(screen.queryByText('cardio.cardio_ecg_ai_interpretation_title')).toBeNull();
      expect(screen.getByText('synthetic.pdf')).toBeTruthy();
    },
  );
  it('displays a verified interpretation', async () => {
    await loadFileAndAnalyze({ interpretation: 'SYNTHETIC INTERPRETATION', ai_safety_meta: { requires_doctor_confirmation: true } });
    expect(await screen.findByText('SYNTHETIC INTERPRETATION')).toBeTruthy();
  });
});
