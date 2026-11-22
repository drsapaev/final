/**
 * CSH-FE-041/042 (follow-up audit 2026-11-02): честность отмены и
 * владение отложенным таймером опроса в PaymentWidget.
 *
 * 041: кнопка «Отмена» только закрывает окно отслеживания — платёж у
 *      провайдера остаётся активным. Прежде подпись об этом молчала.
 * 042: setTimeout(startPolling, 10s) после редиректа не сохранялся и не
 *      гасился: закрытие модалки в первые 10 секунд оставляло живой
 *      таймер, который ПОСЛЕ размонтирования создавал polling-interval.
 *
 * Red-first (оба): hint-элемент отсутствовал; после unmount+advance
 * статус-запросы продолжали уходить.
 *
 * Timer/env strategy mirrors PaymentWidget.polling.test.tsx: fake timers
 * with act(advanceTimersByTimeAsync), DEV stub off, non-local hostname.
 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

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

import PaymentWidget from '../PaymentWidget';
import { ThemeProvider } from '../../../contexts/ThemeContext';

const renderWidget = (ui: React.ReactElement) => render(<ThemeProvider>{ui}</ThemeProvider>);

const providersResponse = () => ({
  data: {
    providers: [
      { code: 'click', name: 'Click', is_active: true, supported_currencies: ['UZS', 'KZT'] },
      { code: 'payme', name: 'Payme', is_active: true, supported_currencies: ['UZS', 'KZT'] },
    ],
  },
});

const statusCalls = () =>
  apiMocks.get.mock.calls.filter(
    ([url]) => String(url).startsWith('/payments/') && url !== '/payments/providers',
  ).length;

const originalLocation = window.location;
const originalOpen = window.open;

beforeEach(() => {
  apiMocks.get.mockReset();
  apiMocks.post.mockReset();
  apiMocks.get.mockImplementation((url: string) => {
    if (url === '/payments/providers') return Promise.resolve(providersResponse());
    return Promise.resolve({ data: { status: 'processing' } });
  });
  vi.stubEnv('DEV', false);
  Object.defineProperty(window, 'location', {
    value: {
      ...originalLocation,
      hostname: 'cashier.clinic.example',
      origin: 'https://cashier.clinic.example',
      href: 'https://cashier.clinic.example/cashier',
    },
    writable: true,
    configurable: true,
  });
  window.open = vi.fn();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.unstubAllEnvs();
  Object.defineProperty(window, 'location', {
    value: originalLocation,
    writable: true,
    configurable: true,
  });
  window.open = originalOpen;
  vi.useRealTimers();
});

const initRedirectedPayment = async ({ paymentId = 601 } = {}) => {
  apiMocks.post.mockResolvedValueOnce({
    data: {
      success: true,
      payment_id: paymentId,
      payment_url: `https://provider.example/pay/${paymentId}`,
    },
  });

  renderWidget(
    <PaymentWidget visitId={1} amount={100000} currency="UZS" onSuccess={vi.fn()} onCancel={vi.fn()} />,
  );

  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });

  const payButton = screen.getByText(/pay_widg_pay_amount/);
  await act(async () => {
    fireEvent.click(payButton);
    await vi.advanceTimersByTimeAsync(0);
  });

  expect(window.open).toHaveBeenCalledWith(`https://provider.example/pay/${paymentId}`, '_blank');
};

describe('CSH-FE-041: cancel is tracking-close, not a transaction cancel', () => {
  it('shows the honest hint while the hosted payment is non-terminal', async () => {
    await initRedirectedPayment();

    // Статус redirected/processing → не терминальный: подпись обязательна.
    expect(screen.queryByTestId('pw-cancel-hint')).toBeInTheDocument();
    expect(screen.getByTestId('pw-cancel-hint').textContent).toContain('payment.pay_widg_cancel_hint');
  }, 20000);

  it('hides the hint once the payment is terminal (paid)', async () => {
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(providersResponse());
      return Promise.resolve({ data: { status: 'paid' } });
    });

    await initRedirectedPayment({ paymentId: 602 });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });

    expect(screen.getByText(/pay_widg_paid_success/)).toBeInTheDocument();
    expect(screen.queryByTestId('pw-cancel-hint')).not.toBeInTheDocument();
  }, 20000);
});

describe('CSH-FE-042: delayed polling timer dies with the widget', () => {
  it('no zombie interval is created after unmount during the 10s delay window', async () => {
    apiMocks.post.mockResolvedValueOnce({
      data: {
        success: true,
        payment_id: 604,
        payment_url: 'https://provider.example/pay/604',
      },
    });

    const { unmount } = renderWidget(
      <PaymentWidget visitId={1} amount={100000} currency="UZS" onSuccess={vi.fn()} onCancel={vi.fn()} />,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const payButton = screen.getByText(/pay_widg_pay_amount/);
    await act(async () => {
      fireEvent.click(payButton);
      await vi.advanceTimersByTimeAsync(0);
    });

    // Санити: редирект-ветка ДОСТИГНУТА — отложенный таймер существует.
    expect(window.open).toHaveBeenCalledWith('https://provider.example/pay/604', '_blank');

    // Окно закрыли на +2s — таймер 10s ещё НЕ сработал.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    unmount();

    // +30s после размонтирования: зомби-интервал НЕ создаётся. Сетевой
    // счётчик здесь не показатель: префиксный delayed-старт замыкался на
    // paymentData=null (CSH-FE-029) и статусов не слал — поэтому
    // наблюдаем САМО создание интервала (setInterval).
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    expect(setIntervalSpy).not.toHaveBeenCalled();
    setIntervalSpy.mockRestore();
  }, 20000);

  it('clearPolling (cancel) also cancels the pending delayed start', async () => {
    await initRedirectedPayment({ paymentId: 603 });

    // Нажимаем «Отмена» внутри 10-секундного окна.
    const cancelButton = screen.getByText('payment.pay_widg_cancel');
    await act(async () => {
      fireEvent.click(cancelButton);
      await vi.advanceTimersByTimeAsync(0);
    });

    // Отложенный старт обязан быть отменён вместе с отслеживанием:
    // интервала не создаётся (см. примечание о CSH-FE-029 выше).
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });

    expect(setIntervalSpy).not.toHaveBeenCalled();
    setIntervalSpy.mockRestore();
  }, 20000);
});
