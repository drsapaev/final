/**
 * CSH-FE-043 / CSH-FE-045 (follow-up audit 2026-11-02): честность печати
 * в PaymentProviderDialog.
 *
 * 043: printTicket прежде использовал «синхронную» обёртку
 *      printPanelTicketInBrowser, которая возвращала true БЕЗУСЛОВНО —
 *      ветка `if (!opened)` была недостижима, и заблокированный popup
 *      молчал. Теперь awaited printPanelTicketInBrowserAsync: blocked —
 *      честный false + warn; render/print-провал — отдельный warn.
 * 045: «Печать талонов» открывает ОДНО окно пакетной печати синхронно в
 *      прямом жесте клика (прежде: попап на каждый талон с задержкой 500мс).
 *
 * Red-first (до фикса): оба сценария проваливались — модуль panelPrint не
 * имел openPanelTicketBatchWindow, а printTicket возвращал true всегда.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

vi.mock('../../../api/client', () => ({
  api: {
    get: apiMocks.get,
    post: apiMocks.post,
    defaults: { headers: { common: {} } },
  },
  getToken: () => 'test-token-123',
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

vi.mock('../../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));

vi.mock('../../../services/panelPrint', () => ({
  printPanelTicketInBrowserAsync: vi.fn(),
  openPanelTicketBatchWindow: vi.fn(),
  printPanelTicketsBatchInExistingWindow: vi.fn(),
}));

import PaymentProviderDialog from '../PaymentProviderDialog';
import {
  openPanelTicketBatchWindow,
  printPanelTicketInBrowserAsync,
  printPanelTicketsBatchInExistingWindow,
} from '../../../services/panelPrint';
import logger from '../../../utils/logger';

const singlePrintMock = printPanelTicketInBrowserAsync as unknown as ReturnType<typeof vi.fn>;
const batchOpenMock = openPanelTicketBatchWindow as unknown as ReturnType<typeof vi.fn>;
const batchFillMock = printPanelTicketsBatchInExistingWindow as unknown as ReturnType<typeof vi.fn>;

const PRINT_TICKETS = [
  { queue_id: 't1', queue_number: 41, patient_name: 'Pat A', doctor_name: 'Doc', queue_name: 'Cardio' },
  { queue_id: 't2', queue_number: 42, patient_name: 'Pat B', doctor_name: 'Doc', queue_name: 'Cardio' },
];

const originalOpen = window.open;

beforeEach(() => {
  apiMocks.get.mockReset();
  apiMocks.post.mockReset();
  singlePrintMock.mockReset();
  batchOpenMock.mockReset();
  batchFillMock.mockReset();

  // init-payment → hosted URL; статус инвойса → paid + print_tickets.
  apiMocks.post.mockResolvedValue({
    status: 200,
    data: { success: true, payment_url: 'https://pay.example/hosted', provider_payment_id: 42 },
  });
  apiMocks.get.mockResolvedValue({
    status: 200,
    data: { status: 'paid', print_tickets: PRINT_TICKETS },
  });

  window.open = vi.fn(() => null) as unknown as typeof window.open;
});

afterEach(() => {
  window.open = originalOpen;
  vi.restoreAllMocks();
});

const mountAndReachSuccess = async () => {
  render(
    <PaymentProviderDialog
      isOpen
      onClose={() => {}}
      invoiceId={77}
      totalAmount={100000}
      provider="click"
      providerLabel="Click"
    />,
  );

  // init → hosted payment (processing state)
  fireEvent.click(screen.getByRole('button', { name: /pay_dlg_pay_via/ }));
  // processing → начать отслеживание (pending state с ручной проверкой)
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /pay_dlg_start_tracking/ })).toBeTruthy();
  });
  fireEvent.click(screen.getByRole('button', { name: /pay_dlg_start_tracking/ }));
  // manual check → статус paid + print_tickets (success state)
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /pay_dlg_check_now/ })).toBeTruthy();
  });
  fireEvent.click(screen.getByRole('button', { name: /pay_dlg_check_now/ }));

  // Талоны для печати отрисованы (per-ticket кнопки).
  await waitFor(() => {
    expect(screen.getAllByRole('button', { name: /pay_dlg_print_ticket_aria/ }).length).toBe(2);
  });
};

describe('PaymentProviderDialog — CSH-FE-043 honest per-ticket print', () => {
  it('popup blocked → printTicket returns FALSE and warns (previously unreachable branch)', async () => {
    const warnSpy = vi.spyOn(logger, 'warn').mockImplementation(() => {});
    singlePrintMock.mockResolvedValue({ opened: false, success: false });

    await mountAndReachSuccess();
    fireEvent.click(screen.getAllByRole('button', { name: /pay_dlg_print_ticket_aria/ })[0]);
    await waitFor(() => expect(singlePrintMock).toHaveBeenCalledTimes(1));

    const rowArg = singlePrintMock.mock.calls[0][0] as Record<string, unknown>;
    expect(rowArg.source).toBe('payment');
    expect(rowArg.specialty_name).toBe('Cardio');
    // Прежде обёртка возвращала true безусловно — теперь blocked честно виден.
    expect(warnSpy).toHaveBeenCalledWith('Browser popup blocked for payment ticket print', expect.anything());
  });

  it('opened + success → no popup-block warning', async () => {
    const warnSpy = vi.spyOn(logger, 'warn').mockImplementation(() => {});
    singlePrintMock.mockResolvedValue({ opened: true, success: true });

    await mountAndReachSuccess();
    fireEvent.click(screen.getAllByRole('button', { name: /pay_dlg_print_ticket_aria/ })[0]);
    await waitFor(() => expect(singlePrintMock).toHaveBeenCalledTimes(1));
    expect(warnSpy).not.toHaveBeenCalledWith('Browser popup blocked for payment ticket print', expect.anything());
  });
});

describe('PaymentProviderDialog — CSH-FE-045 batch print in a single gesture', () => {
  it('«Печать талонов» opens ONE batch window synchronously, then fills it with every ticket', async () => {
    const fakeWindow = { document: { write: vi.fn() } } as unknown as Window;
    batchOpenMock.mockReturnValue(fakeWindow);
    batchFillMock.mockResolvedValue({ opened: true, success: true });

    await mountAndReachSuccess();
    // Кнопка действия «Печать талонов» (pay_dlg_print_tickets).
    fireEvent.click(screen.getByRole('button', { name: /pay_dlg_print_tickets/ }));

    expect(batchOpenMock).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(batchFillMock).toHaveBeenCalledTimes(1));

    const [windowArg, rowsArg] = batchFillMock.mock.calls[0];
    expect(windowArg).toBe(fakeWindow);
    expect(rowsArg).toHaveLength(2);
    expect((rowsArg as Array<Record<string, unknown>>).every((r) => r.source === 'payment')).toBe(true);
    // Один документ вместо попапа на каждый талон.
    expect(singlePrintMock).not.toHaveBeenCalled();
  });

  it('blocked batch window → honest warn, no fill call', async () => {
    const warnSpy = vi.spyOn(logger, 'warn').mockImplementation(() => {});
    batchOpenMock.mockReturnValue(null);

    await mountAndReachSuccess();
    fireEvent.click(screen.getByRole('button', { name: /pay_dlg_print_tickets/ }));

    expect(batchOpenMock).toHaveBeenCalledTimes(1);
    expect(batchFillMock).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith('Browser popup blocked for batch ticket print');
  });
});
