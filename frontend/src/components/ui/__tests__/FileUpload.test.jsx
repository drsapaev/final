import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import FileUpload from '../FileUpload';

vi.mock('heic2any', () => ({
  default: vi.fn().mockResolvedValue(new Blob(['test'], { type: 'image/jpeg' })),
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('FileUpload accessibility', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:test'),
      revokeObjectURL: vi.fn(),
    });
  });

  it('links upload errors to the input', async () => {
    const { container } = render(<FileUpload maxSize={1} />);
    const input = container.querySelector('input');
    const oversizedFile = new File(['test'], 'oversized.png', { type: 'image/png' });

    fireEvent.change(input, { target: { files: [oversizedFile] } });

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveAttribute('id', 'file-upload-error');
    expect(alert).toHaveTextContent(/file size too large/i);

    await waitFor(() => {
      expect(input).toHaveAttribute('aria-describedby', 'file-upload-error');
    });
  });

  it('adds a descriptive label to the preview remove button', async () => {
    const { container } = render(<FileUpload />);
    const input = container.querySelector('input');
    const imageFile = new File(['test'], 'test.png', { type: 'image/png' });

    fireEvent.change(input, { target: { files: [imageFile] } });

    expect(await screen.findByRole('button', { name: /remove test\.png/i })).toBeInTheDocument();
  });
});
