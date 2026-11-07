/**
 * LABH-FE-001 (audit 3886, ledger group «report history and Telegram
 * result notification contract») — fail-first regression for the report
 * history selected-item highlight:
 *
 * `ReportSidebar` passed `activeInstanceId={(typeof activeInstance?.id ===
 * 'number' ? null : undefined)}` — ALWAYS null/undefined — so the history
 * panel's active-report highlight could never appear. The fix passes the
 * real active ID, and the history panel compares IDs through a stable
 * string normalization (numeric vs string) and exposes the current row
 * accessibly via aria-current, not by background color alone.
 *
 * Red-first: on the pre-fix source no row is highlighted even with an open
 * report.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

import LabReportHistoryPanel from '../LabReportHistoryPanel';

const HISTORY_ITEMS = [
  {
    id: 77,
    patient_id: 444,
    status: 'FINALIZED',
    created_at: '2026-11-05T10:00:00Z',
    patient_snapshot: { full_name: 'SYNTHETIC Пациент А' },
    template: { name: 'ОАК' },
  },
  {
    id: 78,
    patient_id: 445,
    status: 'FINALIZED',
    created_at: '2026-11-05T11:00:00Z',
    patient_snapshot: { full_name: 'SYNTHETIC Пациент Б' },
    template: { name: 'БХ' },
  },
];

function renderPanel(activeInstanceId: string | number | null | undefined) {
  return render(
    <ThemeProvider>
      <LabReportHistoryPanel
        reportHistory={HISTORY_ITEMS as never[]}
        historySeverityFilter="all"
        onSeverityFilterChange={vi.fn()}
        activeInstanceId={activeInstanceId}
        onOpenInstance={vi.fn()}
      />
    </ThemeProvider>
  );
}

function historyRow(patientName: string): HTMLElement {
  const row = screen.getByRole('button', {
    name: new RegExp(`,\\s*${patientName},`),
  });
  return row;
}

describe('LABH-FE-001 — the open report is highlighted in the history', () => {
  it('highlights ONLY the row matching the active report ID (pre-fix: never highlighted)', () => {
    renderPanel(77);

    const row77 = historyRow('SYNTHETIC Пациент А');
    const row78 = historyRow('SYNTHETIC Пациент Б');

    expect(row77.getAttribute('aria-current')).toBe('true');
    expect(row78.getAttribute('aria-current')).toBeNull();

    const activeBg = row77.style.background;
    const inactiveBg = row78.style.background;
    expect(activeBg).not.toBe(inactiveBg);
  });

  it('a string-typed active ID highlights the numeric history row (stable normalization)', () => {
    renderPanel('77');
    expect(historyRow('SYNTHETIC Пациент А').getAttribute('aria-current')).toBe('true');
    expect(historyRow('SYNTHETIC Пациент Б').getAttribute('aria-current')).toBeNull();
  });

  it('no selection highlights nothing', () => {
    renderPanel(null);
    expect(historyRow('SYNTHETIC Пациент А').getAttribute('aria-current')).toBeNull();
    expect(historyRow('SYNTHETIC Пациент Б').getAttribute('aria-current')).toBeNull();
  });
});
