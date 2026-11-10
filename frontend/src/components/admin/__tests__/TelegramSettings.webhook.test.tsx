import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import TelegramSettings from '../TelegramSettings';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock('../../../api/client', () => ({ api: apiMocks }));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe('Telegram settings webhook URL', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.get.mockImplementation((path: string) => {
      if (path === '/admin/telegram/settings') {
        return Promise.resolve({ data: {
          bot_token: '********',
          webhook_url: '',
          admin_chat_ids: [],
          notifications_enabled: true,
          appointment_reminders: true,
          lab_results_notifications: true,
          payment_notifications: true,
          default_language: 'ru',
          supported_languages: ['ru', 'uz', 'en'],
        } });
      }
      return Promise.resolve({ data: {} });
    });
    apiMocks.post.mockResolvedValue({ data: { message: 'ok' } });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each([
    ['a separate API origin', 'https://api.example.test'],
    ['an explicitly configured same origin', window.location.origin],
  ])('registers the webhook on %s', async (_description, apiOrigin) => {
    vi.stubEnv('VITE_API_BASE_URL', apiOrigin);

    render(<ThemeProvider><TelegramSettings /></ThemeProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.ts_set_webhook_button' }));

    await waitFor(() => expect(apiMocks.post).toHaveBeenCalledWith(
      '/admin/telegram/set-webhook',
      { webhook_url: `${apiOrigin}/api/v1/telegram/webhook` },
    ));
  });
});
