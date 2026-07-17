// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiGet, loggerError } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  loggerError: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: apiGet,
  },
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    error: loggerError,
    info: vi.fn(),
    warn: vi.fn(),
  },
}));

import NotificationSystemStatus from '../NotificationSystemStatus.tsx';

describe('NotificationSystemStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGet.mockResolvedValue({
      data: {
        email: {
          configured: true,
          server: 'smtp.mail.local',
          port: 587,
        },
        telegram: {
          configured: true,
          bot_token: 'bot-token',
          chat_id: '123456',
        },
        sms: {
          configured: false,
          api_url: 'https://sms.example.local',
        },
      },
    });
  });

  it('renders notification system status from response.data', async () => {
    render(<NotificationSystemStatus />);

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith('/notifications/notification-status');
    });

    expect(await screen.findByText('Email (SMTP)')).toBeInTheDocument();
    expect(screen.getByText('Сервер: smtp.mail.local')).toBeInTheDocument();
    expect(screen.getByText('Порт: 587')).toBeInTheDocument();
    expect(screen.getAllByText('Активен')).toHaveLength(2);
    expect(screen.getByText('Telegram Bot')).toBeInTheDocument();
    expect(screen.getByText('Bot Token: ******')).toBeInTheDocument();
    expect(screen.getByText('Chat ID: 123456')).toBeInTheDocument();
    expect(screen.getByText('SMS Provider')).toBeInTheDocument();
    expect(screen.getByText('API URL: https://sms.example.local')).toBeInTheDocument();
    expect(screen.getByText('Не настроен')).toBeInTheDocument();
  });
});
