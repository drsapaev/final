import React from 'react';
import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PrescriptionEditor from '../PrescriptionEditor';

describe('PrescriptionEditor accessibility', () => {
  it('renders an aria-label on the delete button', () => {
    render(
      <PrescriptionEditor
        prescriptions={[
          {
            id: 1,
            name: 'Test Drug',
            dose: '10mg',
            frequency: '1x',
            duration: '5 days',
          },
        ]}
        isEditable={true}
      />,
    );

    const deleteButton = screen.getByRole('button', { name: /Удалить назначение/i });
    expect(deleteButton).toBeInTheDocument();
    expect(deleteButton).toHaveAttribute('aria-label', 'Удалить назначение');
    expect(deleteButton).toHaveAttribute('title', 'Удалить');
  });
});
