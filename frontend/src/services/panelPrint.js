import { printService } from './print';
import logger from '../utils/logger';

function formatTicketTimeWindow(row) {
  const rawValue = row?.appointment_time || row?.queue_time || row?.created_at || null;
  if (!rawValue) {
    return null;
  }

  const parsedDate = new Date(rawValue);
  if (Number.isNaN(parsedDate.getTime())) {
    return String(rawValue);
  }

  return parsedDate.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function resolveQueueNumber(row) {
  if (row?.queue_number) {
    return row.queue_number;
  }

  if (row?.number) {
    return row.number;
  }

  if (Array.isArray(row?.queue_numbers) && row.queue_numbers.length > 0) {
    return row.queue_numbers[0]?.number || row.queue_numbers[0]?.queue_number || null;
  }

  return null;
}

export function buildPanelTicketPayload(row, overrides = {}) {
  const queueNumber = resolveQueueNumber(row);
  if (!queueNumber) {
    throw new Error('Не удалось определить номер талона для печати');
  }

  return {
    queue_number: String(queueNumber),
    doctor_name:
      overrides.doctorName ||
      row?.doctor_name ||
      row?.doctor ||
      row?.specialist_name ||
      'Специалист',
    specialty_name:
      overrides.specialtyName ||
      row?.specialty_name ||
      row?.queue_name ||
      row?.specialty ||
      'Прием',
    cabinet:
      overrides.cabinet ||
      row?.cabinet ||
      row?.doctor_cabinet ||
      null,
    patient_name:
      row?.patient_fio ||
      row?.patient_name ||
      row?.name ||
      'Пациент',
    source: row?.source || 'desk',
    time_window: formatTicketTimeWindow(row),
    printer_name: overrides.printerName || null
  };
}

export async function printPanelTicket(row, overrides = {}) {
  const payload = buildPanelTicketPayload(row, overrides);
  const result = await printService.printTicket(payload);

  if (!result.success) {
    throw new Error(result.error || 'Ошибка печати талона');
  }

  logger.info('[PanelPrint] Ticket print success', {
    queueNumber: payload.queue_number,
    patientName: payload.patient_name,
    specialty: payload.specialty_name,
    printer: result.data?.printer || null,
    jobId: result.data?.job_id || null
  });

  return result.data;
}
