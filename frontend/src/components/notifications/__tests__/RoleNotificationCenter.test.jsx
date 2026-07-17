import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { useNotificationCenterMock, getProfileMock, loggerWarn } = vi.hoisted(() => ({
  useNotificationCenterMock: vi.fn(),
  getProfileMock: vi.fn(),
  loggerWarn: vi.fn()
}));

vi.mock('../../../contexts/NotificationCenterContext', () => ({
  useNotificationCenter: () => useNotificationCenterMock()
}));

vi.mock('../../../stores/auth', () => ({
  getProfile: getProfileMock
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    info: vi.fn(),
    warn: loggerWarn,
    error: vi.fn()
  }
}));

vi.mock('../NotificationBell', () => ({
  default: ({ unreadCount, onClick }) => (
    <button type="button" onClick={onClick}>
      Bell {unreadCount}
    </button>
  )
}));

vi.mock('../NotificationInbox', () => ({
  default: () => <div data-testid="notification-inbox" />
}));

import RoleNotificationCenter from '../RoleNotificationCenter.tsx';

describe('RoleNotificationCenter', () => {
  let loadNotifications;
  let getUnreadCount;

  beforeEach(() => {
    vi.clearAllMocks();

    loadNotifications = vi.fn().mockResolvedValue([]);
    getUnreadCount = vi.fn().mockReturnValue(3);

    useNotificationCenterMock.mockReturnValue({
      loadNotifications,
      getUnreadCount
    });
  });

  it('loads history for the current recipient scope', async () => {
    getProfileMock.mockResolvedValueOnce({ id: 77, role: 'lab' });

    const { rerender } = render(<RoleNotificationCenter userRole="lab" />);

    await waitFor(() => {
      expect(loadNotifications).toHaveBeenCalledWith(
        expect.objectContaining({
          role: 'lab',
          recipient_id: 77,
          recipient_type: 'lab',
          status: 'all',
          limit: 50
        })
      );
    });

    rerender(<RoleNotificationCenter userRole="lab" />);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(loadNotifications).toHaveBeenCalledTimes(1);
  });

  it('skips history load when the auth profile is unavailable', async () => {
    getProfileMock.mockResolvedValueOnce(null);

    render(<RoleNotificationCenter userRole="lab" />);

    await waitFor(() => {
      expect(getProfileMock).toHaveBeenCalled();
    });

    expect(loadNotifications).not.toHaveBeenCalled();
    expect(loggerWarn).toHaveBeenCalledWith(
      '[NotificationCenter] missing auth profile for role=lab'
    );
  });
});
