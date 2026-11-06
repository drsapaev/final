import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DermatologySection,
} from '../DermatologySection';

/**
 * DERMAPROC-FE-001 (audit 2026-11-06, PR 3892): an unfinished dermatology
 * procedure draft must not survive a patient/visit identity switch — it is
 * reset fail-closed so it cannot be added into patient B's chart.
 */
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

beforeEach(() => {
  vi.clearAllMocks();
});

const openProcedureForm = () => {
  fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_new' }));
};

const fillDraft = () => {
  fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_date'), {
    target: { value: '2026-11-06' },
  });
  fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_type'), {
    target: { value: 'SYNTHETIC laser' },
  });
};

describe('DermatologySection — procedure draft context isolation (DERMAPROC-FE-001)', () => {
  it('resets an open procedure draft when the visit identity switches', async () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <DermatologySection onChange={onChange} cosmeticProcedures={[]} visitId={41} patientId={7} />,
    );

    openProcedureForm();
    fillDraft();
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_type')).toHaveProperty('value', 'SYNTHETIC laser');

    rerender(
      <DermatologySection onChange={onChange} cosmeticProcedures={[]} visitId={42} patientId={8} />,
    );

    // The draft form must be closed after the switch...
    await waitFor(() => {
      expect(screen.queryByLabelText('derma.derma_exams_cosmetic_type')).toBeNull();
    });
    // ...and reopening it must show a clean draft, not patient A's entries.
    openProcedureForm();
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_date')).toHaveProperty('value', '');
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_type')).toHaveProperty('value', '');

    // A clean draft cannot be committed accidentally: the add handler requires
    // date + type, so nothing reaches onChange for patient B.
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_save' }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('keeps the draft while the identity is unchanged across rerenders', () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <DermatologySection onChange={onChange} cosmeticProcedures={[]} visitId={41} patientId={7} />,
    );

    openProcedureForm();
    fillDraft();

    rerender(
      <DermatologySection onChange={onChange} cosmeticProcedures={[]} visitId={41} patientId={7} />,
    );

    expect(screen.getByLabelText('derma.derma_exams_cosmetic_type')).toHaveProperty('value', 'SYNTHETIC laser');
  });
});
