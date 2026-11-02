import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { MouseEventHandler, PropsWithChildren } from 'react';
import { MemoryRouter, useLocation } from 'react-router-dom';

const { listRequests, withdrawRequest, confirmAction } = vi.hoisted(() => ({
  listRequests: vi.fn(),
  withdrawRequest: vi.fn(),
  confirmAction: vi.fn(),
}));

vi.mock('../../api/publicBooking', () => ({
  listPatientPublicBookingRequests: listRequests,
  withdrawPatientPublicBookingRequest: withdrawRequest,
}));

vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key, language: 'ru' }),
}));

vi.mock('../../components/common/ConfirmDialog', () => ({
  useConfirm: () => [confirmAction, null],
}));

vi.mock('../../components/ui/macos', () => ({
  Card: ({ children, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <div {...props}>{children}</div>
  ),
  Button: ({ children, onClick, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <button type="button" onClick={onClick as MouseEventHandler<HTMLButtonElement>} {...props}>
      {children}
    </button>
  ),
  Badge: ({ children }: PropsWithChildren) => <span>{children}</span>,
}));

vi.mock('../../components/patient/PanelEmptyState', () => ({
  default: ({ title, variant }: { title: string; variant?: string }) => (
    <div role={variant === 'error' ? 'alert' : 'status'}>{title}</div>
  ),
}));

import PublicBookingRequestsPanel from '../../components/patient/PublicBookingRequestsPanel';

const pendingRequest = {
  id: '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ab',
  service_slug: 'cardiology',
  doctor_slug: 'doctor-one',
  appointment_date: '2026-10-30',
  appointment_time: '09:20:00',
  timezone: 'Asia/Tashkent' as const,
  status: 'pending' as const,
  settings_version: 1,
  version: 2,
  created_at: '2026-10-29T12:00:00Z',
  updated_at: '2026-10-29T12:00:00Z',
  history: [],
};

describe('patient panel public booking requests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    confirmAction.mockResolvedValue(true);
    withdrawRequest.mockResolvedValue({ ...pendingRequest, status: 'withdrawn', version: 3 });
    listRequests.mockResolvedValue([pendingRequest]);
  });

  it('shows request status and refreshes the self-scoped list on demand', async () => {
    render(<PublicBookingRequestsPanel />);

    expect(await screen.findByText('publicBookingRequests.status.pending')).toBeInTheDocument();
    expect(listRequests).toHaveBeenCalledWith({ limit: 50, offset: 0 });

    listRequests.mockResolvedValueOnce([{ ...pendingRequest, status: 'confirmed' }]);
    fireEvent.click(screen.getByRole('button', { name: 'publicBookingRequests.refresh' }));

    expect(await screen.findByText('publicBookingRequests.status.confirmed')).toBeInTheDocument();
    expect(listRequests).toHaveBeenCalledTimes(2);
  });

  it('allows the patient to withdraw an unprocessed request using its version', async () => {
    listRequests
      .mockResolvedValueOnce([pendingRequest])
      .mockResolvedValueOnce([]);
    render(<PublicBookingRequestsPanel />);

    fireEvent.click(await screen.findByRole('button', { name: 'publicBookingRequests.withdraw' }));

    await waitFor(() => {
      expect(withdrawRequest).toHaveBeenCalledWith(pendingRequest.id, pendingRequest.version);
    });
    expect(confirmAction).toHaveBeenCalledWith(expect.objectContaining({
      title: 'publicBookingRequests.withdrawConfirmTitle',
      intent: 'warning',
    }));
    expect(await screen.findByText('publicBookingRequests.empty')).toBeInTheDocument();
  });

  it('offers the public booking form when the registrar requests a different time', async () => {
    listRequests.mockResolvedValueOnce([{ ...pendingRequest, status: 'needs_new_time' }]);
    const RouteProbe = () => {
      const location = useLocation();
      return (
        <>
          <output data-testid="booking-route">{location.pathname + location.search}</output>
          <output data-testid="booking-route-state">{JSON.stringify(location.state)}</output>
        </>
      );
    };
    render(
      <MemoryRouter initialEntries={['/patient/home']}>
        <RouteProbe />
        <PublicBookingRequestsPanel />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('link', {
      name: 'publicBookingRequests.chooseAnotherTime',
    }));

    expect(screen.getByTestId('booking-route')).toHaveTextContent('/ru/booking');
    expect(screen.getByTestId('booking-route-state')).toHaveTextContent(JSON.stringify({
      publicBookingResubmit: {
        requestId: pendingRequest.id,
        expectedVersion: pendingRequest.version,
        serviceSlug: pendingRequest.service_slug,
        doctorSlug: pendingRequest.doctor_slug,
      },
    }));
    expect(screen.getByTestId('booking-route')).not.toHaveTextContent(/request|doctor|cardiology/i);
  });

  it('distinguishes requests for the same time and keeps each resubmit action on its request', async () => {
    const firstRequest = { ...pendingRequest, status: 'needs_new_time' as const };
    const secondRequest = {
      ...pendingRequest,
      id: '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ac',
      service_slug: 'dentistry',
      doctor_slug: 'doctor-two',
      status: 'needs_new_time' as const,
    };
    listRequests.mockResolvedValueOnce([firstRequest, secondRequest]);
    const RouteProbe = () => {
      const location = useLocation();
      return <output data-testid="booking-route-state">{JSON.stringify(location.state)}</output>;
    };
    render(
      <MemoryRouter initialEntries={['/patient/home']}>
        <RouteProbe />
        <PublicBookingRequestsPanel />
      </MemoryRouter>,
    );

    const cards = await screen.findAllByTestId('patient-booking-request');
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText('publicBookingRequests.serviceCode: cardiology')).toBeInTheDocument();
    expect(within(cards[0]).getByText('publicBookingRequests.doctorCode: doctor-one')).toBeInTheDocument();
    expect(within(cards[1]).getByText('publicBookingRequests.serviceCode: dentistry')).toBeInTheDocument();
    expect(within(cards[1]).getByText('publicBookingRequests.doctorCode: doctor-two')).toBeInTheDocument();

    fireEvent.click(within(cards[0]).getByRole('link', {
      name: 'publicBookingRequests.chooseAnotherTime',
    }));
    expect(screen.getByTestId('booking-route-state')).toHaveTextContent(JSON.stringify({
      publicBookingResubmit: {
        requestId: firstRequest.id,
        expectedVersion: firstRequest.version,
        serviceSlug: firstRequest.service_slug,
        doctorSlug: firstRequest.doctor_slug,
      },
    }));

    fireEvent.click(within(cards[1]).getByRole('link', {
      name: 'publicBookingRequests.chooseAnotherTime',
    }));
    expect(screen.getByTestId('booking-route-state')).toHaveTextContent(JSON.stringify({
      publicBookingResubmit: {
        requestId: secondRequest.id,
        expectedVersion: secondRequest.version,
        serviceSlug: secondRequest.service_slug,
        doctorSlug: secondRequest.doctor_slug,
      },
    }));
  });

  it('offers retry after the request list fails to load', async () => {
    listRequests.mockRejectedValueOnce(new Error('offline'));
    render(<PublicBookingRequestsPanel />);

    expect(await screen.findByRole('alert')).toHaveTextContent('publicBookingRequests.loadError');
    listRequests.mockResolvedValueOnce([]);
    fireEvent.click(screen.getByRole('button', { name: 'publicBookingRequests.retry' }));
    expect(await screen.findByText('publicBookingRequests.empty')).toBeInTheDocument();
  });
});
