/**
 * Tests for billing domain invariants.
 */

import { describe, it, expect } from 'vitest';
import {
  checkPaymentAmount,
  checkInvoiceCanBePaid,
  checkInvoicePaidDoesNotExceedTotal,
  checkPaymentCanBeAppliedToInvoice,
  checkRefundDoesNotExceedPaid,
  assertPaymentAmount,
  assertInvoiceCanBePaid,
  InvariantViolationError,
} from '../billing';

describe('checkPaymentAmount', () => {
  it('passes for positive amount', () => {
    expect(checkPaymentAmount({ amount: 100 }).ok).toBe(true);
  });

  it('passes for zero amount', () => {
    expect(checkPaymentAmount({ amount: 0 }).ok).toBe(true);
  });

  it('passes for undefined amount', () => {
    expect(checkPaymentAmount({ amount: undefined }).ok).toBe(true);
  });

  it('fails for negative amount', () => {
    const result = checkPaymentAmount({ amount: -50 });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('payment.negative_amount');
  });
});

describe('checkInvoiceCanBePaid', () => {
  it('allows paying a pending invoice', () => {
    expect(checkInvoiceCanBePaid({ status: 'pending' }).ok).toBe(true);
  });

  it('allows paying a partial invoice', () => {
    expect(checkInvoiceCanBePaid({ status: 'partial' }).ok).toBe(true);
  });

  it('blocks paying a refunded invoice', () => {
    const result = checkInvoiceCanBePaid({ status: 'refunded' });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('invoice.pay_terminal');
  });

  it('blocks paying a failed invoice', () => {
    const result = checkInvoiceCanBePaid({ status: 'failed' });
    expect(result.ok).toBe(false);
  });
});

describe('checkInvoicePaidDoesNotExceedTotal', () => {
  it('passes when paid equals total', () => {
    expect(checkInvoicePaidDoesNotExceedTotal({ amount: 100, paid_amount: 100 }).ok).toBe(true);
  });

  it('passes when paid is less than total', () => {
    expect(checkInvoicePaidDoesNotExceedTotal({ amount: 100, paid_amount: 50 }).ok).toBe(true);
  });

  it('fails when paid exceeds total', () => {
    const result = checkInvoicePaidDoesNotExceedTotal({ amount: 100, paid_amount: 150 });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('invoice.paid_exceeds_total');
  });

  it('passes when amounts are undefined', () => {
    expect(checkInvoicePaidDoesNotExceedTotal({ amount: undefined, paid_amount: undefined }).ok).toBe(true);
  });
});

describe('checkPaymentCanBeAppliedToInvoice', () => {
  it('allows payment to pending invoice', () => {
    expect(checkPaymentCanBeAppliedToInvoice(
      { status: 'pending' },
      { status: 'pending' },
    ).ok).toBe(true);
  });

  it('blocks payment to failed invoice', () => {
    const result = checkPaymentCanBeAppliedToInvoice(
      { status: 'pending' },
      { status: 'failed' },
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('payment.invoice_failed');
  });

  it('blocks already-refunded payment', () => {
    const result = checkPaymentCanBeAppliedToInvoice(
      { status: 'refunded' },
      { status: 'pending' },
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('payment.already_refunded');
  });
});

describe('checkRefundDoesNotExceedPaid', () => {
  it('passes when refund equals paid', () => {
    expect(checkRefundDoesNotExceedPaid({ amount: 100 }, 100).ok).toBe(true);
  });

  it('passes when refund is less than paid', () => {
    expect(checkRefundDoesNotExceedPaid({ amount: 50 }, 100).ok).toBe(true);
  });

  it('fails when refund exceeds paid', () => {
    const result = checkRefundDoesNotExceedPaid({ amount: 150 }, 100);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('refund.exceeds_paid');
  });
});

describe('throwing variants', () => {
  it('assertPaymentAmount throws for negative', () => {
    expect(() => assertPaymentAmount({ amount: -10 })).toThrow(InvariantViolationError);
  });

  it('assertInvoiceCanBePaid throws for refunded', () => {
    expect(() => assertInvoiceCanBePaid({ status: 'refunded' })).toThrow(InvariantViolationError);
  });

  it('does not throw for valid values', () => {
    expect(() => assertPaymentAmount({ amount: 100 })).not.toThrow();
    expect(() => assertInvoiceCanBePaid({ status: 'pending' })).not.toThrow();
  });
});
