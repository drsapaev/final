/**
 * REG-FE-040/041 (#3820, registrar audit ledger PR #3803) — fail-first:
 * the reschedule dialog must reset its fields on every close and must
 * reschedule exactly ONE explicitly selected visit of a grouped row.
 *
 * REG-FE-040 (state leak): `customRescheduleDate`/`customRescheduleTime`
 * were reset only after a CONFIRMED submit. Closing the modal via Escape /
 * backdrop / cancel kept the previous patient's chosen date and time, which
 * then leaked into the next patient's dialog.
 *
 * REG-FE-041 (silent first pick): for an aggregated row
 * (`visit_ids=[101,102]`) the dialog silently POSTed `visit_ids[0]` while
 * the view removed the whole group — implying the entire group moved. The
 * dialog must require an explicit target-visit choice and POST exactly the
 * selected visit id.
 *
 * ModernDialog is mocked so every close path (Escape, backdrop, X) is
 * simulated by invoking the onClose prop, exactly like the real component
 * does.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RescheduleSlotsDialog from '../RescheduleSlots';
import { rescheduleTomorrow, rescheduleVisit } from '../../../../api/visits';

vi.mock('../../../../api/visits', () => ({
  rescheduleTomorrow: vi.fn(),
  rescheduleVisit: vi.fn(),
}));
vi.mock('../../../../services/notify', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));
vi.mock('../../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), log: vi.fn() },
}));
vi.mock('../../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key, language: 'ru', availableLanguages: [] }),
}));
vi.mock('../../../../components/dialogs/ModernDialog', () => ({
  default: ({ isOpen, onClose, actions, children }: {
    isOpen: boolean;
    onClose: () => void;
    actions: Array<{ label: string; onClick: () => void }>;
    children: React.ReactNode;
  }) =>
    isOpen ? (
      <div data-testid="modern-dialog">
        <button type="button" aria-label="dialog-close" onClick={onClose}>×</button>
        <div data-testid="dialog-body">{children}</div>
        {actions.map((action) => (
          <button key={action.label} type="button" onClick={action.onClick}>{action.label}</button>
        ))}
      </div>
    ) : null,
}));

import notify from '../../../../services/notify';

const tI18n = (key: string, options?: Record<string, unknown>) =>
  options && 'id' in options ? `Визит #${String(options.id)}` : key;

const GROUP_ROW = {
  id: 101,
  visit_id: 101,
  visit_ids: [101, 102],
  patient_fio: 'SYNTHETIC Patient A',
};

const SOLO_ROW = {
  id: 201,
  visit_id: 201,
  patient_fio: 'SYNTHETIC Patient B',
};

type DialogProps = React.ComponentProps<typeof RescheduleSlotsDialog>;

type Props = Partial<DialogProps>;

const makeProps = (overrides: Props = {}): DialogProps => ({
  isOpen: true,
  rescheduleData: GROUP_ROW,
  onClose: vi.fn(),
  confirm: vi.fn(async () => true),
  resolveRescheduleVisitId: (row: Record<string, unknown>) =>
    (row.visit_ids as unknown[] | undefined)?.[0] || row.visit_id || row.visitId || null,
  getRescheduleVisitIds: (row: Record<string, unknown>) => {
    const visitIds = Array.isArray(row?.visit_ids)
      ? (row.visit_ids as unknown[]).filter((id) => id !== null && id !== undefined && id !== '')
      : [];
    if (visitIds.length > 0) return visitIds;
    const single = row?.visit_id ?? row?.visitId ?? null;
    return single !== null && single !== undefined ? [single] : [];
  },
  removeRescheduledAppointmentFromView: vi.fn(),
  loadAppointments: vi.fn(),
  tI18n,
  ...overrides,
});

const dateInput = () => screen.getByLabelText('registrarPanel.rp_aria_reschedule_date') as HTMLInputElement;
const timeInput = () => screen.getByLabelText('registrarPanel.rp_aria_reschedule_time') as HTMLInputElement;
const visitSelect = () => screen.getByLabelText('registrar.reschedule_select_visit_label') as HTMLSelectElement;
const selectDateButton = () => screen.getByRole('button', { name: 'registrarPanel.select_date' });
const tomorrowButton = () => screen.getByRole('button', { name: /registrarPanel\.tomorrow/ });

describe('RescheduleSlotsDialog — REG-FE-040/041 (fail-first)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(rescheduleVisit).mockResolvedValue({} as never);
    vi.mocked(rescheduleTomorrow).mockResolvedValue({} as never);
  });

  it('REG-FE-040: resets date/time on every close path (Escape/backdrop/cancel), not only after submit', () => {
    const onCloseA = vi.fn();
    const { rerender } = render(<RescheduleSlotsDialog {...makeProps({ onClose: onCloseA })} />);

    // Patient A picks a date and a time, then closes the modal WITHOUT
    // submitting (Escape/backdrop/X all route through the onClose prop).
    fireEvent.change(dateInput(), { target: { value: '2999-01-01' } });
    fireEvent.change(timeInput(), { target: { value: '10:30' } });
    fireEvent.click(screen.getByRole('button', { name: 'dialog-close' }));
    expect(onCloseA).toHaveBeenCalledTimes(1);

    // The same mounted dialog is reopened for a DIFFERENT patient — the
    // previous patient's date/time must not leak into it.
    rerender(<RescheduleSlotsDialog {...makeProps({ rescheduleData: SOLO_ROW, onClose: vi.fn() })} />);
    expect(dateInput().value).toBe('');
    expect(timeInput().value).toBe('');
  });

  it('REG-FE-041: renders an explicit target-visit selector for a grouped row (visit_ids=[101,102])', () => {
    // Grouped row → the selector is rendered; solo row → no selector.
    const { rerender } = render(<RescheduleSlotsDialog {...makeProps()} />);
    expect(visitSelect()).toBeInTheDocument();
    rerender(<RescheduleSlotsDialog {...makeProps({ rescheduleData: SOLO_ROW })} />);
    expect(screen.queryByLabelText('registrar.reschedule_select_visit_label')).not.toBeInTheDocument();
  });

  it('REG-FE-041: does not silently POST visit_ids[0] — an explicit choice is required', async () => {
    const onClose = vi.fn();
    render(<RescheduleSlotsDialog {...makeProps({ onClose })} />);
    fireEvent.change(dateInput(), { target: { value: '2999-01-01' } });

    // No visit selected → the confirm dialog is fine, but the command must
    // not fire, the dialog must stay open and an explicit error is shown.
    await act(async () => {
      fireEvent.click(selectDateButton());
    });

    expect(rescheduleVisit).not.toHaveBeenCalled();
    expect(notify.error).toHaveBeenCalledWith('registrar.reschedule_select_visit_required');
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByTestId('modern-dialog')).toBeInTheDocument();
  });

  it('REG-FE-041: POSTs exactly the selected visit id (102, not the silent visit_ids[0]=101)', async () => {
    const onClose = vi.fn();
    const removeFn = vi.fn();
    const loadFn = vi.fn();
    render(<RescheduleSlotsDialog {...makeProps({
      onClose, removeRescheduledAppointmentFromView: removeFn, loadAppointments: loadFn,
    })} />);

    fireEvent.change(visitSelect(), { target: { value: '102' } });
    fireEvent.change(dateInput(), { target: { value: '2999-01-01' } });
    fireEvent.change(timeInput(), { target: { value: '10:30' } });

    await act(async () => {
      fireEvent.click(selectDateButton());
    });

    expect(rescheduleVisit).toHaveBeenCalledTimes(1);
    expect(rescheduleVisit).toHaveBeenCalledWith(102, '2999-01-01', '10:30');
    expect(removeFn).toHaveBeenCalledWith(GROUP_ROW, 102);
    expect(onClose).toHaveBeenCalled();
    await waitFor(() => expect(loadFn).toHaveBeenCalled());
  });

  it('REG-FE-041: "tomorrow" quick action also POSTs the selected visit of a group', async () => {
    render(<RescheduleSlotsDialog {...makeProps()} />);
    fireEvent.change(visitSelect(), { target: { value: '102' } });

    await act(async () => {
      fireEvent.click(tomorrowButton());
    });

    expect(rescheduleTomorrow).toHaveBeenCalledTimes(1);
    expect(rescheduleTomorrow).toHaveBeenCalledWith(102);
    expect(rescheduleVisit).not.toHaveBeenCalled();
  });

  it('single-visit row: no selector, POSTs that visit id (regression pin)', async () => {
    const removeFn = vi.fn();
    render(<RescheduleSlotsDialog {...makeProps({
      rescheduleData: SOLO_ROW, removeRescheduledAppointmentFromView: removeFn,
    })} />);
    fireEvent.change(dateInput(), { target: { value: '2999-01-01' } });

    await act(async () => {
      fireEvent.click(selectDateButton());
    });

    expect(rescheduleVisit).toHaveBeenCalledWith(201, '2999-01-01', undefined);
    expect(removeFn).toHaveBeenCalledWith(SOLO_ROW, 201);
  });

  it('failed command does not claim success and does not remove records', async () => {
    vi.mocked(rescheduleVisit).mockRejectedValue(new Error('SYNTHETIC network failure'));
    const removeFn = vi.fn();
    render(<RescheduleSlotsDialog {...makeProps({
      rescheduleData: SOLO_ROW, removeRescheduledAppointmentFromView: removeFn,
    })} />);
    fireEvent.change(dateInput(), { target: { value: '2999-01-01' } });

    await act(async () => {
      fireEvent.click(selectDateButton());
    });

    expect(notify.error).toHaveBeenCalled();
    expect(notify.success).not.toHaveBeenCalled();
    expect(removeFn).not.toHaveBeenCalled();
  });
});
