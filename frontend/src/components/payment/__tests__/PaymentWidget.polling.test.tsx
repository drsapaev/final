/**
 * CSH-FE-029/030/031 regression tests — PaymentWidget polling, provider
 * loading and timeout semantics (cashier audit ledger 2026-11-01, issue 3813).
 *
 * Fail-first proven on the pre-fix source:
 *  - 030: providers GET looped (85+ calls in 150ms) because unstable t
 *    sat in loadProviders deps; manual provider selection was reset by
 *    every reload; a currency change triggered a refetch storm.
 *  - 029: the redirect-path polling timer closed over the first-render
 *    paymentData=null closure, so the canonical status GET never fired
 *    (0 status GETs) and 'paid' was never picked up.
 *  - 031: reaching the 60x5s observation limit invented a 'failed'
 *    payment status and an error alert, although the provider had not
 *    failed.
 *
 * Timer strategy (per the repo's fake-timer experience):
 *  - 030 runs on REAL timers with a bounded settle and no act — the
 *    pre-fix loop must stay observable without hanging the runner.
 *  - 029/031 run on FAKE timers via act + advanceTimersByTimeAsync
 *    (fake timers freeze React commits, so every advance is wrapped).
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

// Mirrors the real wrapper: a NEW t identity on every render (this is the
// CSH-FE-030 root cause and must stay reproduced here).
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
      { code: 'kaspi', name: 'Kaspi', is_active: true, supported_currencies: ['UZS', 'KZT'] },
    ],
  },
});

const providerGetCalls = () =>
  apiMocks.get.mock.calls.filter(([url]) => url === '/payments/providers').length;

const statusGetCalls = () =>
  apiMocks.get.mock.calls.filter(([url]) => String(url).startsWith('/payments/') && url !== '/payments/providers').length;

const originalLocation = window.location;
const originalOpen = window.open;

const disableLocalSmokeMode = () => {
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
};

const restoreEnvironment = () => {
  vi.unstubAllEnvs();
  Object.defineProperty(window, 'location', {
    value: originalLocation,
    writable: true,
    configurable: true,
  });
  window.open = originalOpen;
};

beforeEach(() => {
  apiMocks.get.mockReset();
  apiMocks.post.mockReset();
  apiMocks.get.mockImplementation(providersResponse);
  disableLocalSmokeMode();
});

afterEach(() => {
  restoreEnvironment();
  vi.useRealTimers();
});

describe('PaymentWidget — CSH-FE-030 provider loading (real timers)', () => {
  it('loads providers exactly once per currency (no refetch loop)', async () => {
    renderWidget(<PaymentWidget visitId={1} amount={100} currency="UZS" />);

    // bounded settle: enough for any loop to explode, short enough to pass
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(providerGetCalls()).toBe(1);
  }, 10000);

  it('preserves a manual provider selection across a reload', async () => {
    const { container, rerender } = renderWidget(<PaymentWidget visitId={1} amount={100} currency="UZS" />);
    await waitFor(() => expect(providerGetCalls()).toBe(1));

    // manual selection: open the dropdown and pick Payme
    fireEvent.click(container.querySelector('.mac-select-trigger')!);
    const paymeOption = await screen.findAllByText('Payme');
    fireEvent.click(paymeOption[paymeOption.length - 1]);

    const trigger = container.querySelector('.mac-select-trigger')!;
    expect(trigger.textContent).toContain('Payme');

    // currency change re-runs loadProviders with the same provider list
    rerender(<ThemeProvider><PaymentWidget visitId={1} amount={100} currency="KZT" /></ThemeProvider>);
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(providerGetCalls()).toBe(2); // one refetch, not a storm
    expect(container.querySelector('.mac-select-trigger')!.textContent).toContain('Payme');
  }, 10000);
});

describe('PaymentWidget — CSH-FE-029/031 polling (fake timers)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  const initRedirectedPayment = async () => {
    apiMocks.post.mockResolvedValueOnce({
      data: {
        success: true,
        payment_id: 555,
        payment_url: 'https://provider.example/pay/555',
      },
    });

    renderWidget(<PaymentWidget visitId={1} amount={100} currency="UZS" />);

    // flush the initial providers load
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // fake timers freeze waitFor — after the act flush the button is
    // already committed, so query synchronously
    const payButton = screen.getByText(/pay_widg_pay_amount/);
    await act(async () => {
      fireEvent.click(payButton);
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(window.open).toHaveBeenCalledWith('https://provider.example/pay/555', '_blank');
  };

  it('redirect-path polling reaches the canonical status GET (stale closure fixed)', async () => {
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(providersResponse());
      return Promise.resolve({ data: { status: 'processing' } });
    });

    await initRedirectedPayment();
    expect(statusGetCalls()).toBe(0);

    // 10s redirect delay + first 5s poll tick
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000 + 5_000);
    });

    expect(statusGetCalls()).toBeGreaterThanOrEqual(1);
    expect(apiMocks.get).toHaveBeenCalledWith('/payments/555');
  }, 20000);

  it('polling picks up the paid status and fires onSuccess', async () => {
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(providersResponse());
      return Promise.resolve({ data: { status: 'paid' } });
    });

    const onSuccess = vi.fn();
    apiMocks.post.mockResolvedValueOnce({
      data: { success: true, payment_id: 556, payment_url: 'https://provider.example/pay/556' },
    });

    renderWidget(<PaymentWidget visitId={1} amount={100} currency="UZS" onSuccess={onSuccess} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // fake timers freeze waitFor — after the act flush the button is
    // already committed, so query synchronously
    const payButton = screen.getByText(/pay_widg_pay_amount/);
    await act(async () => {
      fireEvent.click(payButton);
      await vi.advanceTimersByTimeAsync(0);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });

    expect(apiMocks.get).toHaveBeenCalledWith('/payments/556');
    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(onSuccess.mock.calls[0][0]).toMatchObject({ payment_id: 556, status: 'paid' });
    expect(screen.getByText(/pay_widg_paid_success/)).toBeInTheDocument();
  }, 20000);

  it('the observation limit is a monitoring timeout, not a payment failure (CSH-FE-031)', async () => {
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(providersResponse());
      return Promise.resolve({ data: { status: 'processing' } });
    });

    await initRedirectedPayment();

    // 10s redirect delay + the full 60 attempts x 5s
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000 + 60 * 5_000);
    });

    // explicit monitoring-timeout warning with a manual check action …
    expect(screen.getByText(/pay_widg_timeout/)).toBeInTheDocument();
    expect(screen.getByText(/pay_widg_check_status/)).toBeInTheDocument();
    // … and NOT an invented payment failure or a global error alert
    expect(screen.queryByText(/pay_widg_payment_failed/)).toBeNull();
    expect(document.querySelector('.pw-error-alert')).toBeNull();
  }, 20000);

  it('a manual status check still works after the monitoring timeout', async () => {
    let paymentStatusValue = 'processing';
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(providersResponse());
      return Promise.resolve({ data: { status: paymentStatusValue } });
    });

    await initRedirectedPayment();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000 + 60 * 5_000);
    });
    expect(screen.getByText(/pay_widg_timeout/)).toBeInTheDocument();

    // the provider settles AFTER the observation limit — manual check must
    // surface the real status instead of staying on the timeout warning
    paymentStatusValue = 'paid';
    const manualCheck = screen.getByText(/pay_widg_check_status/);
    await act(async () => {
      fireEvent.click(manualCheck);
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText(/pay_widg_paid_success/)).toBeInTheDocument();
  }, 20000);
});
