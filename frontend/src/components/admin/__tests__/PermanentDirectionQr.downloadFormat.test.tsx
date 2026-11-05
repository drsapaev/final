/**
 * QR-FE-007 (follow-up audit 2026-11-02): расширение скачиваемого файла
 * соответствует реальному формату.
 *
 * Прежде: finishDownload ВСЕГДА называл файл `qr-direction-<code>.png`, а
 * при недоступном canvas-2D / ошибке декодирования скачивался ИСХОДНЫЙ
 * SVG-блоб — файл с .png-расширением содержал SVG/XML байты.
 *
 * Red-first: на префиксном коде fallback-сценарии давали link.download
 * «...png» с blob-URL SVG-блоба; уведомления не существовало.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../../../api/client', () => ({ api: apiMocks }));

const queueResourcesMocks = vi.hoisted(() => ({ listQueueResources: vi.fn() }));
vi.mock('../../../api/queueResources', () => queueResourcesMocks);

const directionMocks = vi.hoisted(() => ({
  fetchAdminQueueDirections: vi.fn(),
  provisionPublicAddress: vi.fn(),
  fetchDirectionEntryMethods: vi.fn(),
}));
vi.mock('../../../api/queueDirections', () => directionMocks);

vi.mock('qrcode.react', () => ({
  // QR-FE-007: downloadPng сериализует РЕАЛЬНЫЙ <svg> из qrWrapRef —
  // мок должен отдавать <svg>, а не <div> (иначе путь молча прерывается).
  QRCodeSVG: (props: { value?: string; 'data-testid'?: string }) => (
    <svg data-testid={props['data-testid'] || 'qr-svg'} data-qr-value={props.value}>
      <rect width="148" height="148" />
    </svg>
  ),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

import AdminSetupDirections from '../AdminSetupDirections';

const SERVICE_ROW = { id: 1, name: 'Service', active: true, requires_doctor: false, queue_tag: 'lab', doctor_id: null };
const PROFILE_ROW = { key: 'lab-key', title_ru: 'Лаборатория', is_active: true, show_on_qr_page: true, queue_tags: ['lab'] };

const ADMIN_DIRECTION = {
  profile: {
    id: 7, key: 'lab-key', title: 'Laboratory', title_ru: 'Лаборатория', queue_tags: ['lab'],
    department_key: 'lab', is_active: true, show_on_qr_page: true, display_order: 1, icon: null, color: null,
  },
  resolved_mode: 'booking',
  configuration_state: 'ready',
  configuration_reasons: [],
  effective_availability: 'available',
  effective_availability_reasons: [],
  booking_targets: [],
  current_day_queues: [],
  public_availability: true,
  permanent_address_exists: false,
  precreate_by_tag: [],
  allowed_next_actions: [{ kind: 'provision_permanent_address', entity_type: 'queue_profile', entity_id: 7, entity_key: 'lab-key' }],
};

const PROVISION_RESPONSE = {
  profile_id: 7,
  direction_key: 'lab-key',
  public_code: 'abcd1234efgh',
  url_path: '/q/abcd1234efgh',
  created: true,
  provisioned_at: '2026-09-20T00:00:00Z',
};

const methodsPayload = (supported: boolean) => ({
  direction_key: 'lab-key',
  entry_methods: [
    { method: 'session_qr', supported: true },
    { method: 'permanent_address', supported },
    { method: 'view_only', supported: true },
  ],
});

/** Перехватчик скачиваний: запоминает link.download/link.href. */
const downloads: Array<{ download: string; href: string }> = [];
const anchorClickStub = vi.fn(function (this: HTMLAnchorElement) {
  downloads.push({ download: this.download, href: this.href });
});

type ImageMode = 'load' | 'error';
let imageMode: ImageMode = 'load';

class FakeImage {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  width = 148;
  height = 148;
  private _src = '';
  get src() { return this._src; }
  set src(value: string) {
    this._src = value;
    // Синхронный ответ «декодера»: режим задаётся тестом.
    if (imageMode === 'load') this.onload?.();
    else this.onerror?.();
  }
}

const origImage = globalThis.Image;
const origCreateObjectURL = URL.createObjectURL;
const origRevokeObjectURL = URL.revokeObjectURL;
const origGetContext = HTMLCanvasElement.prototype.getContext;
const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
const anchorClickRestore = { click: HTMLAnchorElement.prototype.click };

beforeEach(() => {
  vi.clearAllMocks();
  downloads.length = 0;
  imageMode = 'load';

  directionMocks.fetchAdminQueueDirections.mockResolvedValue({
    as_of_day: '2026-11-05',
    directions: [ADMIN_DIRECTION],
    unattached: { queue_tags: [], services: [], resources: [] },
  });
  apiMocks.get.mockImplementation((url: string) => {
    if (url.startsWith('/services?')) return Promise.resolve({ data: [SERVICE_ROW] });
    if (url.startsWith('/queues/profiles')) return Promise.resolve({ data: { profiles: [PROFILE_ROW] } });
    if (url.startsWith('/services/admin/doctors')) return Promise.resolve({ data: [] });
    if (url.includes('/entry-methods')) return Promise.resolve({ data: methodsPayload(false) });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  queueResourcesMocks.listQueueResources.mockResolvedValue([]);
  // Прецедент PIN 2: начальное чтение entry-methods — supported=false
  // (кнопка provision видна); recheck после provision тоже false —
  // на кнопку Download это не влияет (QR-image рендерится).
  directionMocks.fetchDirectionEntryMethods.mockResolvedValue(methodsPayload(false));
  directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);

  globalThis.Image = FakeImage as unknown as typeof Image;
  URL.createObjectURL = vi.fn(() => 'blob:qr-svg-blob');
  URL.revokeObjectURL = vi.fn();
  HTMLAnchorElement.prototype.click = anchorClickStub as unknown as HTMLAnchorElement['click'];
});

afterEach(() => {
  globalThis.Image = origImage;
  URL.createObjectURL = origCreateObjectURL;
  URL.revokeObjectURL = origRevokeObjectURL;
  HTMLCanvasElement.prototype.getContext = origGetContext;
  HTMLCanvasElement.prototype.toDataURL = origToDataURL;
  // anchorClickStub был назначен напрямую на prototype — снимаем его,
  // чтобы не протекал в другие файлы (vi.restoreAllMocks его не знает).
  (HTMLAnchorElement.prototype as unknown as { click: unknown }).click = anchorClickRestore.click;
  vi.restoreAllMocks();
});

/** Проводит экран до состояния «QR provisioned», где доступна кнопка Download. */
const provisionQr = async () => {
  render(
    <ThemeProvider>
      <MemoryRouter>
        <AdminSetupDirections />
      </MemoryRouter>
    </ThemeProvider>,
  );
  fireEvent.click(await screen.findByTestId('setup-qr-expand-lab'));
  fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
  await screen.findByTestId('setup-qr-image-lab');
  return screen.findByTestId('setup-qr-download-lab');
};

describe('QR-FE-007: extension matches the real bytes', () => {
  it('successful PNG conversion → .png with a data: URL', async () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      fillRect: () => {},
      drawImage: () => {},
      fillStyle: '',
    })) as unknown as HTMLCanvasElement['getContext'];
    HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 'data:image/png;base64,iVBORw0KGgo=');

    const downloadBtn = await provisionQr();
    fireEvent.click(downloadBtn);

    await waitFor(() => expect(downloads.length).toBe(1));
    expect(downloads[0].download).toBe('qr-direction-abcd1234efgh.png');
    expect(downloads[0].href).toBe('data:image/png;base64,iVBORw0KGgo=');
    // Успех — уведомления о SVG-fallback нет.
    expect(screen.queryByTestId('setup-qr-svg-fallback-lab')).toBeNull();
  });

  it('canvas 2d unavailable → honest .svg + visible notice (NOT SVG bytes named .png)', async () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as unknown as HTMLCanvasElement['getContext'];

    const downloadBtn = await provisionQr();
    fireEvent.click(downloadBtn);

    await waitFor(() => expect(downloads.length).toBe(1));
    // Прежде: download=«...png», href=blob SVG-блоба.
    expect(downloads[0].download).toBe('qr-direction-abcd1234efgh.svg');
    expect(downloads[0].href).toBe('blob:qr-svg-blob');
    expect(await screen.findByTestId('setup-qr-svg-fallback-lab')).toBeTruthy();
  });

  it('image decode error → .svg (same honest fallback)', async () => {
    imageMode = 'error';
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      fillRect: () => {},
      drawImage: () => {},
      fillStyle: '',
    })) as unknown as HTMLCanvasElement['getContext'];
    HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 'data:image/png;base64,iVBORw0KGgo=');

    const downloadBtn = await provisionQr();
    fireEvent.click(downloadBtn);

    await waitFor(() => expect(downloads.length).toBe(1));
    expect(downloads[0].download).toBe('qr-direction-abcd1234efgh.svg');
    expect(screen.getByTestId('setup-qr-svg-fallback-lab')).toBeTruthy();
  });

  it('toDataURL returns a non-PNG payload → still honest .svg', async () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      fillRect: () => {},
      drawImage: () => {},
      fillStyle: '',
    })) as unknown as HTMLCanvasElement['getContext'];
    // Браузер мог вернуть data:image/svg — не называем файл .png.
    HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 'data:image/svg+xml;base64,PHN2Zy8=');

    const downloadBtn = await provisionQr();
    fireEvent.click(downloadBtn);

    await waitFor(() => expect(downloads.length).toBe(1));
    expect(downloads[0].download).toBe('qr-direction-abcd1234efgh.svg');
    expect(screen.getByTestId('setup-qr-svg-fallback-lab')).toBeTruthy();
  });
});
