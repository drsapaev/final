import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PublicSiteMediaManager from '../PublicSiteMediaManager';

const mocks = vi.hoisted(() => ({
  listMedia: vi.fn(),
  listDoctors: vi.fn(),
  doctorWebsiteContent: vi.fn(),
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
  getPublicSiteDoctorWebsiteContent: mocks.doctorWebsiteContent,
  isPublicSiteDoctorEligible: (content: { active: boolean; owner_active: boolean | null; show_on_website: boolean; missing_fields: string[] }) =>
    content.active && content.owner_active === true && content.show_on_website && content.missing_fields.length === 0,
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
const doctorWebsiteContent = {
  id: 42,
  active: true,
  owner_active: true,
  show_on_website: true,
  missing_fields: [],
};
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
    mocks.doctorWebsiteContent.mockResolvedValue(doctorWebsiteContent);
    mocks.upload.mockResolvedValue(draftMedia);
    mocks.publish.mockResolvedValue({ ...draftMedia, is_published: true });
    mocks.unpublish.mockResolvedValue({ ...draftMedia, is_published: false });
    mocks.confirm.mockResolvedValue(true);
  });

  afterEach(() => cleanup());

  it('shows the selected filename and uploads a supported image as an unpublished clinic-logo draft', async () => {
    mocks.upload.mockResolvedValue(logoMedia);
    render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');

    const file = new File(['synthetic image'], 'clinic-logo.png', { type: 'image/png' });
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });
    expect(screen.getByText('publicSiteMedia.selectedFile: clinic-logo.png')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'publicSiteMedia.uploadDraft' }));
    await waitFor(() => expect(mocks.upload).toHaveBeenCalledWith(file, 'clinic_logo', undefined));
    expect(await screen.findByText('publicSiteMedia.uploadSuccess')).toBeInTheDocument();
    expect(screen.getByText('publicSiteMedia.draft')).toBeInTheDocument();
  });

  it('rejects an unsupported MIME type even when the filename looks like a supported image', async () => {
    render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');

    const file = new File(['synthetic svg'], 'clinic-logo.png', { type: 'image/svg+xml' });
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });

    expect(await screen.findByRole('alert')).toHaveTextContent('publicSiteMedia.invalidFileType');
    expect(mocks.upload).not.toHaveBeenCalled();
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

  it('blocks portrait publication when the doctor is not currently eligible for the public site', async () => {
    mocks.listMedia.mockResolvedValue([draftMedia]);
    mocks.doctorWebsiteContent.mockResolvedValue({ ...doctorWebsiteContent, owner_active: false });
    render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');

    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });
    fireEvent.change(screen.getByLabelText('publicSiteMedia.doctor'), { target: { value: '42' } });

    expect(await screen.findByText('publicSiteMedia.doctorNotPublicReady')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'publicSiteMedia.publish' })).toBeDisabled();
    expect(mocks.publish).not.toHaveBeenCalled();
  });

  it('does not label an ineligible published portrait as publicly available', async () => {
    mocks.listMedia.mockResolvedValue([{ ...draftMedia, is_published: true }]);
    mocks.doctorWebsiteContent.mockResolvedValue({ ...doctorWebsiteContent, show_on_website: false });
    const { container } = render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');

    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });
    fireEvent.change(screen.getByLabelText('publicSiteMedia.doctor'), { target: { value: '42' } });

    expect(await screen.findByText('publicSiteMedia.publishedNotVisible')).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('.public-site-media__item--without-preview')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'publicSiteMedia.unpublish' })).toBeEnabled();
  });

  it('keeps published portraits visible for takedown when the doctor list fails', async () => {
    mocks.listMedia.mockResolvedValue([{ ...draftMedia, is_published: true }]);
    mocks.listDoctors.mockRejectedValue(new Error('offline'));
    render(<PublicSiteMediaManager />);
    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });
    await screen.findByText('publicSiteMedia.doctorsLoadError');

    const unpublishButton = await screen.findByRole('button', { name: 'publicSiteMedia.unpublish' });
    expect(unpublishButton).toBeEnabled();
    expect(screen.getByText('#42')).toBeInTheDocument();
    expect(screen.getByText('publicSiteMedia.publishedVisibilityUnknown')).toBeInTheDocument();
    fireEvent.click(unpublishButton);
    await waitFor(() => expect(mocks.unpublish).toHaveBeenCalledWith(8));
  });

  it('loads doctor options in bounded pages instead of requesting hundreds at once', async () => {
    mocks.listDoctors.mockResolvedValueOnce(
      Array.from({ length: 25 }, (_, index) => ({
        ...doctor,
        id: index + 1,
        displayName: `SYNTHETIC Doctor ${index + 1}`,
      })),
    );
    mocks.listDoctors.mockResolvedValueOnce([{ ...doctor, id: 26, displayName: 'SYNTHETIC Doctor 26' }]);
    render(<PublicSiteMediaManager />);
    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });

    const loadMore = await screen.findByRole('button', { name: 'publicSiteMedia.loadMoreDoctors' });
    fireEvent.click(loadMore);
    await waitFor(() => expect(mocks.listDoctors).toHaveBeenLastCalledWith(25, 25));
    expect(await screen.findByRole('option', { name: 'SYNTHETIC Doctor 26' })).toBeInTheDocument();
  });

  it('marks owners absent from an incomplete doctor list as unverified, not inactive', async () => {
    mocks.listDoctors.mockResolvedValueOnce(
      Array.from({ length: 25 }, (_, index) => ({
        ...doctor,
        id: index + 1,
        displayName: `SYNTHETIC Doctor ${index + 1}`,
      })),
    );
    mocks.listDoctors.mockResolvedValueOnce([{ ...doctor, id: 42, displayName: 'SYNTHETIC Doctor 42' }]);
    mocks.listMedia.mockResolvedValue([{ ...draftMedia, is_published: true }]);
    render(<PublicSiteMediaManager />);
    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });

    const doctorOption = await screen.findByRole('option', {
      name: '#42 · publicSiteMedia.doctorStatusUnverified',
    });
    expect(doctorOption).toBeInTheDocument();
    expect(doctorOption).not.toHaveTextContent('publicSiteMedia.inactiveDoctor');

    fireEvent.change(screen.getByLabelText('publicSiteMedia.doctor'), { target: { value: '42' } });
    expect(await screen.findByText('publicSiteMedia.doctorStatusUnverified')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'publicSiteMedia.loadMoreDoctors' }));
    expect(await screen.findByRole('option', { name: 'SYNTHETIC Doctor 42' })).toBeInTheDocument();
    expect(screen.queryByText('publicSiteMedia.doctorStatusUnverified')).toBeNull();
    expect(screen.getByRole('button', { name: 'publicSiteMedia.unpublish' })).toBeEnabled();
  });

  it('disambiguates duplicate doctor names across loaded pages', async () => {
    mocks.listDoctors.mockResolvedValueOnce([
      { ...doctor, id: 42, displayName: 'SYNTHETIC Shared Doctor' },
      ...Array.from({ length: 24 }, (_, index) => ({
        ...doctor,
        id: index + 100,
        displayName: `SYNTHETIC Doctor ${index + 100}`,
      })),
    ]);
    mocks.listDoctors.mockResolvedValueOnce([{ ...doctor, id: 26, displayName: 'SYNTHETIC Shared Doctor' }]);
    render(<PublicSiteMediaManager />);
    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });

    fireEvent.click(await screen.findByRole('button', { name: 'publicSiteMedia.loadMoreDoctors' }));

    expect(await screen.findByRole('option', { name: 'SYNTHETIC Shared Doctor (#42)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'SYNTHETIC Shared Doctor (#26)' })).toBeInTheDocument();
  });

  it('refreshes the selected doctor public-readiness record', async () => {
    render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');
    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });
    fireEvent.change(screen.getByLabelText('publicSiteMedia.doctor'), { target: { value: '42' } });
    await waitFor(() => expect(mocks.doctorWebsiteContent).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'common.refresh' }));

    await waitFor(() => expect(mocks.doctorWebsiteContent).toHaveBeenCalledTimes(2));
  });

  it('uses a section root because the Clinic OS shell already provides the main landmark', async () => {
    const { container } = render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');
    expect(container.querySelector('main')).toBeNull();
    expect(container.querySelector('section.public-site-media')).toBeInTheDocument();
  });

  it('keeps inactive doctors manageable for unpublishing but blocks new portrait publication', async () => {
    mocks.listDoctors.mockResolvedValue([]);
    mocks.listMedia.mockResolvedValue([
      { ...draftMedia, id: 7, is_published: true },
      { ...draftMedia, id: 8, is_published: false },
    ]);
    mocks.unpublish.mockResolvedValue({ ...draftMedia, id: 7, is_published: false });
    render(<PublicSiteMediaManager />);
    await screen.findByText('publicSiteMedia.noMedia');

    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });
    expect(await screen.findByRole('option', { name: /#42/ })).toBeInTheDocument();
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

  it('keeps storage unavailable visible and mutations disabled after a retry succeeds', async () => {
    mocks.listMedia.mockRejectedValueOnce(new Error('storage')).mockResolvedValueOnce([]);
    render(<PublicSiteMediaManager />);

    expect(await screen.findByRole('alert')).toHaveTextContent('publicSiteMedia.storageUnavailable');
    fireEvent.change(screen.getByLabelText('publicSiteMedia.assetKind'), { target: { value: 'doctor_portrait' } });
    expect(screen.getByRole('alert')).toHaveTextContent('publicSiteMedia.storageUnavailable');
    expect(document.querySelector('input[type="file"]')).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'publicSiteMedia.retry' }));
    await waitFor(() => expect(mocks.listMedia).toHaveBeenCalledTimes(2));

    expect(await screen.findByRole('alert')).toHaveTextContent('publicSiteMedia.storageUnavailable');
    expect(document.querySelector('input[type="file"]')).toBeDisabled();
  });
});
