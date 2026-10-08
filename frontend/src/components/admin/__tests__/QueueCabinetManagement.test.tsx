import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api, apiRequest } from '../../../api/client';
import QueueCabinetManagement from '../QueueCabinetManagement';

const modalTestMode = vi.hoisted(() => ({ useRealModal: false }));

vi.mock('../../../api/client', () => ({
  apiRequest: vi.fn(),
  api: { request: vi.fn() },
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

vi.mock('@/contexts/ThemeContext', () => ({ useTheme: () => ({}) }));

vi.mock('../../ui/macos', async () => {
  const RealModal = (await vi.importActual<typeof import('../../ui/macos/Modal')>(
    '../../ui/macos/Modal',
  )).default;

  return ({
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
  Modal: (props: React.PropsWithChildren<Record<string, any>>) => {
    if (modalTestMode.useRealModal) return React.createElement(RealModal, props);
    const { isOpen, title, children, actions } = props;
    return isOpen ? (
      <section role="dialog" aria-modal="true">
        <h2>{title}</h2>
        {children}
        {actions}
      </section>
    ) : null;
  },
  Select: ({ id, label, value, options, onValueChange, disabled }: Record<string, any>) => (
    <label htmlFor={id}>
      {label}
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => onValueChange?.(event.target.value)}
      >
        {options.map((option: { value: string; label: string }) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  ),
  StatCard: ({ title, value }: Record<string, any>) => (
    <div data-testid="stat-card">
      <span>{title}</span>
      <output>{value}</output>
    </div>
  ),
  });
});

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
const apiClientRequestMock = vi.mocked(api.request);
const uncertainRetryRefusals = [
  {
    label: 'CSRF 403',
    detail: 'CSRF validation failed',
    rejection: {
      response: {
        status: 403,
        headers: { 'x-csrf-status': 'rejected' },
        data: { detail: 'CSRF validation failed', reason: 'missing_cookie' },
      },
    },
  },
  {
    label: 'principal lookup 403',
    detail: 'Пользователь деактивирован или сессия недействительна',
    rejection: {
      response: {
        status: 403,
        data: { detail: 'Пользователь деактивирован или сессия недействительна' },
      },
    },
  },
  {
    label: 'stale state 409',
    detail: 'Synthetic stale queue state',
    rejection: {
      response: {
        status: 409,
        data: { detail: 'Synthetic stale queue state' },
      },
    },
  },
] as const;

describe('QueueCabinetManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    modalTestMode.useRealModal = false;
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
    expect(screen.getByRole('button', { name: 'admin2.qcm_reassign' })).toBeInTheDocument();
    expect(apiRequestMock).toHaveBeenCalledTimes(1);
  });

  it('previews the typed owner snapshot and applies once with the required replay key', async () => {
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 4,
          day: '2026-10-06',
          owner_type: 'resource',
          owner_id: 31,
          owner_name: 'Laboratory',
          owner_default_cabinet: '7',
          queue_tag: 'lab',
          cabinet_number: '8',
          entries_count: 3,
          active: true,
        },
      ])
      .mockResolvedValueOnce({
        clinic_day: '2026-10-06',
        can_apply: true,
        items: [
          {
            queue_id: 4,
            owner_type: 'resource',
            owner_id: 31,
            owner_name: 'Laboratory',
            old_cabinet_number: '8',
            new_cabinet_number: '9',
            waiting_count: 2,
            blocking_reasons: [],
            can_apply: true,
          },
        ],
      });
    apiClientRequestMock
      .mockRejectedValueOnce(new Error('synthetic lost response'))
      .mockResolvedValueOnce({ data: { changed_queue_ids: [4] } });

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    fireEvent.change(screen.getByLabelText('admin2.qcm_new_cabinet'), {
      target: { value: '9' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));

    expect(await screen.findByText('admin2.qcm_preview_result')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_confirm_reassign' }));
    expect(await screen.findByText('admin2.qcm_uncertain_outcome')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' }));

    await waitFor(() => expect(apiClientRequestMock).toHaveBeenCalledTimes(2));
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      'POST',
      '/admin/queues/cabinet-info/preview',
      expect.objectContaining({
        data: { queue_ids: [4], new_cabinet_number: '9' },
      }),
    );
    const applyConfig = apiClientRequestMock.mock.calls[0][0];
    expect(applyConfig).toMatchObject({
      method: 'POST',
      url: '/admin/queues/cabinet-info/apply',
      data: {
        targets: [
          {
            queue_id: 4,
            expected_owner_type: 'resource',
            expected_owner_id: 31,
            expected_cabinet_number: '8',
          },
        ],
        new_cabinet_number: '9',
        reason_code: 'administrative_correction',
      },
      headers: { 'Idempotency-Key': expect.any(String) },
    });
    expect(apiClientRequestMock.mock.calls[1][0]).toEqual(applyConfig);
  });

  it('ignores a preview response after its cabinet draft changes', async () => {
    let resolvePreview: ((value: unknown) => void) | undefined;
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 4,
          day: '2026-10-06',
          owner_type: 'resource',
          owner_id: 31,
          owner_name: 'Laboratory',
          cabinet_number: '8',
          entries_count: 0,
          active: true,
        },
      ])
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolvePreview = resolve;
          }),
      );

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    const cabinetInput = screen.getByLabelText('admin2.qcm_new_cabinet');
    fireEvent.change(cabinetInput, { target: { value: '9' } });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));
    fireEvent.change(cabinetInput, { target: { value: '10' } });

    await act(async () => {
      resolvePreview?.({
        clinic_day: '2026-10-06',
        can_apply: true,
        items: [
          {
            queue_id: 4,
            owner_type: 'resource',
            owner_id: 31,
            owner_name: 'Laboratory',
            old_cabinet_number: '8',
            new_cabinet_number: '9',
            waiting_count: 0,
            blocking_reasons: [],
            can_apply: true,
          },
        ],
      });
    });

    expect(cabinetInput).toHaveValue('10');
    expect(screen.queryByRole('button', { name: 'admin2.qcm_confirm_reassign' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' })).toBeEnabled();
    expect(apiClientRequestMock).not.toHaveBeenCalled();
  });

  it('keeps keyboard focus in the cabinet input while editing with the real modal', async () => {
    modalTestMode.useRealModal = true;
    apiRequestMock.mockResolvedValueOnce([
      {
        id: 4,
        day: '2026-10-06',
        owner_type: 'resource',
        owner_id: 31,
        owner_name: 'Laboratory',
        cabinet_number: '8',
        entries_count: 0,
        active: true,
      },
    ]);

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 40));
    });
    const cabinetInput = screen.getByLabelText('admin2.qcm_new_cabinet');
    cabinetInput.focus();
    expect(cabinetInput).toHaveFocus();

    fireEvent.change(cabinetInput, { target: { value: '9' } });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 40));
    });

    expect(cabinetInput).toHaveFocus();
  });

  it('keeps the reassignment reason reachable in the real modal keyboard path', async () => {
    modalTestMode.useRealModal = true;
    const originalOffsetParent = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      'offsetParent',
    );
    Object.defineProperty(HTMLElement.prototype, 'offsetParent', {
      configurable: true,
      get() { return this.parentElement; },
    });

    try {
      apiRequestMock.mockResolvedValueOnce([
        {
          id: 4,
          day: '2026-10-06',
          owner_type: 'resource',
          owner_id: 31,
          owner_name: 'Synthetic resource',
          cabinet_number: '8',
          entries_count: 0,
          active: true,
        },
      ]);

      const user = userEvent.setup();
      render(<QueueCabinetManagement />);
      fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 40));
      });

      const reasonSelect = screen.getByRole('combobox', { name: 'admin2.qcm_reason' });
      const cabinetInput = screen.getByLabelText('admin2.qcm_new_cabinet');
      cabinetInput.focus();
      expect(cabinetInput).toHaveFocus();
      await user.tab();
      expect(reasonSelect).toHaveFocus();
      await user.selectOptions(reasonSelect, 'room_unavailable');
      expect(reasonSelect).toHaveValue('room_unavailable');
    } finally {
      if (originalOffsetParent) {
        Object.defineProperty(HTMLElement.prototype, 'offsetParent', originalOffsetParent);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, 'offsetParent');
      }
    }
  });

  it('shows the server clinic-day refusal from preview without enabling apply', async () => {
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 5,
          day: '2026-10-05',
          owner_type: 'doctor',
          owner_id: 12,
          owner_name: 'Doctor',
          cabinet_number: '5',
          entries_count: 0,
          active: true,
        },
      ])
      .mockRejectedValueOnce('Preview is only available for clinic today');

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Preview is only available for clinic today',
    );
    expect(screen.queryByRole('button', { name: 'admin2.qcm_confirm_reassign' })).not.toBeInTheDocument();
    expect(apiClientRequestMock).not.toHaveBeenCalled();
  });

  it('reuses the same key when the server reports that the apply is still in flight', async () => {
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 6,
          day: '2026-10-06',
          owner_type: 'doctor',
          owner_id: 12,
          owner_name: 'Doctor',
          cabinet_number: '5',
          entries_count: 0,
          active: true,
        },
      ])
      .mockResolvedValueOnce({
        clinic_day: '2026-10-06',
        can_apply: true,
        items: [
          {
            queue_id: 6,
            owner_type: 'doctor',
            owner_id: 12,
            owner_name: 'Doctor',
            old_cabinet_number: '5',
            new_cabinet_number: '9',
            waiting_count: 0,
            blocking_reasons: [],
            can_apply: true,
          },
        ],
      });
    apiClientRequestMock
      .mockRejectedValueOnce({
        response: {
          status: 409,
          data: {
            code: 'idempotency_in_flight',
            detail: 'Request with this Idempotency-Key is still being processed.',
          },
        },
      })
      .mockResolvedValueOnce({ data: { changed_queue_ids: [6] } });

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    fireEvent.change(screen.getByLabelText('admin2.qcm_new_cabinet'), {
      target: { value: '9' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_confirm_reassign' }));

    expect(await screen.findByText('admin2.qcm_apply_in_flight')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' }));

    await waitFor(() => expect(apiClientRequestMock).toHaveBeenCalledTimes(2));
    expect(apiClientRequestMock.mock.calls[1][0]).toEqual(
      apiClientRequestMock.mock.calls[0][0],
    );
  });

  it('keeps the same-key retry available when a cooldown 429 follows a lost response', async () => {
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 8,
          day: '2026-10-06',
          owner_type: 'doctor',
          owner_id: 14,
          owner_name: 'Doctor',
          cabinet_number: '5',
          entries_count: 0,
          active: true,
        },
      ])
      .mockResolvedValueOnce({
        clinic_day: '2026-10-06',
        can_apply: true,
        items: [
          {
            queue_id: 8,
            owner_type: 'doctor',
            owner_id: 14,
            owner_name: 'Doctor',
            old_cabinet_number: '5',
            new_cabinet_number: '9',
            waiting_count: 0,
            blocking_reasons: [],
            can_apply: true,
          },
        ],
      })
      .mockResolvedValueOnce([]);
    apiClientRequestMock
      .mockRejectedValueOnce(new Error('synthetic response loss'))
      .mockRejectedValueOnce({
        response: {
          status: 429,
          data: { detail: 'Synthetic client cooldown; retry was not sent' },
        },
      })
      .mockResolvedValueOnce({ data: { changed_queue_ids: [8] } });

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    fireEvent.change(screen.getByLabelText('admin2.qcm_new_cabinet'), {
      target: { value: '9' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_confirm_reassign' }));

    expect(await screen.findByText('admin2.qcm_uncertain_outcome')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' }));
    expect(await screen.findByText('Synthetic client cooldown; retry was not sent')).toBeInTheDocument();

    expect(screen.getByLabelText('admin2.qcm_new_cabinet')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'admin2.qcm_cancel' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' }));

    await waitFor(() => expect(apiClientRequestMock).toHaveBeenCalledTimes(3));
    expect(apiClientRequestMock.mock.calls[2][0]).toEqual(
      apiClientRequestMock.mock.calls[0][0],
    );
  });

  it.each(uncertainRetryRefusals)(
    'keeps the same-key retry available when $label follows a lost response',
    async ({ rejection, detail }) => {
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 9,
          day: '2026-10-06',
          owner_type: 'doctor',
          owner_id: 15,
          owner_name: 'Doctor',
          cabinet_number: '5',
          entries_count: 0,
          active: true,
        },
      ])
      .mockResolvedValueOnce({
        clinic_day: '2026-10-06',
        can_apply: true,
        items: [
          {
            queue_id: 9,
            owner_type: 'doctor',
            owner_id: 15,
            owner_name: 'Doctor',
            old_cabinet_number: '5',
            new_cabinet_number: '9',
            waiting_count: 0,
            blocking_reasons: [],
            can_apply: true,
          },
        ],
      })
      .mockResolvedValueOnce([]);
    apiClientRequestMock
      .mockRejectedValueOnce(new Error('synthetic response loss'))
      .mockRejectedValueOnce(rejection)
      .mockResolvedValueOnce({ data: { changed_queue_ids: [9] } });

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    fireEvent.change(screen.getByLabelText('admin2.qcm_new_cabinet'), {
      target: { value: '9' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_confirm_reassign' }));

    expect(await screen.findByText('admin2.qcm_uncertain_outcome')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' }));
    expect(await screen.findByText(detail)).toBeInTheDocument();

    expect(screen.getByLabelText('admin2.qcm_new_cabinet')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'admin2.qcm_cancel' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' }));

    await waitFor(() => expect(apiClientRequestMock).toHaveBeenCalledTimes(3));
    expect(apiClientRequestMock.mock.calls[2][0]).toEqual(
      apiClientRequestMock.mock.calls[0][0],
    );
    },
  );

  it('reads the authoritative queue state and confirms the requested cabinet after an uncertain outcome', async () => {
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 18,
          day: '2026-10-06',
          owner_type: 'resource',
          owner_id: 31,
          owner_name: 'Synthetic resource',
          cabinet_number: '8',
          entries_count: 0,
          active: true,
        },
      ])
      .mockResolvedValueOnce({
        clinic_day: '2026-10-06',
        can_apply: true,
        items: [
          {
            queue_id: 18,
            owner_type: 'resource',
            owner_id: 31,
            owner_name: 'Synthetic resource',
            old_cabinet_number: '8',
            new_cabinet_number: '9',
            waiting_count: 0,
            blocking_reasons: [],
            can_apply: true,
          },
        ],
      })
      .mockResolvedValueOnce({
        id: 18,
        day: '2026-10-06',
        owner_type: 'resource',
        owner_id: 31,
        owner_name: 'Synthetic resource',
        cabinet_number: '9',
        entries_count: 0,
        active: true,
      })
      .mockResolvedValueOnce([
        {
          id: 18,
          day: '2026-10-06',
          owner_type: 'resource',
          owner_id: 31,
          owner_name: 'Synthetic resource',
          cabinet_number: '9',
          entries_count: 0,
          active: true,
        },
      ]);
    apiClientRequestMock
      .mockRejectedValueOnce(new Error('synthetic response loss'))
      .mockRejectedValueOnce({
        response: {
          status: 409,
          data: {
            code: 'idempotency_uncertain_outcome',
            detail: 'Previous outcome is unknown; inspect the current queue state.',
          },
        },
      });

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    fireEvent.change(screen.getByLabelText('admin2.qcm_new_cabinet'), {
      target: { value: '9' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_confirm_reassign' }));
    expect(await screen.findByText('admin2.qcm_uncertain_outcome')).toBeInTheDocument();

    const originalApply = apiClientRequestMock.mock.calls[0][0];
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_retry_apply' }));
    expect(await screen.findByText('Previous outcome is unknown; inspect the current queue state.')).toBeInTheDocument();
    expect(apiClientRequestMock.mock.calls[1][0]).toEqual(originalApply);
    expect(screen.queryByRole('button', { name: 'admin2.qcm_retry_apply' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_check_result' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      3,
      'GET',
      '/admin/queues/18/cabinet-info',
    );
    expect(await screen.findByText('9')).toBeInTheDocument();
  });

  it('requires a fresh preview before issuing a new key when reconciliation still shows the old cabinet', async () => {
    const preview = (cabinet: string) => ({
      clinic_day: '2026-10-06',
      can_apply: true,
      items: [
        {
          queue_id: 19,
          owner_type: 'doctor' as const,
          owner_id: 12,
          owner_name: 'Synthetic doctor',
          old_cabinet_number: cabinet,
          new_cabinet_number: '9',
          waiting_count: 0,
          blocking_reasons: [],
          can_apply: true,
        },
      ],
    });
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 19,
          day: '2026-10-06',
          owner_type: 'doctor',
          owner_id: 12,
          owner_name: 'Synthetic doctor',
          cabinet_number: '8',
          entries_count: 0,
          active: true,
        },
      ])
      .mockResolvedValueOnce(preview('8'))
      .mockResolvedValueOnce({
        id: 19,
        day: '2026-10-06',
        owner_type: 'doctor',
        owner_id: 12,
        owner_name: 'Synthetic doctor',
        cabinet_number: '8',
        entries_count: 0,
        active: true,
      })
      .mockResolvedValueOnce(preview('8'));
    apiClientRequestMock
      .mockRejectedValueOnce(new Error('synthetic response loss'))
      .mockRejectedValueOnce({
        response: {
          status: 409,
          data: { code: 'idempotency_uncertain_outcome', detail: 'Outcome needs reconciliation.' },
        },
      })
      .mockResolvedValueOnce({ data: { changed_queue_ids: [19] } });

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    fireEvent.change(screen.getByLabelText('admin2.qcm_new_cabinet'), {
      target: { value: '9' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_confirm_reassign' }));
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_retry_apply' }));

    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_check_result' }));
    expect(await screen.findByText('admin2.qcm_reconcile_observed')).toHaveAttribute('role', 'status');
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_new_attempt' }));

    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledTimes(4));
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      4,
      'POST',
      '/admin/queues/cabinet-info/preview',
      expect.objectContaining({ data: { queue_ids: [19], new_cabinet_number: '9' } }),
    );
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_confirm_reassign' }));

    await waitFor(() => expect(apiClientRequestMock).toHaveBeenCalledTimes(3));
    const initialRequest = apiClientRequestMock.mock.calls[0]?.[0];
    const freshRequest = apiClientRequestMock.mock.calls[2]?.[0];
    const initialKey = initialRequest?.headers?.['Idempotency-Key'];
    const freshKey = freshRequest?.headers?.['Idempotency-Key'];
    expect(initialKey).toBeTruthy();
    expect(freshKey).toBeTruthy();
    expect(freshKey).not.toBe(initialKey);
  });

  it('allows correcting the draft after a definitive first-apply refusal', async () => {
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 10,
          day: '2026-10-06',
          owner_type: 'doctor',
          owner_id: 16,
          owner_name: 'Doctor',
          cabinet_number: '5',
          entries_count: 0,
          active: true,
        },
      ])
      .mockResolvedValueOnce({
        clinic_day: '2026-10-06',
        can_apply: true,
        items: [
          {
            queue_id: 10,
            owner_type: 'doctor',
            owner_id: 16,
            owner_name: 'Doctor',
            old_cabinet_number: '5',
            new_cabinet_number: '9',
            waiting_count: 0,
            blocking_reasons: [],
            can_apply: true,
          },
        ],
      })
      .mockResolvedValueOnce({
        clinic_day: '2026-10-06',
        can_apply: true,
        items: [
          {
            queue_id: 10,
            owner_type: 'doctor',
            owner_id: 16,
            owner_name: 'Doctor',
            old_cabinet_number: '5',
            new_cabinet_number: '10',
            waiting_count: 0,
            blocking_reasons: [],
            can_apply: true,
          },
        ],
      });
    apiClientRequestMock.mockRejectedValueOnce({
      response: {
        status: 409,
        data: { detail: 'Synthetic stale queue state' },
      },
    });

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    const cabinetInput = screen.getByLabelText('admin2.qcm_new_cabinet');
    fireEvent.change(cabinetInput, { target: { value: '9' } });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_confirm_reassign' }));

    expect(await screen.findByText('Synthetic stale queue state')).toBeInTheDocument();
    expect(cabinetInput).toBeEnabled();
    expect(screen.getByRole('button', { name: 'admin2.qcm_cancel' })).toBeEnabled();
    fireEvent.change(cabinetInput, { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));

    expect(await screen.findByText('admin2.qcm_preview_result')).toBeInTheDocument();
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      3,
      'POST',
      '/admin/queues/cabinet-info/preview',
      expect.objectContaining({ data: { queue_ids: [10], new_cabinet_number: '10' } }),
    );
  });

  it('translates preview blockers and keeps the confirmation disabled', async () => {
    apiRequestMock
      .mockResolvedValueOnce([
        {
          id: 7,
          day: '2026-10-06',
          owner_type: 'doctor',
          owner_id: 13,
          owner_name: 'Doctor',
          cabinet_number: '5',
          entries_count: 1,
          active: true,
        },
      ])
      .mockResolvedValueOnce({
        clinic_day: '2026-10-06',
        can_apply: false,
        items: [
          {
            queue_id: 7,
            owner_type: 'doctor',
            owner_id: 13,
            owner_name: 'Doctor',
            old_cabinet_number: '5',
            new_cabinet_number: '9',
            waiting_count: 0,
            blocking_reasons: ['patient_called', 'clinical_work_in_progress'],
            can_apply: false,
          },
        ],
      });

    render(<QueueCabinetManagement />);
    fireEvent.click(await screen.findByRole('button', { name: 'admin2.qcm_reassign' }));
    fireEvent.change(screen.getByLabelText('admin2.qcm_new_cabinet'), {
      target: { value: '9' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'admin2.qcm_preview_reassign' }));

    expect(await screen.findByText('admin2.qcm_block_patient_called')).toBeInTheDocument();
    expect(screen.getByText('admin2.qcm_block_clinical_work')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'admin2.qcm_confirm_reassign' })).toBeDisabled();
    expect(apiClientRequestMock).not.toHaveBeenCalled();
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
