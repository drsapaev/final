// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React, { StrictMode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext.tsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.tsx';

const {
  apiGet,
  apiPut,
  me,
  getAuthState,
  notificationGetSettings,
  notificationUpdateSettings,
  notificationGetPolicy,
  notificationUpdatePolicy,
} = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  me: vi.fn(),
  getAuthState: vi.fn(),
  notificationGetSettings: vi.fn(),
  notificationUpdateSettings: vi.fn(),
  notificationGetPolicy: vi.fn(),
  notificationUpdatePolicy: vi.fn(),
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

vi.mock('../../../api/services', () => ({
  notificationsService: {
    getSettings: notificationGetSettings,
    updateSettings: notificationUpdateSettings,
    getPolicy: notificationGetPolicy,
    updatePolicy: notificationUpdatePolicy,
  },
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
} from '../NotificationPreferences.tsx';

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
    notificationGetSettings.mockResolvedValue(baseSettings);
    notificationUpdateSettings.mockResolvedValue(baseSettings);
    notificationGetPolicy.mockResolvedValue({ policy: {} });
    notificationUpdatePolicy.mockResolvedValue({ policy: {} });
  });

  it('reuses one in-flight settings request across StrictMode remounts', async () => {
    let resolveRequest;
    notificationGetSettings.mockReturnValue(
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
      expect(notificationGetSettings).toHaveBeenCalledTimes(1);
      expect(notificationGetSettings).toHaveBeenCalledWith(20);
    });

    resolveRequest(baseSettings);

    expect(await screen.findByText('Каналы уведомлений')).toBeInTheDocument();
  });

  it('saves edited notification settings as a batch', async () => {
    notificationUpdateSettings.mockResolvedValue({
      ...baseSettings,
      email_appointment_reminder: false,
    });

    renderPreferences(<NotificationPreferences />);

    await screen.findByText('Каналы уведомлений');

    const switches = screen.getAllByRole('switch');
    fireEvent.click(switches[0]);

    const saveButton = screen.getByRole('button', { name: /сохранить настройки/i });
    expect(saveButton).not.toBeDisabled();
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(notificationUpdateSettings).toHaveBeenCalledWith(
        20,
        expect.objectContaining({
          email_appointment_reminder: false,
        })
      );
    });

    expect(await screen.findByText(/настройки уведомлений сохранены/i)).toBeInTheDocument();
  });
});
