/**
 * DermaVisitGallery — тесты галереи фото текущего визита (пункт 8 плана аудита).
 *
 * Контракт:
 * - /files — единственный источник фото: список GET /files/?patient_id&visit_id,
 *   превью — авторизованный blob-запрос GET /files/{id}/preview;
 * - категории осмотр/до/после берутся из тегов файла;
 * - загрузка сохранённых файлов при открытии, objectURL освобождаются при смене
 *   пациента/визита и размонтировании;
 * - загрузка (upload) не запускает AI-анализ;
 * - удаление через DELETE /files/{id} со сбросом списка.
 */
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiState = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: (...args: unknown[]) => apiState.get(...(args as [string])),
    post: (...args: unknown[]) => apiState.post(...(args as [string])),
    delete: (...args: unknown[]) => apiState.delete(...(args as [string])),
  },
}));

vi.mock('../../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

vi.mock('../../../utils/heicConverter', () => ({
  isHEICFile: () => false,
  convertHEICToJPEG: vi.fn(),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string, options?: Record<string, unknown>) => {
    if (options && typeof options === 'object' && 'category' in options) {
      return `${key}:${String(options.category)}`;
    }
    return key;
  } }),
}));

import DermaVisitGallery from '../DermaVisitGallery';

function fileList(files: File[]): FileList {
  return files as unknown as FileList;
}

const imageBlob = new Blob(['synthetic-image'], { type: 'image/jpeg' });

function listResponse(files: Array<Record<string, unknown>>) {
  return { data: { files, total: files.length } };
}

describe('DermaVisitGallery', () => {
  let createObjectURLMock: ReturnType<typeof vi.fn>;
  let revokeObjectURLMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    apiState.get.mockReset();
    apiState.post.mockReset();
    apiState.delete.mockReset();
    // jsdom не реализует URL.createObjectURL — подставляем детерминированный mock.
    createObjectURLMock = vi.fn(() => `blob:mock-${Math.random().toString(36).slice(2)}`);
    revokeObjectURLMock = vi.fn();
    URL.createObjectURL = createObjectURLMock as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURLMock as unknown as typeof URL.revokeObjectURL;
  });

  afterEach(() => {
    cleanup();
  });

  it('loads saved visit files on open and renders authorized blob previews', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'], title: 'photo-1.jpg' },
        { id: 2, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'before'], title: 'photo-2.jpg' },
        { id: 3, mime_type: 'application/pdf', tags: ['dermatology', 'report'] }, // не изображение — скрыто
      ]);
      if (url === '/files/1/preview' || url === '/files/2/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);

    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 42, visit_id: 900, size: 100 } });
    });
    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/1/preview', { responseType: 'blob' });
      expect(apiState.get).toHaveBeenCalledWith('/files/2/preview', { responseType: 'blob' });
    });
    // Активная категория «осмотр»: виден один img (id 1); id 2 — категория «до»
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_category_before' }));
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });
    // PDF-файл не попадает в галерею
    expect(apiState.get).not.toHaveBeenCalledWith('/files/3/preview', expect.anything());
  });

  it('groups photos by tag category and switches between examination/before/after', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
        { id: 2, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'before'] },
        { id: 3, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'after'] },
        { id: 4, mime_type: 'image/jpeg', tags: ['other'] }, // без тега категории → осмотр
      ]);
      if (/^\/files\/\d+\/preview$/.test(url)) return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);

    await waitFor(() => {
      // осмотр: id 1 + id 4 (без категории)
      expect(screen.getAllByRole('img').length).toBe(2);
    });

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_category_before' }));
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_category_after' }));
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });
  });

  it('uploads a photo through /files/upload with visit binding, private permission and category tags', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([]);
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockResolvedValue({ data: { id: 7 } });

    render(<DermaVisitGallery patientId={42} visitId={900} />);

    const input = screen.getByLabelText('derma.derma_gallery_upload_aria') as HTMLInputElement;
    const file = new File(['synthetic'], 'skin.jpg', { type: 'image/jpeg' });
    fireEvent.change(input, { target: { files: fileList([file]) } });

    await waitFor(() => {
      expect(apiState.post).toHaveBeenCalledTimes(1);
    });
    const [url, body, config] = apiState.post.mock.calls[0] as [string, FormData, { headers: Record<string, string> }];
    expect(url).toBe('/files/upload');
    expect(body.get('patient_id')).toBe('42');
    expect(body.get('visit_id')).toBe('900');
    expect(body.get('permission')).toBe('private');
    expect(body.get('tags')).toBe('dermatology,photo,examination');
    expect(config.headers['Content-Type']).toBe('multipart/form-data');
    // После успешной загрузки список перечитывается
    await waitFor(() => {
      expect(apiState.get.mock.calls.filter((call: unknown[]) => call[0] === '/files/').length).toBeGreaterThanOrEqual(2);
    });
    // Загрузка НЕ запускает AI-анализ
    expect(apiState.post).toHaveBeenCalledTimes(1);
    expect(url).not.toContain('/ai/');
  });

  it('uploads into the selected category', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([]);
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockResolvedValue({ data: { id: 8 } });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_category_after' }));

    const input = screen.getByLabelText('derma.derma_gallery_upload_aria') as HTMLInputElement;
    fireEvent.change(input, { target: { files: fileList([new File(['synthetic'], 'after.jpg', { type: 'image/jpeg' })]) } });

    await waitFor(() => {
      expect(apiState.post).toHaveBeenCalledTimes(1);
    });
    const [, body] = apiState.post.mock.calls[0] as [string, FormData];
    expect(body.get('tags')).toBe('dermatology,photo,after');
  });

  it('deletes a photo and refreshes the list', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
      ]);
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.delete.mockResolvedValue({ data: { success: true } });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' }));
    await waitFor(() => {
      expect(apiState.delete).toHaveBeenCalledWith('/files/5');
    });
    await waitFor(() => {
      expect(apiState.get.mock.calls.filter((call: unknown[]) => call[0] === '/files/').length).toBeGreaterThanOrEqual(2);
    });
  });

  it('revokes object urls and reloads when the patient or visit changes', async () => {
    let filesById: Record<number, Array<Record<string, unknown>>> = {
      42: [{ id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] }],
    };
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') {
        const pid = Number(new URLSearchParams().get('x')); // always null — params приходят в config
        void pid;
        return listResponse(filesById[42] ?? []);
      }
      if (/^\/files\/\d+\/preview$/.test(url)) return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    const { rerender } = render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(revokeObjectURLMock).not.toHaveBeenCalled();
      expect(screen.getByRole('img')).toBeTruthy();
    });

    // Смена пациента: старые objectURL освобождаются, галерея перезагружается
    filesById = { 42: [] };
    rerender(<DermaVisitGallery patientId={77} visitId={901} />);
    await waitFor(() => {
      expect(revokeObjectURLMock).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 77, visit_id: 901, size: 100 } });
    });
  });

  it('shows an error state with retry when the list request fails', async () => {
    apiState.get.mockRejectedValueOnce(new Error('network down'));
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([]);
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_retry' }));
    await waitFor(() => {
      expect(apiState.get.mock.calls.filter((call: unknown[]) => call[0] === '/files/').length).toBeGreaterThanOrEqual(2);
    });
  });

  it('keeps the gallery usable when a preview request fails', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
      ]);
      if (url === '/files/1/preview') throw new Error('preview unavailable');
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    // Карточка файла остаётся с заглушкой, состояние ошибки не блокирует галерею
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' })).toBeTruthy();
    });
    expect(screen.queryByRole('img')).toBeNull();
  });
});
