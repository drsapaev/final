import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import QueueProfilesManager from '../QueueProfilesManager';
import { api } from '@/api/client';
import { notify } from '../../../services/notify';

// jsdom's File lacks .text(); real browsers have it. Polyfill via FileReader
// so the import handler reaches the code under test (test-only shim, the
// product keeps using the standard API).
if (typeof File !== 'undefined' && typeof File.prototype.text !== 'function') {
  File.prototype.text = function text(): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result ?? ''));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(this);
    });
  };
}

// RQ-26.a — CSV round-trip of the current queue-profile contract (F-22):
// export/import must preserve department_key/show_on_qr_page/tags, quoted
// commas/quotes/newlines must not shift columns, blocking issues abort before
// any API call. SYNTHETIC/DEV-DEMO fixtures only — synthetic domain
// identifiers, no PHI/PII values anywhere.

interface SyntheticQueueProfile {
  key: string;
  queue_tags: string[];
  [field: string]: unknown;
}

const syntheticProfiles: SyntheticQueueProfile[] = [
  {
    key: 'synthetic-cardio',
    title: 'Синтетическая кардио, взрослая',
    title_ru: 'Синтетическая кардиология',
    queue_tags: ['cardio', 'ekg'],
    department_key: 'cardiology',
    order: 3,
    is_active: true,
    show_on_qr_page: true,
    icon: 'Heart',
    color: '#E53E3E'
  },
  {
    key: 'synthetic-lab',
    title: 'Синтетическая лаборатория "Тест"',
    title_ru: 'Синтетическая лаборатория',
    queue_tags: ['lab'],
    department_key: null,
    order: 0,
    is_active: false,
    show_on_qr_page: false,
    icon: 'TestTube',
    color: '#718096'
  }
];

vi.mock('../../../api/client', () => {
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url.startsWith('/queues/profiles')) {
        return Promise.resolve({ data: { profiles: [...syntheticProfiles] } });
      }

      if (url === '/admin/departments') {
        return Promise.resolve({ data: { data: [{ key: 'cardiology', name_ru: 'Синтетическое отделение' }] } });
      }

      return Promise.resolve({ data: { data: [] } });
    }),
    post: vi.fn(() => Promise.resolve({ data: { success: true } })),
    put: vi.fn(() => Promise.resolve({ data: { success: true } })),
    delete: vi.fn()
  };

  return {
    default: apiMock,
    api: apiMock,
    apiClient: apiMock
  };
});

vi.mock('../../../services/notify', () => ({
  notify: {
    success: vi.fn(),
    warning: vi.fn()
  }
}));

const newFormatCsv = [
  'key,title,title_ru,queue_tags,department_key,icon,color,display_order,is_active,show_on_qr_page',
  '"synthetic-cardio","Синтетическая кардио, взрослая обновлённая","Синтетическая кардиология","cardio;ekg","cardiology","Heart","#E53E3E","3","true","true"',
  '"synthetic-new","Синтетическая новая вкладка","Синтетическая новая","derma",,,"","7","true","false"'
].join('\n');

const oldFormatCsv = [
  'key,title,title_ru,queue_tags,icon,color,display_order,is_active',
  '"synthetic-cardio","Синтетическая кардио","Синтетическая кардиология","cardio;ekg","Heart","#E53E3E","3","false"'
].join('\n');

const capturedBlobs: Blob[] = [];
const capturedBlobTexts: string[] = [];
const baselineSyntheticProfiles = syntheticProfiles.map((profile) => ({ ...profile, queue_tags: [...profile.queue_tags] }));
const defaultGetImplementation = (api.get as ReturnType<typeof vi.fn>).getMockImplementation();

// jsdom has no URL.createObjectURL/revokeObjectURL and its Blob lacks .text()
// — stub Blob + URL.assign directly (vi.restoreAllMocks would also reset the
// global matchMedia mock from src/test/setup.ts, so stubs are restored
// explicitly below instead).
const originalCreateObjectURL = (globalThis.URL as unknown as Record<string, unknown>).createObjectURL;
const originalRevokeObjectURL = (globalThis.URL as unknown as Record<string, unknown>).revokeObjectURL;
const originalBlob = globalThis.Blob;
let anchorClickSpy: ReturnType<typeof vi.spyOn> | null = null;

const mockDownload = () => {
  capturedBlobs.length = 0;
  capturedBlobTexts.length = 0;
  const urlLike = globalThis.URL as unknown as Record<string, unknown>;
  urlLike.createObjectURL = (blob: Blob) => {
    capturedBlobs.push(blob);
    return 'blob:mock-export';
  };
  urlLike.revokeObjectURL = () => {};
  class MockBlob {
    parts: string[];
    type: string;
    constructor(parts: BlobPart[], options?: { type?: string }) {
      this.parts = parts.map((p) => (typeof p === 'string' ? p : ''));
      this.type = options?.type || '';
      capturedBlobTexts.push(this.parts.join(''));
    }
  }
  globalThis.Blob = MockBlob as unknown as typeof Blob;
  anchorClickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
};

const restoreDownload = () => {
  const urlLike = globalThis.URL as unknown as Record<string, unknown>;
  if (originalCreateObjectURL === undefined) {
    delete urlLike.createObjectURL;
  } else {
    urlLike.createObjectURL = originalCreateObjectURL;
  }
  if (originalRevokeObjectURL === undefined) {
    delete urlLike.revokeObjectURL;
  } else {
    urlLike.revokeObjectURL = originalRevokeObjectURL;
  }
  globalThis.Blob = originalBlob;
  anchorClickSpy?.mockRestore();
  anchorClickSpy = null;
};

const renderManager = async () => {
  const view = render(
    <ThemeProvider>
      <QueueProfilesManager />
    </ThemeProvider>
  );

  await waitFor(() => {
    expect(api.get).toHaveBeenCalledWith('/queues/profiles?active_only=false');
  });
  await waitFor(() => {
    expect(screen.getByText('Синтетическая кардио, взрослая')).toBeInTheDocument();
  });
  return view;
};

const uploadCsv = async (text: string, confirmPreview = true) => {
  const user = userEvent.setup();
  const input = screen.getByLabelText('Импортировать профили очереди из CSV');
  await user.upload(input, new File([text], 'profiles.csv', { type: 'text/csv' }));
  if (confirmPreview) {
    const preview = await screen.findByRole('dialog', { name: 'Предварительный просмотр импорта CSV' });
    await user.click(within(preview).getByRole('button', { name: 'Импортировать' }));
  }
  return user;
};

afterEach(() => {
  vi.clearAllMocks();
  if (defaultGetImplementation) (api.get as ReturnType<typeof vi.fn>).mockImplementation(defaultGetImplementation);
  restoreDownload();
  window.sessionStorage.removeItem('admin.queueProfiles.pendingCsvPublication.v1');
  syntheticProfiles.splice(0, syntheticProfiles.length, ...baselineSyntheticProfiles.map((profile) => ({ ...profile, queue_tags: [...profile.queue_tags] })));
});

describe('QueueProfilesManager CSV export (RQ-26.a)', () => {
  it('exports the full current contract including department_key and show_on_qr_page', async () => {
    mockDownload();
    expect(capturedBlobs.length).toBe(0);
    await renderManager();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Экспорт' }));

    await waitFor(() => {
      expect(capturedBlobs.length).toBe(1);
    });

    const text = capturedBlobTexts[0];
    const headerLine = text.split('\n')[0];
    expect(headerLine).toBe(
      'key,title,title_ru,queue_tags,department_key,icon,color,display_order,is_active,show_on_qr_page'
    );
  });

  it('keeps quoted commas, quotes and the display_order value intact in the export', async () => {
    mockDownload();
    expect(capturedBlobs.length).toBe(0);
    await renderManager();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Экспорт' }));

    await waitFor(() => {
      expect(capturedBlobs.length).toBe(1);
    });

    const text = capturedBlobTexts[0];
    // The comma inside the quoted title must survive the round-trip row.
    expect(text).toContain('"Синтетическая кардио, взрослая"');
    // The escaped inner quotes must survive as "" doubled form.
    expect(text).toContain('"Синтетическая лаборатория ""Тест"""');
    // display_order value comes from the API contract field (order alias).
    expect(text).toContain('"3"');
    // Inactive and QR-hidden flags must be written explicitly.
    expect(text).toContain('"synthetic-lab"');
    expect(text).toContain('"false"');
  });
});

describe('QueueProfilesManager CSV import (RQ-26.a)', () => {
  it('updates an existing profile with every contract field preserved (round-trip)', async () => {
    await renderManager();
    await uploadCsv(newFormatCsv);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        '/queues/profiles/synthetic-cardio',
        expect.objectContaining({
          key: 'synthetic-cardio',
          title: 'Синтетическая кардио, взрослая обновлённая',
          title_ru: 'Синтетическая кардиология',
          queue_tags: ['cardio', 'ekg'],
          department_key: 'cardiology',
          display_order: 3,
          is_active: true,
          show_on_qr_page: true
        })
      );
    });

    // The row without an existing key goes through create, with typed fields.
    expect(api.post).toHaveBeenCalledWith(
      '/queues/profiles',
      expect.objectContaining({
        key: 'synthetic-new',
        title: 'Синтетическая новая вкладка',
        queue_tags: ['derma'],
        display_order: 7,
        is_active: true,
        show_on_qr_page: false
      })
    );
  });

  it('does not wipe omitted contract fields when importing an old-format file', async () => {
    await renderManager();
    await uploadCsv(oldFormatCsv);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        '/queues/profiles/synthetic-cardio',
        expect.objectContaining({ title: 'Синтетическая кардио', is_active: false })
      );
    });

    const payload = (api.put as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    // The backend PUT uses exclude_unset=True: omitted keys keep stored values.
    expect(payload).not.toHaveProperty('department_key');
    expect(payload).not.toHaveProperty('show_on_qr_page');
  });

  it('reports an already matching CSV row as unchanged and avoids a write', async () => {
    const matchingCsv = [
      'key,title,title_ru,queue_tags,department_key,icon,color,display_order,is_active,show_on_qr_page',
      'synthetic-cardio,"Синтетическая кардио, взрослая",Синтетическая кардиология,cardio;ekg,cardiology,Heart,#E53E3E,3,true,true',
    ].join('\n');
    await renderManager();
    await uploadCsv(matchingCsv);

    const results = screen.getByRole('region', { name: 'Результаты операции' });
    const row = within(results).getByRole('listitem');
    expect(row).toHaveTextContent('Выполнено');
    expect(row).toHaveTextContent('Нужное состояние уже сохранено; повторная запись не требовалась.');
    expect(api.put).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
    expect(notify.success).toHaveBeenCalledWith(expect.stringContaining('уже соответствовали 1'));
  });

  it('warns when a CSV-created profile requested for QR remains hidden until explicit publication', async () => {
    const requestedPublicProfileCsv = [
      'key,title,title_ru,queue_tags,department_key,icon,color,display_order,is_active,show_on_qr_page',
      '"synthetic-neurology","Синтетическая неврология","Синтетическая неврология","neuro",,,"#718096","1","true","true"'
    ].join('\n');
    (api.post as ReturnType<typeof vi.fn>).mockImplementationOnce((_url: string, payload: Record<string, unknown>) => {
      syntheticProfiles.push({ ...payload, key: String(payload.key), queue_tags: payload.queue_tags as string[], show_on_qr_page: false });
      return Promise.resolve({ data: { success: true, publication_deferred: true } });
    });

    const { unmount } = await renderManager();
    await uploadCsv(requestedPublicProfileCsv);

    await waitFor(() => {
      expect(notify.warning).toHaveBeenCalledTimes(1);
    });
    const warningMessage = (notify.warning as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(warningMessage).toContain('они пока скрыты');
    expect(warningMessage).toContain('опубликуйте отдельно');
    expect(warningMessage).toContain('создано 1');
    expect(notify.warning).toHaveBeenCalledWith(warningMessage, { autoClose: 8000 });
    expect(notify.success).not.toHaveBeenCalled();
    expect(api.post).toHaveBeenCalledWith('/queues/profiles', expect.objectContaining({
      key: 'synthetic-neurology',
      show_on_qr_page: false
    }));
    expect(api.put).not.toHaveBeenCalled();
    expect(await screen.findByRole('button', { name: 'Проверить QR-настройку synthetic-neurology' })).toBeInTheDocument();
    expect(window.sessionStorage.getItem('admin.queueProfiles.pendingCsvPublication.v1')).toContain('synthetic-neurology');
    unmount();
    await renderManager();
    expect(await screen.findByRole('button', { name: 'Проверить QR-настройку synthetic-neurology' })).toBeInTheDocument();
  });

  it('aborts the whole import with a visible error when the file has duplicate keys', async () => {
    const duplicatedRow = '"synthetic-cardio","Дубль синтетической вкладки","","","","","","","","false"';
    const duplicated = `${newFormatCsv}\n${duplicatedRow}\n`;
    await renderManager();
    await uploadCsv(duplicated, false);

    await waitFor(() => {
      expect(screen.getByText(/Импорт отменён|найдено проблем/i)).toBeInTheDocument();
    });
    expect(api.put).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('reports per-profile API failures instead of silently dropping them', async () => {
    (api.post as ReturnType<typeof vi.fn>).mockImplementationOnce(() =>
      Promise.reject(new Error('synthetic network failure'))
    );

    await renderManager();
    await uploadCsv(newFormatCsv);

    await waitFor(() => {
      expect(screen.getAllByText(/Отклонено/)).toHaveLength(2);
    });
    // The create call happened exactly once and failed (mocked rejection);
    // the existing profile still went through the update path.
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.put).toHaveBeenCalledTimes(1);
  });

  it('shows per-row outcomes after partial import and retries only refused rows after rereading profiles', async () => {
    const twoNewProfilesCsv = [
      'key,title,title_ru,queue_tags,is_active,show_on_qr_page',
      'synthetic-import-a,Synthetic import A,Синтетический импорт A,import_a,true,false',
      'synthetic-import-b,Synthetic import B,Синтетический импорт B,import_b,true,false',
    ].join('\n');
    const createProfile = (_url: string, payload: Record<string, unknown>) => {
      syntheticProfiles.push({ ...payload, key: String(payload.key), queue_tags: payload.queue_tags as string[] });
      return Promise.resolve({ data: { success: true } });
    };
    (api.post as ReturnType<typeof vi.fn>)
      .mockRejectedValueOnce({ response: { status: 409, data: { detail: { reason: 'profile_binding_changed', message: 'Связь профиля изменилась. Обновите список.' } } } })
      .mockImplementationOnce(createProfile)
      .mockImplementationOnce(createProfile);

    await renderManager();
    await uploadCsv(twoNewProfilesCsv);

    expect(api.post).toHaveBeenCalledTimes(2);
    expect(screen.getByRole('region', { name: 'Результаты операции' })).toBeInTheDocument();
    const results = screen.getByRole('region', { name: 'Результаты операции' });
    const resultRows = within(results).getAllByRole('listitem');
    expect(resultRows).toHaveLength(2);
    expect(resultRows[0]).toHaveTextContent('synthetic-import-a');
    expect(resultRows[0]).toHaveTextContent('Отклонено');
    expect(resultRows[0]).toHaveTextContent('Связь профиля изменилась. Обновите список.');
    expect(resultRows[1]).toHaveTextContent('synthetic-import-b');
    expect(resultRows[1]).toHaveTextContent('Выполнено');
    expect(api.post).toHaveBeenCalledTimes(2);

    await userEvent.setup().click(screen.getByRole('button', { name: 'Повторить оставшиеся после проверки' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(3));
    expect((api.post as ReturnType<typeof vi.fn>).mock.calls.map((call) => (call[1] as Record<string, unknown>).key)).toEqual([
      'synthetic-import-a',
      'synthetic-import-b',
      'synthetic-import-a',
    ]);
    expect(await screen.findByText('Синтетический импорт A')).toBeInTheDocument();
    expect(within(results).getAllByRole('listitem').filter((row) => row.textContent?.includes('Выполнено'))).toHaveLength(2);
  });

  it('stops without writing when a profile changes after the CSV impact preview', async () => {
    const updateExistingCsv = [
      'key,title,title_ru,queue_tags,is_active,show_on_qr_page',
      'synthetic-cardio,Updated after preview,Updated after preview,cardio;ekg,true,true',
    ].join('\n');
    const user = userEvent.setup();
    await renderManager();
    await uploadCsv(updateExistingCsv, false);

    const preview = await screen.findByRole('dialog', { name: 'Предварительный просмотр импорта CSV' });
    syntheticProfiles[0].title_ru = 'Изменено после предварительного просмотра';
    await user.click(within(preview).getByRole('button', { name: 'Импортировать' }));

    const results = await screen.findByRole('region', { name: 'Результаты операции' });
    expect(within(results).getByText('synthetic-cardio')).toBeInTheDocument();
    expect(within(results).getByText(/Профиль изменился после предварительного просмотра/)).toBeInTheDocument();
    expect(api.put).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
    expect(within(results).queryByRole('button', { name: 'Повторить оставшиеся после проверки' })).not.toBeInTheDocument();
  });

  it('does not retry an update after the profile changes since the CSV preview', async () => {
    const updateExistingCsv = [
      'key,title,title_ru,queue_tags,is_active,show_on_qr_page',
      'synthetic-cardio,Updated synthetic cardiology,Обновлённая синтетическая кардиология,cardio;ekg,true,true',
    ].join('\n');
    (api.put as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      response: { status: 409, data: { detail: { reason: 'profile_binding_changed', message: 'Связь профиля изменилась.' } } },
    });

    await renderManager();
    await uploadCsv(updateExistingCsv);

    const results = screen.getByRole('region', { name: 'Результаты операции' });
    expect(within(results).getByText(/Связь профиля изменилась/)).toBeInTheDocument();
    expect(api.put).toHaveBeenCalledTimes(1);

    // A different administrator changes the profile after this import's
    // preview and first refused write. Retrying must preserve that change.
    syntheticProfiles[0].title_ru = 'Стороннее изменение после первого отказа';
    await userEvent.setup().click(within(results).getByRole('button', { name: 'Повторить оставшиеся после проверки' }));

    expect(await within(results).findByText(/Профиль изменился после предварительного просмотра/)).toBeInTheDocument();
    expect(api.put).toHaveBeenCalledTimes(1);
    expect(syntheticProfiles[0].title_ru).toBe('Стороннее изменение после первого отказа');
  });

  it('verifies a saved row after a lost response and does not offer a duplicate retry', async () => {
    const newProfileCsv = [
      'key,title,title_ru,queue_tags,is_active,show_on_qr_page',
      'synthetic-lost-response,Synthetic lost response,Синтетический ответ потерян,lost_response,true,false',
    ].join('\n');
    (api.post as ReturnType<typeof vi.fn>).mockImplementationOnce((_url: string, payload: Record<string, unknown>) => {
      syntheticProfiles.push({ ...payload, key: String(payload.key), queue_tags: payload.queue_tags as string[] });
      return Promise.reject({ message: 'synthetic response lost' });
    });

    await renderManager();
    await uploadCsv(newProfileCsv);

    const results = screen.getByRole('region', { name: 'Результаты операции' });
    expect(within(results).getByText('synthetic-lost-response')).toBeInTheDocument();
    expect(within(results).getAllByText(/Выполнено/).length).toBeGreaterThan(0);
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(within(results).queryByRole('button', { name: 'Повторить оставшиеся после проверки' })).not.toBeInTheDocument();
  });

  it('marks a row unverified when refresh fails, then rechecks before avoiding a duplicate retry', async () => {
    const newProfileCsv = [
      'key,title,title_ru,queue_tags,is_active,show_on_qr_page',
      'synthetic-refresh-failure,Synthetic refresh failure,Синтетическая ошибка обновления,refresh_failure,true,false',
    ].join('\n');
    (api.post as ReturnType<typeof vi.fn>).mockImplementationOnce((_url: string, payload: Record<string, unknown>) => {
      // Simulate the server committing the row while the response is lost.
      // The following refresh fails, and retry must discover this saved row.
      syntheticProfiles.push({ ...payload, key: String(payload.key), queue_tags: payload.queue_tags as string[] });
      return Promise.reject(new Error('synthetic response lost after commit'));
    });
    let profileReads = 0;
    (api.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.startsWith('/queues/profiles')) {
        profileReads += 1;
        if (profileReads === 4) return Promise.reject(new Error('synthetic refresh failure'));
      }
      return defaultGetImplementation?.(url);
    });

    await renderManager();
    await uploadCsv(newProfileCsv);

    const results = screen.getByRole('region', { name: 'Результаты операции' });
    expect(within(results).getByText('synthetic-refresh-failure')).toBeInTheDocument();
    expect(within(results).getByText(/Не удалось проверить состояние/)).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledTimes(1);

    await userEvent.setup().click(within(results).getByRole('button', { name: 'Повторить оставшиеся после проверки' }));

    await waitFor(() => expect(within(results).getAllByText(/Выполнено/).length).toBeGreaterThan(0));
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(within(results).queryByRole('button', { name: 'Повторить оставшиеся после проверки' })).not.toBeInTheDocument();
  });
});

// RQ-26.b — CSV import × the new lifecycle contracts: archiving goes through
// the update endpoint only (never destructive), and hand-edited registry
// columns (public_code, E-055) are warned about and never forwarded.
describe('QueueProfilesManager CSV import lifecycle (RQ-26.b)', () => {
  const archiveLifecycleCsv = [
    'key,title,title_ru,queue_tags,department_key,icon,color,display_order,is_active,show_on_qr_page',
    '"synthetic-cardio","Синтетическая кардио, взрослая","Синтетическая кардиология","cardio;ekg","cardiology","Heart","#E53E3E","3","false","true"',
  ].join('\n');

  const publicCodeColumnCsv = [
    'key,title,public_code,is_active',
    '"synthetic-cardio","Синтетическая кардио","aaaaaaaaaaaa","false"',
  ].join('\n');

  it('archives an existing profile through PUT and never calls DELETE', async () => {
    await renderManager();
    await uploadCsv(archiveLifecycleCsv);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        '/queues/profiles/synthetic-cardio',
        expect.objectContaining({ is_active: false })
      );
    });

    // D-02: import is create-or-update only — archiving must not be
    // implemented as (or escalate into) a destructive delete.
    expect(api.delete).not.toHaveBeenCalled();
  });

  it('imports rows from a file with a hand-edited public_code column without forwarding it', async () => {
    await renderManager();
    await uploadCsv(publicCodeColumnCsv);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        '/queues/profiles/synthetic-cardio',
        expect.objectContaining({ is_active: false })
      );
    });

    const payload = (api.put as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    // E-055: the public address is server-SSOT — the CSV column is a
    // non-blocking unknown_column warning, never a payload field.
    expect(payload).not.toHaveProperty('public_code');
  });
});
