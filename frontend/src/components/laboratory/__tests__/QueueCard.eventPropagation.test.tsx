/**
 * LABQ-FE-003 (audit 3886, ledger group «laboratory queue pagination and
 * card interaction») — fail-first regression for the QueueCard patient-ID
 * disclosure:
 *
 * The card wraps everything in a `role=button` container with
 * onClick/onKeyDown(Enter|Space) opening the appointment. The nested
 * native `<details><summary>` patient-ID disclosure had NO propagation
 * control — clicking the summary (an ID peek) also bubbled into the parent
 * and opened the appointment / switched the active patient context, and
 * Enter/Space with focus on the summary likewise triggered the parent
 * open action.
 *
 * Red-first: on the pre-fix source the summary click/keydown assertions
 * fail (onOpenAppointment is called).
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import QueueCard from '../QueueCard';

const APPOINTMENT = {
  id: 501,
  appointment_id: 40,
  visit_id: 98,
  patient_id: 23,
  patient_fio: 'SYNTHETIC PATIENT A',
  patient_phone: '+998900000007',
  status: 'waiting',
  specialty: 'lab',
  services: ['Общий анализ крови'],
  payment_status: 'paid',
} as Record<string, unknown>;

function renderCard(onOpenAppointment: ReturnType<typeof vi.fn>) {
  return render(
    <QueueCard
      appointment={APPOINTMENT as never}
      isSelected={false}
      onOpenAppointment={onOpenAppointment as never}
    />,
  );
}

describe('LABQ-FE-003 — patient-ID disclosure is a peer interactive region', () => {
  it('clicking the disclosure summary does NOT open the appointment (pre-fix: bubbled into the parent)', () => {
    const onOpenAppointment = vi.fn();
    renderCard(onOpenAppointment);

    const summary = document.querySelector('.lqw-pii-summary') as HTMLElement;
    expect(summary).not.toBeNull();
    fireEvent.click(summary);
    expect(onOpenAppointment).not.toHaveBeenCalled();
  });

  it('Enter/Space with focus on the summary stays a disclosure-only action (pre-fix: parent key handler opened the appointment)', () => {
    const onOpenAppointment = vi.fn();
    renderCard(onOpenAppointment);

    const summary = document.querySelector('.lqw-pii-summary') as HTMLElement;
    expect(summary).not.toBeNull();
    summary.focus();
    fireEvent.keyDown(summary, { key: 'Enter' });
    fireEvent.keyDown(summary, { key: ' ' });
    expect(onOpenAppointment).not.toHaveBeenCalled();
  });

  it('clicking the revealed patient-id value does NOT open the appointment', () => {
    const onOpenAppointment = vi.fn();
    renderCard(onOpenAppointment);

    fireEvent.click(screen.getByText('23'));
    expect(onOpenAppointment).not.toHaveBeenCalled();
  });

  it('control: clicking the rest of the card opens the appointment exactly once', () => {
    const onOpenAppointment = vi.fn();
    renderCard(onOpenAppointment);

    fireEvent.click(screen.getByText('SYNTHETIC PATIENT A'));
    expect(onOpenAppointment).toHaveBeenCalledTimes(1);
    expect(onOpenAppointment).toHaveBeenCalledWith(expect.objectContaining({ patient_id: 23 }));
  });

  it('control: Enter on the card itself opens the appointment exactly once', () => {
    const onOpenAppointment = vi.fn();
    renderCard(onOpenAppointment);

    fireEvent.keyDown(screen.getByRole('button'), { key: 'Enter' });
    expect(onOpenAppointment).toHaveBeenCalledTimes(1);
  });
});
