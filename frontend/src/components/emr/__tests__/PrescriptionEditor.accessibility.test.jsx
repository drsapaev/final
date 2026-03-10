import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PrescriptionEditor from '../PrescriptionEditor';
import '@testing-library/jest-dom';

describe('PrescriptionEditor Accessibility', () => {
  it('should have an aria-label on the delete button', () => {
    const mockPrescriptions = [
      { id: 1, name: 'Test Drug', dose: '10mg', frequency: '1x', duration: '5 days' }
    ];
    render(
      <PrescriptionEditor
        prescriptions={mockPrescriptions}
        isEditable={true}
      />
    );

    const deleteButton = screen.getByRole('button', { name: /Удалить назначение/i });
    expect(deleteButton).toBeInTheDocument();
    expect(deleteButton).toHaveAttribute('aria-label', 'Удалить назначение');
    expect(deleteButton).toHaveAttribute('title', 'Удалить');
  });
});
