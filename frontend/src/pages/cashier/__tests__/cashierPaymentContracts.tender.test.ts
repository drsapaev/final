/**
 * CSH-FE-040 (follow-up audit 2026-11-02): кассовое подтверждение
 * «внесено/сдача» проходит в API-пейлоад, а не теряется в сужении.
 *
 * Red-first: grouped-кейс на префиксном коде отправлял ТОЛЬКО
 * amount/method/note/client_request_id — поля received_amount/change_due
 * отсутствовали в теле POST /cashier/payments/grouped.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock('../../../api/client', () => ({
  api: { post: apiMocks.post, get: vi.fn(), defaults: { headers: { common: {} } } },
}));

vi.mock('../../../utils/tokenManager', () => ({
  default: { getAccessToken: () => 'test-token' },
}));

import {
  buildCashierPaymentPayload,
  createGroupedCashierPayment,
  type CashierPaymentData,
} from '../cashierPaymentContracts';
import type { Appointment } from '../../../types/domain/clinic';

const GROUPED_APPOINTMENT = {
  patient_id: 7,
  can_create_grouped_payment: true,
  visit_ids: [11, 12],
} as unknown as Appointment;

describe('CSH-FE-040: cash tender reaches the payment contract', () => {
  beforeEach(() => {
    apiMocks.post.mockReset();
    apiMocks.post.mockResolvedValue({ data: { success: true } });
  });

  it('buildCashierPaymentPayload keeps received_amount/change_due for cash', () => {
    const payload = buildCashierPaymentPayload(42, {
      amount: 100000,
      method: 'cash',
      received_amount: 150000,
      change_due: 50000,
      client_request_id: 'idem-1',
    }, 'default note');
    expect(payload).toMatchObject({
      visit_id: 42,
      amount: 100000,
      method: 'cash',
      received_amount: 150000,
      change_due: 50000,
      client_request_id: 'idem-1',
    });
  });

  it('buildCashierPaymentPayload omits tender for non-cash methods', () => {
    const payload = buildCashierPaymentPayload(42, {
      amount: 100000,
      method: 'card',
      received_amount: 150000,
      change_due: 50000,
    } as CashierPaymentData, 'note');
    expect(payload).not.toHaveProperty('received_amount');
    expect(payload).not.toHaveProperty('change_due');
  });

  it('buildCashierPaymentPayload omits absent tender (legacy callers)', () => {
    const payload = buildCashierPaymentPayload(42, { amount: 1000, method: 'cash' }, 'n');
    expect(payload).not.toHaveProperty('received_amount');
    expect(payload).not.toHaveProperty('change_due');
  });

  it('grouped cashier payment body carries the cash tender', async () => {
    await createGroupedCashierPayment(GROUPED_APPOINTMENT, {
      amount: 100000,
      method: 'cash',
      received_amount: 150000,
      change_due: 50000,
    });
    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    const [, body] = apiMocks.post.mock.calls[0] as [string, Record<string, unknown>];
    expect(body.received_amount).toBe(150000);
    expect(body.change_due).toBe(50000);
  });

  it('grouped cashier payment body omits tender for card', async () => {
    await createGroupedCashierPayment(GROUPED_APPOINTMENT, {
      amount: 100000,
      method: 'card',
      received_amount: 150000,
      change_due: 50000,
    } as CashierPaymentData);
    const [, body] = apiMocks.post.mock.calls[0] as [string, Record<string, unknown>];
    expect(body).not.toHaveProperty('received_amount');
    expect(body).not.toHaveProperty('change_due');
  });
});
