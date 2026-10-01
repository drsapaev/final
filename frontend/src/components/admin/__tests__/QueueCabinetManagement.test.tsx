import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiRequest } from '../../../api/client';
import QueueCabinetManagement from '../QueueCabinetManagement';

vi.mock('../../../api/client', () => ({
  apiRequest: vi.fn(),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
  },
}));

vi.mock('../../ui/macos', () => ({
  AppEmpty: ({ title, description, action }: React.PropsWithChildren<Record<string, any>>) => (
    <section data-testid="empty-state">
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </section>
  ),
  AppError: ({ title, description, action }: Record<string, any>) => (
    <section role="alert">
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </section>
  ),
  Badge: ({ children }: React.PropsWithChildren) => <span>{children}</span>,
  Button: ({ children, onClick, disabled }: React.PropsWithChildren<Record<string, any>>) => (
    <button type="button" onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
  Card: ({ children }: React.PropsWithChildren) => <section>{children}</section>,
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
  StatCard: ({ title, value }: Record<string, any>) => (
    <div data-testid="stat-card">
      <span>{title}</span>
      <output>{value}</output>
    </div>
  ),
}));

vi.mock('../../ui/DataTable', () => ({
  DataTable: ({ data }: { data: Array<Record<string, React.ReactNode>> }) => (
    <div data-testid="queue-table">
      {data.map((row, rowIndex) => (
        <div data-testid="queue-row" key={rowIndex}>
          {Object.entries(row).map(([key, value]) => (
            <span data-cell={key} key={key}>
              {value}
            </span>
          ))}
        </div>
      ))}
    </div>
  ),
}));

const apiRequestMock = vi.mocked(apiRequest);

describe('QueueCabinetManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads one typed owner read and derives the summary from the displayed rows', async () => {
    apiRequestMock.mockResolvedValue([
      {
        id: 4,
        day: '2026-10-01',
        specialist_id: null,
        specialist_name: 'Laboratory',
        owner_type: 'resource',
        owner_id: 31,
        owner_name: 'Laboratory',
        owner_default_cabinet: '7',
        queue_resource_id: 31,
        queue_tag: 'lab',
        cabinet_number: '8',
        effective_cabinet: '8',
        entries_count: 3,
        active: true,
        sync_status: 'resource_owned',
        linked_doctor_found: false,
        doctor_has_cabinet: false,
        integrity_warnings: [],
      },
    ]);

    render(<QueueCabinetManagement />);

    await waitFor(() => {
      expect(screen.getByText('Laboratory')).toBeInTheDocument();
    });
    expect(apiRequestMock).toHaveBeenCalledTimes(1);
    expect(apiRequestMock).toHaveBeenCalledWith(
      'GET',
      '/admin/queues/cabinet-info',
      expect.objectContaining({
        params: expect.objectContaining({ day: undefined }),
      }),
    );
    expect(screen.getByText('admin2.qcm_stat_queues')).toBeInTheDocument();
    expect(screen.getAllByTestId('stat-card')[0]).toHaveTextContent('1');
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(
      screen.getByText(
        (_content, element) => element?.getAttribute('data-cell') === 'cabinet_number',
      ),
    ).toHaveTextContent('admin2.qcm_owner_default_cabinet: 7');
  });

  it('shows a retryable error instead of the empty state when the read fails', async () => {
    apiRequestMock
      .mockRejectedValueOnce(new Error('synthetic read failure'))
      .mockResolvedValueOnce([]);

    render(<QueueCabinetManagement />);

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_retry_load' }));

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
    expect(apiRequestMock).toHaveBeenCalledTimes(2);
  });

  it('ignores a late response for an older filter request', async () => {
    let resolveInitial: ((value: unknown) => void) | undefined;
    let resolveFiltered: ((value: unknown) => void) | undefined;
    apiRequestMock
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveInitial = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFiltered = resolve;
          }),
      );

    render(<QueueCabinetManagement />);

    fireEvent.change(screen.getByLabelText('admin2.qcm_filter_date'), {
      target: { value: '2026-10-02' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_apply' }));

    await act(async () => {
      resolveFiltered?.([
        {
          id: 2,
          day: '2026-10-02',
          owner_type: 'doctor',
          owner_id: 12,
          owner_name: 'Current filter doctor',
          owner_default_cabinet: '5',
          queue_resource_id: null,
          cabinet_number: '5',
          entries_count: 1,
          active: true,
          sync_status: 'synced',
        },
      ]);
    });
    expect(await screen.findByText('Current filter doctor')).toBeInTheDocument();

    await act(async () => {
      resolveInitial?.([
        {
          id: 1,
          day: '2026-10-01',
          owner_type: 'doctor',
          owner_id: 13,
          owner_name: 'Older filter doctor',
          owner_default_cabinet: '6',
          queue_resource_id: null,
          cabinet_number: '6',
          entries_count: 8,
          active: true,
          sync_status: 'synced',
        },
      ]);
    });

    await waitFor(() => {
      expect(screen.queryByText('Older filter doctor')).not.toBeInTheDocument();
      expect(screen.getByText('Current filter doctor')).toBeInTheDocument();
    });
    expect(screen.getAllByTestId('stat-card')[0]).toHaveTextContent('1');
  });
});
