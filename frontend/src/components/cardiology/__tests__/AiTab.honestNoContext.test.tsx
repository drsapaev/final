/**
 * CARDAI-FE-001 (audit 3886, round 28) — the actual cardiology AI tab
 * mount, per the finding's fail-first: "mount actual AiTab with its
 * existing props; require either (a) an actionable, clinically contextual
 * ICD10 suggestion workflow … or (b) a clear no patient/clinical context
 * state explaining why analysis is disabled without presenting an
 * actionable false affordance."
 *
 * The AiTab mount passes `specialty="cardiology"` and no `data` — there
 * is no patient context in this tab, so the honest state is (b).
 * Red-first: on the pre-fix source the tab renders provider chips, a
 * permanently disabled refresh button and a prompt that suggests an
 * analysis is one click away.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

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

vi.mock('../../../api/client', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    apiClient: { post: vi.fn(), get: vi.fn() },
  };
});

import AiTab from '../AiTab';

describe('CARDAI-FE-001: the cardiology AI tab (specialty-only, no patient context)', () => {
  it('renders the explicit no-context state instead of inert analysis controls', () => {
    render(<AiTab />);

    // No provider chips and no refresh action — nothing is configurable
    // or startable without clinical context.
    expect(screen.queryByText('DEEPSEEK')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /обновить/i })).not.toBeInTheDocument();

    // The honest explanation is visible.
    expect(screen.getByText(/AI-анализ недоступен/i)).toBeInTheDocument();
    expect(screen.queryByText(/Нажмите Обновить для запуска/i)).not.toBeInTheDocument();
  });
});
