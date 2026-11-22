import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get, put } = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
}));

vi.mock('../client', () => ({
  api: { get, put },
}));

import { getPublicBookingSettings, updatePublicBookingSettings } from '../adminBookingSettings';

describe('admin public booking settings API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reads the dedicated settings resource', async () => {
    const settings = { version: 0, is_enabled: false, is_ready: false };
    get.mockResolvedValue({ data: settings });

    await expect(getPublicBookingSettings()).resolves.toBe(settings);
    expect(get).toHaveBeenCalledWith('/admin/public-booking-settings');
  });

  it('replaces settings through the versioned endpoint', async () => {
    const update = {
      expected_version: 0,
      is_enabled: false,
      mode: null,
      booking_horizon_days: null,
      service_ids: [],
      doctor_ids: [],
    };
    const settings = { version: 1, is_enabled: false, is_ready: false };
    put.mockResolvedValue({ data: settings });

    await expect(updatePublicBookingSettings(update)).resolves.toBe(settings);
    expect(put).toHaveBeenCalledWith('/admin/public-booking-settings', update);
  });
});
