/**
 * CARDIO-FE-003 (audit 3886 round 20): missing lab values must not be
 * counted as zero in the cardiology blood-test averages.
 *
 * Red-first: on pre-fix source `Number(bt[key])` coerced null/''/whitespace
 * to 0, so [{LDL: 150}, {LDL: null}] reported a mean LDL of 75 (as if the
 * lab had measured 0) and [{LDL: null}, {LDL: ''}] reported 0 instead of
 * "—". The understated average also fed isLdlCritical threshold warnings.
 */
import React from 'react';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../api/client', () => ({
  apiClient: {},
  api: {},
  setSessionInvalidationListener: vi.fn(),
}));

import BloodTestsTab from '../BloodTestsTab';
import { renderWithProviders } from '../../../test/renderWithProviders';

const noop = () => undefined;
const baseProps = {
  bloodTestForm: {},
  setBloodTestForm: noop,
  onNewTest: noop,
  onCancelForm: noop,
  onSubmit: noop,
  getEmptyBloodTestForm: () => ({}),
  getFieldRangeWarning: () => undefined,
  isLdlCritical: (value?: number | string) => Number(value) > 100,
  settings: { ldlThreshold: 100 },
  getColor: (key: string) => (key === 'border' ? '#e5e7eb' : '#111827'),
  getFontSize: () => '14px',
  getSpacing: () => '8px',
};

function statValues() {
  // Stat cards render "<value> <unit>" — extract the numeric cell for LDL.
  const cards = screen.getAllByText(/Средний LDL/);
  return cards;
}

describe('CARDIO-FE-003: averages count only explicitly present measurements', () => {
  it('a missing LDL (null) does not drag the mean toward zero', () => {
    renderWithProviders(
      <BloodTestsTab
        {...baseProps}
        bloodTests={[
          { id: 1, test_date: '2026-11-01', cholesterol_ldl: 150 },
          // The backend CardioBloodTestOut permits None for optional
          // measurements; the frontend interface does not model that, so
          // the runtime null is cast to satisfy the declared prop type.
          { id: 2, test_date: '2026-11-02', cholesterol_ldl: null as unknown as number },
        ]}
      />,
    );
    const label = statValues()[0].closest('div')!.parentElement!;
    // Mean of the single measured 150 — NOT (150 + 0) / 2 = 75.
    expect(label.textContent).toMatch(/150(\.0)?\s/);
    expect(label.textContent).not.toMatch(/75/);
  });

  it('empty and whitespace strings are missing too — mean 150, not 75', () => {
    renderWithProviders(
      <BloodTestsTab
        {...baseProps}
        bloodTests={[
          { id: 1, test_date: '2026-11-01', cholesterol_ldl: 150 },
          { id: 2, test_date: '2026-11-02', cholesterol_ldl: '' },
          { id: 3, test_date: '2026-11-03', cholesterol_ldl: '   ' },
        ]}
      />,
    );
    const label = statValues()[0].closest('div')!.parentElement!;
    expect(label.textContent).toMatch(/150(\.0)?\s/);
    // The mean must NOT be 50 (the (150+0+0)/3 coercion artifact).
    expect(label.textContent).not.toMatch(/(^|[^\d])50(\.0)?\s*мг/);
  });

  it('all-missing (null + empty) renders the "—" placeholder, not 0', () => {
    renderWithProviders(
      <BloodTestsTab
        {...baseProps}
        bloodTests={[
          { id: 1, test_date: '2026-11-01', cholesterol_ldl: null as unknown as number },
          { id: 2, test_date: '2026-11-02', cholesterol_ldl: '' },
        ]}
      />,
    );
    const label = statValues()[0].closest('div')!.parentElement!;
    expect(label.textContent).toContain('—');
    expect(label.textContent).not.toMatch(/\b0\s/);
  });

  it('a genuine measured numeric 0 stays eligible in the mean', () => {
    renderWithProviders(
      <BloodTestsTab
        {...baseProps}
        bloodTests={[
          { id: 1, test_date: '2026-11-01', glucose: 0 },
          { id: 2, test_date: '2026-11-02', glucose: 10 },
        ]}
      />,
    );
    // Average glucose card: (0 + 10) / 2 = 5.
    const glucoseCard = screen.getAllByText(/глюкоз/i)
      .map((el) => el.closest('div')!.parentElement!)
      .find((el) => /5(\.0)?\s/.test(el.textContent ?? ''));
    expect(glucoseCard).toBeDefined();
  });

  it('invalid non-numeric strings are excluded instead of becoming NaN/0', () => {
    renderWithProviders(
      <BloodTestsTab
        {...baseProps}
        bloodTests={[
          { id: 1, test_date: '2026-11-01', cholesterol_total: 'abc' },
          { id: 2, test_date: '2026-11-02', cholesterol_total: 200 },
        ]}
      />,
    );
    const cholesterolCard = screen.getAllByText(/Средний общий холестерин/)
      .map((el) => el.closest('div')!.parentElement!);
    expect(cholesterolCard[0].textContent).toMatch(/200(\.0)?\s/);
  });
});
