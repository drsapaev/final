import { api } from './client';

export async function fetchWizardSettings() {
  const response = await api.get('/admin/wizard-settings');
  return response.data;
}

export async function saveWizardSettings(payload) {
  const response = await api.post('/admin/wizard-settings', payload);
  return response.data;
}

export async function fetchBenefitSettings() {
  const response = await api.get('/admin/benefit-settings');
  return response.data;
}

export async function saveBenefitSettings(payload) {
  const response = await api.post('/admin/benefit-settings', payload);
  return response.data;
}

export async function fetchClinicSettings(category = 'clinic') {
  const response = await api.get('/admin/clinic/settings', {
    params: { category },
  });
  return response.data;
}

export async function saveClinicSettings(payload) {
  const response = await api.put('/admin/clinic/settings', payload);
  return response.data;
}

export async function fetchPaymentProviderSettings() {
  const response = await api.get('/admin/payment-provider-settings');
  return response.data;
}

export async function savePaymentProviderSettings(payload) {
  const response = await api.post('/admin/payment-provider-settings', payload);
  return response.data;
}

export async function testPaymentProviderConfig(provider, config) {
  const response = await api.post('/admin/test-payment-provider', {
    provider,
    config,
  });
  return response.data;
}
