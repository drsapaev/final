import React, { StrictMode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';

const { apiGet, apiPut, me, getAuthState } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  me: vi.fn(),
  getAuthState: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: apiGet,
    put: apiPut,
  },
  me,
}));

vi.mock('../../../stores/auth', () => ({
  getState: getAuthState,
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

import NotificationPreferences, {
  __resetNotificationSettingsCacheForTests,
} from '../NotificationPreferences.jsx';

const baseSettings = {
  email_appointment_reminder: true,
  email_appointment_confirmation: true,
  email_appointment_cancellation: false,
  email_payment_receipt: true,
  email_system_updates: false,
  email_security_alerts: true,
  sms_appointment_reminder: false,
  sms_emergency: true,
  push_appointment_reminder: true,
  push_appointment_confirmation: true,
  push_payment_receipt: false,
  reminder_time_before: 30,
  quiet_hours_start: '22:00',
  quiet_hours_end: '07:00',
};

function renderPreferences(ui) {
  return render(
    <MacOSThemeProvider>
      <ThemeProvider>{ui}</ThemeProvider>
    </MacOSThemeProvider>
  );
}

describe('NotificationPreferences', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetNotificationSettingsCacheForTests();
    getAuthState.mockReturnValue({ profile: { id: 20 } });
    me.mockResolvedValue({ id: 20 });
    apiGet.mockResolvedValue({ data: baseSettings });
    apiPut.mockResolvedValue({ data: baseSettings });
  });

  it('reuses one in-flight settings request across StrictMode remounts', async () => {
    let resolveRequest;
    apiGet.mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve;
      })
    );

    renderPreferences(
      <StrictMode>
        <NotificationPreferences />
      </StrictMode>
    );

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledTimes(1);
      expect(apiGet).toHaveBeenCalledWith('/notifications/settings/20');
    });

    resolveRequest({ data: baseSettings });

    expect(await screen.findByText('Каналы уведомлений')).toBeInTheDocument();
  });

  it('saves edited notification settings as a batch', async () => {
    apiPut.mockResolvedValue({
      data: {
        ...baseSettings,
        email_appointment_reminder: false,
      },
    });

    renderPreferences(<NotificationPreferences />);

    await screen.findByText('Каналы уведомлений');

    const switches = screen.getAllByRole('switch');
    fireEvent.click(switches[0]);

    const saveButton = screen.getByRole('button', { name: /сохранить настройки/i });
    expect(saveButton).not.toBeDisabled();
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(apiPut).toHaveBeenCalledWith(
        '/notifications/settings/20',
        expect.objectContaining({
          email_appointment_reminder: false,
        })
      );
    });

    expect(await screen.findByText(/настройки уведомлений сохранены/i)).toBeInTheDocument();
  });
});
