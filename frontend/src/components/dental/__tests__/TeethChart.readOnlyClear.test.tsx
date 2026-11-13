
/**
 * DENTCHART-FE-002 / DENTCHART-FE-003 (audit 3886 round 26) — TeethChart
 * read-only and Clear All contracts.
 *
 * Red-first: on pre-fix source
 *  - DENTCHART-FE-002: the readOnly branch of handleToothClick still invoked
 *    the parent onToothClick mutation callback, so a keyboard-activated tooth
 *    in a locked chart could dispatch a specialty_data.tooth_status change
 *    (dirty EMR reducer + possibly stale local data) even though the chart
 *    was rendered read-only;
 *  - DENTCHART-FE-003: handleClearAll only reset the local teethData copy and
 *    never notified the owner, so the canonical
 *    specialty_data.tooth_status kept every "cleared" caries/implant label
 *    and a refresh silently restored them.
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import TeethChart from '../TeethChart';
import { TOOTH_STATUS } from '../dentalConstants';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      (params ? `${key}:${JSON.stringify(params)}` : key),
  }),
}));
vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({}),
}));

const toothButton = (toothNumber: number) =>
  screen.getByRole('button', { name: new RegExp(`"toothNumber":${toothNumber}`) });

describe('TeethChart read-only and Clear All contracts (audit 3886 round 26)', () => {
  it('never calls the mutation callback from a read-only chart; inspection goes through onInspect (DENTCHART-FE-002)', () => {
    const onToothClick = vi.fn();
    const onInspect = vi.fn();
    render(
      <TeethChart
        initialData={{ 16: { status: TOOTH_STATUS.CARIES } }}
        onToothClick={onToothClick}
        onInspect={onInspect}
        readOnly
      />,
    );

    // The tooth button stays focusable for accessible inspection (its
    // aria-label/title carry the persisted status)...
    expect(toothButton(16)).toHaveProperty('disabled', false);

    // ...but activating it (pointer or the keyboard-synthesized click of
    // Enter/Space on a focused button) can never reach the parent EMR
    // mutation callback.
    toothButton(16).focus();
    fireEvent.click(toothButton(16));

    expect(onToothClick).not.toHaveBeenCalled();
    expect(onInspect).toHaveBeenCalledTimes(1);
    expect(onInspect).toHaveBeenCalledWith(16, { status: TOOTH_STATUS.CARIES });
  });

  it('keeps a callback-less read-only chart disabled and inert (DENTCHART-FE-002)', () => {
    render(<TeethChart initialData={{ 16: { status: TOOTH_STATUS.CARIES } }} readOnly />);

    expect(toothButton(16)).toHaveProperty('disabled', true);
    fireEvent.click(toothButton(16)); // must not throw and must not mutate anything
    expect(toothButton(16).getAttribute('aria-label')).toContain('Кариес');
  });

  it('Clear All notifies the owner and clears the visible chart (DENTCHART-FE-003)', () => {
    const onClearAll = vi.fn();
    render(
      <TeethChart
        initialData={{
          16: { status: TOOTH_STATUS.CARIES },
          46: { status: TOOTH_STATUS.CROWN },
        }}
        onClearAll={onClearAll}
      />,
    );

    expect(screen.getByText('Кариес: 1')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tc_btn_clear' }));

    expect(onClearAll).toHaveBeenCalledTimes(1);
    // The visible chart is empty again...
    expect(toothButton(16).getAttribute('aria-label')).toContain('Здоров');
    expect(toothButton(46).getAttribute('aria-label')).toContain('Здоров');
    expect(screen.queryByText('Кариес: 1')).toBeNull();
  });

  it('Clear All still clears the local chart when no owner callback is provided (uncontrolled consumers)', () => {
    render(<TeethChart initialData={{ 16: { status: TOOTH_STATUS.CARIES } }} />);

    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tc_btn_clear' }));

    expect(toothButton(16).getAttribute('aria-label')).toContain('Здоров');
    expect(screen.queryByText('Кариес: 1')).toBeNull();
  });
});
