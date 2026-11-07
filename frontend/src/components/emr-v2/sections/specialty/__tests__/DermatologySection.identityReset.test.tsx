/**
 * Audit 3892 round 1 — fail-first regression for DERMAPROC-FE-001:
 * an unfinished dermatology procedure draft must not survive a same-mounted
 * visit/patient change; pressing Save after the switch must append to the
 * NEW patient's cosmetic_procedures only what was entered for the new
 * patient, and patient B's list must stay untouched during the switch.
 */
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DermatologySection,
  type DermatologyCosmeticProcedureRecord,
} from '../DermatologySection';

vi.mock('@/i18n', () => ({
  default: { t: (key: string) => key },
}));

vi.mock('../../EMRSection', () => ({
  default: ({ children }: { children: React.ReactNode }) =>
    React.createElement('section', null, children),
}));

vi.mock('../../EMRSmartFieldV2', () => ({
  default: (props: React.InputHTMLAttributes<HTMLInputElement> & { id?: string }) =>
    React.createElement('input', { ...props, 'data-testid': props.id }),
}));

vi.mock('../../../../ui/macos', () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) =>
    React.createElement('button', props, children),
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) =>
    React.createElement('input', props),
  Textarea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) =>
    React.createElement('textarea', props),
}));

const typeIntoDraft = (type: string, date: string) => {
  fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_type'), {
    target: { value: type },
  });
  fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_date'), {
    target: { value: date },
  });
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('DermatologySection procedure draft identity reset (DERMAPROC-FE-001, audit 3892 round 1)', () => {
  it('drops the open patient A draft when the visit switches to patient B', () => {
    const onChange = vi.fn();
    const bProcedures: DermatologyCosmeticProcedureRecord[] = [];
    const view = render(
      <DermatologySection visitId={41} patientId={7} onChange={onChange} cosmeticProcedures={[]} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_new' }));
    typeIntoDraft('SYNTHETIC laser for A', '2026-11-06');

    // Same-mounted visit change: B is selected while the form stays open.
    view.rerender(
      <DermatologySection visitId={42} patientId={8} onChange={onChange} cosmeticProcedures={bProcedures} />,
    );

    // The A draft form is closed and nothing was written to B's list.
    expect(screen.queryByLabelText('derma.derma_exams_cosmetic_type')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();

    // Reopening the form for B starts from an empty draft.
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_new' }));
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_type')).toHaveProperty('value', '');
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_date')).toHaveProperty('value', '');

    typeIntoDraft('SYNTHETIC peel for B', '2026-11-07');
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_save' }));

    expect(onChange).toHaveBeenCalledExactlyOnceWith('cosmetic_procedures', [
      expect.objectContaining({ procedure_type: 'SYNTHETIC peel for B', procedure_date: '2026-11-07' }),
    ]);
  });
});
