import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PublicSiteMediaManager from '../PublicSiteMediaManager';

const mocks = vi.hoisted(() => ({
  listMedia: vi.fn(),
  listDoctors: vi.fn(),
  upload: vi.fn(),
  publish: vi.fn(),
  unpublish: vi.fn(),
  confirm: vi.fn(),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('../../../api/publicSiteMedia', () => ({
  listPublicSiteMedia: mocks.listMedia,
  listPublicSiteDoctors: mocks.listDoctors,
  uploadPublicSiteMedia: mocks.upload,
  publishPublicSiteMedia: mocks.publish,
  unpublishPublicSiteMedia: mocks.unpublish,
  getPublicSiteMediaErrorKey: (error: unknown) =>
    (error as { message?: string }).message === 'storage'
      ? 'publicSiteMedia.storageUnavailable'
      : 'publicSiteMedia.genericError',
}));

vi.mock('../../common/ConfirmDialog', () => ({
  useConfirm: () => [mocks.confirm, null],
}));

vi.mock('../../ui/macos', () => ({
  Button: ({ children, onClick, disabled, type = 'button' }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button type={type} onClick={onClick} disabled={disabled}>{children}</button>
  ),
  Card: ({ children, className }: React.HTMLAttributes<HTMLElement>) => (
    <section className={className}>{children}</section>
  ),
}));

const doctor = { id: 42, displayName: 'SYNTHETIC Doctor', active: true };
const draftMedia = {
  id: 8,
  asset_kind: 'doctor_portrait' as const,
  doctor_id: 42,
  mime_type: 'image/jpeg',
  byte_size: 2048,
  is_published: false,
  published_at: null,
  created_at: '2026-10-17T09:00:00Z',
  media_url: '/api/v1/public-site/media/synthetic-key',
};
const logoMedia = { ...draftMedia, asset_kind: 'clinic_logo' as const, doctor_id: null };

describe('PublicSiteMediaManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listMedia.mockResolvedValue([]);
    mocks.listDoctors.mockResolvedValue([doctor]);
    mocks.upload.mockResolvedValue(draftMedia);
    mocks.publish.mockResolvedValue({ ...draftMedia, is_published: true });
    mocks.unpublish.mockResolvedValue({ ...draftMedia, is_published: false });
    mocks.confirm.mockResolvedValue(true);
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:synthetic-preview') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  });

  afterEach(() => cleanup());

  it('previews a local image and uploads it as an unpublished clinic-logo draft', async () => {
    mocks.upload.mockResolvedValue(logoMedia);
    render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');

    const file = new File(['synthetic image'], 'clinic-logo.png', { type: 'image/png' });
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });
    expect(await screen.findByRole('img', { name: 'publicSiteMedia.previewAlt' })).toHaveAttribute('src', 'blob:synthetic-preview');

    fireEvent.click(screen.getByRole('button', { name: 'publicSiteMedia.uploadDraft' }));
    await waitFor(() => expect(mocks.upload).toHaveBeenCalledWith(file, 'clinic_logo', undefined));
    expect(await screen.findByText('publicSiteMedia.uploadSuccess')).toBeInTheDocument();
    expect(screen.getByText('publicSiteMedia.draft')).toBeInTheDocument();
  });

  it('requires an active doctor selection for a portrait and uploads only that doctor association', async () => {
    render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');

    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });
    fireEvent.change(screen.getByLabelText('publicSiteMedia.doctor'), { target: { value: '42' } });
    const file = new File(['synthetic portrait'], 'portrait.webp', { type: 'image/webp' });
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'publicSiteMedia.uploadDraft' }));

    await waitFor(() => expect(mocks.upload).toHaveBeenCalledWith(file, 'doctor_portrait', 42));
  });

  it('requires explicit confirmation before publishing and removes a previous published state in the list', async () => {
    mocks.listMedia.mockResolvedValue([{ ...logoMedia, id: 7, is_published: true }, logoMedia]);
    mocks.publish.mockResolvedValue({ ...logoMedia, is_published: true });
    render(<PublicSiteMediaManager />);
    await screen.findByRole('button', { name: 'publicSiteMedia.publish' });

    fireEvent.click(screen.getByRole('button', { name: 'publicSiteMedia.publish' }));
    await waitFor(() => expect(mocks.publish).toHaveBeenCalledWith(8));
    expect(mocks.confirm).toHaveBeenCalledWith(expect.objectContaining({
      title: 'publicSiteMedia.confirmPublishTitle',
      message: 'publicSiteMedia.confirmPublishMessage',
    }));
    expect(await screen.findByText('publicSiteMedia.publishSuccess')).toBeInTheDocument();
    expect(screen.getAllByText('publicSiteMedia.published')).toHaveLength(1);
    expect(screen.getAllByText('publicSiteMedia.draft')).toHaveLength(1);
  });

  it('requires explicit confirmation before removing a published image', async () => {
    mocks.listMedia.mockResolvedValue([{ ...logoMedia, is_published: true }]);
    mocks.unpublish.mockResolvedValue({ ...logoMedia, is_published: false });
    render(<PublicSiteMediaManager />);
    await screen.findByRole('button', { name: 'publicSiteMedia.unpublish' });

    fireEvent.click(screen.getByRole('button', { name: 'publicSiteMedia.unpublish' }));
    await waitFor(() => expect(mocks.unpublish).toHaveBeenCalledWith(8));
    expect(mocks.confirm).toHaveBeenCalledWith(expect.objectContaining({
      title: 'publicSiteMedia.confirmUnpublishTitle',
      message: 'publicSiteMedia.confirmUnpublishMessage',
    }));
    expect(await screen.findByText('publicSiteMedia.unpublishSuccess')).toBeInTheDocument();
  });

  it('keeps inactive doctors manageable for unpublishing but blocks new portrait publication', async () => {
    mocks.listDoctors.mockResolvedValue([{ id: 42, displayName: 'SYNTHETIC Former Doctor', active: false }]);
    mocks.listMedia.mockResolvedValue([
      { ...draftMedia, id: 7, is_published: true },
      { ...draftMedia, id: 8, is_published: false },
    ]);
    mocks.unpublish.mockResolvedValue({ ...draftMedia, id: 7, is_published: false });
    render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');

    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });
    fireEvent.change(screen.getByLabelText('publicSiteMedia.doctor'), { target: { value: '42' } });
    expect(await screen.findByText('publicSiteMedia.inactiveDoctorUpload')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'publicSiteMedia.uploadDraft' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'publicSiteMedia.publish' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'publicSiteMedia.unpublish' })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: 'publicSiteMedia.unpublish' }));
    await waitFor(() => expect(mocks.unpublish).toHaveBeenCalledWith(7));
  });

  it('shows an unavailable-storage message and disables upload when the API reports 503', async () => {
    mocks.listMedia.mockRejectedValue(new Error('storage'));
    render(<PublicSiteMediaManager />);

    expect(await screen.findByRole('alert')).toHaveTextContent('publicSiteMedia.storageUnavailable');
    expect(screen.getByRole('button', { name: 'publicSiteMedia.uploadDraft' })).toBeDisabled();
  });
});
