/**
 * REG-FE-064 / REG-FE-065 (registrar audit ledger 3803) — reschedule
 * dialog truthfulness.
 *
 * 064: the grouped target-visit selector showed only «Визит №<id>» — the
 *      registrar could not tell which visit of a multi-doctor booking is
 *      being moved. Options now carry the per-visit doctor, services and
 *      original date/time from the row's grouped_records (enriched by the
 *      aggregation layer), with row-level fallback.
 * 065: both confirm handlers closed the dialog and reset the form BEFORE
 *      awaiting the API — a rejected reschedule left the user with no
 *      dialog and no entered parameters. Close/reset now happen only after
 *      a successful response; on failure the dialog stays open with the
 *      chosen date/time and selection preserved for an in-place retry.
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../api/visits', () => ({
  rescheduleTomorrow: vi.fn(),
  rescheduleVisit: vi.fn(),
}));
vi.mock('../../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { rescheduleTomorrow, rescheduleVisit } from '../../../api/visits';
import notify from '../../../services/notify';
import RescheduleSlots from '../views/RescheduleSlots';

const tI18n = (key: string, options?: Record<string, unknown>) =>
  options && 'id' in options ? `${key}:${String(options.id)}` : key;

const GROUPED_ROW = {
  id: 55,
  visit_ids: [101, 102],
  grouped_records: [
    {
      record_ref: { record_kind: 'visit', record_id: 101 },
      doctor_name: 'Доктор Один',
      services: [{ name: 'ЭхоКГ' }],
      record_date: '2026-11-03',
      appointment_time: '09:30',
    },
    {
      record_ref: { record_kind: 'visit', record_id: 102 },
      doctor_name: 'Доктор Два',
      services: [{ name: 'Анализ крови' }],
      record_date: '2026-11-03',
      appointment_time: '11:00',
    },
  ],
};

function renderDialog(overrides: Partial<React.ComponentProps<typeof RescheduleSlots>> = {}) {
  const onClose = vi.fn();
  const confirm = vi.fn().mockResolvedValue(true);
  const removeRescheduledAppointmentFromView = vi.fn();
  const loadAppointments = vi.fn();
  render(
    <RescheduleSlots
      isOpen
      rescheduleData={GROUPED_ROW as never}
      onClose={onClose}
      confirm={confirm}
      getRescheduleVisitIds={(row) => (Array.isArray(row.visit_ids) ? row.visit_ids : [])}
      resolveRescheduleVisitId={(row: Record<string, unknown>) => (Array.isArray(row.visit_ids) ? (row.visit_ids as unknown[])[0] : null)}
      removeRescheduledAppointmentFromView={removeRescheduledAppointmentFromView}
      loadAppointments={loadAppointments}
      tI18n={tI18n}
      {...overrides}
    />,
  );
  return { onClose, confirm, removeRescheduledAppointmentFromView, loadAppointments };
}

describe('RescheduleSlots — REG-FE-064 informative visit options', () => {
  beforeEach(() => vi.clearAllMocks());

  it('each grouped visit option shows doctor, service and original date/time next to the id', () => {
    renderDialog();
    const select = screen.getByLabelText('registrar.reschedule_select_visit_label');
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.textContent);
    expect(options.some((text) => text?.includes('101') && text.includes('Доктор Один') && text.includes('ЭхоКГ') && text.includes('09:30'))).toBe(true);
    expect(options.some((text) => text?.includes('102') && text.includes('Доктор Два') && text.includes('Анализ крови') && text.includes('11:00'))).toBe(true);
  });
});

describe('RescheduleSlots — REG-FE-065 close only after server confirmation', () => {
  beforeEach(() => vi.clearAllMocks());

  it('a failed reschedule keeps the dialog open with the entered parameters preserved', async () => {
    vi.mocked(rescheduleVisit).mockRejectedValue(new Error('slot_taken'));
    const { onClose } = renderDialog();

    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: '2026-11-10' } });

    const confirmButton = screen.getByRole('button', { name: /registrarPanel\.select_date/ });
    await act(async () => {
      fireEvent.click(confirmButton);
    });

    await waitFor(() => expect(notify.error).toHaveBeenCalled());
    expect(onClose).not.toHaveBeenCalled();
    // Entered parameters survive for an in-place retry.
    expect((document.querySelector('input[type="date"]') as HTMLInputElement).value).toBe('2026-11-10');
  });

  it('a successful reschedule closes the dialog and resets the form', async () => {
    vi.mocked(rescheduleVisit).mockResolvedValue({ success: true } as never);
    const { onClose } = renderDialog();

    // Grouped row: pick the target visit explicitly (REG-FE-041 guard).
    fireEvent.change(screen.getByLabelText('registrar.reschedule_select_visit_label'), { target: { value: '101' } });
    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: '2026-11-10' } });

    const confirmButton = screen.getByRole('button', { name: /registrarPanel\.select_date/ });
    await act(async () => {
      fireEvent.click(confirmButton);
    });

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(notify.success).toHaveBeenCalled();
  });

  it('a failed tomorrow reschedule keeps the dialog open', async () => {
    vi.mocked(rescheduleTomorrow).mockRejectedValue(new Error('network'));
    const { onClose } = renderDialog();

    const tomorrowButton = screen.getByRole('button', { name: /registrarPanel\.tomorrow/ });
    await act(async () => {
      fireEvent.click(tomorrowButton);
    });

    await waitFor(() => expect(notify.error).toHaveBeenCalled());
    expect(onClose).not.toHaveBeenCalled();
  });
});
