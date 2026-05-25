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
      "onClick={() => confirmPayment(row.id)}",
      '<td colSpan="7"',
    );

    expect(actionCellBlock).toContain("disabled={!hasBackendPaymentAction(row, 'confirm')}");
    expect(actionCellBlock).toContain("disabled={!hasBackendPaymentAction(row, 'cancel')}");
    expect(actionCellBlock).toContain("disabled={!hasBackendPaymentAction(row, 'refund')}");
    expect(actionCellBlock).toContain("disabled={!hasBackendPaymentAction(row, 'print_receipt')}");
    expect(actionCellBlock).not.toContain("row.status ===");
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
    expect(receiptBlock).not.toContain("status: paymentRow?.status || 'paid'");
  });
});
