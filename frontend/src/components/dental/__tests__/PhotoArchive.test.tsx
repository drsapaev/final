import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
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

const savedImage: DentalMediaItem = {
  id: 41,
  title: 'SYNTHETIC-Xray',
  description: null,
  category: 'xray',
  tooth: '16',
  capture_date: '2026-09-20',
  mime_type: 'image/png',
  file_size: 120,
  patient_id: 7,
  visit_id: 9,
  created_at: '2026-09-20T08:00:00Z',
  updated_at: '2026-09-20T08:00:00Z',
};

describe('PhotoArchive', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mediaApi.listDentalMedia.mockResolvedValue({ items: [savedImage], total: 1, page: 1, size: 100 });
    mediaApi.uploadDentalMedia.mockResolvedValue({ ...savedImage, id: 42 });
    mediaApi.updateDentalMedia.mockResolvedValue(savedImage);
    mediaApi.deleteDentalMedia.mockResolvedValue(undefined);
  });

  it('loads saved files from the protected API and refreshes after upload', async () => {
    renderWithProviders(<PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient" />);

    expect(await screen.findByText('SYNTHETIC-Xray')).toBeInTheDocument();
    expect(mediaApi.listDentalMedia).toHaveBeenCalledWith(7, 9);

    const input = screen.getByLabelText(/JPG, PNG|JPG, PNG/);
    const file = new File(['synthetic image bytes'], 'xray.png', { type: 'image/png' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /Загрузить файлы|Upload files/ }));

    await waitFor(() => expect(mediaApi.uploadDentalMedia).toHaveBeenCalledWith(
      7,
      9,
      'photo',
      file,
      expect.objectContaining({ capture_date: null }),
    ));
    expect(await screen.findByText(/Снимок сохранён|Image saved/)).toBeInTheDocument();
    await waitFor(() => expect(mediaApi.listDentalMedia).toHaveBeenCalledTimes(2));
  });

  it('requires an authorized visit before making any archive request', () => {
    renderWithProviders(<PhotoArchive patientId={7} patientName="SYNTHETIC-Patient" />);

    expect(screen.getByText(/confirmed visit|подтверждённым визитом/i)).toBeInTheDocument();
    expect(mediaApi.listDentalMedia).not.toHaveBeenCalled();
    expect(screen.queryByLabelText(/JPG, PNG|JPG, PNG/)).not.toBeInTheDocument();
  });

  it('rejects unsupported formats with a clear message before upload', async () => {
    renderWithProviders(<PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient" />);
    await screen.findByText('SYNTHETIC-Xray');

    const input = screen.getByLabelText(/JPG, PNG|JPG, PNG/);
    fireEvent.change(input, {
      target: { files: [new File(['synthetic'], 'script.exe', { type: 'application/octet-stream' })] },
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(/Choose a JPG|Выберите файл JPG/);
    expect(mediaApi.uploadDentalMedia).not.toHaveBeenCalled();
  });

  it('shows a safe retry message when upload fails', async () => {
    mediaApi.uploadDentalMedia.mockRejectedValue(new Error('patient diagnosis details must not be shown'));
    renderWithProviders(<PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient" />);
    await screen.findByText('SYNTHETIC-Xray');

    const input = screen.getByLabelText(/JPG, PNG|JPG, PNG/);
    fireEvent.change(input, {
      target: { files: [new File(['synthetic'], 'xray.png', { type: 'image/png' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /Загрузить файлы|Upload files/ }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Could not complete the action|Не удалось выполнить действие/);
    expect(alert).not.toHaveTextContent(/patient diagnosis details/);
    expect(mediaApi.uploadDentalMedia).toHaveBeenCalledTimes(1);
  });

  it('offers retry and reloads the archive after a list error', async () => {
    mediaApi.listDentalMedia
      .mockRejectedValueOnce(new Error('synthetic network failure'))
      .mockResolvedValueOnce({ items: [savedImage], total: 1, page: 1, size: 100 });
    renderWithProviders(<PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient" />);

    expect(await screen.findByText(/Could not load the archive|Не удалось загрузить архив/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Retry|Повторить/ }));

    expect(await screen.findByText('SYNTHETIC-Xray')).toBeInTheDocument();
    expect(mediaApi.listDentalMedia).toHaveBeenCalledTimes(2);
  });

  it('surfaces permission errors when an older image cannot be edited', async () => {
    mediaApi.updateDentalMedia.mockRejectedValue({ response: { status: 403 } });
    renderWithProviders(<PhotoArchive patientId={7} visitId={9} patientName="SYNTHETIC-Patient" />);
    await screen.findByText('SYNTHETIC-Xray');

    fireEvent.click(screen.getByRole('button', { name: /Редактировать|Edit/ }));
    fireEvent.click(screen.getByRole('button', { name: /Сохранить|Save/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/permission|прав на изменение/i);
    expect(mediaApi.updateDentalMedia).toHaveBeenCalledWith(41, expect.objectContaining({ category: 'xray' }));
  });
});
