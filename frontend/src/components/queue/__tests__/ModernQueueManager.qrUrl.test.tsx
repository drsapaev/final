/**
 * QR-FE-003/004 (follow-up audit 2026-11-02): серверный qr_url в
 * SVG-fallback и живой пересчёт экспирации открытого QR-диалога.
 *
 * 003: fallback-SVG кодировал ЗАХАРДКОЖЕННЫЙ https://med-queue.uz/... —
 *      клиника на другом домене отправляла пациентов на чужой сайт.
 *      Теперь SVG кодирует ТОЛЬКО серверный qr_url; без него — честное
 *      «недоступно», без конструирования кросс-доменного URL.
 * 004: классификация срока мемоизировалась только по [expires_at,
 *      showQrDialog] — открытый диалог «замораживал» valid навсегда.
 *      Теперь ограниченный таймер до горизонта истечения переворачивает
 *      подпись в expired ПРИ ОТКРЫТОМ диалоге.
 *
 * Red-first (оба): на префиксном коде SVG-значение было med-queue.uz, а
 * caption оставался valid после advance.
 */
import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '../../../contexts/ThemeContext';

const state = vi.hoisted(() => ({
  qrData: null as Record<string, unknown> | null,
}));

const queueMocks = vi.hoisted(() => ({
  loadQueueSnapshot: vi.fn(async () => ({ entries: [], is_open: true })),
  generateClinicQRCode: vi.fn(async () => ({})),
  generateDoctorQRCode: vi.fn(async () => ({})),
  setQrData: vi.fn(),
}));

vi.mock('../../../hooks/useQueueManager', () => ({
  useQueueManager: () => ({
    loading: false,
    queueData: { entries: [], is_open: true },
    statistics: null,
    qrData: state.qrData,
    specialists: [{ id: '7', full_name: 'Registrar test doctor', specialty: 'cardiology' }],
    loadQueueSnapshot: queueMocks.loadQueueSnapshot,
    generateDoctorQRCode: queueMocks.generateDoctorQRCode,
    generateClinicQRCode: queueMocks.generateClinicQRCode,
    openReceptionForDoctor: vi.fn(),
    closeReceptionForDoctor: vi.fn(),
    callNextPatientInQueue: vi.fn(),
    setQrData: queueMocks.setQrData,
  }),
}));

vi.mock('../../../hooks/useQueueWebSocket', () => ({
  useQueueWebSocket: () => ({ state: 'disconnected' }),
}));

vi.mock('../../common/ConfirmDialog', () => ({
  useConfirm: () => [vi.fn(async () => true), null],
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const qrSvgMocks = vi.hoisted(() => ({ values: [] as string[] }));
vi.mock('qrcode.react', () => ({
  QRCodeSVG: (props: { value?: string }) => {
    qrSvgMocks.values.push(String(props.value ?? ''));
    return <div className="mqm-qr-svg-stub" data-qr-value={props.value} />;
  },
}));

import ModernQueueManager from '../ModernQueueManager';

async function openClinicQrDialog() {
  const result = render(
    <ThemeProvider>
      <ModernQueueManager mode="registrar" />
    </ThemeProvider>,
  );
  const clinicQrButton = await screen.findByText('misc.mqm_clinic_qr');
  await act(async () => {
    fireEvent.click(clinicQrButton);
  });
  return result;
}

beforeEach(() => {
  vi.clearAllMocks();
  state.qrData = null;
});

afterEach(() => {
  vi.useRealTimers();
});

describe('QR-FE-003: fallback SVG encodes the SERVER qr_url only', () => {
  it('SVG value is the backend-provided URL, not med-queue.uz', async () => {
    state.qrData = {
      token: 'opaque-token',
      qr_code_base64: null,
      qr_url: 'https://clinic.example/queue/join?token=opaque-token',
      expires_at: new Date(Date.now() + 60_000).toISOString(),
    };
    await openClinicQrDialog();

    // QRCodeSVG замокан: проверяем ЗНАЧЕНИЕ, которое кодируется в QR.
    const stub = document.querySelector('[data-qr-value]');
    expect(stub).not.toBeNull();
    expect(stub!.getAttribute('data-qr-value'))
      .toBe('https://clinic.example/queue/join?token=opaque-token');
    expect(stub!.getAttribute('data-qr-value')).not.toContain('med-queue.uz');
  });

  it('token without qr_url renders an honest unavailable state, never a foreign URL', async () => {
    state.qrData = {
      token: 'opaque-token',
      qr_code_base64: null,
      // qr_url отсутствует — конструировать кросс-доменный URL запрещено.
      expires_at: new Date(Date.now() + 60_000).toISOString(),
    };
    await openClinicQrDialog();

    expect(screen.getByTestId('mqm-qr-url-missing')).toBeInTheDocument();
    expect(document.querySelector('[data-qr-value]')).toBeNull();
  });
});

describe('QR-FE-004: open dialog flips to expired at the horizon', () => {
  it('valid caption becomes expired after the expiry moment passes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const expiresAt = new Date(Date.now() + 10_000).toISOString();
    state.qrData = {
      token: 'opaque-token',
      qr_code_base64: null,
      qr_url: 'https://clinic.example/queue/join?token=opaque-token',
      expires_at: expiresAt,
    };
    await openClinicQrDialog();

    // Диалог открыт, до истечения < 10s — подпись valid.
    expect(screen.getByText(/mqm_qr_valid_until/)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });

    expect(screen.getByText('misc.mqm_qr_expired')).toBeInTheDocument();
    expect(screen.getByText('misc.mqm_qr_expired_hint')).toBeInTheDocument();
  }, 20000);
});
