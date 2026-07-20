import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import FileUpload from '../FileUpload';

const { heic2anyMock } = vi.hoisted(() => ({
  heic2anyMock: vi.fn(),
}));

vi.mock('heic2any', () => ({
  default: heic2anyMock,
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

// heic2anyMock is replaced at runtime; cast through unknown so we can
// call vitest mock methods on it.
const heic2anyMockTyped = heic2anyMock as unknown as ReturnType<typeof vi.fn>;

describe('FileUpload accessibility', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:test'),
      revokeObjectURL: vi.fn(),
    });
    heic2anyMockTyped.mockReset();
    heic2anyMockTyped.mockResolvedValue(new Blob(['test'], { type: 'image/jpeg' }));
  });

  it('links upload errors to the input', async () => {
    const { container } = render(<FileUpload maxSize={1} />);
    const input = container.querySelector('input') as HTMLInputElement;
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
    const input = container.querySelector('input') as HTMLInputElement;
    const imageFile = new File(['test'], 'test.png', { type: 'image/png' });

    fireEvent.change(input, { target: { files: [imageFile] } });

    expect(await screen.findByRole('button', { name: /remove test\.png/i })).toBeInTheDocument();
  });

  it('does not invoke the HEIC fallback dependency for non-HEIC image uploads', async () => {
    const onFilesSelected = vi.fn();
    const { container } = render(<FileUpload onFilesSelected={onFilesSelected} />);
    const input = container.querySelector('input') as HTMLInputElement;
    const imageFile = new File(['test'], 'scan.png', { type: 'image/png' });

    fireEvent.change(input, { target: { files: [imageFile] } });

    await waitFor(() => {
      expect(onFilesSelected).toHaveBeenCalledTimes(1);
    });

    expect(heic2anyMockTyped).not.toHaveBeenCalled();

    const [processedFiles] = onFilesSelected.mock.calls[0] as [Array<File | Blob>];
    expect(processedFiles).toHaveLength(1);
    expect(processedFiles[0]).toBe(imageFile);
  });

  it('converts HEIC uploads to JPEG through the shared converter boundary', async () => {
    const onFilesSelected = vi.fn();
    const { container } = render(<FileUpload onFilesSelected={onFilesSelected} />);
    const input = container.querySelector('input') as HTMLInputElement;
    const heicFile = new File(['test'], 'skin.heic', { type: 'image/heic' });

    fireEvent.change(input, { target: { files: [heicFile] } });

    await waitFor(() => {
      expect(onFilesSelected).toHaveBeenCalledTimes(1);
    });

    expect(heic2anyMockTyped).toHaveBeenCalledWith({
      blob: heicFile,
      toType: 'image/jpeg',
      quality: 0.9,
    });

    const [processedFiles] = onFilesSelected.mock.calls[0] as [Array<File | Blob>];
    expect(processedFiles[0]).toBeInstanceOf(File);
    expect((processedFiles[0] as File).name).toBe('skin.jpg');
    expect((processedFiles[0] as File).type).toBe('image/jpeg');
  });
});
