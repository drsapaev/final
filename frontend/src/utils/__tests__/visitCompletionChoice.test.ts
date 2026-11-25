import { beforeEach, describe, expect, it, vi } from 'vitest';

import notify from '../../services/notify';
import { reportVisitCompletionCall } from '../visitCompletionChoice';

vi.mock('../../services/notify', () => ({
  default: { success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));

const translate = (key: string) => key;
const called = 'test.patient_called';
const unconfirmed = 'misc.queue_called_display_unconfirmed';

describe('optional call after confirmed visit completion', () => {
  beforeEach(() => vi.clearAllMocks());

  it.each(['unconfirmed', 'partial'] as const)(
    'reports committed call separately from %s announcement and never retries',
    async (displayDelivery) => {
      const call = vi.fn(async () => ({
        success: true as const, entry: { number: 17 }, displayDelivery,
      }));
      await reportVisitCompletionCall(call, translate, called);
      expect(notify.success).toHaveBeenCalledOnce();
      expect(notify.success).toHaveBeenCalledWith(called);
      expect(notify.warning).toHaveBeenCalledExactlyOnceWith(unconfirmed);
      expect(call).toHaveBeenCalledOnce();
    },
  );

  it.each(['published_only', 'delivered_local', undefined] as const)(
    'does not claim screen receipt for %s',
    async (displayDelivery) => {
      const call = vi.fn(async () => ({
        success: true as const, entry: { number: 17 }, displayDelivery,
      }));
      await reportVisitCompletionCall(call, translate, called);
      expect(notify.success).toHaveBeenCalledExactlyOnceWith(called);
      expect(notify.warning).not.toHaveBeenCalled();
      expect(call).toHaveBeenCalledOnce();
    },
  );
});
