/**
 * RETRO-3966-01 (post-merge code review #3968 of round-26 PR #3966) —
 * fail-first regression for the read-only tooth chart enablement rule.
 *
 * In readOnly the chart enabled a tooth button whenever EITHER callback was
 * provided. The DentistrySection consumer passes only `onToothClick`, so its
 * read-only chart rendered live-looking buttons whose activation did nothing
 * (the handler routes to onInspect, which was undefined). Read-only buttons
 * are enabled only when a genuine inspection callback exists.
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TeethChart from '../TeethChart';

vi.mock('../../../i18n/useTranslation', () => {
  return {
    useTranslation: () => ({ t: (key: string) => key }),
    TranslationProvider: ({ children }: { children: unknown }) => children,
  };
});
vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({}),
}));

const toothData = { 16: { status: 'caries' } };

const toothButtons = () =>
  screen.getAllByRole('button', { name: 'dental.dental_tc_tooth_aria' }) as HTMLButtonElement[];

beforeEach(() => {
  vi.clearAllMocks();
});

describe('TeethChart read-only enablement (RETRO-3966-01)', () => {
  it('readOnly with only onToothClick renders disabled tooth buttons (no dead inspection affordance)', () => {
    render(
      <TeethChart initialData={toothData} onToothClick={vi.fn()} readOnly />,
    );

    for (const button of toothButtons()) {
      expect(button).toBeDisabled();
    }
  });

  it('readOnly with onInspect keeps the inspection affordance enabled and never mutates', () => {
    const onInspect = vi.fn();
    const onToothClick = vi.fn();
    render(
      <TeethChart initialData={toothData} onToothClick={onToothClick} onInspect={onInspect} readOnly />,
    );

    const target = toothButtons().find((b) => !b.disabled);
    expect(target).toBeDefined();
    fireEvent.click(target!);
    // The inspection callback receives the clicked tooth's number and its
    // current data (tooth identity within the chart layout is the chart's
    // concern; the contract under test is inspect-only, never mutate).
    expect(onInspect).toHaveBeenCalledTimes(1);
    expect(onInspect.mock.calls[0][0]).toEqual(expect.any(Number));
    expect(onInspect.mock.calls[0][1]).toEqual(expect.any(Object));
    expect(onToothClick).not.toHaveBeenCalled();
  });

  it('control: an editable chart still fires onToothClick', () => {
    const onToothClick = vi.fn();
    render(
      <TeethChart initialData={toothData} onToothClick={onToothClick} />,
    );

    fireEvent.click(toothButtons()[0]);
    expect(onToothClick).toHaveBeenCalledTimes(1);
  });
});
