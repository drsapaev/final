// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';

import { usePayments } from '../usePayments';

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../../api/client', () => ({ api }));

vi.mock('../../utils/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    log: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('usePayments cashier payment history contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('passes the backend status query alias for payment history filters', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        items: [],
        total: 0,
        page: 1,
        size: 20,
        pages: 0,
      },
    });

    const { result } = renderHook(() => usePayments());

    await act(async () => {
      await result.current.getPayments({
        date_from: '2026-05-01',
        date_to: '2026-05-25',
        page: 2,
        search: 'Karimov',
        status: 'refunded',
      });
    });

    expect(api.get).toHaveBeenCalledWith('/cashier/payments', {
      params: {
        page: 2,
        size: 20,
        date_from: '2026-05-01',
        date_to: '2026-05-25',
        search: 'Karimov',
        status: 'refunded',
      },
    });
  });
});
