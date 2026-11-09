import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import '@/i18n'; // side-effect: initialize i18n (ru) for component text

/**
 * EMRVITAL-FE-001 (audit 3886, round 21) — fail-first.
 *
 * Pre-fix: BMI was computed from any truthy `vitals.height`/`vitals.weight`.
 * HTML number inputs supply STRINGS, so height '0' is truthy and the widget
 * rendered «ИМТ: Infinity»; negative height/weight, SpO₂ 150 and pulse -1
 * were silently accepted with no feedback. Post-fix every field is parsed
 * with Number() and checked against a physiologically possible range; BMI is
 * computed only from positive finite values, and out-of-range entries get an
 * explicit in-place invalid flag (class + aria-invalid + hint) instead of
 * being transformed into plausible results.
 *
 * The bug-case assertions below fail on the pre-fix source; the valid-value
 * and BP-warning cases are positive controls that stay green.
 */

import VitalsWidgetRaw from '../VitalsWidget';

const VitalsWidget = VitalsWidgetRaw as unknown as React.ComponentType<Record<string, unknown>>;

function renderVitals(vitals: Record<string, string>) {
  const onChange = vi.fn();
  const utils = render(
    <ThemeProvider>
      <VitalsWidget vitals={vitals} onChange={onChange as unknown as (v: Record<string, unknown>) => void} />
    </ThemeProvider>
  );
  return { ...utils, onChange };
}

const fieldByAria = (label: string) => screen.getByLabelText(label) as HTMLInputElement;

describe('EMRVITAL-FE-001: BMI integrity', () => {
  it('never renders an Infinity BMI for height "0" and flags the field invalid', () => {
    renderVitals({ height: '0', weight: '70' });
    expect(screen.queryByText(/ИМТ/)).toBeNull();
    expect(document.body.textContent || '').not.toMatch(/Infinity|NaN/);
    const height = fieldByAria('Height in centimeters');
    expect(height).toHaveAttribute('aria-invalid', 'true');
    expect(document.querySelectorAll('.emr-vitals__field--invalid').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Значение вне клинического диапазона/).length).toBeGreaterThan(0);
  });

  it('never renders a BMI for negative anthropometry and flags both fields', () => {
    renderVitals({ height: '-170', weight: '-60' });
    expect(screen.queryByText(/ИМТ/)).toBeNull();
    expect(document.body.textContent || '').not.toMatch(/Infinity|NaN/);
    expect(fieldByAria('Height in centimeters')).toHaveAttribute('aria-invalid', 'true');
    expect(fieldByAria('Weight in kilograms')).toHaveAttribute('aria-invalid', 'true');
  });

  it('zero weight (below the clinical minimum) yields no BMI and an invalid flag', () => {
    renderVitals({ height: '170', weight: '0' });
    expect(screen.queryByText(/ИМТ/)).toBeNull();
    expect(fieldByAria('Weight in kilograms')).toHaveAttribute('aria-invalid', 'true');
  });

  it('positive control: valid adult anthropometry still renders the correct BMI', () => {
    renderVitals({ height: '170', weight: '70' });
    expect(screen.getByText('ИМТ: 24.2')).toBeInTheDocument();
    expect(document.querySelectorAll('.emr-vitals__field--invalid').length).toBe(0);
  });

  it('BMI is marked, never rewritten: the raw entry still flows to onChange untouched', () => {
    const { onChange } = renderVitals({ height: '0', weight: '70' });
    const height = fieldByAria('Height in centimeters');
    // '1' is a DIFFERENT but still invalid value (below the 20 cm clinical
    // minimum) so React's value tracker actually dispatches the change.
    fireEvent.change(height, { target: { value: '1' } });
    expect(onChange).toHaveBeenCalled();
    const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as Record<string, string>;
    expect(last.height).toBe('1'); // not clamped, not blanked — flagged instead
    expect(fieldByAria('Height in centimeters')).toHaveAttribute('aria-invalid', 'true');
  });
});

describe('EMRVITAL-FE-001: clinical range validation with explicit feedback', () => {
  it('SpO₂ 150 is out of range and flagged', () => {
    renderVitals({ spo2: '150' });
    expect(fieldByAria('Blood oxygen saturation')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getAllByText(/клинического диапазона/).length).toBeGreaterThan(0);
  });

  it('pulse -1 is out of range and flagged', () => {
    renderVitals({ pulse: '-1' });
    expect(fieldByAria('Pulse')).toHaveAttribute('aria-invalid', 'true');
  });

  it('implausible BP values are flagged while real hypertension warnings are preserved', () => {
    // 190/110 is physiologically possible → keeps the pre-existing critical
    // warning, and is NOT flagged invalid (macos Input always renders
    // aria-invalid="false" for valid fields — only "true" means invalid).
    renderVitals({ systolic: '190', diastolic: '110' });
    expect(fieldByAria('Systolic blood pressure')).not.toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('⚠️ Криз')).toBeInTheDocument();
  });

  it('out-of-range systolic (350) is flagged invalid', () => {
    renderVitals({ systolic: '350' });
    expect(fieldByAria('Systolic blood pressure')).toHaveAttribute('aria-invalid', 'true');
  });

  it('empty fields are simply not filled — no invalid noise', () => {
    renderVitals({});
    expect(document.querySelectorAll('.emr-vitals__field--invalid').length).toBe(0);
    expect(screen.queryByText(/клинического диапазона/)).toBeNull();
    expect(screen.queryByText(/ИМТ/)).toBeNull();
  });
});
