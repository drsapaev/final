// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

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
  fetchTicketPrintSettings,
  fetchWizardSettings,
  saveClinicSettings,
  saveTicketPrintSettings,
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

  it('fetches ticket print settings via dedicated endpoint', async () => {
    api.get.mockResolvedValueOnce({ data: { show_logo: true } });
    const data = await fetchTicketPrintSettings();

    expect(api.get).toHaveBeenCalledWith('/admin/clinic/ticket-print-settings');
    expect(data).toEqual({ show_logo: true });
  });

  it('saves ticket print settings via dedicated endpoint', async () => {
    const payload = { show_logo: true, show_patient_name: false };
    api.put.mockResolvedValueOnce({ data: { show_logo: true } });
    const data = await saveTicketPrintSettings(payload);

    expect(api.put).toHaveBeenCalledWith('/admin/clinic/ticket-print-settings', payload);
    expect(data).toEqual({ show_logo: true });
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
