import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { useNotificationCenterMock, loggerWarn } = vi.hoisted(() => ({
  useNotificationCenterMock: vi.fn(),
  loggerWarn: vi.fn()
}));

vi.mock('../../../contexts/NotificationCenterContext', () => ({
  useNotificationCenter: () => useNotificationCenterMock()
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    info: vi.fn(),
    warn: loggerWarn,
    error: vi.fn()
  }
}));

import NotificationInbox from '../NotificationInbox.jsx';

describe('NotificationInbox', () => {
  let notificationCenterState;

  const notifications = [
    {
      id: 'delivery-1',
      title: 'Очередь обновлена',
      message: 'Пациент вызван к врачу',
      type: 'queue_changed',
      eventType: 'queue_changed',
      severity: 'warning',
      isRead: false,
      isSeen: false,
      isArchived: false,
      sequenceId: 2,
      createdAt: '2026-03-30T10:00:00.000Z'
    },
    {
      id: 'delivery-2',
      title: 'Системное уведомление',
      message: 'Архивный элемент',
      type: 'system_alert',
      eventType: 'system_alert',
      severity: 'info',
      isRead: true,
      isSeen: true,
      isArchived: false,
      sequenceId: 1,
      createdAt: '2026-03-29T10:00:00.000Z'
    }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    notificationCenterState = {
      getNotificationsByRole: vi.fn().mockReturnValue(notifications),
      markAsRead: vi.fn().mockResolvedValue({ ok: true }),
      markAsSeen: vi.fn().mockResolvedValue({ ok: true }),
      archiveNotification: vi.fn().mockResolvedValue({ ok: true }),
      markAllAsRead: vi.fn().mockResolvedValue({ ok: true })
    };
    useNotificationCenterMock.mockReturnValue(notificationCenterState);
  });

  it('renders a keyboard-accessible inbox item and wires read/archive actions', async () => {
    // eslint-disable-next-line jsx-a11y/aria-role
    render(<NotificationInbox role="admin" onClose={vi.fn()} />);
    window.history.pushState({}, '', '/');

    expect(screen.getByRole('dialog', { name: /центр уведомлений/i })).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', { name: /Открыть уведомление: Очередь обновлена/i })
    );

    await waitFor(() => {
      expect(notificationCenterState.markAsSeen).toHaveBeenCalledWith('delivery-1');
      expect(notificationCenterState.markAsRead).toHaveBeenCalledWith('delivery-1');
    });
    await waitFor(() => {
      expect(window.location.pathname).toBe('/queue');
    });

    fireEvent.click(screen.getByRole('button', { name: /^Прочитать все$/i }));

    await waitFor(() => {
      expect(notificationCenterState.markAllAsRead).toHaveBeenCalledWith('admin');
    });

    fireEvent.click(screen.getAllByRole('button', { name: /^Архив$/i })[0]);

    await waitFor(() => {
      expect(notificationCenterState.archiveNotification).toHaveBeenCalledWith('delivery-1');
    });
  });
});
