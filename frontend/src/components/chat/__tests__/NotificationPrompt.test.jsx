import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { requestPermissionMock, loggerLog, loggerWarn, loggerError } = vi.hoisted(() => ({
  requestPermissionMock: vi.fn(),
  loggerLog: vi.fn(),
  loggerWarn: vi.fn(),
  loggerError: vi.fn()
}));

vi.mock('../../../services/pushNotifications', () => ({
  pushNotifications: {
    isSupported: true,
    requestPermission: requestPermissionMock
  }
}));

vi.mock('../../../services/notify', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn()
  }
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    log: loggerLog,
    warn: loggerWarn,
    error: loggerError
  }
}));

import NotificationPrompt from '../NotificationPrompt.tsx';

describe('NotificationPrompt', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    vi.stubGlobal('Notification', undefined);
    requestPermissionMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('does not crash when the Notification API is unavailable', () => {
    render(<NotificationPrompt />);
    expect(screen.queryByText(/включить уведомления/i)).not.toBeInTheDocument();
  });

  it('shows the banner after the delay and remembers dismissal', async () => {
    vi.stubGlobal('Notification', {
      permission: 'default'
    });

    render(<NotificationPrompt />);

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByText('Включить уведомления?')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /закрыть/i }));

    expect(sessionStorage.getItem('notification-prompt-dismissed')).toBe('true');
    expect(screen.queryByText('Включить уведомления?')).not.toBeInTheDocument();
  });
});
