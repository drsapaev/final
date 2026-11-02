/**
 * CSH-FE-036 P2 regression (PR #3830 review, comment 4439005298):
 * CashierStatsCard must distinguish a MISSING stats field from a real zero.
 *
 * Rolling deployments can pair this frontend with an older /cashier/stats
 * that predates the net-of-refunds contract — such a response has no
 * refunded_amount / net_total_amount keys. Those tiles must render «—»
 * (value unavailable), NOT a fake «0 сум» that misreports real receipts.
 * A real zero reported by the current API still renders as «0 сум».
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../../components/ui/macos', () => ({
  Card: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Button: (props: Record<string, unknown>) => <button {...props} />,
}));

import CashierStatsCard from '../CashierStatsCard';
import type { CashierStatsSnapshot } from '../../useCashierWorklistData';
import type { CashierTranslationFn } from '../../cashierPaymentContracts';

const tI18n: CashierTranslationFn = (key) => key;

/** /cashier/stats BEFORE CSH-FE-036: gross counters only, no net keys. */
const legacyApiSnapshot: CashierStatsSnapshot = {
  total_amount: 100000,
  cash_amount: 60000,
  card_amount: 40000,
  pending_count: 2,
  pending_amount: 25000,
  paid_count: 3,
  cancelled_count: 1,
};

/** Value shown by the tile whose caption key is `captionKey`. */
const tileValue = (captionKey: string): string => {
  const captionEl = screen.getByText(captionKey);
  const valueEl = captionEl.previousElementSibling;
  // ru-RU Intl grouping uses U+00A0 — normalize for exact assertions.
  return (valueEl?.textContent ?? '').replace(/\u00A0/g, ' ');
};

const renderCard = (stats: CashierStatsSnapshot) =>
  render(
    <CashierStatsCard
      isHistoryTab={true}
      stats={stats}
      onRefresh={vi.fn()}
      onExport={vi.fn()}
      onHourlyStats={vi.fn()}
      tI18n={tI18n}
    />,
  );

describe('CashierStatsCard — CSH-FE-036 P2: missing field ≠ zero (4439005298)', () => {
  it('renders «—» for refunds/net tiles when the old API omits the new fields', () => {
    renderCard(legacyApiSnapshot);

    // Gross tiles keep showing the real legacy amounts.
    expect(tileValue('cashier.total_period')).toBe('100 000 сум');
    expect(tileValue('cashier.method_cash')).toBe('60 000 сум');
    expect(tileValue('cashier.method_card')).toBe('40 000 сум');

    // Missing fields must NOT be reported as zero receipts/refunds.
    expect(tileValue('cashier.refunded_total')).toBe('—');
    expect(tileValue('cashier.net_total')).toBe('—');
  });

  it('renders a real zero as «0 сум» when the current API reports zero', () => {
    renderCard({
      ...legacyApiSnapshot,
      refunded_amount: 0,
      net_total_amount: 0,
      net_cash_amount: 0,
      net_card_amount: 0,
    });

    expect(tileValue('cashier.refunded_total')).toBe('0 сум');
    expect(tileValue('cashier.net_total')).toBe('0 сум');
  });

  it('renders net values when the current API supplies them', () => {
    renderCard({
      ...legacyApiSnapshot,
      refunded_amount: 7000,
      net_total_amount: 93000,
      net_cash_amount: 56000,
      net_card_amount: 37000,
    });

    expect(tileValue('cashier.refunded_total')).toBe('7 000 сум');
    expect(tileValue('cashier.net_total')).toBe('93 000 сум');
  });

  it('EMPTY_STATS-shaped snapshot: net tiles «—», legacy zeros stay «0 сум»', () => {
    // Initial/failed-load snapshot: CSH-FE-036 keys absent → «—»,
    // legacy counters keep the whole-card zero convention.
    renderCard({
      total_amount: 0,
      cash_amount: 0,
      card_amount: 0,
      pending_count: 0,
      pending_amount: 0,
      paid_count: 0,
      cancelled_count: 0,
    });

    expect(tileValue('cashier.total_period')).toBe('0 сум');
    expect(tileValue('cashier.refunded_total')).toBe('—');
    expect(tileValue('cashier.net_total')).toBe('—');
  });
});
