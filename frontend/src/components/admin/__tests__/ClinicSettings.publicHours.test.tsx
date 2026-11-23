import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import ClinicSettings from '../ClinicSettings';

const settingsMocks = vi.hoisted(() => ({
  fetchClinicSettings: vi.fn(),
  saveClinicSettings: vi.fn(),
  fetchTicketPrintSettings: vi.fn(),
  saveTicketPrintSettings: vi.fn(),
  uploadLogo: vi.fn(),
}));

vi.mock('../../../hooks/useClinicSettings', () => ({
  useClinicSettings: () => settingsMocks,
  TICKET_PRINT_SETTINGS_DEFINITIONS: [],
  TICKET_PRINT_SETTINGS_DEFAULTS: {},
}));

describe('ClinicSettings public hours', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    settingsMocks.fetchClinicSettings.mockResolvedValue([]);
    settingsMocks.saveClinicSettings.mockResolvedValue([]);
    settingsMocks.fetchTicketPrintSettings.mockResolvedValue({});
    settingsMocks.saveTicketPrintSettings.mockResolvedValue({});
    settingsMocks.uploadLogo.mockResolvedValue('/unused-logo.png');
  });

  it('lets an administrator edit the hours used by the public contacts page', async () => {
    render(
      <ThemeProvider>
        <ClinicSettings />
      </ThemeProvider>,
    );

    const opening = await screen.findByLabelText('Начало работы');
    const closing = screen.getByLabelText('Окончание работы');
    expect(opening).toHaveValue('09:00');
    expect(closing).toHaveValue('17:00');

    fireEvent.change(opening, { target: { value: '08:30' } });
    fireEvent.click(screen.getAllByRole('button', { name: 'Сохранить' })[0]);

    await waitFor(() => expect(settingsMocks.saveClinicSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        settings: expect.objectContaining({
          clinic_working_hours_start: '08:30',
          clinic_working_hours_end: '17:00',
        }),
      }),
    ));
  });
});
