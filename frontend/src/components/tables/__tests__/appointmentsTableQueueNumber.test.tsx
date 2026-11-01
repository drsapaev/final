/**
 * REG-FE-056 — registrar queue ticket identity belongs to the backend.
 * These are synthetic UI fixtures; never use production patient records.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, renderHook, screen } from '@testing-library/react';
import type { Appointment } from '../../../types/domain/clinic';
import type { AppointmentRow } from '../appointmentsTableContracts';
import { useAppointmentsTableRenderers } from '../appointmentsTableColumns';
import { getLocalDateString } from '../../../utils/dateUtils';

afterEach(() => cleanup());

const t = (key: string) => key;

const renderTicket = (row: Record<string, unknown>, otherRows: Record<string, unknown>[] = []) => {
  const { result } = renderHook(() => useAppointmentsTableRenderers({
    t,
    services: {},
    data: [...otherRows, row] as unknown as AppointmentRow[],
  }));
  render(<div>{result.current.renderQueueNumbers(row as unknown as Appointment)}</div>);
};

describe('REG-FE-056: registrar ticket column', () => {
  it('keeps the actual backend ticket number on a historical date instead of the row index', () => {
    const oldDate = '2020-01-20';
    renderTicket(
      {
        id: 501,
        date: oldDate,
        appointment_date: oldDate,
        queue_number: 17,
        queue_numbers: [{ number: 17, queue_tag: 'cardiology', status: 'served' }],
        cabinet: '205',
      },
      [{ id: 500, date: oldDate, appointment_date: oldDate, queue_number: 3 }],
    );
    expect(screen.getByText('17')).toBeTruthy();
    expect(screen.queryByText('#2')).toBeNull();
    expect(screen.queryByText('205')).toBeNull();
  });

  it('keeps an assigned future-date ticket instead of inventing a display index', () => {
    const futureDate = '2099-01-20';
    renderTicket({
      id: 502,
      date: futureDate,
      appointment_date: futureDate,
      queue_number: 8,
      queue_numbers: [{ number: 8, queue_tag: 'lab', status: 'waiting' }],
      cabinet: '205',
    });
    expect(screen.getByText('8')).toBeTruthy();
    expect(screen.queryByText('#1')).toBeNull();
  });

  it('does not fabricate a queue number from row order when no ticket is supplied', () => {
    const date = getLocalDateString();
    renderTicket({
      id: 503,
      date,
      appointment_date: date,
      queue_number: null,
      queue_numbers: [],
      cabinet: '205',
    });
    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.queryByText('1')).toBeNull();
    expect(screen.queryByText('205')).toBeNull();
  });
});
