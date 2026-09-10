import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useRegistrarActions } from '../useRegistrarActions';
import { aggregatePatientsForAllDepartments } from '../../../utils/registrarAggregation';
import { api } from '../../../api/client';

vi.mock('../../../api/client', () => ({ api: { post: vi.fn() } }));
vi.mock('../../../services/notify', () => ({ default: { error: vi.fn(), success: vi.fn() } }));
vi.mock('../../../utils/logger', () => ({ default: { warn: vi.fn(), error: vi.fn() } }));

const record = { id: 1, patient_id: 1, record_kind: 'visit', record_id: 1, available_actions: ['mark_paid'], payment_status: 'partial' };
const payment = { amount: 30000, method: 'cash', payment_snapshot: 'snapshot' };

describe('registrar payment acknowledgement', () => {
  beforeEach(() => vi.clearAllMocks());

  it.each([
    { success: false, failed_count: 1, results: [{ success: false }] },
    { success: false, failed_count: 1, success_count: 1, results: [{ success: true }, { success: false }] },
    { success: true, failed_count: 0, results: [] },
  ])('rejects unsuccessful or unconfirmed response %j', async (data) => {
    vi.mocked(api.post).mockResolvedValue({ data });
    const { result } = renderHook(() => useRegistrarActions({ appointments: [], loadAppointments: vi.fn() }));
    await act(async () => {
      await expect(result.current.handlePayment(record, payment)).rejects.toThrow();
    });
  });

  it('propagates a transport error', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('network'));
    const { result } = renderHook(() => useRegistrarActions({ appointments: [], loadAppointments: vi.fn() }));
    await expect(result.current.handlePayment(record, payment)).rejects.toThrow('network');
  });

  it('returns the server balance even if the subsequent worklist refresh fails', async () => {
    const summary = { paid_amount: 30000, remaining_amount: 70000, payment_status: 'partial', snapshot: 'next' };
    vi.mocked(api.post).mockResolvedValue({ data: { success: true, failed_count: 0, payment_summary: summary } });
    const loadAppointments = vi.fn().mockRejectedValue(new Error('refresh'));
    const { result } = renderHook(() => useRegistrarActions({ appointments: [], loadAppointments }));
    await act(async () => {
      await expect(result.current.handlePayment(record, payment)).resolves.toEqual(summary);
    });
    expect(api.post).toHaveBeenCalledWith('/registrar/records/actions', expect.objectContaining(payment));
    expect(loadAppointments).toHaveBeenCalledOnce();
  });

  it('keeps the partial payment status through patient grouping', () => {
    const rows = aggregatePatientsForAllDepartments([record]);
    expect(rows[0].payment_status).toBe('partial');
  });
});
