import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

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

import VitalsWidget from '../VitalsWidget';

function renderVitals(vitals: Record<string, string>, collapseAdditional = false) {
  const onChange = vi.fn();
  const utils = render(
    <ThemeProvider>
      <VitalsWidget vitals={vitals} onChange={onChange} collapseAdditional={collapseAdditional} />
    </ThemeProvider>
  );
  return { ...utils, onChange };
}

const fieldByName = (name: string) => screen.getByRole('spinbutton', { name });

describe('EMRVITAL-FE-001: BMI integrity', () => {
  it('never renders an Infinity BMI for height "0" and flags the field invalid', () => {
    renderVitals({ height: '0', weight: '70' });
    expect(screen.queryByText(/ИМТ/)).toBeNull();
    expect(document.body.textContent || '').not.toMatch(/Infinity|NaN/);
    const height = fieldByName('Рост');
    expect(height).toHaveAttribute('aria-invalid', 'true');
    expect(document.querySelectorAll('.emr-vitals__field--invalid').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Значение вне клинического диапазона/).length).toBeGreaterThan(0);
  });

  it('never renders a BMI for negative anthropometry and flags both fields', () => {
    renderVitals({ height: '-170', weight: '-60' });
    expect(screen.queryByText(/ИМТ/)).toBeNull();
    expect(document.body.textContent || '').not.toMatch(/Infinity|NaN/);
    expect(fieldByName('Рост')).toHaveAttribute('aria-invalid', 'true');
    expect(fieldByName('Вес')).toHaveAttribute('aria-invalid', 'true');
  });

  it('zero weight (below the clinical minimum) yields no BMI and an invalid flag', () => {
    renderVitals({ height: '170', weight: '0' });
    expect(screen.queryByText(/ИМТ/)).toBeNull();
    expect(fieldByName('Вес')).toHaveAttribute('aria-invalid', 'true');
  });

  it('positive control: valid adult anthropometry still renders the correct BMI', () => {
    renderVitals({ height: '170', weight: '70' });
    expect(screen.getByText('ИМТ 24.2')).toBeInTheDocument();
    expect(document.querySelectorAll('.emr-vitals__field--invalid').length).toBe(0);
  });

  it('BMI is marked, never rewritten: the raw entry still flows to onChange untouched', () => {
    const { onChange } = renderVitals({ height: '0', weight: '70' });
    const height = fieldByName('Рост');
    // '1' is a DIFFERENT but still invalid value (below the 20 cm clinical
    // minimum) so React's value tracker actually dispatches the change.
    fireEvent.change(height, { target: { value: '1' } });
    expect(onChange).toHaveBeenCalled();
    const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as Record<string, string>;
    expect(last.height).toBe('1'); // not clamped, not blanked — flagged instead
    expect(fieldByName('Рост')).toHaveAttribute('aria-invalid', 'true');
  });
});

describe('EMRVITAL-FE-001: clinical range validation with explicit feedback', () => {
  it('SpO₂ 150 is out of range and flagged', () => {
    renderVitals({ spo2: '150' });
    expect(fieldByName('SpO₂')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getAllByText(/клинического диапазона/).length).toBeGreaterThan(0);
  });

  it('pulse -1 is out of range and flagged', () => {
    renderVitals({ pulse: '-1' });
    expect(fieldByName('Пульс')).toHaveAttribute('aria-invalid', 'true');
  });

  it('implausible BP values are flagged while real hypertension warnings are preserved', () => {
    // 190/110 is physiologically possible → keeps the pre-existing critical
    // warning, and is NOT flagged invalid (macos Input always renders
    // aria-invalid="false" for valid fields — only "true" means invalid).
    renderVitals({ systolic: '190', diastolic: '110' });
    expect(fieldByName('АД сист.')).not.toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('⚠️ Криз')).toBeInTheDocument();
  });

  it('out-of-range systolic (350) is flagged invalid', () => {
    renderVitals({ systolic: '350' });
    expect(fieldByName('АД сист.')).toHaveAttribute('aria-invalid', 'true');
  });

  it('empty fields are simply not filled — no invalid noise', () => {
    renderVitals({});
    expect(document.querySelectorAll('.emr-vitals__field--invalid').length).toBe(0);
    expect(screen.queryByText(/клинического диапазона/)).toBeNull();
    expect(screen.queryByText(/ИМТ/)).toBeNull();
  });
});

describe('Localized native vital labels', () => {
  afterEach(async () => {
    await act(async () => { await i18n.changeLanguage('ru'); });
  });

  it.each([
    ['ru', 'АД сист.', 'АД диаст.', 'Пульс'],
    ['uz-Latn', 'Sistolik QB', 'Diastolik QB', 'Puls'],
    ['uz-Cyrl', 'Систолик ҚБ', 'Диастолик ҚБ', 'Пульс'],
    ['en', 'Systolic BP', 'Diastolic BP', 'Pulse'],
    ['kk', 'Систолалық ҚҚ', 'Диастолалық ҚҚ', 'Пульс'],
  ])('names core fields from their visible labels in %s', async (locale, systolic, diastolic, pulse) => {
    await i18n.changeLanguage(locale);
    renderVitals({}, true);

    expect(fieldByName(systolic)).toBe(screen.getByLabelText(systolic));
    expect(fieldByName(diastolic)).toBe(screen.getByLabelText(diastolic));
    expect(fieldByName(pulse)).toBe(screen.getByLabelText(pulse));
    expect(fieldByName(pulse)).not.toHaveAttribute('aria-label');
    expect(fieldByName('SpO₂')).toHaveAccessibleDescription('%');
  });

  it.each([
    ['ru', '↑ АД', '⚠️ Криз'],
    ['uz-Latn', '↑ QB', '⚠️ Kriz'],
    ['uz-Cyrl', '↑ ҚБ', '⚠️ Криз'],
    ['en', '↑ BP', '⚠️ Crisis'],
    ['kk', '↑ ҚҚ', '⚠️ Криз'],
  ])('shows localized blood-pressure warning captions in %s', async (locale, warning, critical) => {
    await i18n.changeLanguage(locale);
    const { rerender } = renderVitals({ systolic: '150' });
    expect(screen.getByText(warning)).toBeVisible();

    rerender(<ThemeProvider><VitalsWidget vitals={{ systolic: '190' }} /></ThemeProvider>);
    expect(screen.getByText(critical)).toBeVisible();
    expect(screen.queryByText(warning)).toBeNull();
  });

  it('reveals labeled additional fields with spoken units', () => {
    renderVitals({}, true);
    fireEvent.click(screen.getByText('Дополнительные показатели'));

    expect(fieldByName('Рост')).toHaveAccessibleDescription('см');
    expect(fieldByName('Вес')).toHaveAccessibleDescription('кг');
  });

  it('binds each label to a unique control when widgets coexist', () => {
    render(<ThemeProvider><VitalsWidget /><VitalsWidget /></ThemeProvider>);

    const controls = screen.getAllByRole('spinbutton');
    const ids = controls.map(control => control.id);
    expect(ids).toHaveLength(12);
    expect(ids).not.toContain('');
    expect(new Set(ids).size).toBe(ids.length);
    expect(screen.getAllByLabelText('Пульс')).toEqual(screen.getAllByRole('spinbutton', { name: 'Пульс' }));
  });
});
