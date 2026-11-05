import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import DisplayBoardSettings from '../DisplayBoardSettings';
import { api } from '@/api/client';

// QR-FE-013 — every legal patient-name privacy choice (full/initials/none)
// must reach PUT /admin/display/boards/{id} as its exact STRING value.
// Previously all three choices were coerced to boolean false
// (value.target.value === 'true'), which the backend string field rejects
// (422) and a privacy downgrade silently never happens. SYNTHETIC fixtures
// only — no real patient names or boards.

const syntheticBoard = {
  id: 'main_board',
  display_name: 'Синтетическое табло',
  location: 'Synthetic Hall',
  theme: 'light',
  show_patient_names: 'full',
  queue_display_count: 5,
  sound_enabled: true,
  voice_announcements: false,
  show_doctor_photos: false,
  show_announcements: true,
  show_banners: false,
  show_videos: false,
  call_display_duration: 30,
  voice_language: 'ru',
};

vi.mock('@/api/client', () => {
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url === '/admin/display/boards') {
        return Promise.resolve({ status: 200, data: [syntheticBoard] });
      }
      if (url === '/admin/display/themes') {
        return Promise.resolve({ status: 200, data: [] });
      }
      if (url === '/admin/display/stats') {
        return Promise.resolve({ status: 200, data: {} });
      }
      return Promise.resolve({ status: 200, data: [] });
    }),
    put: vi.fn(() => Promise.resolve({ status: 200, data: { message: 'ok' } })),
    post: vi.fn(() => Promise.resolve({ status: 200, data: {} })),
    delete: vi.fn(),
  };
  return {
    default: apiMock,
    api: apiMock,
    apiClient: apiMock,
  };
});

const renderScreen = async () => {
  const view = render(
    <ThemeProvider>
      <DisplayBoardSettings />
    </ThemeProvider>
  );
  await waitFor(() => {
    expect(api.get).toHaveBeenCalledWith('/admin/display/boards');
  });
  // Board loaded → the settings form (incl. the privacy select) is rendered.
  await screen.findByText('Отображение пациентов');
  return view;
};

const choosePrivacy = async (optionText: string) => {
  const fieldLabel = screen.getByText('Отображение пациентов');
  const fieldDiv = fieldLabel.closest('div');
  expect(fieldDiv).not.toBeNull();
  const trigger = within(fieldDiv as HTMLElement).getByRole('button');
  await userEvent.click(trigger);
  // Options render in a portal (document.body) as role="option".
  const option = await screen.findByRole('option', { name: (name) => name.includes(optionText) });
  await userEvent.click(option);
};

describe('DisplayBoardSettings privacy contract (QR-FE-013)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    ['none', 'Только номер'],
    ['initials', 'Инициалы'],
    ['full', 'Полное ФИО'],
  ])('saves privacy choice %s as a string, not boolean false', async (value, optionText) => {
    await renderScreen();
    await choosePrivacy(optionText);

    const saveButton = screen.getByRole('button', { name: /Сохранить/ });
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        '/admin/display/boards/main_board',
        expect.any(Object)
      );
    });
    const putCalls = (api.put as ReturnType<typeof vi.fn>).mock.calls;
    const boardPut = putCalls.find((call) => call[0] === '/admin/display/boards/main_board');
    expect(boardPut).toBeDefined();
    const body = boardPut![1] as Record<string, unknown>;
    // The exact string value must survive; the legacy coercion produced
    // boolean false for every choice and the backend rejects booleans (422).
    expect(body.show_patient_names).toBe(value);
    expect(body.show_patient_names).not.toBe(false);
  });
});
