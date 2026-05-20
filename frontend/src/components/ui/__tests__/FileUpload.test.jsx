import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import heic2any from 'heic2any';

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
    heic2any.mockClear();
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

  it('converts HEIC uploads to JPEG through the shared converter boundary', async () => {
    const onFilesSelected = vi.fn();
    const { container } = render(<FileUpload onFilesSelected={onFilesSelected} />);
    const input = container.querySelector('input');
    const heicFile = new File(['test'], 'skin.heic', { type: 'image/heic' });

    fireEvent.change(input, { target: { files: [heicFile] } });

    await waitFor(() => {
      expect(onFilesSelected).toHaveBeenCalledTimes(1);
    });

    expect(heic2any).toHaveBeenCalledWith({
      blob: heicFile,
      toType: 'image/jpeg',
      quality: 0.9,
    });

    const [processedFiles] = onFilesSelected.mock.calls[0];
    expect(processedFiles[0]).toBeInstanceOf(File);
    expect(processedFiles[0].name).toBe('skin.jpg');
    expect(processedFiles[0].type).toBe('image/jpeg');
  });
});
