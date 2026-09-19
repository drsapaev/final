import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext';

import PatientActivationTokenDialog from '../PatientActivationTokenDialog';

vi.mock('../../../api/patientAccess', () => ({
  issueActivationToken: vi.fn(),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'ru',
    setLanguage: vi.fn(),
    availableLanguages: [{ code: 'ru', name: 'Русский', flag: 'RU' }],
    t: (key: string, options?: Record<string, unknown>) =>
      options && Object.keys(options).length > 0
        ? `${key}:${Object.values(options).join(':')}`
        : key,
  }),
}));

import { issueActivationToken } from '../../../api/patientAccess';

const mockedIssue = vi.mocked(issueActivationToken);

const PATIENT = {
  id: 5,
  full_name: 'Иванов Тест Тестович',
  phone: '+998901234567',
};

const TOKEN_RESPONSE = {
  activation_token: 'f'.repeat(64),
  expires_in_hours: 72,
  phone_masked: '+998 *** *** 45 67',
};

function renderDialog(patient: Record<string, unknown> | null = PATIENT) {
  const onClose = vi.fn();
  render(
    <ThemeProvider>
      <PatientActivationTokenDialog isOpen onClose={onClose} patient={patient} />
    </ThemeProvider>
  );
  return { onClose };
}

describe('PatientActivationTokenDialog (Phase 0 PR-B)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedIssue.mockResolvedValue(TOKEN_RESPONSE);
  });

  it('starts at the confirm stage and issues only on explicit action', async () => {
    const { onClose } = renderDialog();

    expect(screen.getByText('patientPortal.pi_confirm_text:Иванов Тест Тестович')).toBeInTheDocument();
    expect(mockedIssue).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pi_issue' }));

    await waitFor(() => {
      expect(mockedIssue).toHaveBeenCalledWith(5);
      expect(screen.getByText(TOKEN_RESPONSE.activation_token)).toBeInTheDocument();
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  it('surfaces the already-linked 409 as a controlled error', async () => {
    mockedIssue.mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'already linked' } },
    });
    renderDialog();

    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pi_issue' }));

    expect(
      await screen.findByText('patientPortal.pi_error_already_linked')
    ).toBeInTheDocument();
    expect(screen.queryByText(TOKEN_RESPONSE.activation_token)).not.toBeInTheDocument();
  });

  it('shows token TTL and masked phone after issuance', async () => {
    renderDialog();

    fireEvent.click(screen.getByRole('button', { name: 'patientPortal.pi_issue' }));

    await waitFor(() => {
      expect(screen.getByText('patientPortal.pi_phone:+998 *** *** 45 67')).toBeInTheDocument();
      expect(screen.getByText('patientPortal.pi_expires:72')).toBeInTheDocument();
    });
  });
});
