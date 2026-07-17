import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import NotificationInbox from '../NotificationInbox.tsx';

const {
  store,
  getNotificationsByRole,
  markAsRead,
  markAsSeen,
  archiveNotification,
  markAllAsRead,
} = vi.hoisted(() => {
  const store = { notifications: [] };
  return {
    store,
    getNotificationsByRole: vi.fn(() => store.notifications),
    markAsRead: vi.fn(async () => {}),
    markAsSeen: vi.fn(async () => {}),
    archiveNotification: vi.fn(async () => {}),
    markAllAsRead: vi.fn(async () => {}),
  };
});

vi.mock('../../../contexts/NotificationCenterContext', () => ({
  useNotificationCenter: () => ({
    getNotificationsByRole,
    markAsRead,
    markAsSeen,
    archiveNotification,
    markAllAsRead,
  }),
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    warn: vi.fn(),
  },
}));

function createNotification(overrides = {}) {
  return {
    id: 'notification-1',
    title: 'Тестовое уведомление',
    message: 'Тестовое сообщение',
    type: 'system_alert',
    eventType: 'system_alert',
    createdAt: '2026-04-17T08:00:00Z',
    sequenceId: 1,
    isRead: false,
    isSeen: false,
    isArchived: false,
    ...overrides,
  };
}

describe('NotificationInbox routing', () => {
  let pushStateSpy;

  beforeEach(() => {
    vi.clearAllMocks();
    store.notifications = [];
    pushStateSpy = vi.spyOn(window.history, 'pushState');
  });

  afterEach(() => {
    pushStateSpy.mockRestore();
  });

  it.each([
    { role: 'admin', type: 'all_free_requested', expectedTarget: '/admin/all-free-requests' },
    {
      role: 'admin',
      type: 'message_received',
      payloadSnapshot: { metadata: { conversation_id: 'conv-42' } },
      expectedTarget: '/messages?conversation=conv-42',
    },
    { role: 'doctor', type: 'lab_critical_result', expectedTarget: '/lab/results?critical=1' },
    { role: 'registrar', type: 'patient_registered', expectedTarget: '/registrar/patients' },
    { role: 'doctor', type: 'queue_position', expectedTarget: '/queue' },
    { role: 'admin', type: 'security_alert', expectedTarget: '/admin' },
    { role: 'admin', type: 'payment_notification', deepLink: '/patient', expectedTarget: '/patient' },
    { role: 'admin', type: 'system_alert', expectedTarget: '/admin' },
    { role: 'registrar', type: 'system_alert', expectedTarget: '/registrar' },
  ])(
    'navigates $type to $expectedTarget',
    async ({ role, type, expectedTarget, payloadSnapshot, deepLink }) => {
      store.notifications = [
        createNotification({
          id: `notification-${type}-${role}`,
          type,
          eventType: type,
          payloadSnapshot,
          deepLink,
        }),
      ];

      render(<NotificationInbox userRole={role} onClose={() => {}} />);
      fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));

      await waitFor(() => {
        expect(pushStateSpy).toHaveBeenCalledWith({}, '', expectedTarget);
      });

      expect(markAsSeen).toHaveBeenCalledTimes(1);
      expect(markAsRead).toHaveBeenCalledTimes(1);
    },
  );

  it('uses explicit deep link over type-based routing', async () => {
    store.notifications = [
      createNotification({
        id: 'notification-explicit-deep-link',
        type: 'all_free_requested',
        eventType: 'all_free_requested',
        deepLink: '/custom-target',
      }),
    ];

    render(<NotificationInbox userRole="admin" onClose={() => {}} />);
    fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));

    await waitFor(() => {
      expect(pushStateSpy).toHaveBeenCalledWith({}, '', '/custom-target');
    });
  });

  it('does not navigate when notification type is unknown and no deep link exists', async () => {
    store.notifications = [
      createNotification({
        id: 'notification-unknown-type',
        type: 'unknown_runtime_event',
        eventType: 'unknown_runtime_event',
        deepLink: '',
      }),
    ];

    render(<NotificationInbox userRole="admin" onClose={() => {}} />);
    fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));

    await waitFor(() => {
      expect(markAsSeen).toHaveBeenCalledTimes(1);
      expect(markAsRead).toHaveBeenCalledTimes(1);
    });
    expect(pushStateSpy).not.toHaveBeenCalled();
  });
});
