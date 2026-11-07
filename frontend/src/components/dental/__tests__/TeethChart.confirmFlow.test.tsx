/**
 * Audit 3892 round 3 — fail-first regression for DENTVISIT-FE-003:
 * clicking a tooth must not mutate the displayed chart status before the
 * editing modal is confirmed. The chart only changes after the parent's
 * canonical tooth_status updates (a confirmed modal Save); the click merely
 * selects the tooth, emits its CURRENT data plus the palette-suggested
 * status, and opens the modal.
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

describe('TeethChart click-to-confirm flow (DENTVISIT-FE-003, audit 3892 round 3)', () => {
  it('emits the current tooth data and the palette status without mutating the chart', () => {
    const onToothClick = vi.fn();
    render(<TeethChart initialData={{}} onToothClick={onToothClick} readOnly={false} />);

    // Tooth 11 is healthy (absent from the map). Clicking it opens the modal
    // path but must NOT paint the default caries status onto the chart.
    fireEvent.click(toothButton(11));

    expect(onToothClick).toHaveBeenCalledTimes(1);
    expect(onToothClick).toHaveBeenCalledWith(11, {}, TOOTH_STATUS.CARIES);
    // The displayed tooth keeps its healthy status — no pre-confirmation mutation.
    expect(toothButton(11).getAttribute('aria-label')).toContain('Здоров');
    expect(toothButton(11).getAttribute('aria-label')).not.toContain('Кариес');
  });

  it('keeps the chart unchanged when the tooth already carries a persisted status', () => {
    const onToothClick = vi.fn();
    render(
      <TeethChart
        initialData={{ 16: { status: TOOTH_STATUS.CROWN } }}
        onToothClick={onToothClick}
        readOnly={false}
      />,
    );

    fireEvent.click(toothButton(16));

    // The emitted data is the tooth's CURRENT record — the palette selection
    // is passed separately and never injected into the tooth record.
    expect(onToothClick).toHaveBeenCalledWith(16, { status: TOOTH_STATUS.CROWN }, TOOTH_STATUS.CARIES);
    expect(toothButton(16).getAttribute('aria-label')).toContain('Коронка');
  });

  it('reflects a parent-confirmed status once the canonical data changes', () => {
    const onToothClick = vi.fn();
    const { rerender } = render(
      <TeethChart initialData={{}} onToothClick={onToothClick} readOnly={false} />,
    );

    // A confirmed modal save lands in the parent state → the chart follows.
    rerender(
      <TeethChart
        initialData={{ 16: { status: TOOTH_STATUS.FILLED } }}
        onToothClick={onToothClick}
        readOnly={false}
      />,
    );
    expect(toothButton(16).getAttribute('aria-label')).toContain('Пломба');
  });

  it('passes the palette-selected status as the suggested status for the modal', () => {
    const onToothClick = vi.fn();
    render(<TeethChart initialData={{}} onToothClick={onToothClick} readOnly={false} />);

    // The status palette stays meaningful: it selects the status that the
    // about-to-open modal will suggest, instead of painting the chart.
    fireEvent.click(screen.getAllByText('Пломба')[0]);
    fireEvent.click(toothButton(21));

    expect(onToothClick).toHaveBeenCalledWith(21, {}, TOOTH_STATUS.FILLED);
  });
});
