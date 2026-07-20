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

// Cast api through unknown so we can call vitest mock methods on its
// members without fighting the real AxiosInstance type.
const apiMock = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
};

describe('adminSettings API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches wizard settings via admin endpoint', async () => {
    apiMock.get.mockResolvedValueOnce({ data: { success: true } });
    const data = await fetchWizardSettings();

    expect(apiMock.get).toHaveBeenCalledWith('/admin/wizard-settings');
    expect(data).toEqual({ success: true });
  });

  it('fetches clinic settings with category query param', async () => {
    apiMock.get.mockResolvedValueOnce({ data: { category: 'branding' } });
    const data = await fetchClinicSettings('branding');

    expect(apiMock.get).toHaveBeenCalledWith('/admin/clinic/settings', {
      params: { category: 'branding' },
    });
    expect(data).toEqual({ category: 'branding' });
  });

  it('saves clinic settings via PUT contract endpoint', async () => {
    const payload = { clinic_name: 'Test Clinic' };
    apiMock.put.mockResolvedValueOnce({ data: { ok: true } });
    const data = await saveClinicSettings(payload);

    expect(apiMock.put).toHaveBeenCalledWith('/admin/clinic/settings', payload);
    expect(data).toEqual({ ok: true });
  });

  it('fetches ticket print settings via dedicated endpoint', async () => {
    apiMock.get.mockResolvedValueOnce({ data: { show_logo: true } });
    const data = await fetchTicketPrintSettings();

    expect(apiMock.get).toHaveBeenCalledWith('/admin/clinic/ticket-print-settings');
    expect(data).toEqual({ show_logo: true });
  });

  it('saves ticket print settings via dedicated endpoint', async () => {
    const payload = { show_logo: true, show_patient_name: false };
    apiMock.put.mockResolvedValueOnce({ data: { show_logo: true } });
    const data = await saveTicketPrintSettings(payload);

    expect(apiMock.put).toHaveBeenCalledWith('/admin/clinic/ticket-print-settings', payload);
    expect(data).toEqual({ show_logo: true });
  });

  it('tests payment provider config via dedicated endpoint', async () => {
    apiMock.post.mockResolvedValueOnce({ data: { status: 'ok' } });
    const data = await testPaymentProviderConfig('payme', { merchant_id: 'abc' });

    expect(apiMock.post).toHaveBeenCalledWith('/admin/test-payment-provider', {
      provider: 'payme',
      config: { merchant_id: 'abc' },
    });
    expect(data).toEqual({ status: 'ok' });
  });
});
