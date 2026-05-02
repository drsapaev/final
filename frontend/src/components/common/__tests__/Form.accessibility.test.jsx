import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({
    getColor: () => '#111111',
    getSpacing: () => '8px',
    getFontSize: () => '14px',
  }),
}));

import { FormField, FormProvider, FormSelect, FormTextArea } from '../Form';

function renderWithProvider(ui) {
  return render(<FormProvider>{ui}</FormProvider>);
}

describe('Form accessibility', () => {
  it('wires labels and validation state for text inputs', async () => {
    renderWithProvider(
      <FormField
        formId="field-form"
        name="fullName"
        label="Full name"
        required
        validationRules={{ required: 'Required field' }}
      />,
    );

    const input = screen.getByLabelText(/full name/i);
    fireEvent.blur(input);

    expect(input).toHaveAttribute('id', 'field-fullName');
    expect(input).toHaveAttribute('aria-required', 'true');
    expect(await screen.findByRole('alert')).toHaveAttribute('id', 'error-fullName');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'error-fullName');
  });

  it('wires labels and validation state for textareas', async () => {
    renderWithProvider(
      <FormTextArea
        formId="textarea-form"
        name="notes"
        label="Notes"
        required
        validationRules={{ required: 'Notes required' }}
      />,
    );

    const textarea = screen.getByLabelText(/notes/i);
    fireEvent.blur(textarea);

    expect(textarea).toHaveAttribute('id', 'field-notes');
    expect(await screen.findByRole('alert')).toHaveAttribute('id', 'error-notes');
    expect(textarea).toHaveAttribute('aria-describedby', 'error-notes');
  });

  it('wires labels and validation state for selects', async () => {
    renderWithProvider(
      <FormSelect
        formId="select-form"
        name="role"
        label="Role"
        required
        options={[{ value: 'admin', label: 'Admin' }]}
        validationRules={{ required: 'Role required' }}
      />,
    );

    const select = screen.getByLabelText(/role/i);
    fireEvent.blur(select);

    expect(select).toHaveAttribute('id', 'field-role');
    expect(await screen.findByRole('alert')).toHaveAttribute('id', 'error-role');
    expect(select).toHaveAttribute('aria-describedby', 'error-role');
  });
});
