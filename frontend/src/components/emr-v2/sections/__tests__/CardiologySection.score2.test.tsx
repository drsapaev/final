import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import '@/i18n'; // side-effect: initialize i18n (ru) for component text

/**
 * EMRSCORE-FE-001, EMRSCORE-FE-002, EMRCARD-FE-001 (audit 3886, round 21) — fail-first.
 *
 * EMRSCORE-FE-001: the risk tab used to feed the legacy mg/dL cholesterol
 * straight into a per-mmol/L formula and present the clamped product as a
 * «SCORE2 10-летний риск» with fixed 5/10/20% treatment bands. The tests pin
 * that NO fabricated number/category/recommendation is ever rendered, and that
 * mg/dL ↔ mmol/L conversion is unit-explicit (exact 38.67 divisor, display only).
 *
 * EMRSCORE-FE-002: SCORE2 eligibility gates — hard 40–69 age band, no
 * established CVD, no diabetes, explicit ESC risk region. Out-of-cohort
 * synthetic patients must get an explicit «not applicable» verdict, never a
 * pseudo-numeric score.
 *
 * EMRCARD-FE-001: the four specialty tab buttons only switch the local view;
 * they must stay clickable for signed/completed (disabled) EMRs so the doctor
 * can read the Echo/Labs/Risk summaries, while clinical inputs stay disabled.
 *
 * The assertions below fail on the pre-fix source.
 */

vi.mock('@/hooks/useDoctorPhrases', () => ({
  useDoctorPhrases: () => ({ suggestions: [], loading: false }),
}));

import CardiologySectionRaw from '../specialty/CardiologySection';

const CardiologySection = CardiologySectionRaw as unknown as React.ComponentType<Record<string, unknown>>;

type LabResults = Record<string, string>;

const FULL_ELIGIBLE: LabResults = {
  patient_age: '55',
  patient_sex: 'male',
  smoking: 'no',
  systolic_bp: '130',
  score2_chol: '5.17',
  score2_chol_unit: 'mmol',
  prior_cvd: 'no',
  diabetes: 'no',
  risk_region: 'low',
};

function renderCardio(opts: { disabled?: boolean; labResults?: LabResults } = {}) {
  const onChange = vi.fn();
  const labResults = opts.labResults ?? FULL_ELIGIBLE;
  const utils = render(
    <ThemeProvider>
      <CardiologySection
        ecgData={{ heart_rate: 72, rhythm: 'синусовый' }}
        echoData={{ ef: 55, conclusion: 'без патологии' }}
        labResults={labResults}
        onChange={onChange as unknown as (field: string, value: unknown) => void}
        disabled={opts.disabled ?? false}
      />
    </ThemeProvider>
  );
  return { ...utils, onChange };
}

function openRiskTab() {
  fireEvent.click(screen.getByRole('button', { name: 'Риски' }));
}

function openTabByName(name: string) {
  fireEvent.click(screen.getByRole('button', { name }));
}

function getVerdict(): HTMLElement {
  return screen.getByTestId('score2-verdict');
}

/** Find a <select> by one of its option labels (selects lack label wiring). */
function getSelectWithOption(optionText: string): HTMLSelectElement {
  const selects = Array.from(document.querySelectorAll('select')) as HTMLSelectElement[];
  const found = selects.find((s) =>
    Array.from(s.options).some((o) => (o.textContent || '').trim() === optionText)
  );
  if (!found) throw new Error(`select with option "${optionText}" not found`);
  return found;
}

describe('EMRCARD-FE-001: specialty tab navigation stays available when read-only', () => {
  it('renders all four tab buttons enabled for a disabled (signed/completed) section', () => {
    renderCardio({ disabled: true });
    for (const name of ['ЭКГ', 'ЭхоКГ', 'Анализы', 'Риски']) {
      const btn = screen.getByRole('button', { name }) as HTMLButtonElement;
      expect(btn.disabled).toBe(false);
    }
  });

  it('reveals the read-only Echo summary and keeps clinical inputs disabled', () => {
    renderCardio({ disabled: true });
    openTabByName('ЭхоКГ');
    expect(screen.getByText('ЭхоКГ доступна на отдельной вкладке')).toBeInTheDocument();
    expect(screen.getByText('без патологии')).toBeInTheDocument(); // echo conclusion is reviewable

    openTabByName('Анализы');
    const troponin = screen.getByLabelText('Тропонин I (нг/мл)') as HTMLInputElement;
    expect(troponin).toBeDisabled();

    openRiskTab();
    const age = screen.getByLabelText('Возраст (лет)') as HTMLInputElement;
    expect(age).toBeDisabled();
    const region = getSelectWithOption('Выберите');
    expect(region).toBeDisabled();
  });

  it('still writes lab edits through onChange when the section is editable', () => {
    renderCardio({ disabled: false });
    openTabByName('Анализы');
    const troponin = screen.getByLabelText('Тропонин I (нг/мл)');
    expect(troponin).not.toBeDisabled();
    fireEvent.change(troponin, { target: { value: '0.02' } });
    // positive control: editability decoupled from navigation, not removed
  });
});

describe('EMRSCORE-FE-001: no fabricated SCORE2 number is ever displayed', () => {
  it('renders NO numeric risk, category, legend or 10-year claim for the old complete input set', () => {
    // The PRE-FIX input shape: everything the old calculator needed
    // (cholesterol_total in legacy mg/dL storage) used to produce a fabricated
    // clamped percentage with treatment advice.
    const { container } = renderCardio({
      labResults: {
        patient_age: '50',
        patient_sex: 'male',
        smoking: 'no',
        systolic_bp: '120',
        cholesterol_total: '200',
      },
    });
    openRiskTab();
    expect(container.querySelector('.cardiology-risk-score')).toBeNull();
    expect(container.querySelector('.cardiology-risk-category')).toBeNull();
    expect(container.querySelector('.cardiology-risk-legend')).toBeNull();
    expect(screen.queryByText(/10-летний риск/)).toBeNull();
    const verdict = getVerdict();
    expect(verdict.textContent || '').not.toMatch(/%/);
  });

  it('renders NO numeric risk for a fully eligible patient either — honest pointer instead', () => {
    const { container } = renderCardio({ labResults: FULL_ELIGIBLE });
    openRiskTab();
    const verdict = getVerdict();
    expect(verdict.textContent || '').toContain('Условия применимости SCORE2 выполнены');
    expect(container.querySelector('.cardiology-risk-score')).toBeNull();
    expect(verdict.textContent || '').not.toMatch(/%/);
  });

  it('converts mg/dL to mmol/L with the exact 38.67 divisor for display only', () => {
    // Ledger synthetic pair: 200 mg/dL ≈ 5.17 mmol/L
    const { container, rerender } = renderCardio({
      labResults: { ...FULL_ELIGIBLE, score2_chol: '200', score2_chol_unit: 'mgdl' },
    });
    openRiskTab();
    expect(screen.getByTestId('score2-chol-equiv').textContent).toContain('5.2');
    expect(getVerdict().textContent || '').toContain('5.2'); // canonical mmol/L echo

    // Second ledger pair: 150 mg/dL ≈ 3.88 mmol/L
    rerender(
      <ThemeProvider>
        <CardiologySection
          labResults={{ ...FULL_ELIGIBLE, score2_chol: '150', score2_chol_unit: 'mgdl' }}
          onChange={vi.fn() as unknown as (field: string, value: unknown) => void}
        />
      </ThemeProvider>
    );
    expect(screen.getByTestId('score2-chol-equiv').textContent).toContain('3.9');
    expect(getVerdict().textContent || '').toContain('3.9');

    // mmol/L entry of the equivalent value shows the same canonical echo
    rerender(
      <ThemeProvider>
        <CardiologySection
          labResults={{ ...FULL_ELIGIBLE, score2_chol: '3.88', score2_chol_unit: 'mmol' }}
          onChange={vi.fn() as unknown as (field: string, value: unknown) => void}
        />
      </ThemeProvider>
    );
    expect(container.querySelector('[data-testid="score2-chol-equiv"]')).toBeNull(); // no conversion needed
    expect(getVerdict().textContent || '').toContain('3.9');
  });
});

describe('EMRSCORE-FE-002: eligibility gates produce explicit not-applicable verdicts', () => {
  it('age 25 (below the 40–69 cohort) gets a not-applicable notice, never a number', () => {
    const { container } = renderCardio({ labResults: { ...FULL_ELIGIBLE, patient_age: '25' } });
    openRiskTab();
    expect(getVerdict().textContent || '').toMatch(/40–69/);
    expect(container.querySelector('.cardiology-risk-score')).toBeNull();
  });

  it('age 85 (above the cohort) gets the same not-applicable notice', () => {
    renderCardio({ labResults: { ...FULL_ELIGIBLE, patient_age: '85' } });
    openRiskTab();
    expect(getVerdict().textContent || '').toMatch(/40–69/);
  });

  it('established CVD is outside the SCORE2 population', () => {
    renderCardio({ labResults: { ...FULL_ELIGIBLE, prior_cvd: 'yes' } });
    openRiskTab();
    expect(getVerdict().textContent || '').toMatch(/SCORE2 неприменим/);
    expect(getVerdict().textContent || '').not.toMatch(/%/);
  });

  it('diabetes is outside the SCORE2 population', () => {
    renderCardio({ labResults: { ...FULL_ELIGIBLE, diabetes: 'yes' } });
    openRiskTab();
    expect(getVerdict().textContent || '').toMatch(/SCORE2 неприменим/);
  });

  it('missing ESC risk region is an explicit not-evaluable state', () => {
    renderCardio({ labResults: { ...FULL_ELIGIBLE, risk_region: '' } });
    openRiskTab();
    expect(getVerdict().textContent || '').toMatch(/Оценка невозможна/);
    expect(getVerdict().textContent || '').not.toMatch(/%/);
  });

  it('incomplete inputs keep the fill-in placeholder (no partial verdicts)', () => {
    renderCardio({ labResults: { patient_age: '55' } });
    openRiskTab();
    expect(getVerdict().textContent || '').toContain('Заполните все поля');
  });

  it('boundary ages 40 and 69 are inside the cohort (eligible verdict)', () => {
    renderCardio({ labResults: { ...FULL_ELIGIBLE, patient_age: '40' } });
    openRiskTab();
    expect(getVerdict().textContent || '').toContain('Условия применимости SCORE2 выполнены');
  });

  it('persisted shape: eligibility inputs flow through onChange as plain facts', () => {
    const { onChange } = renderCardio({ labResults: FULL_ELIGIBLE });
    openRiskTab();
    const region = getSelectWithOption('Низкий риск-регион');
    fireEvent.change(region, { target: { value: 'high' } });
    expect(onChange).toHaveBeenCalledWith('cardio_labs', { ...FULL_ELIGIBLE, risk_region: 'high' });
  });
});
