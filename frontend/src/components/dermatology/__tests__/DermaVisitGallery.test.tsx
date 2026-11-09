/**
 * DermaVisitGallery — тесты галереи фото текущего визита (пункт 8 плана аудита).
 *
 * Контракт:
 * - /files — единственный источник фото: список GET /files/?patient_id&visit_id
 *   (доменный предикат dermatology+photo+file_type=image применяется сервером
 *   в derma-ветке; клиентский MIME-фильтр — вторая линия),
 *   превью — авторизованный blob-запрос GET /files/{id}/preview;
 * - пагинация по серверному контракту FileList (follow-up P2-2): первая
 *   страница — при открытии (page: 1), следующие — кнопкой «Показать ещё»
 *   (page: N+1) с аппендом без дублей; кнопка исчезает, когда загружено всё;
 * - категории осмотр/до/после берутся из тегов файла;
 * - загрузка сохранённых файлов при открытии, objectURL освобождаются при смене
 *   пациента/визита и размонтировании;
 * - загрузка (upload) не запускает AI-анализ;
 * - удаление через DELETE /files/{id} со сбросом списка.
 *
 * Регрессии аудита 3892 (fail-first):
 * - DERMAGALLERY-FE-001: смена пациента/визита синхронно убирает старые
 *   карточки/действия до разрешения нового GET;
 * - DERMAGALLERY-FE-002: позднее завершение upload/delete из A не перечитывает
 *   и не перезаписывает галерею под B;
 * - DERMAGALLERY-FE-003: застрявший loadingMore сбрасывается при смене контекста;
 * - DERMAGALLERY-FE-004: пагинация доступна и в пустой локально категории;
 * - DERMAGALLERY-FE-005: частично успешная загрузка перечитывает список и
 *   честно сообщает о частичном результате;
 * - DERMAGALLERY-FE-006: DELETE только со второго явного подтверждения;
 * - DERMAGALLERY-FE-007: зависшее превью не блокирует остальные превью и
 *   пагинацию; кнопка «Показать ещё» честно отключена во время загрузки;
 * - DERMAAI-FE-001: поздний AI-ответ после смены контекста не показывается;
 * - DERMAAI-FE-002: HTTP 200 с каноническим status='error' — ошибка, не успех;
 * - DERMAAI-FE-004: подсказка AI удалённого файла исчезает и не «воскрешается»;
 * - DERMAAI-FE-005: панель подсказки называет фото-источник при смене категории.
 */
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import notify from '../../../services/notify';

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

function listResponse(files: Array<Record<string, unknown>>, total?: number) {
  return { data: { files, total: total ?? files.length } };
}

/** Отложенный ответ: позволяет разрешать запросы в контролируемом порядке. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => { resolve = res; });
  return { promise, resolve };
}

/** Параметры GET /files/ конкретного пациента (для стражей контекста). */
function listCallsFor(patientId: number): Array<unknown[]> {
  return apiState.get.mock.calls.filter((call: unknown[]) =>
    call[0] === '/files/' && (call[1] as { params?: { patient_id?: number } } | undefined)?.params?.patient_id === patientId);
}

describe('DermaVisitGallery', () => {
  let createObjectURLMock: ReturnType<typeof vi.fn>;
  let revokeObjectURLMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    apiState.get.mockReset();
    apiState.post.mockReset();
    apiState.delete.mockReset();
    vi.mocked(notify.success).mockReset();
    vi.mocked(notify.error).mockReset();
    vi.mocked(notify.warning).mockReset();
    vi.mocked(notify.info).mockReset();
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
        { id: 3, mime_type: 'application/pdf', tags: ['dermatology', 'report'] }, // не изображение — скрыто (MIME-фильтр — вторая линия)
      ]);
      if (url === '/files/1/preview' || url === '/files/2/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);

    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 42, visit_id: 900, size: 100, page: 1 } });
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
        { id: 4, mime_type: 'image/jpeg', tags: ['dermatology', 'photo'] }, // без тега категории (сервер такие отдаёт) → осмотр
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

  it('deletes a photo only after an explicit confirmation and refreshes the list (DERMAGALLERY-FE-006)', async () => {
    let files = [
      { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
    ];
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse(files);
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.delete.mockResolvedValue({ data: { success: true } });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    // Первый клик только взводит подтверждение: DELETE не уходит
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' }));
    expect(apiState.delete).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'derma.derma_gallery_delete_confirm_yes' })).toBeTruthy();

    // Явное подтверждение выполняет DELETE
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_confirm_yes' }));
    await waitFor(() => {
      expect(apiState.delete).toHaveBeenCalledWith('/files/5');
    });
    files = [];
    await waitFor(() => {
      expect(apiState.get.mock.calls.filter((call: unknown[]) => call[0] === '/files/').length).toBeGreaterThanOrEqual(2);
    });
  });

  it('canceling the delete confirmation never sends DELETE (DERMAGALLERY-FE-006)', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
      ]);
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' }));
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_cancel' }));

    // Подтверждение снято, DELETE не было, фото осталось
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'derma.derma_gallery_delete_confirm_yes' })).toBeNull();
    });
    expect(apiState.delete).not.toHaveBeenCalled();
    expect(screen.getByRole('img')).toBeTruthy();
  });

  it('appends the next page without duplicates and hides the button when everything is loaded', async () => {
    let page = 1;
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') {
        if (page === 1) {
          return { data: { files: [
            { id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
            { id: 2, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          ], total: 3 } };
        }
        // Страница 2: id 2 повторяется (сдвиг границы страницы) + новое id 3
        return { data: { files: [
          { id: 2, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          { id: 3, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
        ], total: 3 } };
      }
      if (/^\/files\/\d+\/preview$/.test(url)) return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(2);
    });

    // total(3) > загружено(2): кнопка следующей страницы видна
    const loadMoreButton = screen.getByRole('button', { name: 'derma.derma_gallery_load_more' });
    page = 2;
    fireEvent.click(loadMoreButton);

    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 42, visit_id: 900, size: 100, page: 2 } });
    });
    // Аппенд без дублей: 1, 2, 3 — ровно три карточки
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(3);
    });
    // Всё загружено (3 из 3): кнопка исчезает
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'derma.derma_gallery_load_more' })).toBeNull();
    });
  });

  it('keeps the gallery usable when loading the next page fails', async () => {
    let page = 1;
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') {
        if (page === 1) {
          return { data: { files: [
            { id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          ], total: 2 } };
        }
        throw new Error('page 2 unavailable');
      }
      if (url === '/files/1/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    page = 2;
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' }));

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('derma.derma_gallery_load_more_failed');
    });
    // Ошибка подгрузки не ломает галерею: фото доступно, error-состояния нет,
    // кнопка остаётся для повторной попытки
    expect(screen.getByRole('img')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' })).toBeTruthy();
  });

  it('revokes object urls and reloads when the patient or visit changes', async () => {
    let filesById: Record<number, Array<Record<string, unknown>>> = {
      42: [{ id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] }],
    };
    apiState.get.mockImplementation(async (url: string, config?: { params?: { patient_id?: number } }) => {
      if (url === '/files/') {
        return listResponse(filesById[config?.params?.patient_id ?? 42] ?? []);
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
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 77, visit_id: 901, size: 100, page: 1 } });
    });
  });

  it('clears the previous patient\'s photos and actions synchronously before the new list resolves (DERMAGALLERY-FE-001)', async () => {
    const bList = deferred<{ data: { files: Array<Record<string, unknown>>; total: number } }>();
    apiState.get.mockImplementation(async (url: string, config?: { params?: { patient_id?: number } }) => {
      if (url === '/files/') {
        if (config?.params?.patient_id === 77) return bList.promise;
        return listResponse([
          { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'], title: 'a-photo.jpg' },
        ]);
      }
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    const { rerender } = render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    // Смена контекста: GET пациента B подвешен — старые карточки и действия A
    // уже недоступны, галерея в состоянии загрузки B.
    rerender(<DermaVisitGallery patientId={77} visitId={901} />);
    await waitFor(() => {
      expect(screen.queryByRole('img')).toBeNull();
      expect(screen.queryByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' })).toBeNull();
      expect(screen.getByText('derma.derma_gallery_loading')).toBeTruthy();
    });

    bList.resolve({ data: { files: [], total: 0 } });
    await waitFor(() => {
      expect(screen.queryByText('derma.derma_gallery_loading')).toBeNull();
      expect(screen.getByText('derma.derma_gallery_empty')).toBeTruthy();
    });
  });

  it('does not let a late upload completion from patient A refresh the list under patient B (DERMAGALLERY-FE-002)', async () => {
    const uploadPost = deferred<{ data: { id: number } }>();
    apiState.get.mockImplementation(async (url: string, config?: { params?: { patient_id?: number } }) => {
      if (url === '/files/') {
        if (config?.params?.patient_id === 42) {
          return listResponse([
            { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          ]);
        }
        return listResponse([]);
      }
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockImplementation(async () => uploadPost.promise);

    const { rerender } = render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    // Начата загрузка файла под A; POST подвешен.
    const input = screen.getByLabelText('derma.derma_gallery_upload_aria') as HTMLInputElement;
    fireEvent.change(input, { target: { files: fileList([new File(['synthetic'], 'a.jpg', { type: 'image/jpeg' })]) } });

    // Пациент сменился на B, список B разрешился пустым.
    rerender(<DermaVisitGallery patientId={77} visitId={901} />);
    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 77, visit_id: 901, size: 100, page: 1 } });
    });
    await waitFor(() => {
      expect(screen.getByText('derma.derma_gallery_empty')).toBeTruthy();
    });

    // Позднее завершение POST'а A: перезагрузки списка A под B не происходит.
    uploadPost.resolve({ data: { id: 9 } });
    await new Promise((resolve) => { setTimeout(resolve, 30); });
    expect(listCallsFor(42).length).toBe(1);
    expect(screen.getByText('derma.derma_gallery_empty')).toBeTruthy();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('does not let a late delete completion from patient A refresh the list under patient B (DERMAGALLERY-FE-002)', async () => {
    const deleteRequest = deferred<{ data: { success: boolean } }>();
    apiState.get.mockImplementation(async (url: string, config?: { params?: { patient_id?: number } }) => {
      if (url === '/files/') {
        if (config?.params?.patient_id === 42) {
          return listResponse([
            { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          ]);
        }
        return listResponse([]);
      }
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.delete.mockImplementation(async () => deleteRequest.promise);

    const { rerender } = render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    // Двухшаговое удаление: взводим и подтверждаем — DELETE подвешен.
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' }));
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_confirm_yes' }));
    await waitFor(() => {
      expect(apiState.delete).toHaveBeenCalledWith('/files/5');
    });

    rerender(<DermaVisitGallery patientId={77} visitId={901} />);
    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 77, visit_id: 901, size: 100, page: 1 } });
    });

    deleteRequest.resolve({ data: { success: true } });
    await new Promise((resolve) => { setTimeout(resolve, 30); });
    expect(listCallsFor(42).length).toBe(1);
  });

  it('re-enables Load More for the next patient after a stale page request (DERMAGALLERY-FE-003)', async () => {
    const stalePage = deferred<{ data: { files: Array<Record<string, unknown>>; total: number } }>();
    apiState.get.mockImplementation(async (url: string, config?: { params?: { patient_id?: number; page?: number } }) => {
      if (url === '/files/') {
        if (config?.params?.patient_id === 42) {
          if (config?.params?.page === 2) return stalePage.promise;
          return { data: { files: [
            { id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
            { id: 2, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          ], total: 5 } };
        }
        // Пациент B: первая страница уже длиннее одной карточки
        return { data: { files: Array.from({ length: 10 }, (_, i) => ({
          id: 100 + i, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'],
        })), total: 25 } };
      }
      if (/^\/files\/\d+\/preview$/.test(url)) return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    const { rerender } = render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(2);
    });

    // Страница 2 пациента A запрошена и подвешена (loadingMore=true).
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' }));
    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 42, visit_id: 900, size: 100, page: 2 } });
    });

    // Смена на B: флаг постраничной загрузки сброшен, кнопка доступна.
    rerender(<DermaVisitGallery patientId={77} visitId={901} />);
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(10);
    });
    const loadMoreButton = screen.getByRole('button', { name: 'derma.derma_gallery_load_more' }) as HTMLButtonElement;
    expect(loadMoreButton.disabled).toBe(false);

    // Поздняя страница A игнорируется: список B не загрязняется чужими рядами,
    // кнопка остаётся доступной.
    stalePage.resolve({ data: { files: [
      { id: 3, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
    ], total: 5 } });
    await new Promise((resolve) => { setTimeout(resolve, 30); });
    expect(screen.getAllByRole('img').length).toBe(10);
    expect((screen.getByRole('button', { name: 'derma.derma_gallery_load_more' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('keeps pagination reachable when the selected category is locally empty (DERMAGALLERY-FE-004)', async () => {
    let page = 1;
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') {
        if (page === 1) {
          // Первая страница — только фото осмотра; total больше: страница 2
          // содержит фото категории «до».
          return { data: { files: [
            { id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          ], total: 2 } };
        }
        return { data: { files: [
          { id: 2, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'before'], title: 'before-page2.jpg' },
        ], total: 2 } };
      }
      if (/^\/files\/\d+\/preview$/.test(url)) return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    // Пустая локально категория «до»: честное сообщение И доступная пагинация.
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_category_before' }));
    await waitFor(() => {
      expect(screen.getByText('derma.derma_gallery_empty_category')).toBeTruthy();
    });
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' })).toBeTruthy();

    // Страница 2 подтягивает фото «до» — оно становится видимым.
    page = 2;
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' }));
    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/', { params: { patient_id: 42, visit_id: 900, size: 100, page: 2 } });
    });
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'derma.derma_gallery_load_more' })).toBeNull();
    });
  });

  it('reloads the list and reports partial success when some uploads fail (DERMAGALLERY-FE-005)', async () => {
    let uploaded = false;
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') {
        if (uploaded) {
          return listResponse([
            { id: 9, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'], title: 'a.jpg' },
          ]);
        }
        return listResponse([]);
      }
      if (url === '/files/9/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockImplementation(async (_url: string, formData: FormData) => {
      const name = String(formData.get('file') instanceof File ? (formData.get('file') as File).name : '');
      if (name === 'a.jpg') {
        uploaded = true;
        return { data: { id: 9 } };
      }
      throw new Error('upload rejected');
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByText('derma.derma_gallery_empty')).toBeTruthy();
    });

    const input = screen.getByLabelText('derma.derma_gallery_upload_aria') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: fileList([
        new File(['synthetic'], 'a.jpg', { type: 'image/jpeg' }),
        new File(['synthetic'], 'b.jpg', { type: 'image/jpeg' }),
      ]) },
    });

    // Частичный результат: предупреждение вместо «успеха», список перечитан,
    // успешно сохранённый файл виден.
    await waitFor(() => {
      expect(notify.warning).toHaveBeenCalledWith('derma.derma_gallery_upload_partial');
    });
    expect(notify.success).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });
    await waitFor(() => {
      expect(apiState.get.mock.calls.filter((call: unknown[]) => call[0] === '/files/').length).toBeGreaterThanOrEqual(2);
    });
  });

  it('does not block other previews or the Load More button while one preview hangs (DERMAGALLERY-FE-007)', async () => {
    const hanging = deferred<{ data: Blob }>();
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') {
        return { data: { files: [
          { id: 1, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          { id: 2, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
        ], total: 3 } };
      }
      if (url === '/files/1/preview') return hanging.promise;
      if (url === '/files/2/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);

    // Превью файла 2 доступно, хотя превью файла 1 зависло: запросы идут
    // параллельно, карточка 1 остаётся с заглушкой.
    await waitFor(() => {
      expect(apiState.get).toHaveBeenCalledWith('/files/2/preview', { responseType: 'blob' });
    });
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });

    // Загрузка списка завершена despite зависшее превью: пагинация доступна
    // и честно включена (total=3 > загружено=2).
    const loadMoreButton = screen.getByRole('button', { name: 'derma.derma_gallery_load_more' }) as HTMLButtonElement;
    expect(loadMoreButton.disabled).toBe(false);

    hanging.resolve({ data: imageBlob });
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(2);
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

  it('runs AI analysis only on click with {visit_id, file_id} and shows the suggestion', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
      ]);
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockImplementation(async (url: string) => {
      if (url === '/ai/v2/analyze-skin-file') {
        return {
          data: {
            status: 'success',
            data: { content: 'SYNTHETIC suggestion' },
            provider: 'mock',
            ai_notice: 'AI suggestions are advisory only',
            requires_doctor_confirmation: true,
            decision_boundary: 'suggestion_only',
          },
        };
      }
      throw new Error(`unexpected POST ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });
    // До клика анализа нет
    expect(apiState.post).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_ai_button_aria:derma.derma_gallery_category_examination' }));
    await waitFor(() => {
      expect(apiState.post).toHaveBeenCalledTimes(1);
      expect(apiState.post).toHaveBeenCalledWith('/ai/v2/analyze-skin-file', { visit_id: 900, file_id: 5 });
    });
    await waitFor(() => {
      expect(screen.getByText('SYNTHETIC suggestion')).toBeTruthy();
      expect(screen.getByText('derma.derma_gallery_ai_confirmation')).toBeTruthy();
      expect(screen.getByText('AI suggestions are advisory only')).toBeTruthy();
    });
    // DERMAAI-FE-005: панель называет фото-источник подсказки — атрибуция
    // задана именем фото-источника (#5: файл без title).
    expect(screen.getByText('#5')).toBeTruthy();
  });

  it('keeps photos accessible when AI analysis fails with 503', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
      ]);
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockRejectedValueOnce(new Error('503 feature disabled'));

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_ai_button_aria:derma.derma_gallery_category_examination' }));
    await waitFor(() => {
      expect(screen.getByText('derma.derma_gallery_ai_error')).toBeTruthy();
    });
    // Фото остаётся доступным после ошибки/503
    expect(screen.getByRole('img')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' })).toBeTruthy();
  });

  it('treats HTTP 200 with canonical status="error" as an analysis error, not a success (DERMAAI-FE-002)', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
      ]);
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    // Бэкенд-контракт: gateway-ошибка возвращается HTTP 200 со status='error'.
    apiState.post.mockResolvedValueOnce({
      data: { status: 'error', ai_notice: 'AI gateway degraded', data: {} },
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_ai_button_aria:derma.derma_gallery_category_examination' }));

    await waitFor(() => {
      expect(screen.getByText('derma.derma_gallery_ai_error')).toBeTruthy();
    });
    // Панель успеха не показывается
    expect(screen.queryByText('derma.derma_gallery_ai_confirmation')).toBeNull();
    expect(screen.queryByText('derma.derma_gallery_ai_empty')).toBeNull();
    // Фото остаётся доступным
    expect(screen.getByRole('img')).toBeTruthy();
  });

  it('discards a late AI response after the patient context switch (DERMAAI-FE-001)', async () => {
    const analyze = deferred<{ data: { status: string; data: { content: string } } }>();
    apiState.get.mockImplementation(async (url: string, config?: { params?: { patient_id?: number } }) => {
      if (url === '/files/') {
        if (config?.params?.patient_id === 42) {
          return listResponse([
            { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
          ]);
        }
        return listResponse([]);
      }
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockImplementation(async () => analyze.promise);

    const { rerender } = render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    // Запрос анализа A отправлен и подвешен (панель «Анализ…»).
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_ai_button_aria:derma.derma_gallery_category_examination' }));
    await waitFor(() => {
      expect(screen.getByText('derma.derma_gallery_ai_analyzing')).toBeTruthy();
    });

    // Смена контекста: анализ A сброшен вместе с остальным состоянием A.
    rerender(<DermaVisitGallery patientId={77} visitId={901} />);
    await waitFor(() => {
      expect(screen.queryByText('derma.derma_gallery_ai_analyzing')).toBeNull();
      expect(screen.getByText('derma.derma_gallery_empty')).toBeTruthy();
    });

    // Поздний ответ A не «воскрешает» подсказку под B.
    analyze.resolve({ data: { status: 'success', data: { content: 'A SUGGESTION' } } });
    await new Promise((resolve) => { setTimeout(resolve, 30); });
    expect(screen.queryByText('A SUGGESTION')).toBeNull();
    expect(screen.queryByText('derma.derma_gallery_ai_analyzing')).toBeNull();
  });

  it('clears the AI suggestion when its photo is deleted and never resurrects it (DERMAAI-FE-004)', async () => {
    const analyze = deferred<{ data: { status: string; data: { content: string } } }>();
    let files = [
      { id: 5, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] },
    ];
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse(files);
      if (url === '/files/5/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockImplementation(async () => analyze.promise);
    apiState.delete.mockResolvedValue({ data: { success: true } });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getByRole('img')).toBeTruthy();
    });

    // Анализ файла 5 запущен и подвешен.
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_ai_button_aria:derma.derma_gallery_category_examination' }));
    await waitFor(() => {
      expect(screen.getByText('derma.derma_gallery_ai_analyzing')).toBeTruthy();
    });

    // Файл удалён (двухшаговое подтверждение), список перечитан без файла.
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' }));
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_confirm_yes' }));
    files = [];
    await waitFor(() => {
      expect(apiState.delete).toHaveBeenCalledWith('/files/5');
      expect(screen.queryByRole('img')).toBeNull();
    });
    // Панель «Анализ…» исчезла вместе с фото
    await waitFor(() => {
      expect(screen.queryByText('derma.derma_gallery_ai_analyzing')).toBeNull();
    });

    // Поздний ответ AI по удалённому файлу не показывает подсказку.
    analyze.resolve({ data: { status: 'success', data: { content: 'LATE SUGGESTION' } } });
    await new Promise((resolve) => { setTimeout(resolve, 30); });
    expect(screen.queryByText('LATE SUGGESTION')).toBeNull();
    expect(screen.queryByText('derma.derma_gallery_ai_analyzing')).toBeNull();
  });

  it('labels the AI suggestion with its source photo across category switches (DERMAAI-FE-005)', async () => {
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse([
        { id: 11, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'], title: 'photo-11.jpg' },
        { id: 12, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'after'], title: 'photo-12.jpg' },
      ]);
      if (url === '/files/11/preview' || url === '/files/12/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.post.mockResolvedValueOnce({
      data: { status: 'success', data: { content: 'EXAMINATION PHOTO SUGGESTION' } },
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1); // категория «осмотр»: фото 11
    });

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_ai_button_aria:derma.derma_gallery_category_examination' }));
    await waitFor(() => {
      expect(screen.getByText('EXAMINATION PHOTO SUGGESTION')).toBeTruthy();
    });

    // Смена категории: показано фото 12, но подсказка явно приписана фото 11.
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_category_after' }));
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1); // категория «после»: фото 12
    });
    expect(screen.getByText('EXAMINATION PHOTO SUGGESTION')).toBeTruthy();
    expect(screen.getByText('photo-11.jpg')).toBeTruthy();
  });
});

describe('DermaVisitGallery — RETRO-3942-01 (post-merge review #3944)', () => {
  let createObjectURLMock: ReturnType<typeof vi.fn>;
  let revokeObjectURLMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    apiState.get.mockReset();
    apiState.post.mockReset();
    apiState.delete.mockReset();
    vi.mocked(notify.success).mockReset();
    vi.mocked(notify.error).mockReset();
    vi.mocked(notify.warning).mockReset();
    vi.mocked(notify.info).mockReset();
    createObjectURLMock = vi.fn((blob: Blob) => `blob:mock-${(blob as { size?: number }).size ?? 0}-${Math.random().toString(36).slice(2)}`);
    revokeObjectURLMock = vi.fn();
    URL.createObjectURL = createObjectURLMock as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURLMock as unknown as typeof URL.revokeObjectURL;
  });

  afterEach(() => {
    cleanup();
  });

  it('loading page 2 does not cancel pending page-1 previews — they attach when their responses arrive', async () => {
    let page = 1;
    // Страница 1: пять фото (больше PREVIEW_CONCURRENCY=4 — вторая пачка
    // превью стартует только после первой), total 7 → есть «Показать ещё».
    const page1 = [1, 2, 3, 4, 5].map((id) => ({
      id, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'], title: `photo-${id}.jpg`,
    }));
    const page2 = [6, 7].map((id) => ({
      id, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'], title: `photo-${id}.jpg`,
    }));

    // Превью файла 1 (первая пачка) подвешено до явного resolve.
    const file1Preview = deferred<{ data: Blob }>();
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') {
        return page === 1 ? { data: { files: page1, total: 7 } } : { data: { files: page2, total: 7 } };
      }
      if (url === '/files/1/preview') return file1Preview.promise;
      if (/^\/files\/\d+\/preview$/.test(url)) return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    // Карточки страницы 1 уже видны; превью первой пачки приходят сразу,
    // НО файл 5 (вторая пачка) ждёт подвешенное превью файла 1 из первой
    // пачки — сейчас видны 3 готовых превью (файлы 2, 3, 4).
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(3);
    });

    // «Показать ещё» ДО завершения превью файла 1 (аппенд того же списка).
    page = 2;
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_load_more' }));
    // Карточек стало 7; превью файлов 6 и 7 прикрепились сразу.
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(5);
    });

    // Поздний ответ превью файла 1 приходит ПОСЛЕ загрузки страницы 2 —
    // карточка файла 1 обязана получить свой blob-URL (заглушки больше нет).
    file1Preview.resolve({ data: imageBlob });
    await waitFor(() => {
      const imgs = screen.getAllByRole('img');
      expect(imgs.length).toBe(7);
      // Все семь карточек показывают настоящие blob-превью — ни одной заглушки.
      imgs.forEach((img) => {
        expect((img as HTMLImageElement).getAttribute('src')).toMatch(/^blob:mock-/);
      });
    });
    expect(createObjectURLMock).toHaveBeenCalledTimes(7);
  });

  it('a context switch still invalidates pending previews of the previous context', async () => {
    // Пациент A: превью подвешено; переключаемся на пациента B до его resolve.
    const patientAFiles = [1, 2].map((id) => ({
      id, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'],
    }));
    const patientBFiles = [{ id: 9, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] }];
    const fileA1Preview = deferred<{ data: Blob }>();
    const filesByPatient: Record<number, Array<Record<string, unknown>>> = { 42: patientAFiles, 77: patientBFiles };

    apiState.get.mockImplementation(async (url: string, config?: { params?: { patient_id?: number } }) => {
      if (url === '/files/') {
        return listResponse(filesByPatient[config?.params?.patient_id ?? 42] ?? []);
      }
      if (url === '/files/1/preview') return fileA1Preview.promise;
      if (url === '/files/2/preview' || url === '/files/9/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });

    const { rerender } = render(<DermaVisitGallery patientId={42} visitId={900} />);
    // Файл 2 с готовым превью; файл 1 — заглушка (его превью подвешено).
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });

    rerender(<DermaVisitGallery patientId={77} visitId={901} />);
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });
    const blobCallsForB = createObjectURLMock.mock.calls.length;

    // Поздние превью контекста A не создают blob-URL и не трогают карточки B.
    fileA1Preview.resolve({ data: imageBlob });
    await new Promise((resolve) => { setTimeout(resolve, 30); });
    expect(createObjectURLMock.mock.calls.length).toBe(blobCallsForB);
    expect(screen.getAllByRole('img').length).toBe(1);
    expect((screen.getByRole('img') as HTMLImageElement).getAttribute('src')).toMatch(/^blob:mock-/);
  });

  it('a full reload (new list generation) still supersedes pending append previews', async () => {
    // Страница 1 загружена; превью файла 1 подвешено; затем происходит полный
    // перезапуск списка (удаление файла → loadGallery) — превью старого
    // поколения не прикрепляется, новое поколение перезапрашивает свои.
    let files = [1, 2].map((id) => ({
      id, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'],
    }));
    const stalePreview = deferred<{ data: Blob }>();
    let stalePreviewTaken = false;
    apiState.get.mockImplementation(async (url: string) => {
      if (url === '/files/') return listResponse(files);
      if (url === '/files/1/preview') {
        if (!stalePreviewTaken) {
          stalePreviewTaken = true;
          return stalePreview.promise;
        }
        return { data: imageBlob };
      }
      if (url === '/files/2/preview') return { data: imageBlob };
      throw new Error(`unexpected GET ${url}`);
    });
    apiState.delete.mockResolvedValue({ data: { success: true } });

    render(<DermaVisitGallery patientId={42} visitId={900} />);
    // Файл 2 с готовым превью; файл 1 — заглушка (его превью подвешено).
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });

    // Удаляем файл 1 (двухшаговое подтверждение) — список перечитывается.
    // Файлов два — кнопка удаления первой карточки принадлежит файлу 1.
    fireEvent.click(screen.getAllByRole('button', { name: 'derma.derma_gallery_delete_aria:derma.derma_gallery_category_examination' })[0]);
    files = [{ id: 2, mime_type: 'image/jpeg', tags: ['dermatology', 'photo', 'examination'] }];
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_gallery_delete_confirm_yes' }));
    // Дожидаемся именно ПЕРЕЧИТЫВАНИЯ списка (второй GET /files/), чтобы
    // поздний resolve превью старого поколения точно шёл после нового
    // поколения, а не наперегонки с ним.
    await waitFor(() => {
      expect(apiState.delete).toHaveBeenCalledWith('/files/1');
      expect(apiState.get.mock.calls.filter((call) => call[0] === '/files/').length).toBe(2);
    });
    await waitFor(() => {
      expect(screen.getAllByRole('img').length).toBe(1);
    });

    // Поздний ответ превью удалённого файла не «воскрешает» карточку и не
    // создаёт лишний blob-URL.
    const callsAfterReload = createObjectURLMock.mock.calls.length;
    stalePreview.resolve({ data: imageBlob });
    await new Promise((resolve) => { setTimeout(resolve, 30); });
    expect(createObjectURLMock.mock.calls.length).toBe(callsAfterReload);
    expect(screen.getAllByRole('img').length).toBe(1);
  });
});
