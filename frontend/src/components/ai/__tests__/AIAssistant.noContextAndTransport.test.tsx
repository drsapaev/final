/**
 * CARDAI-FE-001 / CARDAI-FE-002 (audit 3886, ledger group "cardiology AI
 * tab", round 28) — fail-first regressions for the shared AIAssistant.
 *
 * CARDAI-FE-001 (P1/P2): a specialty-only mount (`<AIAssistant
 * specialty="cardiology" />`, used by the cardiology AiTab, DoctorPanel
 * and DermatologistPanelUnified) passes no `data`. The assistant computed
 * an `effectiveData` fallback that no analysis branch ever used:
 * `analyzeData` returned early on `if (!data)`, and the only analysis
 * action was `disabled={loading || !data}` — the visible screen offered
 * provider controls and a prompt to click refresh, but no request could
 * ever start (false affordance).
 *
 * CARDAI-FE-002 (P2): the non-MCP HTTP paths called
 * `apiClient.post('/api/v1/ai/...')` although the shared axios instance's
 * baseURL already ends with `/api/v1`, producing
 * `.../api/v1/api/v1/ai/...` (404 / wrong endpoint) for complaint, ICD-10,
 * lab and ECG transports.
 *
 * Red-first: on the pre-fix source the no-context assertions fail
 * (provider chips + disabled refresh + misleading prompt are rendered)
 * and the transport assertions fail (duplicated `/api/v1/` prefix).
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function SnackbarProviderMock({ children }: { children?: React.ReactNode }) {
  return <div>{children}</div>;
}

vi.mock('notistack', () => ({
  SnackbarProvider: SnackbarProviderMock,
  useSnackbar: () => ({ enqueueSnackbar: vi.fn() })
}));

vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light' })
}));

vi.mock('../../../services/notify', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() }
}));

vi.mock('../../../hooks/useMcpClient', () => ({
  useMcpClient: () => ({
    analyzeComplaint: vi.fn(),
    suggestICD10: vi.fn(),
    interpretLabResults: vi.fn(),
    analyzeSkinLesion: vi.fn(),
    analyzeImage: vi.fn()
  })
}));

const apiMocks = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock('../../../api/client', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    apiClient: { post: apiMocks.post, get: vi.fn() },
  };
});

import AIAssistant from '../AIAssistant';

describe('CARDAI-FE-001: a specialty-only mount is honestly inert, not a false affordance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows an explicit no-clinical-context state and no provider/refresh controls', () => {
    render(<AIAssistant specialty="cardiology" />);

    // No provider chips: with no clinical context there is nothing to
    // configure a provider FOR — offering them is a false affordance.
    expect(screen.queryByText('DEEPSEEK')).not.toBeInTheDocument();
    expect(screen.queryByText('GEMINI')).not.toBeInTheDocument();
    expect(screen.queryByText('OPENAI')).not.toBeInTheDocument();
    expect(screen.queryByText('DEFAULT')).not.toBeInTheDocument();

    // No refresh action at all (pre-fix: a permanently disabled refresh
    // button next to a prompt telling the doctor to click it).
    expect(screen.queryByRole('button', { name: /обновить/i })).not.toBeInTheDocument();

    // The explicit no-context state explains WHY analysis is unavailable.
    expect(screen.getByText(/AI-анализ недоступен/i)).toBeInTheDocument();

    // The old "click refresh" prompt must not appear without data.
    expect(screen.queryByText(/Нажмите Обновить для запуска/i)).not.toBeInTheDocument();
  });

  it('keeps the actionable analysis UI when the parent supplies clinical data (control)', () => {
    render(
      <AIAssistant
        analysisType="icd10"
        data={{ symptoms: ['боль в груди'], diagnosis: 'I20.0', specialty: 'cardiology' }}
      />
    );

    expect(screen.getByText('DEEPSEEK')).toBeInTheDocument();
    const refresh = screen.getByRole('button', { name: /обновить/i });
    expect(refresh).toBeEnabled();
    expect(screen.getByText(/Нажмите Обновить для запуска/i)).toBeInTheDocument();
    expect(screen.queryByText(/AI-анализ недоступен/i)).not.toBeInTheDocument();
  });
});

describe('CARDAI-FE-002: non-MCP AI transport uses the versioned client without a duplicated /api/v1 prefix', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.post.mockResolvedValue({ data: [] });
  });

  const clickRefresh = () => {
    fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
  };

  it('icd10 (useMCP=false) posts once to /ai/icd-suggest with no duplicated prefix', async () => {
    render(
      <AIAssistant
        analysisType="icd10"
        useMCP={false}
        data={{ symptoms: ['боль в груди'], diagnosis: 'I20.0', specialty: 'cardiology' }}
      />
    );
    clickRefresh();
    await waitFor(() => expect(apiMocks.post).toHaveBeenCalledTimes(1));
    expect(apiMocks.post).toHaveBeenCalledWith(
      '/ai/icd-suggest',
      expect.objectContaining({ provider: 'deepseek' })
    );
    expect(apiMocks.post.mock.calls[0][0]).not.toMatch(/api\/v1/);
  });

  it('complaint (useMCP=false) posts once to /ai/complaint-to-plan with no duplicated prefix', async () => {
    render(
      <AIAssistant
        analysisType="complaint"
        useMCP={false}
        data={{ complaint: 'головная боль', patient_age: 30, patient_gender: 'female' }}
      />
    );
    clickRefresh();
    await waitFor(() => expect(apiMocks.post).toHaveBeenCalledTimes(1));
    expect(apiMocks.post).toHaveBeenCalledWith(
      '/ai/complaint-to-plan',
      expect.objectContaining({ provider: 'deepseek', use_mcp: false })
    );
    expect(apiMocks.post.mock.calls[0][0]).not.toMatch(/api\/v1/);
  });

  it('lab (useMCP=false) posts once to /ai/lab-interpret with no duplicated prefix', async () => {
    render(
      <AIAssistant
        analysisType="lab"
        useMCP={false}
        data={{ results: [{ name: 'гемоглобин', value: '130', unit: 'г/л' }], patient_age: 30, patient_gender: 'male' }}
      />
    );
    clickRefresh();
    await waitFor(() => expect(apiMocks.post).toHaveBeenCalledTimes(1));
    expect(apiMocks.post).toHaveBeenCalledWith(
      '/ai/lab-interpret',
      expect.objectContaining({ provider: 'deepseek' })
    );
    expect(apiMocks.post.mock.calls[0][0]).not.toMatch(/api\/v1/);
  });

  it('ecg (always non-MCP transport) posts once to /ai/ecg-interpret with no duplicated prefix', async () => {
    render(
      <AIAssistant
        analysisType="ecg"
        useMCP={false}
        data={{ rhythm: 'синусовый', rate: 72, conduction: 'норма', axis: 'норма', abnormalities: [] }}
      />
    );
    clickRefresh();
    await waitFor(() => expect(apiMocks.post).toHaveBeenCalledTimes(1));
    expect(apiMocks.post).toHaveBeenCalledWith(
      '/ai/ecg-interpret',
      expect.objectContaining({ provider: 'deepseek' })
    );
    expect(apiMocks.post.mock.calls[0][0]).not.toMatch(/api\/v1/);
  });
});
