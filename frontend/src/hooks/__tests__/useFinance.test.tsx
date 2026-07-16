// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

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

const CACHE_KEY = 'admin_finance_transactions_cache';

const cachedPayload = (transactions, deletedIds = []) => ({
  updatedAt: '2026-03-27T00:00:00.000Z',
  transactions,
  deletedIds
});

describe('useFinance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.getItem.mockImplementation(() => null);
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

    localStorage.getItem.mockImplementation((key) => {
      if (key === CACHE_KEY) {
        return JSON.stringify(cachedPayload([cachedTransaction]));
      }
      return null;
    });

    api.get.mockResolvedValueOnce({ data: [] });

    const { result } = renderHook(() => useFinance());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.allTransactions).toHaveLength(1);
    expect(result.current.allTransactions[0].id).toBe(501);
    expect(result.current.allTransactions[0].reference).toBe('FIN-CACHE-501');
    expect(localStorage.setItem).toHaveBeenCalledWith(
      CACHE_KEY,
      expect.stringContaining('"id":501')
    );
  });

  it('preserves missing backend transaction status as unknown instead of completed', async () => {
    api.get.mockResolvedValueOnce({
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

    const { result } = renderHook(() => useFinance());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.allTransactions).toHaveLength(1);
    expect(result.current.allTransactions[0].status).toBeNull();
    expect(result.current.allTransactions[0].status).not.toBe('completed');
  });

  it('persists create, update, and delete mutations across reloads using cached finance state', async () => {
    api.get
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });

    const { result, unmount } = renderHook(() => useFinance());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.allTransactions).toHaveLength(0);

    api.post.mockResolvedValueOnce({
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

    api.put.mockResolvedValueOnce({
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

    api.delete.mockResolvedValueOnce({ data: { success: true } });
    api.get.mockResolvedValueOnce({
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
    expect(localStorage.setItem).toHaveBeenCalledWith(
      CACHE_KEY,
      expect.stringContaining('"deletedIds":[777]')
    );

    unmount();

    api.get.mockResolvedValueOnce({
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

    const { result: remounted } = renderHook(() => useFinance());
    await waitFor(() => expect(remounted.current.loading).toBe(false));

    expect(remounted.current.allTransactions).toHaveLength(0);
  });
});
