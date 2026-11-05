import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QRCodeSVG } from 'qrcode.react';
import { fetchClinicSettings } from '../api/adminSettings';
import {
  fetchTicketPrintSettings,
  normalizeTicketPrintSettings,
  TICKET_PRINT_SETTINGS_DEFAULTS,
} from '../api/ticketPrintSettings';

// Phase 1 — panelPrint.ts has 1140 lines with heterogeneous return shapes.
// Proper typing requires modeling the full print pipeline (Phase 9 cleanup).
// Using `any` for return types and some params as a pragmatic measure.

import logger from '../utils/logger';
import {
  formatRegistrarDate,
  formatRegistrarDateTime,
  formatRegistrarTime,
  parseRegistrarTimestamp,
} from '../utils/dateUtils';
import { finalizePrintableWindow, openPrintableWindow, type PrintableWindowResult } from '../utils/printWindow';

function normalizePrintableDateString(value: unknown): string | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }

  return String(value)
    .trim()
    .replace(/(\+\d{2}:\d{2})Z$/, '$1')
    .replace(/(\.\d{3})\d+(?=(Z|[+-]\d{2}:\d{2})?$)/, '$1');
}

function tryParsePrintableDate(value: unknown): Date | null {
  const normalized = normalizePrintableDateString(value);
  if (!normalized) {
    return null;
  }

  const candidates = [normalized];
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(normalized)) {
    candidates.unshift(normalized.replace(' ', 'T'));
  }

  for (const candidate of candidates) {
    const parsed = parseRegistrarTimestamp(candidate);
    if (parsed && !Number.isNaN(parsed.getTime())) {
      return parsed;
    }
  }

  return null;
}

function formatPrintableDate(date: Date | string | null | undefined): string | null {
  return formatRegistrarDate(date);
}

function formatPrintableTime(date: Date | string | null | undefined): string | null {
  return formatRegistrarTime(date);
}

function formatPrintableDateTime(date: Date | string | null | undefined): string | null {
  return formatRegistrarDateTime(date);
}

function normalizeDateOnly(value: unknown): string | null {
  const normalized = normalizePrintableDateString(value);
  if (!normalized) {
    return null;
  }

  const directMatch = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (directMatch) {
    return `${directMatch[3]}.${directMatch[2]}.${directMatch[1]}`;
  }

  const parsed = tryParsePrintableDate(normalized);
  return parsed ? formatPrintableDate(parsed) : null;
}

function normalizeTimeOnly(value: unknown): string | null {
  const normalized = normalizePrintableDateString(value);
  if (!normalized) {
    return null;
  }

  const directMatch = normalized.match(/(?:T|\s)?(\d{2}:\d{2})(?::\d{2})?/);
  if (directMatch) {
    return directMatch[1];
  }

  const parsed = tryParsePrintableDate(normalized);
  return parsed ? formatPrintableTime(parsed) : null;
}

// REG-FE-081 (follow-up audit 2026-11-02): источник времени талона.
// 'appointment'  — каноническое время приёма (appointment_time / visit_datetime);
// 'scheduled'    — явно назначенный приём (visit_date [± visit_time]);
// 'registration' — штамп регистрации в очереди (queue_time / created_at):
//                  «время регистрации в очереди», НЕ время приёма — талон
//                  обязан помечать его отдельной меткой, а не выдавать за приём.
export type TicketTimeWindowSource = 'appointment' | 'scheduled' | 'registration' | null;

export interface TicketTimeWindow {
  value: string | null;
  source: TicketTimeWindowSource;
}

function formatTicketTimeWindow(row: Record<string, unknown>): TicketTimeWindow {
  // 1. Каноническое время приёма — выше всего.
  const parsedAppointment = tryParsePrintableDate(row?.appointment_time);
  if (parsedAppointment) {
    return { value: formatPrintableDateTime(parsedAppointment), source: 'appointment' };
  }

  // REG-FE-081: ЯВНО назначенный приём (visit_date + visit_time) теперь
  // ВЫШЕ штампов регистрации/создания. Прежде очередь «впереди» явного
  // назначения: пациент, записанный на 03.11 14:00, но зарегистрированный
  // в очереди 02.11 09:00, получал на талоне штамп регистрации, а не время
  // приёма. Формат «дд.мм.гггг чч:мм» сохранён.
  const visitDate = normalizeDateOnly(row?.visit_date);
  const visitTime = normalizeTimeOnly(row?.visit_time);
  if (visitDate && visitTime) {
    return { value: `${visitDate} ${visitTime}`, source: 'scheduled' };
  }
  if (visitDate) {
    return { value: visitDate, source: 'scheduled' };
  }

  // 2. Штампы регистрации/создания — ниже явного назначения. Помечаются
  // источником 'registration': талон покажет их под меткой «Время
  // регистрации» (см. renderPanelTicketMarkup), а не под «Дата и время».
  const registrationCandidate = getFirstDefined(row?.queue_time, row?.created_at);
  const parsedRegistration = tryParsePrintableDate(registrationCandidate);
  if (parsedRegistration) {
    return { value: formatPrintableDateTime(parsedRegistration), source: 'registration' };
  }

  // visit_datetime — datetime самой записи приёма (не штамп регистрации).
  const parsedVisitDatetime = tryParsePrintableDate(row?.visit_datetime);
  if (parsedVisitDatetime) {
    return { value: formatPrintableDateTime(parsedVisitDatetime), source: 'appointment' };
  }

  // Хвостовые одиночные поля — как прежде, но с источником.
  const parsedVisitTime = tryParsePrintableDate(row?.visit_time);
  if (parsedVisitTime) {
    return { value: formatPrintableDateTime(parsedVisitTime), source: 'scheduled' };
  }

  const parsedVisitDate = tryParsePrintableDate(row?.visit_date);
  if (parsedVisitDate) {
    return { value: formatPrintableDate(parsedVisitDate), source: 'scheduled' };
  }

  return { value: null, source: null };
}

function extractQueueNumberCandidate(value: unknown): string | null {
  if (value === undefined || value === null || value === '') {
    return null;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const candidate = extractQueueNumberCandidate(item);
      if (candidate !== null && candidate !== undefined && candidate !== '') {
        return String(candidate);
      }
    }
    return null;
  }

  if (typeof value === 'object' && value !== null) {
    const obj = value as Record<string, unknown>;
    const direct = getFirstDefined(
      obj.queue_number,
      obj.number,
      obj.ticket_number,
      obj.queue_position,
      obj.queue_no,
      obj.display_number,
      obj.id
    );

    if (direct !== null && direct !== undefined && direct !== '') {
      return String(direct);
    }

    for (const nestedValue of Object.values(value)) {
      const nestedCandidate = extractQueueNumberCandidate(nestedValue);
      if (nestedCandidate !== null && nestedCandidate !== undefined && nestedCandidate !== '') {
        return String(nestedCandidate);
      }
    }

    return null;
  }

  return String(value);
}

function resolveQueueNumber(row: Record<string, unknown> | null | undefined): string | null {
  const directCandidates = [
    row?.queue_number,
    row?.number,
    row?.ticket_number,
    row?.queue_position,
    row?.queue_no,
    row?.display_number,
    (row?.queue_entry as Record<string, unknown> | undefined)?.queue_number,
    (row?.queue_entry as Record<string, unknown> | undefined)?.number,
    (row?.queue_entry as Record<string, unknown> | undefined)?.ticket_number,
    (row?.queue_entry as Record<string, unknown> | undefined)?.queue_position,
    (row?.queue_entry as Record<string, unknown> | undefined)?.queue_no,
    (row?.queue_entry as Record<string, unknown> | undefined)?.display_number,
    (row?.queue_ticket as Record<string, unknown> | undefined)?.queue_number,
    (row?.queue_ticket as Record<string, unknown> | undefined)?.number,
    (row?.queue_ticket as Record<string, unknown> | undefined)?.ticket_number,
    (row?.queue_ticket as Record<string, unknown> | undefined)?.queue_position,
    (row?.queue_ticket as Record<string, unknown> | undefined)?.queue_no,
    (row?.queue_ticket as Record<string, unknown> | undefined)?.display_number,
  ];

  const nestedQueueNumber = extractQueueNumberCandidate(row?.queue_numbers);
  const nestedQueueEntry = extractQueueNumberCandidate(row?.queue_entry);
  const nestedQueueTicket = extractQueueNumberCandidate(row?.queue_ticket);

  const resolved = getFirstDefined(
    ...directCandidates,
    nestedQueueNumber,
    nestedQueueEntry,
    nestedQueueTicket
  );

  if (resolved !== null && resolved !== undefined && resolved !== '') {
    return String(resolved);
  }

  return null;
}

function getFirstDefined(...values: unknown[]): unknown {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== '') {
      return value;
    }
  }

  return null;
}

// REG-FE-082 (follow-up audit 2026-11-02): дефолты брендинга — ПУСТЫЕ.
// Прежде дефолт подставлял «Programma Clinic» + '/static/logo.png':
// при сбое настроек (или настройках без clinic_name) талон любой клиники
// молча идентифицировал себя как Programma Clinic. Теперь дефолт ничего
// не подменяет: имя/логотип появятся только из реальных настроек или из
// снапшота строки (row.clinic_name / row.clinic_logo_url).
function normalizeClinicBrandingSettings(settings: Record<string, unknown>): Record<string, unknown> {
  const normalized = {
    clinic_name: '',
    logo_url: '',
  };

  if (!Array.isArray(settings)) {
    return normalized;
  }

  for (const setting of settings) {
    if (!setting || typeof setting !== 'object') {
      continue;
    }

    if (setting.key === 'clinic_name' && setting.value) {
      normalized.clinic_name = String(setting.value);
    } else if (setting.key === 'logo_url' && setting.value) {
      normalized.logo_url = String(setting.value);
    }
  }

  return normalized;
}

function resolveQrPayload(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): unknown {
  return getFirstDefined(
    overrides.qrPayload,
    overrides.qrUrl,
    row?.qr_payload,
    row?.qr_url,
    row?.qr_data,
    row?.qr_code_url,
    row?.qr_code_base64,
    row?.token,
    row?.queue_token,
    row?.queue_ticket_url
  );
}

function resolveClinicLogo(row: Record<string, unknown>, overrides: Record<string, unknown> = {}, branding: Record<string, unknown> = {}): unknown {
  return getFirstDefined(
    overrides.logoUrl,
    row?.logo_url,
    row?.clinic_logo_url,
    branding?.logo_url
  );
}

function resolveClinicName(row: Record<string, unknown>, overrides: Record<string, unknown> = {}, branding: Record<string, unknown> = {}): unknown {
  // REG-FE-082 (follow-up audit 2026-11-02): удалён финальный фолбэк
  // 'Programma Clinic'. Раньше при недоступных настройках клиники (или
  // настройках без clinic_name) ТАЛОН ДРУГОЙ КЛИНИКИ печатался под брендом
  // «Programma Clinic» — подмена чужой идентичности без ведома оператора.
  // Теперь пустое имя не подменяется: строка имени просто не печатается.
  return getFirstDefined(
    overrides.clinicName,
    row?.clinic_name,
    row?.clinic,
    branding?.clinic_name
  );
}

function resolveServicePrice(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): unknown {
  return getFirstDefined(
    overrides.servicePrice,
    row?.service_price,
    row?.price,
    row?.price_default,
    row?.cost,
    row?.amount,
    row?.service_cost
  );
}

const QUEUE_DISPLAY_NAMES = {
  cardiology: 'Кардиология',
  cardiology_common: 'Кардиология',
  dermatology: 'Дерматология',
  stomatology: 'Стоматология',
  dentistry: 'Стоматология',
  echokg: 'ЭхоКГ',
  ecg: 'ЭКГ',
  laboratory: 'Лаборатория',
  lab: 'Лаборатория',
  general: 'Общая очередь',
  cosmetology: 'Косметология',
};

function normalizeDisplayLabel(value: unknown): string | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }

  const raw = String(value).trim();
  if (!raw) {
    return null;
  }

  const mapped = QUEUE_DISPLAY_NAMES[raw.toLowerCase() as keyof typeof QUEUE_DISPLAY_NAMES];
  if (mapped) {
    return mapped;
  }

  return raw
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeTicketSources(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): unknown[] {
  const explicitSources = Array.isArray(overrides.printTickets)
    ? overrides.printTickets.filter(Boolean)
    : null;
  if (explicitSources && explicitSources.length > 0) {
    return explicitSources;
  }

  if (Array.isArray(row?.print_tickets) && row.print_tickets.length > 0) {
    return row.print_tickets.filter(Boolean);
  }

  if (Array.isArray(row?.queue_numbers) && row.queue_numbers.length > 0) {
    return row.queue_numbers.filter(Boolean);
  }

  return [];
}

function resolveServicePriceForTicket(row: Record<string, unknown>, source: Record<string, unknown>, overrides: Record<string, unknown> = {}): Record<string, unknown> | null {
  const directPrice = getFirstDefined(
    overrides.servicePrice,
    source?.service_price,
    source?.price,
    source?.service_cost,
    source?.amount
  );
  if (directPrice !== null && directPrice !== undefined && directPrice !== '') {
    return directPrice as Record<string, unknown>;
  }

  const normalizedCandidates = [
    source?.service_name,
    source?.queue_name,
    normalizeDisplayLabel(source?.queue_tag),
    normalizeDisplayLabel(source?.specialty),
    normalizeDisplayLabel(source?.department),
  ]
    .filter(Boolean)
    .map((value: unknown) => String(value).trim().toLowerCase());

  if (normalizedCandidates.length === 0) {
    return null;
  }

  const services = Array.isArray(row?.services) ? row.services : [];
  for (const service of services) {
    if (!service || typeof service !== 'object') {
      continue;
    }

    const serviceLabels = [
      service?.name,
      service?.display_name,
      service?.title,
      service?.service_name,
      service?.code,
    ]
      .filter(Boolean)
      .map((value: Record<string, unknown>) => String(value).trim().toLowerCase());

    if (serviceLabels.some((label) => normalizedCandidates.includes(label))) {
      return getFirstDefined(
        service?.price,
        service?.service_price,
        service?.amount,
        service?.cost
      ) as Record<string, unknown>;
    }
  }

  return {};
}

function resolveTicketCabinet(row: Record<string, unknown>, source: Record<string, unknown> | null = null, overrides: Record<string, unknown> = {}): unknown {
  return getFirstDefined(
    overrides.cabinet,
    source?.cabinet,
    source?.cabinet_number,
    source?.effective_cabinet,
    source?.queue_cabinet,
    source?.room,
    source?.doctor_cabinet,
    row?.effective_cabinet,
    row?.queue_cabinet,
    row?.cabinet_number,
    row?.cabinet,
    row?.doctor_cabinet
  );
}

function buildPanelTicketPayloadForSource(row: Record<string, unknown>, source: Record<string, unknown>, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  const mergedRow = {
    ...row,
    ...(source && typeof source === 'object' ? source : {}),
    patient_fio: getFirstDefined(
      source?.patient_name,
      source?.patient_fio,
      row?.patient_fio,
      row?.patient_name,
      row?.name
    ),
    doctor_name: getFirstDefined(
      source?.doctor_name,
      source?.doctor,
      row?.doctor_name,
      row?.doctor,
      row?.specialist_name
    ),
    specialty_name: getFirstDefined(
      source?.queue_name,
      source?.service_name,
      source?.specialty_name,
      normalizeDisplayLabel(source?.queue_tag),
      normalizeDisplayLabel(source?.specialty),
      normalizeDisplayLabel(source?.department),
      row?.specialty_name,
      row?.queue_name,
      row?.service_name
    ),
    queue_name: getFirstDefined(
      source?.queue_name,
      source?.service_name,
      normalizeDisplayLabel(source?.queue_tag),
      normalizeDisplayLabel(source?.specialty),
      normalizeDisplayLabel(source?.department),
      row?.queue_name
    ),
    specialty: getFirstDefined(
      source?.specialty,
      source?.queue_tag,
      source?.department,
      row?.specialty
    ),
    department: getFirstDefined(
      source?.department,
      source?.specialty,
      source?.queue_tag,
      row?.department
    ),
    cabinet: resolveTicketCabinet(row, source, overrides),
    doctor_cabinet: getFirstDefined(
      source?.doctor_cabinet,
      source?.effective_cabinet,
      source?.cabinet,
      source?.cabinet_number,
      row?.doctor_cabinet,
      row?.cabinet
    ),
    visit_date: getFirstDefined(
      source?.visit_date,
      source?.appointment_date,
      row?.visit_date,
      row?.appointment_date,
      row?.date
    ),
    visit_time: getFirstDefined(
      source?.visit_time,
      row?.visit_time
    ),
    queue_time: getFirstDefined(
      source?.queue_time,
      row?.queue_time
    ),
    appointment_time: getFirstDefined(
      source?.appointment_time,
      row?.appointment_time
    ),
    queue_number: getFirstDefined(
      source?.queue_number,
      source?.number,
      source?.ticket_number,
      source?.queue_position,
      row?.queue_number
    ),
    queue_numbers: source ? [source] : row?.queue_numbers,
    service_price: resolveServicePriceForTicket(row, source, overrides),
    price: resolveServicePriceForTicket(row, source, overrides),
    cost: resolveServicePriceForTicket(row, source, overrides),
  };

  return buildPanelTicketPayload(mergedRow, overrides);
}

export function resolvePanelTicketPayloads(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): Record<string, unknown>[] {
  const ticketSources = normalizeTicketSources(row, overrides);
  if (ticketSources.length === 0) {
    return [buildPanelTicketPayload(row, overrides)];
  }

  const seenKeys = new Set();
  const payloads: Record<string, unknown>[] = [];

  for (const source of ticketSources) {
    const payload = buildPanelTicketPayloadForSource(row, source as Record<string, unknown>, overrides);
    const dedupeKey = [
      payload.queue_number,
      payload.specialty_name,
      payload.cabinet || '',
      (source as Record<string, unknown>)?.visit_id || '',
      (source as Record<string, unknown>)?.queue_id || '',
      (source as Record<string, unknown>)?.queue_tag || '',
    ].join('::');

    if (!seenKeys.has(dedupeKey)) {
      seenKeys.add(dedupeKey);
      payloads.push(payload);
    }
  }

  return payloads.length > 0 ? payloads : [buildPanelTicketPayload(row, overrides)];
}

export function buildPanelTicketPayload(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  const queueNumber = resolveQueueNumber(row);
  if (!queueNumber) {
    // Desk/laboratory visits never join the queue machinery (prod:
    // queue_entries is empty by workflow — visits carry their own id), so
    // a missing queue number is EXPECTED there. Fall back to the visit
    // identifier instead of failing the print: "В-<id>" identifies the
    // talon just as well for these flows. Only rows with no identifier at
    // all still fail.
    const visitFallback = getFirstDefined(row?.visit_id, row?.id);
    if (visitFallback === null || visitFallback === undefined || visitFallback === '') {
      logger.warn('[PanelPrint] Queue number missing in row payload', {
        rowKeys: row && typeof row === 'object' ? Object.keys(row) : [],
        appointmentId: row?.appointment_id || row?.id || null,
        visitId: row?.visit_id || null,
        specialty: row?.specialty_name || row?.specialty || row?.department || null,
      });
      throw new Error('Не удалось определить номер талона для печати');
    }
    logger.info('[PanelPrint] No queue entry — printing visit-based talon', {
      visitId: visitFallback,
    });
    const timeWindow = formatTicketTimeWindow(row);
    return {
      queue_number: `В-${visitFallback}`,
      doctor_name:
        overrides.doctorName ||
        row?.doctor_name ||
        row?.doctor ||
        row?.specialist_name ||
        row?.specialty_doctor_name ||
        'Специалист',
      specialty_name:
        overrides.specialtyName ||
        row?.specialty_name ||
        row?.queue_name ||
        row?.specialty ||
        row?.department ||
        row?.service_name ||
        'Прием',
      cabinet: resolveTicketCabinet(row, null, overrides) || null,
      patient_name:
        row?.patient_fio ||
        row?.patient_name ||
        row?.name ||
        'Пациент',
      clinic_name: getFirstDefined(overrides.clinicName, row?.clinic_name, row?.clinic),
      logo_url: getFirstDefined(overrides.logoUrl, row?.logo_url, row?.clinic_logo_url),
      service_price: resolveServicePrice(row, overrides),
      qr_payload: resolveQrPayload(row, overrides),
      // REG-FE-081: значение + источник (метка в шаблоне зависит от источника).
      time_window: timeWindow.value,
      time_window_source: timeWindow.source,
      printer_name: overrides.printerName || null
    };
  }

  const timeWindow = formatTicketTimeWindow(row);
  return {
    queue_number: String(queueNumber),
    doctor_name:
      overrides.doctorName ||
      row?.doctor_name ||
      row?.doctor ||
      row?.specialist_name ||
      row?.specialty_doctor_name ||
      'Специалист',
    specialty_name:
      overrides.specialtyName ||
      row?.specialty_name ||
      row?.queue_name ||
      row?.specialty ||
      row?.department ||
      row?.service_name ||
      'Прием',
    cabinet:
      resolveTicketCabinet(row, null, overrides) || null,
    patient_name:
      row?.patient_fio ||
      row?.patient_name ||
      row?.name ||
      'Пациент',
    clinic_name: getFirstDefined(overrides.clinicName, row?.clinic_name, row?.clinic),
    logo_url: getFirstDefined(overrides.logoUrl, row?.logo_url, row?.clinic_logo_url),
    service_price: resolveServicePrice(row, overrides),
    qr_payload: resolveQrPayload(row, overrides),
    // REG-FE-081: значение + источник (метка в шаблоне зависит от источника).
    time_window: timeWindow.value,
    time_window_source: timeWindow.source,
    printer_name: overrides.printerName || null
  };
}

function escapeHtml(value: unknown) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderTicketMetadata(label: unknown, value: unknown, visible: unknown) {
  if (!visible || value === null || value === undefined || value === '') {
    return '';
  }

  return `<div class="meta"><span class="label">${escapeHtml(label)}:</span> ${escapeHtml(value)}</div>`;
}

function renderTicketQrMarkup(qrPayload: unknown, visible: unknown) {
  if (!visible || !qrPayload) {
    return '';
  }

  const payloadString = String(qrPayload).trim();
  if (!payloadString) {
    return '';
  }

  if (/^data:image\//i.test(payloadString)) {
    return `
      <div class="qr-wrap">
        <img class="qr-image" src="${escapeHtml(payloadString)}" alt="QR-код" />
      </div>
    `;
  }

  const qrSvg = renderToStaticMarkup(
    createElement(QRCodeSVG, {
      value: payloadString,
      size: 120,
      level: 'M',
      includeMargin: true,
    })
  );

  return `<div class="qr-wrap">${qrSvg}</div>`;
}

function renderPanelTicketMarkup(payload: Record<string, unknown>, settings: Record<string, unknown>, branding: Record<string, unknown>, issuedAt: unknown): string {
  const clinicName = resolveClinicName(payload, {}, branding);
  const logoUrl = resolveClinicLogo(payload, {}, branding);
  const servicePrice = resolveServicePrice(payload);
  const qrPayload = payload?.qr_payload;
  const showPriceValue = settings.show_price && servicePrice !== null && servicePrice !== undefined && String(servicePrice) !== '' && Number(servicePrice) !== 0;
  const priceValue = showPriceValue ? formatMoney(servicePrice, 'UZS') : null;

  // REG-FE-082: блок бренда рендерится только при честном имени/логотипе
  // (реальные настройки или снапшот строки); пустые значения не
  // подменяются посторонним брендом и не рисуют пустой блок.
  // REG-FE-081: если источником времени стал штамп регистрации в очереди
  // (queue_time/created_at) — метка «Время регистрации», не «Дата и время».
  return `
    <div class="ticket">
      ${(settings.show_clinic_name && clinicName) || (settings.show_logo && logoUrl) ? `
        <div class="clinic-brand">
          ${settings.show_logo && logoUrl ? `<img class="clinic-logo" src="${escapeHtml(logoUrl)}" alt="Логотип клиники" />` : ''}
          ${settings.show_clinic_name && clinicName ? `<div class="clinic-name">${escapeHtml(clinicName)}</div>` : ''}
        </div>
      ` : ''}
      ${settings.show_service_name ? `<div class="center service-name">${escapeHtml(payload.specialty_name)}</div>` : ''}
      <div class="line"></div>
      ${settings.show_queue_number ? `<div class="center queue-number">Очередь №${escapeHtml(payload.queue_number)}</div>` : ''}
      <div class="line"></div>
      ${renderTicketMetadata('Пациент', payload.patient_name, settings.show_patient_name)}
      ${renderTicketMetadata('Врач', payload.doctor_name, settings.show_doctor_name)}
      ${renderTicketMetadata('Кабинет', payload.cabinet || 'Не указан', settings.show_cabinet)}
      ${renderTicketMetadata('Цена', priceValue, settings.show_price)}
      ${renderTicketMetadata(
        payload.time_window_source === 'registration' ? 'Время регистрации' : 'Дата и время',
        payload.time_window,
        Boolean(payload.time_window)
      )}
      ${renderTicketQrMarkup(qrPayload, settings.show_qr_code)}
      <div class="line"></div>
      ${settings.show_printed_at ? `
        <div class="center footnote">
          Выдан: ${escapeHtml(issuedAt)}<br/>
          Сохраните талон до завершения приёма
        </div>
      ` : ''}
    </div>
  `;
}

function renderPanelTicketHtml(payloads: unknown, settings: Record<string, unknown>, branding: Record<string, unknown>) {
  const issuedAt = formatRegistrarDateTime(new Date().toISOString());
  const safePayloads = Array.isArray(payloads) && payloads.length > 0 ? payloads : [];
  const documentTitle = safePayloads.length > 1
    ? `Талоны (${safePayloads.length})`
    : `Талон №${escapeHtml(safePayloads[0]?.queue_number || '')}`;

  return `
    <html>
      <head>
        <title>${documentTitle}</title>
        <style>
          @page { size: 58mm auto; margin: 2mm 1mm 2mm 2mm; }
          body {
            font-family: Arial, "Helvetica Neue", Helvetica, sans-serif;
            margin: 0;
            font-size: 16px;
            line-height: 1.35;
            color: #111827;
            background: #ffffff;
            font-weight: 700;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          .ticket {
            width: 55mm;
            margin: 0;
            padding: 4px 0;
            box-sizing: border-box;
          }
          .ticket-page {
            break-after: page;
            page-break-after: always;
          }
          .ticket-page:last-child {
            break-after: auto;
            page-break-after: auto;
          }
          .clinic-brand {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            margin-bottom: 8px;
          }
          .clinic-logo {
            max-width: 40mm;
            max-height: 14mm;
            object-fit: contain;
          }
          .clinic-name {
            font-size: 17px;
            font-weight: 700;
            text-align: center;
            line-height: 1.2;
          }
          .center { text-align: center; }
          .title {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 8px;
            line-height: 1.15;
            letter-spacing: 0.3px;
          }
          .service-name {
            font-size: 16px;
            font-weight: 700;
            line-height: 1.25;
          }
          .queue-number {
            font-size: 32px;
            font-weight: 700;
            margin: 10px 0;
            letter-spacing: 0.4px;
            line-height: 1;
            white-space: nowrap;
          }
          .line {
            border-top: 2px solid #111827;
            margin: 10px 0;
          }
          .meta {
            font-size: 14px;
            line-height: 1.35;
            white-space: pre-line;
            font-weight: 700;
            margin-bottom: 3px;
          }
          .label {
            font-weight: 700;
          }
          .footnote {
            margin-top: 10px;
            font-size: 12px;
            color: #111827;
            font-weight: 700;
            line-height: 1.3;
          }
          .qr-wrap {
            display: flex;
            justify-content: center;
            margin-top: 12px;
          }
          .qr-wrap svg,
          .qr-image {
            width: 24mm;
            height: 24mm;
          }
        </style>
      </head>
      <body>
        ${safePayloads.map((payload: Record<string, unknown>) => `
          <div class="ticket-page">
            ${renderPanelTicketMarkup(payload, settings, branding, issuedAt)}
          </div>
        `).join('')}
      </body>
    </html>
  `;
}

function renderPanelTicketErrorHtml(message: unknown, details: string = '') {
  const safeMessage = escapeHtml(message || 'Не удалось подготовить талон к печати');
  const safeDetails = details ? escapeHtml(details) : '';

  return `
    <html>
      <head>
        <title>Ошибка печати</title>
        <style>
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            padding: 24px;
            background: #ffffff;
            color: #111827;
          }
          .card {
            max-width: 420px;
            margin: 0 auto;
            padding: 20px;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            background: #f9fafb;
          }
          .title {
            margin: 0 0 12px 0;
            font-size: 18px;
            font-weight: 700;
          }
          .message {
            margin: 0;
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-line;
          }
          .details {
            margin-top: 12px;
            font-size: 12px;
            color: #6b7280;
            white-space: pre-wrap;
          }
        </style>
      </head>
      <body>
        <div class="card">
          <div class="title">Не удалось подготовить талон к печати</div>
          <p class="message">${safeMessage}</p>
          ${safeDetails ? `<div class="details">${safeDetails}</div>` : ''}
        </div>
      </body>
    </html>
  `;
}

async function loadPanelTicketRenderContextForRows(
  rows: Array<Record<string, unknown>>,
  overrides: Record<string, unknown> = {}
): Promise<any> {
  // CSH-FE-045: контекст рендера умеет собирать НЕСКОЛЬКО строк в один
  // документ (один запрос настроек на весь пакет) — основа для
  // пакетной печати одним окном из прямого жеста пользователя.
  const payloads = rows.flatMap((row) => resolvePanelTicketPayloads(row, overrides));

  const [ticketSettingsResult, clinicSettingsResult] = await Promise.allSettled([
    fetchTicketPrintSettings(),
    fetchClinicSettings('clinic'),
  ]);

  const settings =
    ticketSettingsResult.status === 'fulfilled'
      ? normalizeTicketPrintSettings(ticketSettingsResult.value)
      : { ...TICKET_PRINT_SETTINGS_DEFAULTS };

  // REG-FE-082: при сбое запроса настроек клиники талон печатается БЕЗ
  // бренда (никакой «Programma Clinic»), с честным предупреждением в
  // лог; имя/логотип берутся только из реальных настроек либо из
  // снапшота строки (payload.clinic_name / payload.clinic_logo_url).
  const branding =
    clinicSettingsResult.status === 'fulfilled'
      ? normalizeClinicBrandingSettings(clinicSettingsResult.value)
      : (() => {
          logger.warn('[PanelPrint] Clinic settings unavailable — ticket will print unbranded');
          return { clinic_name: '', logo_url: '' };
        })();

  return { payloads, settings, branding };
}

async function loadPanelTicketRenderContext(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): Promise<any> {
  return loadPanelTicketRenderContextForRows([row], overrides);
}

export async function buildPanelTicketPrintableHtml(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): Promise<any> {
  const { payloads, settings, branding } = await loadPanelTicketRenderContext(row, overrides);
  return renderPanelTicketHtml(payloads, settings, branding);
}

// CSH-FE-045: HTML одного документа с несколькими талонами (по одному
// .ticket-page на талон, page-break между ними — порядок печати задан
// порядком строк в массиве).
export async function buildPanelTicketsBatchPrintableHtml(
  rows: Array<Record<string, unknown>>,
  overrides: Record<string, unknown> = {}
): Promise<any> {
  if (!Array.isArray(rows) || rows.length === 0) {
    throw new Error('Пакетная печать: список талонов пуст');
  }
  const { payloads, settings, branding } = await loadPanelTicketRenderContextForRows(rows, overrides);
  return renderPanelTicketHtml(payloads, settings, branding);
}

async function buildAndFinalizePanelTicketWindow(printWindow: Window, row: Record<string, unknown>, overrides: Record<string, unknown> = {}) {
  const html = await buildPanelTicketPrintableHtml(row, overrides);
  // CSH-FE-044: успех талона теперь включает честный вызов print():
  // printInvoked (синхронно прошёл) либо deferred (окно открыто, печать
  // отложена). Исключение print() больше не маскируется под успех —
  // вызывающий (кнопка «Печать», пакетная печать) видит провал и может
  // оставить пользователю путь восстановления.
  const fin = finalizePrintableWindow(printWindow, html, logger);
  return { success: Boolean(fin.printInvoked || fin.deferred) };
}

function renderPrintableErrorWindow(printWindow: Window, error: unknown, row: Record<string, unknown>) {
  const details = [
    row?.appointment_id ? `appointment_id: ${row.appointment_id}` : null,
    row?.visit_id ? `visit_id: ${row.visit_id}` : null,
    row?.id ? `id: ${row.id}` : null,
  ].filter(Boolean).join('\n');

  try {
    const errorHtml = renderPanelTicketErrorHtml(
      (error instanceof Error && error.message) ? error.message : 'Не удалось подготовить талон к печати',
      details
    );
    printWindow.document.open();
    printWindow.document.write(errorHtml);
    printWindow.document.close();
  } catch {
    try {
      printWindow.close();
    } catch {
      // ignore
    }
  }
}

export async function printPanelTicketInBrowserAsync(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): Promise<any> {
  const printWindow = window.open('', '_blank', 'width=420,height=720');

  if (!printWindow) {
    return { opened: false, success: false };
  }

  try {
    const fin = await buildAndFinalizePanelTicketWindow(printWindow, row, overrides);
    return { opened: true, success: fin.success };
  } catch (error) {
    logger.error('[PanelPrint] Failed to build ticket preview', error);
    renderPrintableErrorWindow(printWindow, error, row);
    return { opened: true, success: false, error };
  }
}

// CSH-FE-043: удалена «синхронная» обёртка printPanelTicketInBrowser,
// которая запускала промис через void и НЕУСЛОВНО возвращала true —
// её единственный живой потребитель (PaymentProviderDialog.printTicket)
// проверял `if (!opened)` в недостижимой ветке. Потребители переведены на
// await printPanelTicketInBrowserAsync (типизированный {opened, success}).

// CSH-FE-045: пакетная печать одним документом. Окно открывается
// СИНХРОННО в прямом жесте пользователя (клик «Печать всех»), до любых
// сетевых запросов; заполнение и print() — позже (отсчёт/подготовка).
// Прежде окно открывалось на 5с+800мс ПОСЛЕ клика — вне окна доверенной
// активации, и popup-блокировщик отклонял окно.
export function openPanelTicketBatchWindow(): Window | null {
  const printWindow = window.open('', '_blank', 'width=420,height=720');
  if (!printWindow) {
    return null;
  }
  try {
    printWindow.document.open();
    printWindow.document.write(
      '<!DOCTYPE html><html lang="ru"><head><title>Талоны</title></head>' +
      '<body style="font-family: Arial, sans-serif; padding: 24px; color: #111827;">' +
      '<p>Подготовка талонов к печати…</p></body></html>'
    );
    printWindow.document.close();
  } catch {
    // Плейсхолдер — best-effort: главное, окно уже открыто в жесте.
  }
  return printWindow;
}

// CSH-FE-045: заполнить уже открытое окно пакетом талонов и вызвать печать.
export async function printPanelTicketsBatchInExistingWindow(
  printWindow: Window | null,
  rows: Array<Record<string, unknown>>,
  overrides: Record<string, unknown> = {}
): Promise<{ opened: boolean; success: boolean; error?: unknown }> {
  if (!printWindow) {
    return { opened: false, success: false, error: new Error('Окно пакетной печати не открыто') };
  }
  try {
    const html = await buildPanelTicketsBatchPrintableHtml(rows, overrides);
    const fin = finalizePrintableWindow(printWindow, html, logger);
    return { opened: true, success: Boolean(fin.printInvoked || fin.deferred) };
  } catch (error) {
    logger.error('[PanelPrint] Failed to build batch ticket preview', error);
    renderPrintableErrorWindow(printWindow, error, rows[0] ?? {});
    return { opened: true, success: false, error };
  }
}

export async function printPanelTicket(row: Record<string, unknown>, overrides: Record<string, unknown> = {}): Promise<any> {
  const result = await printPanelTicketInBrowserAsync(row, overrides);
  if (!result?.opened) {
    throw new Error('Браузер заблокировал окно печати. Разрешите всплывающие окна для приложения и повторите печать.');
  }
  if (!result?.success) {
    throw result?.error || new Error('Не удалось подготовить талон к печати');
  }

  const payloads = resolvePanelTicketPayloads(row, overrides);
  logger.info('[PanelPrint] Ticket print dialog opened', {
    ticketCount: payloads.length,
    queueNumbers: payloads.map((payload: Record<string, unknown>) => payload.queue_number),
    patientName: payloads[0]?.patient_name || null,
    specialties: payloads.map((payload: Record<string, unknown>) => payload.specialty_name),
  });

  return {
    success: true,
    message: 'Открыт системный диалог печати текущего компьютера',
    data: payloads.length === 1 ? payloads[0] : payloads,
  };
}

function formatMoney(value: unknown, currency: string = 'UZS') {
  const normalizedValue = typeof value === 'number'
    ? value
    : Number(String(value ?? 0).replace(/[^\d.-]/g, ''));
  const amount = Number.isFinite(normalizedValue) ? normalizedValue : 0;
  return `${new Intl.NumberFormat('ru-RU').format(amount)} ${escapeHtml(currency)}`;
}

export function buildPanelReceiptPrintableHtml(receiptPayload: Record<string, unknown>) {
  const payment = (receiptPayload?.payment as Record<string, unknown> | null | undefined) || {} as Record<string, unknown>;
  const patient = (receiptPayload?.patient as Record<string, unknown> | null | undefined) || {} as Record<string, unknown>;
  const services = Array.isArray(receiptPayload?.services) ? receiptPayload.services : [];
  const currency = services[0]?.currency || 'UZS';
  const issuedAt = formatRegistrarDateTime(new Date().toISOString());

  const serviceRows = services.length > 0
    ? services.map((service: Record<string, unknown>) => `
        <tr>
          <td>${escapeHtml(service?.name || '—')}</td>
          <td class="center">${escapeHtml(service?.quantity || 1)}</td>
          <td class="right">${formatMoney(service?.price, service?.currency || currency)}</td>
          <td class="right">${formatMoney(service?.total, service?.currency || currency)}</td>
        </tr>
      `).join('')
    : `
      <tr>
        <td>${escapeHtml('—')}</td>
        <td class="center">1</td>
        <td class="right">${formatMoney(payment?.total, currency)}</td>
        <td class="right">${formatMoney(payment?.total, currency)}</td>
      </tr>
    `;

  return `
    <html>
      <head>
        <title>Чек ${escapeHtml(payment?.number || '')}</title>
        <style>
          @page { size: A5 portrait; margin: 10mm; }
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            color: #111827;
            background: #ffffff;
          }
          .receipt {
            max-width: 680px;
            margin: 0 auto;
            padding: 4mm 0;
          }
          .header,
          .footer {
            text-align: center;
          }
          .title {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 6px;
          }
          .muted {
            color: #4b5563;
            font-size: 12px;
          }
          .line {
            border-top: 1px dashed #6b7280;
            margin: 12px 0;
          }
          .meta-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px 16px;
            font-size: 13px;
            line-height: 1.5;
          }
          .meta-item strong {
            display: block;
            font-size: 11px;
            text-transform: uppercase;
            color: #6b7280;
          }
          table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            font-size: 13px;
          }
          th, td {
            border-bottom: 1px solid #e5e7eb;
            padding: 8px 6px;
            vertical-align: top;
          }
          th {
            text-align: left;
            font-size: 11px;
            text-transform: uppercase;
            color: #6b7280;
          }
          .center { text-align: center; }
          .right { text-align: right; }
          .totals {
            margin-top: 12px;
            margin-left: auto;
            width: min(280px, 100%);
            font-size: 13px;
          }
          .totals-row {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
          }
          .totals-row.total {
            font-size: 16px;
            font-weight: 700;
            border-top: 1px solid #d1d5db;
            margin-top: 6px;
            padding-top: 8px;
          }
        </style>
      </head>
      <body>
        <div class="receipt">
          <div class="header">
            <div class="title">ЧЕК ОБ ОПЛАТЕ</div>
            <div class="muted">Сформировано: ${escapeHtml(issuedAt)}</div>
          </div>
          <div class="line"></div>
          <div class="meta-grid">
            <div class="meta-item">
              <strong>Номер чека</strong>
              <span>${escapeHtml(payment?.number || '-')}</span>
            </div>
            <div class="meta-item">
              <strong>Дата и время</strong>
              <span>${escapeHtml([payment?.date, payment?.time].filter(Boolean).join(' ')) || '-'}</span>
            </div>
            <div class="meta-item">
              <strong>Пациент</strong>
              <span>${escapeHtml(patient?.full_name || 'Пациент')}</span>
            </div>
            <div class="meta-item">
              <strong>Телефон</strong>
              <span>${escapeHtml(patient?.phone || 'Не указан')}</span>
            </div>
            <div class="meta-item">
              <strong>Способ оплаты</strong>
              <span>${escapeHtml(payment?.method_name || payment?.method || 'Наличные')}</span>
            </div>
            <div class="meta-item">
              <strong>Статус</strong>
              <span>${escapeHtml(payment?.status ?? 'unknown')}</span>
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th>Услуга</th>
                <th class="center">Кол-во</th>
                <th class="right">Цена</th>
                <th class="right">Сумма</th>
              </tr>
            </thead>
            <tbody>${serviceRows}</tbody>
          </table>
          <div class="totals">
            <div class="totals-row">
              <span>Подытог</span>
              <span>${formatMoney(payment?.subtotal, currency)}</span>
            </div>
            <div class="totals-row">
              <span>Скидка</span>
              <span>${formatMoney(payment?.discount, currency)}</span>
            </div>
            <div class="totals-row total">
              <span>Итого</span>
              <span>${formatMoney(payment?.total, currency)}</span>
            </div>
          </div>
          <div class="line"></div>
          <div class="footer muted">
            Чек открыт через браузер текущего компьютера.<br/>
            Для печати используйте системный диалог этого ПК.
          </div>
        </div>
      </body>
    </html>
  `;
}

// CSH-FE-044 (follow-up audit 2026-11-02): квитанция возвращает
// типизированный исход печати (PrintableWindowResult), а не «true всегда».
// Прежнее булево означало «окно открыто» даже когда print() бросил
// исключение — кассирный путь (useCashierActions) на этом «успехе»
// пропускал серверный PDF-fallback. printInvoked/deferred позволяют
// вызывающему честно ветвиться (диалог открыт / печать не подтверждена /
// вызов печати провалился → PDF).
export function printPanelReceiptInBrowser(receiptPayload: Record<string, unknown>): PrintableWindowResult {
  return openPrintableWindow({
    features: 'width=720,height=900',
    html: buildPanelReceiptPrintableHtml(receiptPayload),
    logger,
  });
}
