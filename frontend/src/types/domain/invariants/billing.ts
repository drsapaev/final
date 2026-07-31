/**
 * Billing domain invariants (Invoice + Payment).
 *
 * Business rules:
 * 1. Payment amount must be >= 0
 * 2. Invoice cannot be paid after cancellation
 * 3. Invoice paid_amount cannot exceed total amount
 * 4. Payment cannot be applied to a cancelled invoice
 * 5. Refund amount cannot exceed paid amount
 */

import type { Invoice, Payment, Refund } from '../billing';
import type { InvariantResult } from './base';
import { ok, fail } from './base';

/**
 * Invariant: Payment amount is non-negative.
 */
export function checkPaymentAmount(payment: Pick<Payment, 'amount'>): InvariantResult {
  if (payment.amount != null && payment.amount < 0) {
    return fail('payment.negative_amount', 'Payment amount cannot be negative.');
  }
  return ok();
}

/**
 * Invariant: Invoice can be paid (not in cancelled/failed terminal state).
 */
export function checkInvoiceCanBePaid(invoice: Pick<Invoice, 'status'>): InvariantResult {
  if (invoice.status === 'refunded' || invoice.status === 'failed') {
    return fail('invoice.pay_terminal', `Cannot pay an invoice with status '${invoice.status}'.`);
  }
  return ok();
}

/**
 * Invariant: Invoice paid_amount does not exceed total amount.
 */
export function checkInvoicePaidDoesNotExceedTotal(invoice: Pick<Invoice, 'amount' | 'paid_amount'>): InvariantResult {
  const total = invoice.amount;
  const paid = invoice.paid_amount;
  if (total != null && paid != null && paid > total) {
    return fail('invoice.paid_exceeds_total', `Paid amount (${paid}) exceeds total amount (${total}).`);
  }
  return ok();
}

/**
 * Invariant: Payment can be applied to the invoice (invoice is not cancelled/failed).
 */
export function checkPaymentCanBeAppliedToInvoice(
  payment: Pick<Payment, 'status'>,
  invoice: Pick<Invoice, 'status'>,
): InvariantResult {
  if (invoice.status === 'failed') {
    return fail('payment.invoice_failed', 'Cannot apply payment to a failed invoice.');
  }
  if (payment.status === 'refunded') {
    return fail('payment.already_refunded', 'Cannot apply a refunded payment.');
  }
  return ok();
}

/**
 * Invariant: Refund amount does not exceed paid amount.
 */
export function checkRefundDoesNotExceedPaid(
  refund: Pick<Refund, 'amount'>,
  paidAmount: number,
): InvariantResult {
  if (refund.amount != null && refund.amount > paidAmount) {
    return fail('refund.exceeds_paid', `Refund amount (${refund.amount}) exceeds paid amount (${paidAmount}).`);
  }
  return ok();
}

/**
 * Throwing variants.
 */
import { InvariantViolationError } from './base';

export function assertPaymentAmount(payment: Pick<Payment, 'amount'>): void {
  const result = checkPaymentAmount(payment);
  if (!result.ok) throw new InvariantViolationError(result.invariant, result.message);
}

export function assertInvoiceCanBePaid(invoice: Pick<Invoice, 'status'>): void {
  const result = checkInvoiceCanBePaid(invoice);
  if (!result.ok) throw new InvariantViolationError(result.invariant, result.message);
}

export function assertRefundDoesNotExceedPaid(refund: Pick<Refund, 'amount'>, paidAmount: number): void {
  const result = checkRefundDoesNotExceedPaid(refund, paidAmount);
  if (!result.ok) throw new InvariantViolationError(result.invariant, result.message);
}

export { InvariantViolationError } from './base';
