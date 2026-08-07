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

// ValidationRules contract (Form.tsx:42):
//   type ValidationRules = Record<string, ValidationRule | string>;
//   — a map of FIELD NAME → rule spec.
// The handleBlur implementation (Form.tsx:351) looks up the rule by field name:
//   const rules = validationRules[name];
// So validationRules must be keyed by the field's `name` prop, not by rule kind.
// The earlier test shape `validationRules={{ required: 'msg' }}` only worked when
// the field name happened to be literally 'required' — it never validated fields
// named 'fullName', 'notes', 'role', etc. The corrected shape below matches the
// implemented API contract.

function renderWithProvider(ui: React.ReactNode) {
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
        validationRules={{ fullName: { required: 'Required field' } }}
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
        validationRules={{ notes: { required: 'Notes required' } }}
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
        validationRules={{ role: { required: 'Role required' } }}
      />,
    );

    const select = screen.getByLabelText(/role/i);
    fireEvent.blur(select);

    expect(select).toHaveAttribute('id', 'field-role');
    expect(await screen.findByRole('alert')).toHaveAttribute('id', 'error-role');
    expect(select).toHaveAttribute('aria-describedby', 'error-role');
  });
});
