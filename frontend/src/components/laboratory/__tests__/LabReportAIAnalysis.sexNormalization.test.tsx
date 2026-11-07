/**
 * LABAI-FE-002 (audit 3886, ledger group «report history and Telegram
 * result notification contract») — fail-first regression for the AI sex
 * prerequisite:
 *
 * `normalizeSexForAI()` coalesced EVERY non-empty string into 'other', so
 * legacy/free-form values ('unknown', 'N/A', '?', whitespace, unexpected
 * codes) passed the AI prerequisite as a fabricated «other» demographic —
 * obscuring that the clinical parameter is UNKNOWN. The canonical backend
 * domain is M|F|X: a legitimate non-binary 'X' must stay supported while
 * unknown values fail closed (AI blocked).
 *
 * Red-first: on the pre-fix source the 'unknown'/'N/A'/'?' cases render an
 * ENABLED AI button (falsely accepted as 'other').
 */
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

import LabReportAIAnalysis from '../LabReportAIAnalysis';

const FILLED_SECTIONS = [
  {
    key: 'cbc',
    title: 'CBC',
    fields: [
      { field_key: 'hgb', label: 'Гемоглобин', value_type: 'numeric', value_text: '140', comment: null },
    ],
  },
];

function instanceWithSex(sex: unknown) {
  return {
    id: 91,
    status: 'FINALIZED',
    patient_id: 444,
    sections: FILLED_SECTIONS,
    patient_snapshot: { patient_id: 444, full_name: 'SYNTHETIC Пациент', age_years: 30, sex },
  } as never;
}

function renderAnalysis(sex: unknown) {
  const view = render(
    <ThemeProvider>
      <LabReportAIAnalysis activeInstance={instanceWithSex(sex)} notify={vi.fn()} />
    </ThemeProvider>
  );
  const button = view.container.querySelector('button') as HTMLButtonElement;
  return { view, button };
}

describe('LABAI-FE-002 — unknown sex values fail closed instead of becoming «other»', () => {
  it.each([
    ['unknown'],
    ['N/A'],
    ['?'],
    ['  '],
    ['something-legacy'],
  ])('sex %j blocks the AI analysis (pre-fix: accepted as other)', (sex) => {
    const { view, button } = renderAnalysis(sex);
    expect(button.disabled).toBe(true);
    // The honest blocked reason names the missing sex parameter.
    expect(
      view.container.querySelector('[title*=\'не указан пол\']')
    ).not.toBeNull();
    view.unmount();
  });

  it.each([
    ['M'],
    ['male'],
    ['F'],
    ['female'],
  ])('canonical sex %j keeps the AI analysis available', (sex) => {
    const { view, button } = renderAnalysis(sex);
    expect(button.disabled).toBe(false);
    view.unmount();
  });

  it('a legitimate non-binary X stays a supported «other» category', () => {
    const { view, button } = renderAnalysis('X');
    // The button stays available: X is a known demographic, not unknown.
    expect(button.disabled).toBe(false);
    view.unmount();
  });

  it('empty/null sex still blocks (existing fail-closed behavior preserved)', () => {
    const nullView = renderAnalysis(null);
    expect(nullView.button.disabled).toBe(true);
    nullView.view.unmount();

    const emptyView = renderAnalysis('');
    expect(emptyView.button.disabled).toBe(true);
    emptyView.view.unmount();
  });
});
