import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

import { api } from '../client';
import {
  fetchClinicSettings,
  fetchWizardSettings,
  saveClinicSettings,
  testPaymentProviderConfig,
} from '../adminSettings';

describe('adminSettings API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches wizard settings via admin endpoint', async () => {
    api.get.mockResolvedValueOnce({ data: { success: true } });
    const data = await fetchWizardSettings();

    expect(api.get).toHaveBeenCalledWith('/admin/wizard-settings');
    expect(data).toEqual({ success: true });
  });

  it('fetches clinic settings with category query param', async () => {
    api.get.mockResolvedValueOnce({ data: { category: 'branding' } });
    const data = await fetchClinicSettings('branding');

    expect(api.get).toHaveBeenCalledWith('/admin/clinic/settings', {
      params: { category: 'branding' },
    });
    expect(data).toEqual({ category: 'branding' });
  });

  it('saves clinic settings via PUT contract endpoint', async () => {
    const payload = { clinic_name: 'Test Clinic' };
    api.put.mockResolvedValueOnce({ data: { ok: true } });
    const data = await saveClinicSettings(payload);

    expect(api.put).toHaveBeenCalledWith('/admin/clinic/settings', payload);
    expect(data).toEqual({ ok: true });
  });

  it('tests payment provider config via dedicated endpoint', async () => {
    api.post.mockResolvedValueOnce({ data: { status: 'ok' } });
    const data = await testPaymentProviderConfig('payme', { merchant_id: 'abc' });

    expect(api.post).toHaveBeenCalledWith('/admin/test-payment-provider', {
      provider: 'payme',
      config: { merchant_id: 'abc' },
    });
    expect(data).toEqual({ status: 'ok' });
  });
});
