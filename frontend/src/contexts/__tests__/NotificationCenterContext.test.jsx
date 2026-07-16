import { describe, expect, it } from 'vitest';
import { applyUnreadSnapshot } from '../NotificationCenterContext';

describe('NotificationCenterContext unread snapshot helpers', () => {
  it('merges websocket unread totals without discarding existing breakdowns', () => {
    const current = {
      total: 3,
      by_role: { doctor: 2 },
      by_channel: { inbox: 3 },
      by_severity: { info: 3 }
    };

    const next = applyUnreadSnapshot(current, { unread_count: 5 });

    expect(next).toEqual({
      total: 5,
      by_role: { doctor: 2 },
      by_channel: { inbox: 3 },
      by_severity: { info: 3 }
    });
  });

  it('replaces the snapshot when the backend sends a full unread payload', () => {
    const current = {
      total: 7,
      by_role: { doctor: 4 },
      by_channel: { inbox: 7 },
      by_severity: { info: 7 }
    };

    const next = applyUnreadSnapshot(
      current,
      {
        total: 2,
        by_role: { doctor: 1, registrar: 1 },
        by_channel: { inbox: 2 },
        by_severity: { warning: 1, info: 1 }
      },
      true
    );

    expect(next).toEqual({
      total: 2,
      by_role: { doctor: 1, registrar: 1 },
      by_channel: { inbox: 2 },
      by_severity: { warning: 1, info: 1 }
    });
  });
});
