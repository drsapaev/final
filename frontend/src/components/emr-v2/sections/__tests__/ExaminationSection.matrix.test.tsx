import React, { useState } from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * EMREXAM-FE-001 (audit 3886, round 19) — fail-first.
 *
 * The examination matrix emits the FULL snapshot of active items on every
 * toggle (and an EMPTY string when the last mark is removed). The old
 * handler in ExaminationSection blindly appended every emission and ignored
 * empty ones, so:
 *   - «norm» then «pathology» on the same item produced a saved narrative
 *     containing BOTH contradictory phrases;
 *   - toggling a mark off could not retract its phrase;
 *   - the same phrase accumulated duplicates on every re-mark.
 * The tests below fail on the pre-fix source.
 */

vi.mock('@/hooks/useDoctorPhrases', () => ({
  useDoctorPhrases: () => ({ suggestions: [], loading: false }),
}));

vi.mock('@/hooks/useDoctorSectionTemplates', () => ({
  useDoctorSectionTemplates: () => ({ templates: [], loading: false, hasTemplates: false }),
}));

vi.mock('../../DoctorTemplatesPanel', () => ({
  DoctorTemplatesButton: () => null,
  DoctorTemplatesPanel: () => null,
}));

import ExaminationSectionRaw from '../ExaminationSection';

const ExaminationSection = ExaminationSectionRaw as unknown as React.ComponentType<Record<string, unknown>>;

function Section(props: { value: string; onChange: (v: string) => void }) {
  return (
    <ThemeProvider>
      <ExaminationSection
        value={props.value}
        onChange={props.onChange}
        specialty="general"
      />
      <span data-testid="exam-value">{props.value}</span>
    </ThemeProvider>
  );
}

/** Self-contained controlled harness for interactive sequences. */
function Harness({ initial = '' }: { initial?: string }) {
  const [value, setValue] = useState(initial);
  return <Section value={value} onChange={setValue} />;
}

// The matrix aria-labels come from the ru locale:
//   em_mark_norm  -> 'Отметить "{item}" как норму'
//   em_mark_path  -> 'Отметить "{item}" как патологию'
function normButton(item: string) {
  return screen.getByRole('button', { name: `Отметить "${item}" как норму` });
}
function pathButton(item: string) {
  return screen.getByRole('button', { name: `Отметить "${item}" как патологию` });
}

const t = (key: string) => i18n.t(key) as string;

const COND = 'Состояние';
const CONSC = 'Сознание';
const condNorm = () => t('misc.em_tpl_condition_norm');
const condPath = () => t('misc.em_tpl_condition_path');
const conscNorm = () => t('misc.em_tpl_consciousness_norm');

beforeEach(async () => {
  vi.clearAllMocks();
  await act(async () => { await i18n.changeLanguage('ru'); });
});

describe('EMREXAM-FE-001: matrix-generated block is replaced, not appended', () => {
  it('norm -> pathology -> off: exactly one canonical phrase, no residual contradiction', async () => {
    render(<Harness />);
    // 1. Mark «Состояние» as norm.
    await act(async () => { fireEvent.click(normButton(COND)); });
    let value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe(`${condNorm()}.`);

    // 2. Same item switched to pathology: the norm phrase must be REPLACED.
    await act(async () => { fireEvent.click(pathButton(COND)); });
    value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe(`${condPath()}.`);
    expect(value).not.toContain(condNorm());

    // 3. Toggle off (empty snapshot): the generated block is removed.
    await act(async () => { fireEvent.click(pathButton(COND)); });
    value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe('');
  });

  it('manual prose is preserved and never erased by matrix changes', async () => {
    render(<Harness initial="Бледный, в сознании." />);
    await act(async () => { fireEvent.click(normButton(COND)); });
    let value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe(`Бледный, в сознании. ${condNorm()}.`);

    await act(async () => { fireEvent.click(pathButton(COND)); });
    value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe(`Бледный, в сознании. ${condPath()}.`);

    // Toggle off: the block disappears, the manual prose survives.
    await act(async () => { fireEvent.click(pathButton(COND)); });
    value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe('Бледный, в сознании.');
  });

  it('multiple markers: each active phrase appears exactly once; removing one keeps the other', async () => {
    render(<Harness />);
    await act(async () => { fireEvent.click(normButton(COND)); });
    await act(async () => { fireEvent.click(normButton(CONSC)); });
    let value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe(`${condNorm()}. ${conscNorm()}.`);
    // Pre-fix: the second click APPENDED the whole new snapshot after the
    // first one — the condition phrase appeared twice.
    expect(value.split(condNorm()).length - 1).toBe(1);

    // Retract only «Состояние»: the «Сознание» phrase must remain.
    await act(async () => { fireEvent.click(normButton(COND)); });
    value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe(`${conscNorm()}.`);
    expect(value).not.toContain(condNorm());
  });

  it('a block manually deleted by the doctor is re-applied fresh, without the old phrase', async () => {
    // Externally controlled value: the test simulates the doctor manually
    // wiping the field between matrix interactions (no unmount).
    const state = { value: '' };
    const onValue = (v: string) => { state.value = v; };
    const view = render(<Section value={state.value} onChange={onValue} />);

    await act(async () => { fireEvent.click(normButton(COND)); });
    view.rerender(<Section value={state.value} onChange={onValue} />);
    expect(screen.getByTestId('exam-value').textContent).toBe(`${condNorm()}.`);

    // The doctor clears the field by hand (value changes outside the section).
    state.value = '';
    view.rerender(<Section value={state.value} onChange={onValue} />);

    // A new mark appends a fresh block; the old phrase must not resurrect.
    await act(async () => { fireEvent.click(pathButton(COND)); });
    view.rerender(<Section value={state.value} onChange={onValue} />);
    const value = screen.getByTestId('exam-value').textContent ?? '';
    expect(value).toBe(`${condPath()}.`);
    expect(value).not.toContain(condNorm());
  });
});
