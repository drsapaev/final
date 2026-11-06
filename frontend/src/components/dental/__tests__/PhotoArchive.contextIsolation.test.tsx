import { fireEvent, screen, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/renderWithProviders';
import PhotoArchive from '../PhotoArchive';
import type { DentalMediaItem } from '../../../api/dentalMedia';

/**
 * DENTPHOTO-FE-001 / DENTPHOTO-FE-002 (audit 2026-11-06, PR 3892): the
 * upload form state (selected file + draft fields) and the media preview
 * must not survive a patient/visit identity switch, and a delayed preview
 * response for the previous patient must not reopen under the new one.
 */
const mediaApi = vi.hoisted(() => ({
  listDentalMedia: vi.fn(),
  uploadDentalMedia: vi.fn(),
  updateDentalMedia: vi.fn(),
  deleteDentalMedia: vi.fn(),
  loadDentalMediaContent: vi.fn(),
}));

vi.mock('../../../api/dentalMedia', () => mediaApi);

const savedImage = (patientId: number, visitId: number): DentalMediaItem => ({
  id: 41,
  title: 'SYNTHETIC-Xray',
  description: null,
  category: 'xray',
  tooth: '16',
  capture_date: '2026-09-20',
  mime_type: 'image/png',
  file_size: 120,
  patient_id: patientId,
  visit_id: visitId,
  created_at: '2026-09-20T08:00:00Z',
  updated_at: '2026-09-20T08:00:00Z',
});

const syntheticFile = () =>
  new File(['synthetic image bytes'], 'xray.png', { type: 'image/png' });

const viewButton = () => screen.getByRole('button', { name: /Просмотр|View/ });
const uploadButton = () => screen.getByRole('button', { name: /Загрузить файлы|Upload files/ });

beforeEach(() => {
  vi.clearAllMocks();
  mediaApi.listDentalMedia.mockResolvedValue({ items: [savedImage(7, 41)], total: 1, page: 1, size: 100 });
  mediaApi.uploadDentalMedia.mockResolvedValue({ ...savedImage(7, 41), id: 42 });
  mediaApi.updateDentalMedia.mockResolvedValue(savedImage(7, 41));
  mediaApi.deleteDentalMedia.mockResolvedValue(undefined);
  mediaApi.loadDentalMediaContent.mockResolvedValue(new Blob(['synthetic image bytes'], { type: 'image/png' }));
});

describe('PhotoArchive — patient-context isolation (DENTPHOTO-FE-001/002)', () => {
  it('clears a selected file on identity switch so it cannot be uploaded to patient B', async () => {
    const view = renderWithProviders(
      <PhotoArchive patientId={7} visitId={41} patientName="SYNTHETIC Patient A" />,
    );
    await screen.findByText('SYNTHETIC-Xray');

    const input = screen.getByLabelText(/JPG, PNG|JPG, PNG/) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [syntheticFile()] } });

    view.rerender(
      <PhotoArchive patientId={8} visitId={42} patientName="SYNTHETIC Patient B" />,
    );
    await waitFor(() => expect(mediaApi.listDentalMedia).toHaveBeenCalledWith(8, 42));

    fireEvent.click(uploadButton());

    // Patient A's file must not reach the upload API under patient B's ids.
    await waitFor(() => expect(mediaApi.uploadDentalMedia).not.toHaveBeenCalled());
    expect(mediaApi.uploadDentalMedia).not.toHaveBeenCalledWith(
      8,
      42,
      expect.anything(),
      expect.anything(),
      expect.anything(),
    );
  });

  it('closes an open preview when the identity switches', async () => {
    const view = renderWithProviders(
      <PhotoArchive patientId={7} visitId={41} patientName="SYNTHETIC Patient A" />,
    );
    await screen.findByText('SYNTHETIC-Xray');

    fireEvent.click(viewButton());
    expect(await screen.findByAltText('SYNTHETIC-Xray')).toBeTruthy();
    expect(screen.getByRole('dialog')).toBeTruthy();

    view.rerender(
      <PhotoArchive patientId={8} visitId={42} patientName="SYNTHETIC Patient B" />,
    );
    await waitFor(() => expect(mediaApi.listDentalMedia).toHaveBeenCalledWith(8, 42));

    // The old preview overlay must be gone.
    await waitFor(() => {
      expect(screen.queryByAltText('SYNTHETIC-Xray')).toBeNull();
      expect(screen.queryByRole('dialog')).toBeNull();
    });
  });

  it('does not reopen a delayed preview response from the previous patient after a switch', async () => {
    let resolveContent: ((blob: Blob) => void) | undefined;
    mediaApi.loadDentalMediaContent.mockReturnValueOnce(new Promise((resolve) => {
      resolveContent = resolve;
    }));

    const view = renderWithProviders(
      <PhotoArchive patientId={7} visitId={41} patientName="SYNTHETIC Patient A" />,
    );
    await screen.findByText('SYNTHETIC-Xray');

    fireEvent.click(viewButton());
    await waitFor(() => expect(mediaApi.loadDentalMediaContent).toHaveBeenCalled());

    view.rerender(
      <PhotoArchive patientId={8} visitId={42} patientName="SYNTHETIC Patient B" />,
    );
    await waitFor(() => expect(mediaApi.listDentalMedia).toHaveBeenCalledWith(8, 42));

    await act(async () => {
      resolveContent?.(new Blob(['synthetic old patient bytes'], { type: 'image/png' }));
      await Promise.resolve();
    });
    await new Promise((resolve) => setTimeout(resolve, 30));

    // A late resolution for patient A must not render a preview under patient B.
    expect(screen.queryByAltText('SYNTHETIC-Xray')).toBeNull();
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
