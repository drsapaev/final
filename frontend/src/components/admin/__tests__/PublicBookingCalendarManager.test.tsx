import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import PublicBookingCalendarManager from '../PublicBookingCalendarManager';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  confirm: vi.fn(),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('../../../api/adminBookingCalendar', () => ({
  getPublicBookingCalendar: mocks.get,
  updatePublicBookingCalendar: mocks.update,
  confirmPublicBookingCalendar: mocks.confirm,
}));

vi.mock('../../ui/macos', () => ({
  Alert: ({ title, message }: { title: string; message: string }) => (
    <div role="alert">{title}: {message}</div>
  ),
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  Button: ({
    children,
    disabled,
    loading,
    onClick,
  }: {
    children: React.ReactNode;
    disabled?: boolean;
    loading?: boolean;
    onClick?: () => void;
  }) => (
    <button type="button" disabled={disabled || loading} onClick={onClick}>{children}</button>
  ),
  Card: ({ children }: { children: React.ReactNode }) => <section>{children}</section>,
  Checkbox: ({
    checked,
    onChange,
    label,
    description,
    disabled,
    ...props
  }: {
    checked: boolean;
    onChange: (checked: boolean) => void;
    label: string;
    description?: string;
    disabled?: boolean;
    'aria-label'?: string;
  }) => (
    <label>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.currentTarget.checked)}
        disabled={disabled}
        aria-label={props['aria-label']}
      />
      {label}
      {description && <span>{description}</span>}
    </label>
  ),
  Input: (props: React.ComponentProps<'input'>) => <input {...props} />,
}));

function emptyCalendar(year: number, version = 0) {
  return {
    year,
    version,
    is_confirmed: false,
    holidays: [],
    confirmed_at: null,
    confirmed_by: null,
    updated_at: null,
    updated_by: null,
  };
}

function currentClinicYear(): number {
  return Number(new Intl.DateTimeFormat('en', {
    year: 'numeric',
    timeZone: 'Asia/Tashkent',
  }).format(new Date()));
}

describe('PublicBookingCalendarManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const year = currentClinicYear();
    mocks.get.mockResolvedValue(emptyCalendar(year));
    mocks.update.mockImplementation(async (_year, update) => ({
      ...emptyCalendar(year, update.expected_version + 1),
      holidays: update.holidays,
    }));
    mocks.confirm.mockImplementation(async (_year, body) => ({
      ...emptyCalendar(year, body.expected_version + 1),
      is_confirmed: true,
      confirmed_at: '2026-10-24T12:00:00Z',
      confirmed_by: 7,
    }));
  });

  afterEach(() => cleanup());

  it('saves official holidays and requires a separate completeness confirmation', async () => {
    const year = currentClinicYear();
    mocks.confirm.mockResolvedValueOnce({
      ...emptyCalendar(year, 2),
      is_confirmed: true,
      holidays: [{ date: `${year}-01-01`, is_working_day: false }],
      confirmed_at: '2026-10-24T12:00:00Z',
      confirmed_by: 7,
    });
    render(<PublicBookingCalendarManager />);

    await screen.findByText('admin2.pbc_status_closed');
    fireEvent.change(screen.getByLabelText('admin2.pbc_date_label'), {
      target: { value: `${year}-01-01` },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.pbc_add_date' }));
    fireEvent.click(screen.getByRole('button', { name: 'admin2.pbc_save' }));

    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(year, {
      expected_version: 0,
      holidays: [{ date: `${year}-01-01`, is_working_day: false }],
    }));
    expect(mocks.confirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('checkbox', { name: 'admin2.pbc_confirm_reviewed' }));
    fireEvent.click(screen.getByRole('button', { name: 'admin2.pbc_confirm_year' }));

    await waitFor(() => expect(mocks.confirm).toHaveBeenCalledWith(year, {
      expected_version: 1,
    }));
    expect(await screen.findByText('admin2.pbc_status_confirmed')).toBeInTheDocument();
  });

  it('offers a retry when the calendar cannot be loaded', async () => {
    const year = currentClinicYear();
    mocks.get.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(emptyCalendar(year));
    render(<PublicBookingCalendarManager />);

    fireEvent.click(await screen.findByRole('button', { name: 'admin2.pbc_retry_load' }));

    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('admin2.pbc_status_closed')).toBeInTheDocument();
  });

  it('shows that editing a confirmed calendar will require confirmation again', async () => {
    const year = currentClinicYear();
    mocks.get.mockResolvedValueOnce({
      ...emptyCalendar(year, 2),
      is_confirmed: true,
      holidays: [{ date: `${year}-01-01`, is_working_day: false }],
      confirmed_at: '2026-10-24T12:00:00Z',
      confirmed_by: 7,
    });
    render(<PublicBookingCalendarManager />);

    await screen.findByText('admin2.pbc_status_confirmed');
    fireEvent.change(screen.getByLabelText('admin2.pbc_date_label'), {
      target: { value: `${year}-01-02` },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.pbc_add_date' }));

    expect(screen.getByText('admin2.pbc_status_unsaved')).toBeInTheDocument();
    expect(screen.getByText('admin2.pbc_reconfirm_after_save')).toBeInTheDocument();
    expect(screen.queryByText('admin2.pbc_status_confirmed')).not.toBeInTheDocument();
  });
});
