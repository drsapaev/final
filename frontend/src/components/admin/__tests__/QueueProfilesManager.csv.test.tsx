import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import QueueProfilesManager from '../QueueProfilesManager';
import { api } from '@/api/client';

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

const syntheticProfiles = [
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
        return Promise.resolve({ data: { profiles: syntheticProfiles } });
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

const newFormatCsv = [
  'key,title,title_ru,queue_tags,department_key,icon,color,display_order,is_active,show_on_qr_page',
  '"synthetic-cardio","Синтетическая кардио, взрослая","Синтетическая кардиология","cardio;ekg","cardiology","Heart","#E53E3E","3","true","true"',
  '"synthetic-new","Синтетическая новая вкладка","Синтетическая новая","derma",,,"","7","true","false"'
].join('\n');

const oldFormatCsv = [
  'key,title,title_ru,queue_tags,icon,color,display_order,is_active',
  '"synthetic-cardio","Синтетическая кардио","Синтетическая кардиология","cardio;ekg","Heart","#E53E3E","3","false"'
].join('\n');

const capturedBlobs: Blob[] = [];
const capturedBlobTexts: string[] = [];

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
  render(
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
};

const uploadCsv = async (text: string) => {
  const user = userEvent.setup();
  const input = screen.getByLabelText('Импортировать профили очереди из CSV');
  await user.upload(input, new File([text], 'profiles.csv', { type: 'text/csv' }));
  return user;
};

afterEach(() => {
  vi.clearAllMocks();
  restoreDownload();
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
          title: 'Синтетическая кардио, взрослая',
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

  it('aborts the whole import with a visible error when the file has duplicate keys', async () => {
    const duplicatedRow = '"synthetic-cardio","Дубль синтетической вкладки","","","","","","","","false"';
    const duplicated = `${newFormatCsv}\n${duplicatedRow}\n`;
    await renderManager();
    await uploadCsv(duplicated);

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
      expect(screen.getByText(/qp_import_failed_count|Не удалось импортировать/)).toBeInTheDocument();
    });
    // The create call happened exactly once and failed (mocked rejection);
    // the existing profile still went through the update path.
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.put).toHaveBeenCalledTimes(1);
  });
});
