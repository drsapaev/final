import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StaffPublicBookingRequest } from '../../../api/adminPublicBookingRequests';

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  confirm: vi.fn(),
  requestNewTime: vi.fn(),
  reject: vi.fn(),
  askConfirm: vi.fn(),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key, language: 'ru' }),
}));

vi.mock('../../../api/adminPublicBookingRequests', () => ({
  listStaffPublicBookingRequests: mocks.list,
  confirmStaffPublicBookingRequest: mocks.confirm,
  requestNewTimeForPublicBookingRequest: mocks.requestNewTime,
  rejectPublicBookingRequest: mocks.reject,
  getStaffBookingRequestErrorCode: (error: unknown) => {
    const detail = (error as { response?: { data?: { detail?: { code?: unknown } } } })
      ?.response?.data?.detail;
    return typeof detail?.code === 'string' ? detail.code : null;
  },
  STAFF_BOOKING_REQUEST_PAGE_SIZE: 50,
}));

vi.mock('../../common/ConfirmDialog', () => ({
  useConfirm: () => [mocks.askConfirm, null],
}));

vi.mock('../../ui/macos', () => ({
  Button: ({
    children,
    onClick,
    disabled,
    type = 'button',
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) => (
    <button type={type} onClick={onClick} disabled={disabled}>{children}</button>
  ),
  Badge: ({ children, variant }: React.HTMLAttributes<HTMLSpanElement> & { variant?: string }) => (
    <span data-variant={variant}>{children}</span>
  ),
  Card: ({ children, className }: React.HTMLAttributes<HTMLElement>) => (
    <section className={className}>{children}</section>
  ),
}));

import PublicBookingRequestsManager from '../PublicBookingRequestsManager';

const pendingRequest: StaffPublicBookingRequest = {
  id: 'd0552c55-0a77-4c7f-a6de-22580d270ab5',
  patientDisplayName: 'SYNTHETIC Patient',
  serviceName: 'SYNTHETIC Consultation',
  doctorDisplayName: 'SYNTHETIC Doctor',
  serviceSlug: 'synthetic-service',
  doctorSlug: 'synthetic-doctor',
  appointmentDate: '2026-11-04',
  appointmentTime: '10:20:00',
  status: 'pending',
  version: 7,
  createdAt: '2026-10-28T08:15:00+05:00',
};

describe('PublicBookingRequestsManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.list.mockResolvedValue([pendingRequest]);
    mocks.confirm.mockResolvedValue({ ...pendingRequest, status: 'confirmed' });
    mocks.requestNewTime.mockResolvedValue({ ...pendingRequest, status: 'needs_new_time' });
    mocks.reject.mockResolvedValue({ ...pendingRequest, status: 'rejected' });
    mocks.askConfirm.mockResolvedValue(true);
  });

  afterEach(cleanup);

  it('shows a pending request with only the booking facts needed by staff', async () => {
    const { container } = render(<PublicBookingRequestsManager />);

    expect(await screen.findByText('SYNTHETIC Patient')).toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC Consultation')).toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC Doctor')).toBeInTheDocument();
    expect(screen.getByText('admin2.pbr_contact_note')).toBeInTheDocument();
    expect(container).not.toHaveTextContent('987654');
    expect(container).not.toHaveTextContent(pendingRequest.id);
    expect(mocks.list).toHaveBeenCalledWith({ status: 'pending', offset: 0 });
    expect(screen.getByRole('button', { name: 'admin2.pbr_confirm' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'admin2.pbr_request_new_time' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'admin2.pbr_reject' })).toBeEnabled();
  });

  it('shows newly arrived requests after a manual refresh', async () => {
    const newlyArrivedRequest = {
      ...pendingRequest,
      id: 'newly-arrived-request',
      patientDisplayName: 'SYNTHETIC New Patient',
    };
    mocks.list
      .mockResolvedValueOnce([pendingRequest])
      .mockResolvedValueOnce([newlyArrivedRequest]);
    render(<PublicBookingRequestsManager />);

    expect(await screen.findByText('SYNTHETIC Patient')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'common.refresh' }));

    expect(await screen.findByText('SYNTHETIC New Patient')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(2);
    expect(mocks.list).toHaveBeenLastCalledWith({ status: 'pending', offset: 0 });
  });

  it('ignores a load-more response from before an action refresh', async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) => ({
      ...pendingRequest,
      id: `request-${index}`,
      patientDisplayName: `SYNTHETIC Patient ${index}`,
    }));
    const refreshedRequest = {
      ...firstPage[0],
      patientDisplayName: 'SYNTHETIC Refreshed Patient',
      version: pendingRequest.version + 1,
    };
    const staleRequest = {
      ...pendingRequest,
      id: 'stale-load-more-request',
      patientDisplayName: 'SYNTHETIC Stale Patient',
    };
    let resolveLoadMore!: (page: StaffPublicBookingRequest[]) => void;
    const loadMoreResponse = new Promise<StaffPublicBookingRequest[]>((resolve) => {
      resolveLoadMore = resolve;
    });
    mocks.list
      .mockResolvedValueOnce(firstPage)
      .mockReturnValueOnce(loadMoreResponse)
      .mockResolvedValueOnce([refreshedRequest]);
    render(<PublicBookingRequestsManager />);

    expect(await screen.findByText('SYNTHETIC Patient 0')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'admin2.pbr_load_more' }));
    await waitFor(() => expect(mocks.list).toHaveBeenNthCalledWith(
      2,
      { status: 'pending', offset: 50 },
    ));

    fireEvent.click(screen.getAllByRole('button', { name: 'admin2.pbr_confirm' })[0]);
    await waitFor(() => expect(mocks.confirm).toHaveBeenCalledWith(firstPage[0].id, 7));
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(3));
    expect(await screen.findByText('SYNTHETIC Refreshed Patient')).toBeInTheDocument();

    await act(async () => {
      resolveLoadMore([staleRequest]);
      await loadMoreResponse;
    });

    expect(screen.queryByText('SYNTHETIC Stale Patient')).not.toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC Refreshed Patient')).toBeInTheDocument();
  });

  it('rechecks and confirms using the request version, then keeps the result visible during refresh', async () => {
    mocks.list.mockResolvedValueOnce([pendingRequest]).mockResolvedValueOnce([]);
    const { container } = render(<PublicBookingRequestsManager />);

    fireEvent.click(await screen.findByRole('button', { name: 'admin2.pbr_confirm' }));

    await waitFor(() => expect(mocks.confirm).toHaveBeenCalledWith(pendingRequest.id, 7));
    expect(mocks.askConfirm).toHaveBeenCalledWith(expect.objectContaining({
      title: 'admin2.pbr_confirm_confirm',
      message: 'admin2.pbr_confirm_confirm_description',
    }));
    expect(await screen.findByText('admin2.pbr_notice_confirmed')).toBeInTheDocument();
    expect(container).toHaveTextContent('admin2.pbr_notice_confirmed');
    expect(mocks.list).toHaveBeenCalledTimes(2);
  });

  it('marks an unavailable time as needing a new time without claiming the patient was notified', async () => {
    mocks.requestNewTime.mockResolvedValue({ ...pendingRequest, status: 'needs_new_time' });
    render(<PublicBookingRequestsManager />);

    fireEvent.click(await screen.findByRole('button', { name: 'admin2.pbr_request_new_time' }));

    await waitFor(() => expect(mocks.requestNewTime).toHaveBeenCalledWith(pendingRequest.id, 7));
    expect(await screen.findByText('admin2.pbr_notice_new_time')).toBeInTheDocument();
    expect(screen.getByText('admin2.pbr_contact_note')).toBeInTheDocument();
  });

  it('shows a retry action when the request list cannot be loaded', async () => {
    mocks.list.mockRejectedValueOnce(new Error('synthetic network failure'));
    render(<PublicBookingRequestsManager />);

    expect(await screen.findByRole('alert')).toHaveTextContent('admin2.pbr_error_load');
    fireEvent.click(screen.getByRole('button', { name: 'admin2.pbr_retry' }));
    expect(await screen.findByText('SYNTHETIC Patient')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(2);
  });

  it('keeps the concurrency conflict visible while refreshing the request', async () => {
    mocks.list.mockResolvedValueOnce([pendingRequest]).mockResolvedValueOnce([]);
    mocks.confirm.mockRejectedValueOnce({
      response: { data: { detail: { code: 'booking_request_version_conflict' } } },
    });
    render(<PublicBookingRequestsManager />);

    fireEvent.click(await screen.findByRole('button', { name: 'admin2.pbr_confirm' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('admin2.pbr_error_changed');
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('alert')).toHaveTextContent('admin2.pbr_error_changed');
  });

  it('shows only the reject action for a request that needs a new time', async () => {
    mocks.list.mockImplementation(({ status }: { status: string }) => Promise.resolve(
      status === 'needs_new_time' ? [{ ...pendingRequest, status: 'needs_new_time' }] : [],
    ));
    render(<PublicBookingRequestsManager />);

    fireEvent.change(await screen.findByLabelText('admin2.pbr_filter_label'), {
      target: { value: 'needs_new_time' },
    });

    expect(await screen.findByText('SYNTHETIC Patient')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'admin2.pbr_confirm' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'admin2.pbr_request_new_time' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'admin2.pbr_reject' })).toBeEnabled();
  });
});
