import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const cashierPanelPath = path.resolve(__dirname, '../CashierPanel.tsx');

const readCashierPanelSource = () => fs.readFileSync(cashierPanelPath, 'utf8');

const extractSourceBlock = (source: string, startMarker: string, endMarker: string) => {
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
      'const hasBackendPaymentAction = (paymentRow: CashierPaymentRow | null | undefined, action: string): boolean => {',
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
      '<td colSpan={7}',
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
    // i18n-unification: buildReceiptPrintPayload now takes (paymentRow, labels, defaultPatientLabel)
    // Strict:true migration: signature gained param types + return type (multi-line).
    const receiptBlock = extractSourceBlock(
      source,
      'const buildReceiptPrintPayload = (',
      'const getPaymentStatusMeta = (status: unknown, t: CashierTranslationFn) => {',
    );

    expect(receiptBlock).toContain('status: paymentRow?.status ?? null');
    expect(receiptBlock).not.toContain('status: paymentRow?.status || \'paid\'');
  });

  it('delegates grouped cashier payment allocation to the backend contract', () => {
    const source = readCashierPanelSource();
    const groupedContractBlock = extractSourceBlock(
      source,
      'const createGroupedCashierPayment = async (appointment: Appointment, paymentData: CashierPaymentData) => {',
      'const PAYMENT_ACTION_CAN_FIELD = {',
    );
    const processPaymentBlock = extractSourceBlock(
      source,
      'const processPayment = async (appointment: unknown, paymentData: unknown) => {',
      'const confirmPayment = async (paymentId: string | number | undefined) => {',
    );

    expect(groupedContractBlock).toContain('/cashier/payments/grouped');  // PR-53: axios path (was /api/v1/cashier/payments/grouped)
    expect(groupedContractBlock).toContain('appointment?.can_create_grouped_payment !== true');
    expect(groupedContractBlock).toContain('visit_ids: visitIds');
    expect(processPaymentBlock).toContain('const groupedPayment = isBackendGroupedCashierPayment(appt);');
    expect(processPaymentBlock).toContain('await createGroupedCashierPayment(appt, pData);');
    expect(processPaymentBlock).toContain('paymentsHook.createPayment');
    expect(processPaymentBlock).not.toContain('remaining_amount -');
    expect(processPaymentBlock).not.toContain('remainingAmount');
    expect(processPaymentBlock).not.toContain('Math.min');
  });

  it('does not route grouped cashier rows through the single-visit online widget', () => {
    const source = readCashierPanelSource();
    // P-018 fix: aria-labels were localized to Russian (PHI removed).
    // i18n-unification: aria-labels now use tI18n('cashier.cash_payment_aria')
    const onlineActionBlock = extractSourceBlock(
      source,
      'onClick={() => openPaymentWidget(appointment)}',
      "aria-label={tI18n('cashier.cash_payment_aria')}",
    );
    const paymentWidgetBlock = extractSourceBlock(
      source,
      '<PaymentWidget',
      'amount={Number((paymentWidget.selectedItem as unknown as Appointment).remaining_amount',
    );

    expect(onlineActionBlock).toContain('disabled={!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)}');
    expect(paymentWidgetBlock).toContain('canCreateDirectCashierPayment(paymentWidget.selectedItem as unknown as Appointment)');
    expect(paymentWidgetBlock).not.toContain('can_create_grouped_payment');
  });

  it('does not infer direct cashier payment availability from visit ids', () => {
    const source = readCashierPanelSource();
    const helperBlock = extractSourceBlock(
      source,
      'const canCreateDirectCashierPayment = (appointment: Appointment) => {',
      'const canCreateCashierPayment = (appointment: Appointment) =>',
    );

    expect(helperBlock).toContain('appointment?.can_create_direct_payment === true');
    expect(helperBlock).not.toContain('resolveSingleCashierVisitId');
    expect(helperBlock).not.toContain('visit_id');
    expect(helperBlock).not.toContain('visit_ids');
  });
});
