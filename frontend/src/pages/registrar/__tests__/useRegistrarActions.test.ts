import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useRegistrarActions } from '../useRegistrarActions';
import { aggregatePatientsForAllDepartments } from '../../../utils/registrarAggregation';
import { api } from '../../../api/client';
import { getBackendActionAvailability } from '../../../components/tables/appointmentsTableContracts';
import { hasBackendAction } from '../registrarHelpers';

vi.mock('../../../api/client', () => ({ api: { post: vi.fn() } }));
vi.mock('../../../services/notify', () => ({
  default: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({ default: { warn: vi.fn(), error: vi.fn(), info: vi.fn() } }));

import notify from '../../../services/notify';

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

  it.each([false, true])('allows a grouped top-up when one visit is already paid (reverse=%s)', async (reverse) => {
    const paid = { ...record, id: 2, record_id: 2, payment_status: 'paid', available_actions: [], can_mark_paid: false };
    const partial = { ...record, can_mark_paid: true };
    const [group] = aggregatePatientsForAllDepartments(reverse ? [partial, paid] : [paid, partial]);
    expect(getBackendActionAvailability(group, 'payment', 'can_mark_paid')).toBe(true);
    const summary = { paid_amount: 100000, remaining_amount: 0, payment_status: 'paid', snapshot: 'next' };
    vi.mocked(api.post).mockResolvedValue({ data: { success: true, failed_count: 0, payment_summary: summary } });
    const { result } = renderHook(() => useRegistrarActions({ appointments: [group], loadAppointments: vi.fn() }));
    await act(async () => {
      await expect(result.current.handlePayment(group, payment)).resolves.toEqual(summary);
    });
    expect(api.post).toHaveBeenCalledWith('/registrar/records/actions', expect.objectContaining({
      ...payment,
      records: expect.arrayContaining([
        { record_kind: 'visit', record_id: 1 },
        { record_kind: 'visit', record_id: 2 },
      ]),
    }));
    expect(hasBackendAction(group, 'start_visit')).toBe(false);
  });

  it('does not infer permission to pay from a group balance or stale parent flag', async () => {
    const group = {
      ...record, can_mark_paid: true,
      grouped_records: [{ ...record, available_actions: [], can_mark_paid: false }],
    };
    expect(getBackendActionAvailability(group, 'payment', 'can_mark_paid')).toBe(false);
    const { result } = renderHook(() => useRegistrarActions({ appointments: [group], loadAppointments: vi.fn() }));
    await expect(result.current.handlePayment(group, payment)).rejects.toThrow();
    expect(api.post).not.toHaveBeenCalled();
  });
});

// REG-FE-015 (audit #3803): серверный батч-эндпоинт не атомарен — при
// частичном успехе часть записей уже изменена. Хук обязан выравнять
// ворклист по каноническому read-model и честно сообщить частичный
// результат, а не показывать только ошибку поверх устаревших строк.
const visitRecord = { id: 5, patient_id: 5, record_kind: 'visit', record_id: 5, available_actions: ['start_visit'] };

function renderActions(loadAppointments: (opts?: Record<string, unknown>) => Promise<void> | void = vi.fn()) {
  const { result } = renderHook(() => useRegistrarActions({ appointments: [visitRecord], loadAppointments }));
  return { result, loadAppointments };
}

describe('registrar partial batch reconciliation (REG-FE-015)', () => {
  beforeEach(() => vi.clearAllMocks());

  const partialResponse = {
    success: false,
    success_count: 1,
    failed_count: 1,
    results: [
      { success: true, record_id: 1 },
      { success: false, record_id: 2, error: 'conflict' },
    ],
  };

  it('updateAppointmentStatus refreshes the worklist and reports a partial outcome instead of a bare error', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: partialResponse });
    const loadAppointments = vi.fn();
    const { result } = renderActions(loadAppointments);
    let outcome: unknown = null;
    await act(async () => {
      outcome = await result.current.updateAppointmentStatus('visit:5', 'in_cabinet', '');
    });
    // часть записей реально изменена: результат не null, список выровнен
    expect(loadAppointments).toHaveBeenCalledTimes(1);
    expect(notify.warning).toHaveBeenCalledTimes(1);
    expect(String(vi.mocked(notify.warning).mock.calls[0][0])).toMatch(/1/);
    expect(String(vi.mocked(notify.warning).mock.calls[0][0])).toMatch(/частично/i);
    expect(notify.error).not.toHaveBeenCalled();
    expect(outcome).toEqual(partialResponse);
  });

  it('handleStartVisit refreshes the worklist and reports a partial outcome', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: partialResponse });
    const loadAppointments = vi.fn();
    const { result } = renderActions(loadAppointments);
    let outcome: unknown = null;
    await act(async () => {
      outcome = await result.current.handleStartVisit(visitRecord);
    });
    expect(loadAppointments).toHaveBeenCalledTimes(1);
    expect(notify.warning).toHaveBeenCalledTimes(1);
    expect(notify.success).not.toHaveBeenCalled();
    expect(outcome).toEqual(partialResponse);
  });

  it('an all-failed batch keeps the existing error path and does not refresh', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        success: false,
        success_count: 0,
        failed_count: 1,
        results: [{ success: false, record_id: 2, error: 'not_allowed' }],
      },
    });
    const loadAppointments = vi.fn();
    const { result } = renderActions(loadAppointments);
    let outcome: unknown = 'sentinel';
    await act(async () => {
      outcome = await result.current.updateAppointmentStatus('visit:5', 'in_cabinet', '');
    });
    expect(outcome).toBeNull();
    expect(notify.error).toHaveBeenCalledTimes(1);
    expect(loadAppointments).not.toHaveBeenCalled();
  });

  it('an all-success batch keeps the single success acknowledgement and refresh', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { success: true, success_count: 1, failed_count: 0, results: [{ success: true, record_id: 1 }] },
    });
    const loadAppointments = vi.fn();
    const { result } = renderActions(loadAppointments);
    await act(async () => {
      await result.current.updateAppointmentStatus('visit:5', 'in_cabinet', '');
    });
    expect(notify.success).toHaveBeenCalledTimes(1);
    expect(notify.warning).not.toHaveBeenCalled();
    expect(loadAppointments).toHaveBeenCalledTimes(1);
  });
});
