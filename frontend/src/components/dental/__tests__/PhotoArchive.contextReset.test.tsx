/**
 * Audit 3892 round 1 — fail-first regressions for PhotoArchive
 * patient/visit context isolation.
 *
 * Covers:
 *  - DENTPHOTO-FE-001: a file previously chosen for patient A must never be
 *    uploaded under patient B after the archive switches context while the
 *    dialog stays mounted.
 *  - DENTPHOTO-FE-002: an open preview must close (and revoke its blob URL)
 *    on a context switch, and a delayed old-patient preview request must not
 *    reopen under the new patient's archive.
 */
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/renderWithProviders';
import PhotoArchive from '../PhotoArchive';
import type { DentalMediaItem } from '../../../api/dentalMedia';

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

const originalCreateObjectURL = URL.createObjectURL;
const originalRevokeObjectURL = URL.revokeObjectURL;

beforeAll(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock-preview-url');
  URL.revokeObjectURL = vi.fn();
});

afterAll(() => {
  URL.createObjectURL = originalCreateObjectURL;
  URL.revokeObjectURL = originalRevokeObjectURL;
});

const fileInputLabel = /JPG, PNG|JPG, PNG/;
const uploadButton = () => screen.getByRole('button', { name: /Загрузить файлы|Upload files/ });

beforeEach(() => {
  vi.clearAllMocks();
  mediaApi.listDentalMedia.mockResolvedValue({ items: [savedImage(7, 9)], total: 1, page: 1, size: 100 });
});

describe('PhotoArchive patient-context isolation (audit 3892 round 1)', () => {
  it('DENTPHOTO-FE-001: patient A\'s selected file is not uploaded under patient B after a context switch', async () => {
    const view = renderWithProviders(
      <PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient-A" />,
    );

    const input = await screen.findByLabelText(fileInputLabel);
    const aFile = new File(['synthetic patient A bytes'], 'a-xray.png', { type: 'image/png' });
    fireEvent.change(input, { target: { files: [aFile] } });

    view.rerender(
      <PhotoArchive patientId={8} visitId={42} patientName="SYNTHETIC-Patient-B" />,
    );

    await waitFor(() => expect(mediaApi.listDentalMedia).toHaveBeenCalledWith(8, 42));

    // Upload attempt after the switch: the A file must already be cleared.
    fireEvent.click(uploadButton());

    const uploadCalls = mediaApi.uploadDentalMedia.mock.calls;
    expect(uploadCalls.filter((call) => call[3] === aFile)).toHaveLength(0);
    expect(uploadCalls.filter((call) => call[0] === 8 && call[1] === 42)).toHaveLength(0);
  });

  it('DENTPHOTO-FE-002: the open preview closes and revokes its URL on a context switch', async () => {
    mediaApi.loadDentalMediaContent.mockResolvedValue(new Blob(['synthetic image'], { type: 'image/png' }));
    const view = renderWithProviders(
      <PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient-A" />,
    );

    fireEvent.click(await screen.findByRole('button', { name: /Просмотр|View/ }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());

    view.rerender(
      <PhotoArchive patientId={8} visitId={42} patientName="SYNTHETIC-Patient-B" />,
    );

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-preview-url');
  });

  it('review 3903 P2 (DENTPHOTO): a late A-context upload completion preserves B\'s in-progress upload form', async () => {
    let resolveUpload: (() => void) | undefined;
    mediaApi.uploadDentalMedia.mockImplementation(() => new Promise<void>((resolve) => {
      resolveUpload = resolve;
    }));
    const view = renderWithProviders(
      <PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient-A" />,
    );

    const input = await screen.findByLabelText(fileInputLabel) as HTMLInputElement;
    const aFile = new File(['synthetic patient A bytes'], 'a-xray.png', { type: 'image/png' });
    fireEvent.change(input, { target: { files: [aFile] } });
    const titleInput = screen.getByLabelText(/Название снимка|Title/) as HTMLInputElement;
    fireEvent.change(titleInput, { target: { value: 'SYNTHETIC A title' } });
    fireEvent.click(uploadButton());

    // The archive switches to B while A's upload POST is still pending; B
    // picks a file and types metadata.
    view.rerender(
      <PhotoArchive patientId={8} visitId={42} patientName="SYNTHETIC-Patient-B" />,
    );
    await waitFor(() => expect(mediaApi.listDentalMedia).toHaveBeenCalledWith(8, 42));

    const bFile = new File(['synthetic patient B bytes'], 'b-photo.png', { type: 'image/png' });
    fireEvent.change(input, { target: { files: [bFile] } });
    fireEvent.change(titleInput, { target: { value: 'SYNTHETIC B title' } });

    // A's upload completes only now — its late callback must not clear B's
    // in-progress form.
    await act(async () => {
      resolveUpload?.();
      await Promise.resolve();
    });

    // B's in-progress form survives: the typed metadata is intact, the
    // selected file is still B's (the submit control stays enabled — jsdom
    // file inputs do not reflect the file name in .value, so the enabled
    // state and the eventual upload carry prove preservation), and the
    // spinner A left behind was cleared by the context switch.
    expect(titleInput).toHaveProperty('value', 'SYNTHETIC B title');
    expect(uploadButton()).toHaveProperty('disabled', false);

    mediaApi.uploadDentalMedia.mockResolvedValue(undefined);
    fireEvent.click(uploadButton());
    await waitFor(() => expect(mediaApi.uploadDentalMedia).toHaveBeenCalledWith(
      8,
      42,
      'photo',
      bFile,
      expect.objectContaining({ title: 'SYNTHETIC B title' }),
    ));
  });

  it('DENTPHOTO-FE-002: a delayed old-patient preview response cannot reopen under the new patient', async () => {
    let resolveContent: ((blob: Blob) => void) | undefined;
    mediaApi.loadDentalMediaContent.mockImplementation(() => new Promise((resolve) => {
      resolveContent = resolve;
    }));

    const view = renderWithProviders(
      <PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient-A" />,
    );
    fireEvent.click(await screen.findByRole('button', { name: /Просмотр|View/ }));

    view.rerender(
      <PhotoArchive patientId={8} visitId={42} patientName="SYNTHETIC-Patient-B" />,
    );
    await waitFor(() => expect(mediaApi.listDentalMedia).toHaveBeenCalledWith(8, 42));

    // The old patient's content request resolves only after B is selected.
    await act(async () => {
      resolveContent?.(new Blob(['late old patient blob'], { type: 'image/png' }));
      await Promise.resolve();
    });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-preview-url');
  });
});
