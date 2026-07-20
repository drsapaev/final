import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';

import useFinance from '../useFinance';

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn()
}));

vi.mock('../../api/client', () => ({ api }));

vi.mock('../../utils/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    log: vi.fn(),
    debug: vi.fn(),
    group: vi.fn(),
    groupEnd: vi.fn()
  }
}));

// Cast api through unknown so vitest mock methods are visible to TS.
const apiMock = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

// localStorage spies so .mockImplementation and toHaveBeenCalledWith work.
const localStorageGetItem = vi.spyOn(Storage.prototype, 'getItem');
const localStorageSetItem = vi.spyOn(Storage.prototype, 'setItem');
const localStorageRemoveItem = vi.spyOn(Storage.prototype, 'removeItem');

interface FinanceTransaction {
  id: number;
  type: string;
  category: string;
  amount: number;
  description?: string;
  patientId?: string | null;
  doctorId?: string | null;
  paymentMethod?: string;
  status?: string | null;
  transactionDate?: string;
  notes?: string | null;
  reference?: string;
}

interface CachedPayload {
  updatedAt: string;
  transactions: FinanceTransaction[];
  deletedIds?: number[];
}

// useFinance returns implicit-any values; cast to a typed shape so the
// test's property accesses (allTransactions[0].id, .status, etc.)
// compile.
interface UseFinanceResult {
  loading: boolean;
  allTransactions: FinanceTransaction[];
  createTransaction: (payload: Record<string, unknown>) => Promise<unknown>;
  updateTransaction: (id: number, payload: Record<string, unknown>) => Promise<unknown>;
  deleteTransaction: (id: number) => Promise<unknown>;
}

function useFinanceTyped(): UseFinanceResult {
  return useFinance() as unknown as UseFinanceResult;
}

const CACHE_KEY = 'admin_finance_transactions_cache';

const cachedPayload = (transactions: FinanceTransaction[], deletedIds: number[] = []): CachedPayload => ({
  updatedAt: '2026-03-27T00:00:00.000Z',
  transactions,
  deletedIds
});

describe('useFinance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorageGetItem.mockImplementation(() => null);
  });

  it('restores cached transactions after reload even when backend returns an empty list', async () => {
    const cachedTransaction = {
      id: 501,
      type: 'income',
      category: 'Консультация врача',
      amount: 150000,
      description: 'Cached finance row',
      patientId: null,
      doctorId: null,
      paymentMethod: 'cash',
      status: 'completed',
      transactionDate: '2026-03-27',
      notes: 'cached',
      reference: 'FIN-CACHE-501'
    };

    localStorageGetItem.mockImplementation((key: string) => {
      if (key === CACHE_KEY) {
        return JSON.stringify(cachedPayload([cachedTransaction]));
      }
      return null;
    });

    apiMock.get.mockResolvedValueOnce({ data: [] });

    const { result } = renderHook(() => useFinanceTyped());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.allTransactions).toHaveLength(1);
    expect(result.current.allTransactions[0].id).toBe(501);
    expect(result.current.allTransactions[0].reference).toBe('FIN-CACHE-501');
    expect(localStorageSetItem).toHaveBeenCalledWith(
      CACHE_KEY,
      expect.stringContaining('"id":501')
    );
  });

  it('preserves missing backend transaction status as unknown instead of completed', async () => {
    apiMock.get.mockResolvedValueOnce({
      data: [
        {
          id: 601,
          type: 'income',
          category: 'РљРѕРЅСЃСѓР»СЊС‚Р°С†РёСЏ',
          amount: 90000,
          description: 'Backend row without status',
          patient_id: null,
          doctor_id: null,
          payment_method: 'cash',
          transaction_date: '2026-03-27',
          notes: null,
          reference: 'FIN-601'
        }
      ]
    });

    const { result } = renderHook(() => useFinanceTyped());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.allTransactions).toHaveLength(1);
    expect(result.current.allTransactions[0].status).toBeNull();
    expect(result.current.allTransactions[0].status).not.toBe('completed');
  });

  it('persists create, update, and delete mutations across reloads using cached finance state', async () => {
    apiMock.get
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });

    const { result, unmount } = renderHook(() => useFinanceTyped());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.allTransactions).toHaveLength(0);

    apiMock.post.mockResolvedValueOnce({
      data: {
        id: 777,
        type: 'income',
        category: 'Диагностика',
        amount: 12000,
        description: 'New finance row',
        patient_id: null,
        doctor_id: null,
        payment_method: 'cash',
        status: 'pending',
        transaction_date: '2026-03-27',
        notes: null,
        reference: 'FIN-777'
      }
    });

    await act(async () => {
      await result.current.createTransaction({
        type: 'income',
        category: 'Диагностика',
        amount: 12000,
        description: 'New finance row',
        patientId: '',
        doctorId: '',
        paymentMethod: 'cash',
        status: 'pending',
        transactionDate: '2026-03-27',
        notes: '',
        reference: 'FIN-777'
      });
    });

    expect(result.current.allTransactions).toHaveLength(1);
    expect(result.current.allTransactions[0].id).toBe(777);
    expect(result.current.allTransactions[0].status).toBe('pending');

    apiMock.put.mockResolvedValueOnce({
      data: {
        id: 777,
        type: 'income',
        category: 'Диагностика',
        amount: 12000,
        description: 'New finance row',
        patient_id: null,
        doctor_id: null,
        payment_method: 'cash',
        status: 'completed',
        transaction_date: '2026-03-27',
        notes: 'updated',
        reference: 'FIN-777-UPD'
      }
    });

    await act(async () => {
      await result.current.updateTransaction(777, {
        type: 'income',
        category: 'Диагностика',
        amount: 12000,
        description: 'New finance row',
        patientId: '',
        doctorId: '',
        paymentMethod: 'cash',
        status: 'completed',
        transactionDate: '2026-03-27',
        notes: 'updated',
        reference: 'FIN-777-UPD'
      });
    });

    expect(result.current.allTransactions).toHaveLength(1);
    expect(result.current.allTransactions[0].status).toBe('completed');
    expect(result.current.allTransactions[0].reference).toBe('FIN-777-UPD');

    apiMock.delete.mockResolvedValueOnce({ data: { success: true } });
    apiMock.get.mockResolvedValueOnce({
      data: [
        {
          id: 777,
          type: 'income',
          category: 'Диагностика',
          amount: 12000,
          description: 'New finance row',
          patient_id: null,
          doctor_id: null,
          payment_method: 'cash',
          status: 'completed',
          transaction_date: '2026-03-27',
          notes: 'updated',
          reference: 'FIN-777-UPD'
        }
      ]
    });

    await act(async () => {
      await result.current.deleteTransaction(777);
    });

    expect(result.current.allTransactions).toHaveLength(0);
    expect(localStorageSetItem).toHaveBeenCalledWith(
      CACHE_KEY,
      expect.stringContaining('"deletedIds":[777]')
    );

    unmount();

    apiMock.get.mockResolvedValueOnce({
      data: [
        {
          id: 777,
          type: 'income',
          category: 'Диагностика',
          amount: 12000,
          description: 'New finance row',
          patient_id: null,
          doctor_id: null,
          payment_method: 'cash',
          status: 'completed',
          transaction_date: '2026-03-27',
          notes: 'updated',
          reference: 'FIN-777-UPD'
        }
      ]
    });

    const { result: remounted } = renderHook(() => useFinanceTyped());
    await waitFor(() => expect(remounted.current.loading).toBe(false));

    expect(remounted.current.allTransactions).toHaveLength(0);
  });
});
