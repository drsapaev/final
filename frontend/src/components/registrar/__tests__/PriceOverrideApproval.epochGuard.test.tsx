/**
 * REG-FE-073 (follow-up audit 2026-11-02): request-epoch guard для
 * PriceOverrideApproval.
 *
 * Прежде каждый ответ безусловно звал setPriceOverrides(data): быстрое
 * переключение фильтра pending→approved, где «медленный» pending-ответ
 * приходил ПОСЛЕ approved-ответа, отрисовывал pending-записи под
 * approved-фильтром. Теперь применяется только ответ ПОСЛЕДНЕЙ
 * инициированной загрузки (loading и error-toast тоже эпохой).
 *
 * Red-first (до фикса): разрешение A-после-B перерисовывало список
 * записями «pending» под фильтром «approved».
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

vi.mock('react-toastify', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));

const apiMocks = vi.hoisted(() => ({
  fetchPriceOverrides: vi.fn(),
  approvePriceOverride: vi.fn(),
}));

vi.mock('../../../hooks/useRegistrarApi', () => ({
  useRegistrarApi: () => apiMocks,
}));

import PriceOverrideApproval from '../PriceOverrideApproval';
import { ThemeProvider } from '../../../contexts/ThemeContext';

const renderApproval = (ui: React.ReactElement) => render(<ThemeProvider>{ui}</ThemeProvider>);

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

const makeDeferred = <T,>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const PENDING_ENTRY = {
  id: 'p1',
  status: 'pending',
  service_name: 'SVC-PENDING-LIST',
  doctor_name: 'Doc P',
  requested_price: 150000,
  original_price: 100000,
};

const APPROVED_ENTRY = {
  id: 'a1',
  status: 'approved',
  service_name: 'SVC-APPROVED-LIST',
  doctor_name: 'Doc A',
  requested_price: 200000,
  original_price: 100000,
};

const findListContainer = () => {
  // Список рендерится карточками записей (не пустым состоянием).
  return screen.getByText(/SVC-/).closest('div.bg-white')?.parentElement ?? document.body;
};

beforeEach(() => {
  apiMocks.fetchPriceOverrides.mockReset();
  apiMocks.approvePriceOverride.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('REG-FE-073 — stale filter response cannot overwrite the latest list', () => {
  it('pending→approved: late pending response must NOT repaint pending entries under the approved filter', async () => {
    const pendingA = makeDeferred<unknown>();
    const approvedB = makeDeferred<unknown>();
    apiMocks.fetchPriceOverrides.mockImplementation(({ statusFilter }: { statusFilter: string }) => {
      if (statusFilter === 'pending') return pendingA.promise;
      if (statusFilter === 'approved') return approvedB.promise;
      return Promise.resolve([]);
    });

    renderApproval(<PriceOverrideApproval />);

    // Начальная загрузка (filter=pending) инициирована на mount.
    await waitFor(() => expect(apiMocks.fetchPriceOverrides).toHaveBeenCalledTimes(1));
    expect(apiMocks.fetchPriceOverrides.mock.calls[0][0]).toMatchObject({ statusFilter: 'pending', limit: 100 });

    // Быстрое переключение фильтра на «approved» до ответа A.
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'approved' } });

    await waitFor(() => expect(apiMocks.fetchPriceOverrides).toHaveBeenCalledTimes(2));
    expect(apiMocks.fetchPriceOverrides.mock.calls[1][0]).toMatchObject({ statusFilter: 'approved', limit: 100 });

    // Approved-ответ (B) приходит ПЕРВЫМ — список становится approved.
    approvedB.resolve([APPROVED_ENTRY]);
    await waitFor(() => {
      expect(screen.getByText('SVC-APPROVED-LIST')).toBeTruthy();
    });

    // «Медленный» pending-ответ (A) приходит ПОСЛЕ — и обязан быть отброшен.
    pendingA.resolve([PENDING_ENTRY]);
    // Дать шанс перерисоваться, если бы баг жил (эпоха должна блокировать).
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.getByText('SVC-APPROVED-LIST')).toBeTruthy();
    expect(screen.queryByText('SVC-PENDING-LIST')).toBeNull();
    // Список не вернулся в loading.
    expect(screen.queryByText(/poa_zagruzka|загрузка/i)).toBeNull();
  });

  it('stale failure is silent for the active filter (no error toast for a dropped epoch)', async () => {
    const pendingA = makeDeferred<unknown>();
    const approvedB = makeDeferred<unknown>();
    apiMocks.fetchPriceOverrides.mockImplementation(({ statusFilter }: { statusFilter: string }) => {
      if (statusFilter === 'pending') return pendingA.promise;
      if (statusFilter === 'approved') return approvedB.promise;
      return Promise.resolve([]);
    });

    renderApproval(<PriceOverrideApproval />);
    await waitFor(() => expect(apiMocks.fetchPriceOverrides).toHaveBeenCalledTimes(1));

    const select = screen.getByRole('combobox') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'approved' } });
    await waitFor(() => expect(apiMocks.fetchPriceOverrides).toHaveBeenCalledTimes(2));

    approvedB.resolve([APPROVED_ENTRY]);
    await waitFor(() => expect(screen.getByText('SVC-APPROVED-LIST')).toBeTruthy());

    // Теперь «старый» запрос не просто опоздал — он ПРОВАЛИЛСЯ. Его ошибка
    // не должна касаться активного фильтра.
    pendingA.reject(new Error('pending request failed'));
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.getByText('SVC-APPROVED-LIST')).toBeTruthy();
    // Активная загрузка завершилась успешно: loading сброшен её же эпохой.
    expect(screen.queryByText(/poa_zagruzka|загрузка/i)).toBeNull();
  });
});
