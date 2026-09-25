import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  deleteDentalMedia,
  listDentalMedia,
  loadDentalMediaContent,
  updateDentalMedia,
  uploadDentalMedia,
} from '../dentalMedia';

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('../client', () => ({ apiClient: api }));

describe('dental media API adapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 100 } });
    api.post.mockResolvedValue({ data: { id: 1 } });
    api.patch.mockResolvedValue({ data: { id: 1 } });
    api.delete.mockResolvedValue({ data: { success: true } });
  });

  it('requests the archive with both patient and confirmed visit context', async () => {
    await listDentalMedia(12, 34, 2);
    expect(api.get).toHaveBeenCalledWith('/dental/media', {
      params: { patient_id: 12, visit_id: 34, page: 2, size: 100 },
    });
  });

  it('uploads only through authenticated multipart API and keeps the visit context', async () => {
    const file = new File(['synthetic image'], 'synthetic.png', { type: 'image/png' });
    await uploadDentalMedia(12, 34, 'photo', file, {
      title: 'Synthetic image', description: null, tooth: '16', capture_date: '2026-09-20',
    });

    const [url, payload, config] = api.post.mock.calls[0];
    expect(url).toBe('/dental/media');
    expect(payload).toBeInstanceOf(FormData);
    expect(payload.get('patient_id')).toBe('12');
    expect(payload.get('visit_id')).toBe('34');
    expect(payload.get('category')).toBe('photo');
    expect(payload.get('file')).toBe(file);
    expect(config.headers['Content-Type']).toBe('multipart/form-data');
  });

  it('uses authenticated blob preview and metadata/delete routes', async () => {
    const blob = new Blob(['synthetic image'], { type: 'image/png' });
    api.get.mockResolvedValueOnce({ data: blob });
    expect(await loadDentalMediaContent(41, 34)).toBe(blob);
    expect(api.get).toHaveBeenCalledWith('/dental/media/41/content', {
      params: { visit_id: 34 },
      responseType: 'blob',
    });

    await updateDentalMedia(41, { tooth: '17' });
    expect(api.patch).toHaveBeenCalledWith('/dental/media/41', { tooth: '17' });
    await deleteDentalMedia(41);
    expect(api.delete).toHaveBeenCalledWith('/dental/media/41');
  });
});
