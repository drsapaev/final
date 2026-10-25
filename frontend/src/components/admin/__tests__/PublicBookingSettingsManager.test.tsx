import '@testing-library/jest-dom';
import type { ComponentProps, ReactNode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getSettings, updateSettings } = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
}));

vi.mock('../../../api/adminBookingSettings', () => ({
  getPublicBookingSettings: getSettings,
  updatePublicBookingSettings: updateSettings,
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('../../ui/macos', () => ({
  Alert: ({ title, message }: { title: string; message: string }) => (
    <div role="alert">{title}: {message}</div>
  ),
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
  Button: ({
    children,
    disabled,
    onClick,
  }: {
    children: ReactNode;
    disabled?: boolean;
    onClick?: () => void;
  }) => <button type="button" disabled={disabled} onClick={onClick}>{children}</button>,
  Card: ({ children }: { children: ReactNode }) => <section>{children}</section>,
  Input: (props: ComponentProps<'input'>) => <input {...props} />,
}));

import PublicBookingSettingsManager from '../PublicBookingSettingsManager';

const initialSettings = {
  version: 0,
  is_enabled: false,
  is_ready: false,
  mode: null,
  booking_horizon_days: null,
  service_ids: [],
  doctor_ids: [],
  services: [{ id: 11, label: 'Test service', eligible: true }],
  doctors: [{ id: 22, label: 'Test doctor', eligible: true }],
  updated_at: null,
  updated_by: null,
};

describe('PublicBookingSettingsManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSettings.mockResolvedValue(initialSettings);
  });

  it('keeps booking disabled until the required settings are complete', async () => {
    render(<PublicBookingSettingsManager />);

    const enable = await screen.findByRole('checkbox', { name: 'admin2.pbs_enable' });
    expect(enable).toBeDisabled();
    expect(screen.getByRole('button', { name: 'admin2.pbs_save' })).toBeDisabled();
  });

  it('saves a complete versioned configuration before enabling the settings', async () => {
    const savedSettings = {
      ...initialSettings,
      version: 1,
      is_enabled: true,
      is_ready: true,
      mode: 'registrar_request',
      booking_horizon_days: 30,
      service_ids: [11],
      doctor_ids: [22],
    };
    updateSettings.mockResolvedValue(savedSettings);
    render(<PublicBookingSettingsManager />);

    await screen.findByRole('checkbox', { name: 'admin2.pbs_enable' });
    fireEvent.change(screen.getByLabelText('admin2.pbs_mode_label'), {
      target: { value: 'registrar_request' },
    });
    fireEvent.change(screen.getByLabelText('admin2.pbs_horizon_label'), {
      target: { value: '30' },
    });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Test service' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Test doctor' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'admin2.pbs_enable' }));
    fireEvent.click(screen.getByRole('button', { name: 'admin2.pbs_save' }));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledWith({
      expected_version: 0,
      is_enabled: true,
      mode: 'registrar_request',
      booking_horizon_days: 30,
      service_ids: [11],
      doctor_ids: [22],
    }));
    expect(await screen.findByRole('alert')).toHaveTextContent('admin2.pbs_success_saved');
  });
});
