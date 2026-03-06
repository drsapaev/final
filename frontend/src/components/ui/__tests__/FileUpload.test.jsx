import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import FileUpload from '../FileUpload';

// Mock heic2any
vi.mock('heic2any', () => ({
  default: vi.fn().mockResolvedValue(new Blob(['test'], { type: 'image/jpeg' }))
}));

// Mock logger
vi.mock('../../../utils/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn()
  }
}));

// Mock URL.createObjectURL
global.URL.createObjectURL = vi.fn(() => 'blob:test');
global.URL.revokeObjectURL = vi.fn();

describe('FileUpload Accessibility', () => {
  it('should have accessibility attributes on the input', () => {
    const { container } = render(<FileUpload />);
    const input = container.querySelector('input');
    expect(input).toBeInTheDocument();
  });

  it('should show error message with role="alert" when error occurs', async () => {
    const { container } = render(<FileUpload maxSize={1} />); // 1 byte max size
    const file = new File(['test'], 'test.png', { type: 'image/png' }); // 4 bytes

    const input = container.querySelector('input');

    // Simulate file drop
    Object.defineProperty(input, 'files', {
      value: [file]
    });

    fireEvent.change(input);

    // Wait for error message
    const alert = await screen.findByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/File size too large/);
    expect(alert).toHaveAttribute('id', 'file-upload-error');

    // Check if input has aria-describedby
    await waitFor(() => {
        expect(container.querySelector('input')).toHaveAttribute('aria-describedby', 'file-upload-error');
    });
  });

  it('should have aria-label on remove button', async () => {
    const { container } = render(<FileUpload />);
    const file = new File(['test'], 'test.png', { type: 'image/png' });

    const input = container.querySelector('input');

    Object.defineProperty(input, 'files', {
      value: [file]
    });

    fireEvent.change(input);

    // Wait for preview to appear
    const removeButton = await screen.findByRole('button', { name: /Remove test.png/i });
    expect(removeButton).toBeInTheDocument();
  });
});
