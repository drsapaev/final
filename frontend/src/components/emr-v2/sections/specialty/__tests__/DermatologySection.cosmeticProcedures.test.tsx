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

const seededProcedure: DermatologyCosmeticProcedureRecord = {
  procedure_date: '2026-09-25',
  procedure_type: 'SYNTHETIC procedure',
  area_treated: 'SYNTHETIC area',
  products_used: 'SYNTHETIC product',
  results: 'SYNTHETIC result',
};

describe('DermatologySection cosmetic procedures (P2-4b)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('adds a procedure to specialty_data.cosmetic_procedures through onChange', () => {
    const onChange = vi.fn();
    render(<DermatologySection onChange={onChange} cosmeticProcedures={[]} />);

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_new' }));
    fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_date'), {
      target: { value: '2026-09-25' },
    });
    fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_type'), {
      target: { value: 'laser' },
    });
    fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_area'), {
      target: { value: 'Щеки' },
    });
    fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_products'), {
      target: { value: 'Cooling gel' },
    });
    fireEvent.change(screen.getByLabelText('derma.derma_exams_cosmetic_results'), {
      target: { value: 'Минимальное покраснение' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_save' }));

    expect(onChange).toHaveBeenCalledExactlyOnceWith('cosmetic_procedures', [
      {
        procedure_date: '2026-09-25',
        procedure_type: 'laser',
        area_treated: 'Щеки',
        products_used: 'Cooling gel',
        results: 'Минимальное покраснение',
      },
    ]);
  });

  it('requires the date and the procedure type before adding', () => {
    const onChange = vi.fn();
    render(<DermatologySection onChange={onChange} cosmeticProcedures={[]} />);

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_new' }));
    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_save' }));

    expect(onChange).not.toHaveBeenCalled();
  });

  it('removes a procedure through onChange', () => {
    const onChange = vi.fn();
    render(<DermatologySection onChange={onChange} cosmeticProcedures={[seededProcedure]} />);

    fireEvent.click(
      screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_remove' }),
    );

    expect(onChange).toHaveBeenCalledExactlyOnceWith('cosmetic_procedures', []);
  });

  it('hides add and remove controls and shows the list when disabled', () => {
    const onChange = vi.fn();
    render(
      <DermatologySection onChange={onChange} cosmeticProcedures={[seededProcedure]} disabled />,
    );

    expect(
      screen.queryByRole('button', { name: 'derma.derma_exams_cosmetic_new' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'derma.derma_exams_cosmetic_remove' }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC procedure/)).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC area/)).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC product/)).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC result/)).toBeInTheDocument();
  });

  it('renders the procedure fields without a price input', () => {
    const onChange = vi.fn();
    render(<DermatologySection onChange={onChange} cosmeticProcedures={[seededProcedure]} />);

    fireEvent.click(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_new' }));
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_date')).toHaveValue('');
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
    expect(screen.queryByText('derma.derma_exams_cosmetic_cost')).not.toBeInTheDocument();
  });

  it('shows the empty state when there are no procedures', () => {
    render(<DermatologySection onChange={vi.fn()} cosmeticProcedures={[]} />);

    expect(screen.getByText('derma.derma_exams_cosmetic_empty')).toBeInTheDocument();
  });
});
