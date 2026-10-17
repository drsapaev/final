import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getPublicSiteDoctorWebsiteContent,
  getPublicSiteMediaErrorKey,
  isPublicSiteDoctorEligible,
  listPublicSiteDoctors,
  listPublicSiteMedia,
  publishPublicSiteMedia,
  unpublishPublicSiteMedia,
  uploadPublicSiteMedia,
} from '../publicSiteMedia';

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock('../client', () => ({ apiClient: api }));

const media = {
  id: 8,
  asset_kind: 'doctor_portrait' as const,
  doctor_id: 42,
  mime_type: 'image/jpeg',
  byte_size: 2048,
  is_published: false,
  published_at: null,
  created_at: '2026-10-17T09:00:00Z',
  media_url: '/api/v1/public-site/media/abc',
};

describe('public site media API adapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: [] });
    api.post.mockResolvedValue({ data: media });
    api.put.mockResolvedValue({ data: { ...media, is_published: true } });
  });

  it('lists media and projects only compact doctor-option fields', async () => {
    api.get.mockResolvedValueOnce({ data: [media] });
    expect(await listPublicSiteMedia()).toEqual([media]);
    expect(api.get).toHaveBeenNthCalledWith(1, '/admin/public-site/media');

    api.get.mockResolvedValueOnce({ data: [
      { id: 42, active: true, specialty: 'Cardiology', cabinet: '2' },
      { id: 44, active: true, specialty: 'Dermatology', cabinet: null },
    ] });
    expect(await listPublicSiteDoctors()).toEqual([
      { id: 42, displayName: 'Cardiology · 2 (#42)', active: true },
      { id: 44, displayName: 'Dermatology (#44)', active: true },
    ]);
    expect(api.get).toHaveBeenNthCalledWith(2, '/services/admin/doctors', {
      params: { limit: 25, offset: 0 },
    });
  });

  it('loads one doctor public-readiness record without fetching every doctor detail', async () => {
    const content = {
      id: 42,
      active: true,
      owner_active: true,
      show_on_website: true,
      missing_fields: [],
    };
    api.get.mockResolvedValueOnce({ data: content });

    expect(await getPublicSiteDoctorWebsiteContent(42)).toEqual(content);
    expect(api.get).toHaveBeenCalledWith('/admin/doctors/42/website-content');
    expect(isPublicSiteDoctorEligible(content)).toBe(true);
    expect(isPublicSiteDoctorEligible({ ...content, owner_active: false })).toBe(false);
    expect(isPublicSiteDoctorEligible({ ...content, show_on_website: false })).toBe(false);
    expect(isPublicSiteDoctorEligible({ ...content, missing_fields: ['bio_uz'] })).toBe(false);
  });

  it('uploads only as a draft through authenticated multipart API', async () => {
    const file = new File(['synthetic image'], 'portrait.png', { type: 'image/png' });
    await uploadPublicSiteMedia(file, 'doctor_portrait', 42);

    const [url, payload, config] = api.post.mock.calls[0];
    expect(url).toBe('/admin/public-site/media');
    expect(payload).toBeInstanceOf(FormData);
    expect(payload.get('file')).toBe(file);
    expect(payload.get('asset_kind')).toBe('doctor_portrait');
    expect(payload.get('doctor_id')).toBe('42');
    expect(config.headers['Content-Type']).toBe('multipart/form-data');
  });

  it('does not attach a doctor to the clinic logo and uses explicit publication routes', async () => {
    const file = new File(['synthetic image'], 'logo.png', { type: 'image/png' });
    await uploadPublicSiteMedia(file, 'clinic_logo');
    expect(api.post.mock.calls[0][1].get('asset_kind')).toBe('clinic_logo');
    expect(api.post.mock.calls[0][1].has('doctor_id')).toBe(false);

    await publishPublicSiteMedia(8);
    expect(api.put).toHaveBeenNthCalledWith(1, '/admin/public-site/media/8/publish');
    await unpublishPublicSiteMedia(8);
    expect(api.put).toHaveBeenNthCalledWith(2, '/admin/public-site/media/8/unpublish');
  });

  it('maps storage and image validation failures to localized UI messages', () => {
    const storageError = Object.assign(new Error('unavailable'), {
      isAxiosError: true,
      response: { status: 503, data: { detail: { code: 'public_media_storage_unavailable' } } },
    });
    const fileError = Object.assign(new Error('too large'), {
      isAxiosError: true,
      response: { status: 413, data: { detail: { code: 'public_media_file_too_large' } } },
    });
    const networkError = Object.assign(new Error('offline'), {
      isAxiosError: true,
      code: 'ECONNABORTED',
    });
    const cancelledError = Object.assign(new Error('cancelled'), {
      isAxiosError: true,
      code: 'ERR_CANCELED',
    });
    const genericServiceUnavailable = Object.assign(new Error('service unavailable'), {
      isAxiosError: true,
      response: { status: 503, data: { detail: 'temporarily unavailable' } },
    });
    expect(getPublicSiteMediaErrorKey(storageError)).toBe('publicSiteMedia.storageUnavailable');
    expect(getPublicSiteMediaErrorKey(genericServiceUnavailable)).toBe('publicSiteMedia.genericError');
    expect(getPublicSiteMediaErrorKey(fileError)).toBe('publicSiteMedia.fileTooLarge');
    expect(getPublicSiteMediaErrorKey(networkError)).toBe('publicSiteMedia.networkError');
    expect(getPublicSiteMediaErrorKey(cancelledError)).toBe('publicSiteMedia.genericError');
    expect(getPublicSiteMediaErrorKey(new Error('unexpected'))).toBe('publicSiteMedia.genericError');
  });
});
