import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const cashierPanelPath = path.resolve(__dirname, '../CashierPanel.jsx');

const readCashierPanelSource = () => fs.readFileSync(cashierPanelPath, 'utf8');

const extractSourceBlock = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('CashierPanel payment action contract', () => {
  it('fails closed when backend payment action fields are missing', () => {
    const source = readCashierPanelSource();
    const helperBlock = extractSourceBlock(
      source,
      'const hasBackendPaymentAction = (paymentRow, action) => {',
      'const CashierPanel = () => {',
    );

    expect(helperBlock).toContain('paymentRow?.available_actions');
    expect(helperBlock).toContain('PAYMENT_ACTION_CAN_FIELD');
    expect(helperBlock).toContain('return false;');
    expect(helperBlock).not.toContain('return true;');
  });

  it('renders all payment history commands from backend-provided actions or can flags', () => {
    const source = readCashierPanelSource();
    const actionCellBlock = extractSourceBlock(
      source,
      'onClick={() => confirmPayment(row.id)}',
      '<td colSpan="7"',
    );

    // UX Audit #4.5: disabled теперь также учитывает processingAction (anti-double-click),
    // но hasBackendPaymentAction(row, '<action>') остаётся обязательной частью условия.
    expect(actionCellBlock).toContain('hasBackendPaymentAction(row, \'confirm\')');
    expect(actionCellBlock).toContain('hasBackendPaymentAction(row, \'cancel\')');
    expect(actionCellBlock).toContain('hasBackendPaymentAction(row, \'refund\')');
    expect(actionCellBlock).toContain('hasBackendPaymentAction(row, \'print_receipt\')');
    expect(actionCellBlock).not.toContain('row.status ===');
    expect(actionCellBlock).not.toContain('payment_status');
  });

  it('does not invent a paid status in receipt print payloads', () => {
    const source = readCashierPanelSource();
    const receiptBlock = extractSourceBlock(
      source,
      'const buildReceiptPrintPayload = (paymentRow) => {',
      'const getPaymentStatusMeta = (status) => {',
    );

    expect(receiptBlock).toContain('status: paymentRow?.status ?? null');
    expect(receiptBlock).not.toContain('status: paymentRow?.status || \'paid\'');
  });

  it('delegates grouped cashier payment allocation to the backend contract', () => {
    const source = readCashierPanelSource();
    const groupedContractBlock = extractSourceBlock(
      source,
      'const createGroupedCashierPayment = async (appointment, paymentData) => {',
      'const PAYMENT_ACTION_CAN_FIELD = {',
    );
    const processPaymentBlock = extractSourceBlock(
      source,
      'const processPayment = async (appointment, paymentData) => {',
      'const confirmPayment = async (paymentId) => {',
    );

    expect(groupedContractBlock).toContain('/cashier/payments/grouped');  // PR-53: axios path (was /api/v1/cashier/payments/grouped)
    expect(groupedContractBlock).toContain('appointment?.can_create_grouped_payment !== true');
    expect(groupedContractBlock).toContain('visit_ids: visitIds');
    expect(processPaymentBlock).toContain('const groupedPayment = isBackendGroupedCashierPayment(appointment);');
    expect(processPaymentBlock).toContain('await createGroupedCashierPayment(appointment, paymentData);');
    expect(processPaymentBlock).toContain('paymentsHook.createPayment');
    expect(processPaymentBlock).not.toContain('remaining_amount -');
    expect(processPaymentBlock).not.toContain('remainingAmount');
    expect(processPaymentBlock).not.toContain('Math.min');
  });

  it('does not route grouped cashier rows through the single-visit online widget', () => {
    const source = readCashierPanelSource();
    // P-018 fix: aria-labels were localized to Russian (PHI removed).
    // The block now ends at the Cash-button aria-label instead of the English one.
    const onlineActionBlock = extractSourceBlock(
      source,
      'onClick={() => openPaymentWidget(appointment)}',
      'aria-label="Принять оплату через кассу"',
    );
    const paymentWidgetBlock = extractSourceBlock(
      source,
      '<PaymentWidget',
      'amount={paymentWidget.selectedItem.remaining_amount',
    );

    expect(onlineActionBlock).toContain('disabled={!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)}');
    expect(paymentWidgetBlock).toContain('canCreateDirectCashierPayment(paymentWidget.selectedItem)');
    expect(paymentWidgetBlock).not.toContain('can_create_grouped_payment');
  });

  it('does not infer direct cashier payment availability from visit ids', () => {
    const source = readCashierPanelSource();
    const helperBlock = extractSourceBlock(
      source,
      'const canCreateDirectCashierPayment = (appointment) => {',
      'const canCreateCashierPayment = (appointment) =>',
    );

    expect(helperBlock).toContain('appointment?.can_create_direct_payment === true');
    expect(helperBlock).not.toContain('resolveSingleCashierVisitId');
    expect(helperBlock).not.toContain('visit_id');
    expect(helperBlock).not.toContain('visit_ids');
  });
});
