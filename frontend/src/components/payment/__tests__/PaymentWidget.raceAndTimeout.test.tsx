/**
 * CSH-FE-037/038 regression tests — PaymentWidget polling-budget vs terminal
 * status, and stale provider responses across currency switches (cashier
 * audit ledger 2026-11-01, follow-up to the #3813 batch).
 *
 * Fail-first proven on the pre-fix source:
 *  - 037: the interval callback applied `status_check_timeout` AFTER
 *    `await checkPaymentStatus()` unconditionally — when the very poll that
 *    exhausted the 60x5s budget observed 'paid' (and fired onSuccess), the
 *    timeout state overwrote it and a PAID visit rendered as timed out.
 *  - 038: `loadProviders` had no sequence guard — a currency switch could
 *    overlap two provider requests and the LATE response of the previous
 *    currency overwrote the state of the newer one, resurrecting a provider
 *    list (and a selected provider) under a currency it does not support;
 *    an empty list also kept the previously selected provider code, and
 *    `initializePayment` only checked truthiness, not list membership.
 *
 * Timer strategy (per the repo's fake-timer experience):
 *  - 037 runs on FAKE timers via act + advanceTimersByTimeAsync (the full
 *    60-poll budget has to elapse deterministically).
 *  - 038 runs on REAL timers with deferred provider responses (the race is
 *    orchestrated manually, so no timer control is needed).
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

describe('PaymentWidget — CSH-FE-037 polling budget vs terminal status (fake timers)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  const initRedirectedPayment = async (onSuccess?: () => void) => {
    apiMocks.post.mockResolvedValueOnce({
      data: {
        success: true,
        payment_id: 777,
        payment_url: 'https://provider.example/pay/777',
      },
    });

    renderWidget(<PaymentWidget visitId={1} amount={100} currency="UZS" onSuccess={onSuccess} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const payButton = screen.getByText(/pay_widg_pay_amount/);
    await act(async () => {
      fireEvent.click(payButton);
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(window.open).toHaveBeenCalledWith('https://provider.example/pay/777', '_blank');
  };

  it('the poll that exhausts the budget keeps its terminal paid status (no timeout overwrite)', async () => {
    let statusCallCount = 0;
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(providersResponse());
      statusCallCount += 1;
      // 'processing' for polls 1..59, the provider confirms 'paid' exactly
      // on the 60th — the poll that also exhausts the attempt budget.
      return Promise.resolve({ data: { status: statusCallCount >= 60 ? 'paid' : 'processing' } });
    });

    const onSuccess = vi.fn();
    await initRedirectedPayment(onSuccess);

    // 10s redirect delay + the full 60 attempts x 5s
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000 + 60 * 5_000);
    });

    expect(statusCallCount).toBeGreaterThanOrEqual(60);
    expect(onSuccess).toHaveBeenCalled();
    // The visit is PAID — the success alert must survive the budget branch…
    expect(screen.getByText(/pay_widg_paid_success/)).toBeInTheDocument();
    // …and the monitoring-timeout warning must NOT replace it.
    expect(screen.queryByText(/pay_widg_timeout/)).toBeNull();
    expect(screen.queryByText(/pay_widg_check_status/)).toBeNull();
  }, 20000);

  it('a non-terminal status at budget exhaustion still yields the monitoring timeout (CSH-FE-031 kept)', async () => {
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(providersResponse());
      return Promise.resolve({ data: { status: 'processing' } });
    });

    await initRedirectedPayment();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000 + 60 * 5_000);
    });

    expect(screen.getByText(/pay_widg_timeout/)).toBeInTheDocument();
  }, 20000);

  it('an errored status endpoint at budget exhaustion still yields the monitoring timeout (unknown status is not terminal)', async () => {
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(providersResponse());
      return Promise.reject(new Error('network down'));
    });

    await initRedirectedPayment();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000 + 60 * 5_000);
    });

    expect(screen.getByText(/pay_widg_timeout/)).toBeInTheDocument();
  }, 20000);
});

describe('PaymentWidget — CSH-FE-038 stale provider responses (real timers)', () => {
  const createDeferred = <T,>() => {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((res) => { resolve = res; });
    return { promise, resolve };
  };

  it('a late stale provider response from a previous currency is discarded', async () => {
    const deferreds: ReturnType<typeof createDeferred>[] = [];
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') {
        const deferred = createDeferred();
        deferreds.push(deferred);
        return deferred.promise;
      }
      return Promise.resolve({ data: { status: 'processing' } });
    });

    const uszProviders = {
      data: {
        providers: [
          { code: 'click', name: 'Click', is_active: true, supported_currencies: ['UZS'] },
        ],
      },
    };

    // UZS request goes out and hangs…
    const { rerender } = renderWidget(<PaymentWidget visitId={1} amount={100} currency="UZS" />);
    await waitFor(() => expect(deferreds.length).toBe(1));

    // …the cashier switches the currency: the KZT request goes out too.
    rerender(
      <ThemeProvider>
        <PaymentWidget visitId={1} amount={100} currency="KZT" />
      </ThemeProvider>,
    );
    await waitFor(() => expect(deferreds.length).toBe(2));

    // The NEWER request resolves first: no provider supports KZT.
    deferreds[1].resolve(uszProviders);
    await waitFor(() => expect(screen.getByText(/pay_widg_no_methods/)).toBeInTheDocument());
    expect(screen.queryByText(/pay_widg_pay_amount/)).toBeNull();

    // The STALE UZS response lands late, out of order.
    await act(async () => {
      deferreds[0].resolve(uszProviders);
    });
    await new Promise((resolve) => setTimeout(resolve, 100));

    // It must be discarded: the widget stays on the no-methods state for
    // KZT — no UZS provider list, no payable button with a mismatched
    // provider/currency pair.
    expect(providerGetCalls()).toBe(2);
    expect(screen.getByText(/pay_widg_no_methods/)).toBeInTheDocument();
    expect(screen.queryByText(/pay_widg_pay_amount/)).toBeNull();
  }, 10000);

  it('a refill after an empty list restores a valid selection paired with the current currency', async () => {
    const responses = [
      // render 1 (UZS): Click
      { data: { providers: [{ code: 'click', name: 'Click', is_active: true, supported_currencies: ['UZS'] }] } },
      // render 2 (KZT): nothing supports KZT → empty list
      { data: { providers: [{ code: 'click', name: 'Click', is_active: true, supported_currencies: ['UZS'] }] } },
      // render 3 (USD): Payme only
      { data: { providers: [{ code: 'payme', name: 'Payme', is_active: true, supported_currencies: ['USD'] }] } },
    ];
    let responseIndex = 0;
    apiMocks.get.mockImplementation((url: string) => {
      if (url === '/payments/providers') return Promise.resolve(responses[responseIndex++]);
      return Promise.resolve({ data: { status: 'processing' } });
    });

    apiMocks.post.mockResolvedValueOnce({ data: { success: true, payment_id: 901 } });

    const { rerender, container } = renderWidget(<PaymentWidget visitId={1} amount={100} currency="UZS" />);
    await waitFor(() => expect(container.querySelector('.mac-select-trigger')?.textContent).toContain('Click'));

    // KZT has no providers — the selection must not survive as a stale code.
    rerender(
      <ThemeProvider>
        <PaymentWidget visitId={1} amount={100} currency="KZT" />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText(/pay_widg_no_methods/)).toBeInTheDocument());

    // Back to a payable currency: the new list's provider is selected.
    rerender(
      <ThemeProvider>
        <PaymentWidget visitId={1} amount={100} currency="USD" />
      </ThemeProvider>,
    );
    await waitFor(() => expect(container.querySelector('.mac-select-trigger')?.textContent).toContain('Payme'));

    const payButton = screen.getByText(/pay_widg_pay_amount/);
    await act(async () => {
      fireEvent.click(payButton);
    });

    await waitFor(() => expect(apiMocks.post).toHaveBeenCalled());
    const initCall = apiMocks.post.mock.calls.find(([url]) => url === '/payments/init');
    expect(initCall).toBeDefined();
    // The POST must pair a provider from the CURRENT list with the CURRENT
    // currency — never a leftover selection from another currency.
    expect(initCall![1]).toMatchObject({ provider: 'payme', currency: 'USD', visit_id: 1 });
  }, 10000);
});
