import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getPublicSiteMediaErrorKey,
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

  it('lists media and only projects active doctor names for the selector', async () => {
    api.get.mockResolvedValueOnce({ data: [media] });
    expect(await listPublicSiteMedia()).toEqual([media]);
    expect(api.get).toHaveBeenNthCalledWith(1, '/admin/public-site/media');

    api.get.mockResolvedValueOnce({ data: [
      { id: 42, active: true, user: { full_name: 'SYNTHETIC Doctor' }, phone: 'not projected' },
      { id: 44, active: true, user: { full_name: 'SYNTHETIC Doctor' }, phone: 'not projected' },
      { id: 43, active: false, user: { full_name: '  ' }, email: 'not projected' },
    ] });
    expect(await listPublicSiteDoctors()).toEqual([
      { id: 42, displayName: 'SYNTHETIC Doctor (#42)', active: true },
      { id: 44, displayName: 'SYNTHETIC Doctor (#44)', active: true },
      { id: 43, displayName: '#43', active: false },
    ]);
    expect(api.get).toHaveBeenNthCalledWith(2, '/admin/doctors', {
      params: { active_only: false, limit: 500 },
    });
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
    expect(getPublicSiteMediaErrorKey(storageError)).toBe('publicSiteMedia.storageUnavailable');
    expect(getPublicSiteMediaErrorKey(fileError)).toBe('publicSiteMedia.fileTooLarge');
    expect(getPublicSiteMediaErrorKey(new Error('unexpected'))).toBe('publicSiteMedia.genericError');
  });
});
