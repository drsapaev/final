import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QRCodeSVG } from 'qrcode.react';
import { fetchClinicSettings } from '../api/adminSettings';
import {
  fetchTicketPrintSettings,
  normalizeTicketPrintSettings,
  TICKET_PRINT_SETTINGS_DEFAULTS,
} from '../api/ticketPrintSettings';
import logger from '../utils/logger';
import { finalizePrintableWindow, openPrintableWindow } from '../utils/printWindow';

function formatTicketTimeWindow(row) {
  const combinedVisitTime = row?.visit_date && row?.visit_time
    ? `${row.visit_date} ${row.visit_time}`
    : null;
  const rawValue =
    row?.appointment_time ||
    row?.queue_time ||
    combinedVisitTime ||
    row?.visit_time ||
    row?.visit_date ||
    row?.created_at ||
    null;
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

function getFirstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== '') {
      return value;
    }
  }

  return null;
}

function normalizeClinicBrandingSettings(settings) {
  const normalized = {
    clinic_name: 'Programma Clinic',
    logo_url: '/static/logo.png',
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

function resolveQrPayload(row, overrides = {}) {
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

function resolveClinicLogo(row, overrides = {}, branding = {}) {
  return getFirstDefined(
    overrides.logoUrl,
    row?.logo_url,
    row?.clinic_logo_url,
    branding?.logo_url
  );
}

function resolveClinicName(row, overrides = {}, branding = {}) {
  return getFirstDefined(
    overrides.clinicName,
    row?.clinic_name,
    row?.clinic,
    branding?.clinic_name,
    'Programma Clinic'
  );
}

function resolveServicePrice(row, overrides = {}) {
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
      overrides.cabinet ||
      row?.cabinet ||
      row?.doctor_cabinet ||
      null,
    patient_name:
      row?.patient_fio ||
      row?.patient_name ||
      row?.name ||
      'Пациент',
    clinic_name: getFirstDefined(overrides.clinicName, row?.clinic_name, row?.clinic),
    logo_url: getFirstDefined(overrides.logoUrl, row?.logo_url, row?.clinic_logo_url),
    service_price: resolveServicePrice(row, overrides),
    qr_payload: resolveQrPayload(row, overrides),
    source: row?.source || 'desk',
    time_window: row?.time_window || formatTicketTimeWindow(row),
    printer_name: overrides.printerName || null
  };
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderTicketMetadata(label, value, visible) {
  if (!visible || value === null || value === undefined || value === '') {
    return '';
  }

  return `<div class="meta"><span class="label">${escapeHtml(label)}:</span> ${escapeHtml(value)}</div>`;
}

function renderTicketQrMarkup(qrPayload, visible) {
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

function renderPanelTicketHtml(payload, settings, branding) {
  const issuedAt = new Date().toLocaleString('ru-RU');
  const clinicName = resolveClinicName(payload, {}, branding);
  const logoUrl = resolveClinicLogo(payload, {}, branding);
  const servicePrice = resolveServicePrice(payload);
  const qrPayload = payload?.qr_payload;
  const showPriceValue = settings.show_price && servicePrice !== null && servicePrice !== undefined && servicePrice !== '';
  const priceValue = showPriceValue ? formatMoney(servicePrice, 'UZS') : null;

  return `
    <html>
      <head>
        <title>Талон №${escapeHtml(payload.queue_number)}</title>
        <style>
          @page { size: 80mm auto; margin: 6mm; }
          body {
            font-family: "Courier New", monospace;
            margin: 0;
            color: #111827;
            background: #ffffff;
          }
          .ticket {
            width: 72mm;
            margin: 0 auto;
            padding: 8px 0;
          }
          .clinic-brand {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            margin-bottom: 8px;
          }
          .clinic-logo {
            max-width: 52mm;
            max-height: 18mm;
            object-fit: contain;
          }
          .clinic-name {
            font-size: 15px;
            font-weight: 700;
            text-align: center;
          }
          .center { text-align: center; }
          .title {
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 8px;
          }
          .queue-number {
            font-size: 36px;
            font-weight: 700;
            margin: 10px 0;
            letter-spacing: 1px;
          }
          .line {
            border-top: 1px dashed #374151;
            margin: 10px 0;
          }
          .meta {
            font-size: 13px;
            line-height: 1.5;
            white-space: pre-line;
          }
          .label {
            font-weight: 700;
          }
          .footnote {
            margin-top: 12px;
            font-size: 11px;
            color: #4b5563;
          }
          .qr-wrap {
            display: flex;
            justify-content: center;
            margin-top: 12px;
          }
          .qr-wrap svg,
          .qr-image {
            width: 32mm;
            height: 32mm;
          }
        </style>
      </head>
      <body>
        <div class="ticket">
          ${settings.show_clinic_name || settings.show_logo ? `
            <div class="clinic-brand">
              ${settings.show_logo && logoUrl ? `<img class="clinic-logo" src="${escapeHtml(logoUrl)}" alt="Логотип клиники" />` : ''}
              ${settings.show_clinic_name ? `<div class="clinic-name">${escapeHtml(clinicName)}</div>` : ''}
            </div>
          ` : ''}
          <div class="center title">ТАЛОН НА ПРИЁМ</div>
          ${settings.show_service_name ? `<div class="center">${escapeHtml(payload.specialty_name)}</div>` : ''}
          <div class="line"></div>
          ${settings.show_queue_number ? `<div class="center queue-number">${escapeHtml(payload.queue_number)}</div>` : ''}
          <div class="line"></div>
          ${renderTicketMetadata('Пациент', payload.patient_name, settings.show_patient_name)}
          ${renderTicketMetadata('Врач', payload.doctor_name, settings.show_doctor_name)}
          ${renderTicketMetadata('Кабинет', payload.cabinet || 'Не указан', settings.show_cabinet)}
          ${renderTicketMetadata('Цена', priceValue, settings.show_price)}
          ${renderTicketMetadata('Время', payload.time_window || 'По очереди', true)}
          ${renderTicketMetadata('Источник', payload.source || 'desk', true)}
          ${renderTicketQrMarkup(qrPayload, settings.show_qr_code)}
          <div class="line"></div>
          ${settings.show_printed_at ? `
            <div class="center footnote">
              Выдан: ${escapeHtml(issuedAt)}<br/>
              Сохраните талон до завершения приёма
            </div>
          ` : ''}
        </div>
      </body>
    </html>
  `;
}

async function loadPanelTicketRenderContext(row, overrides = {}) {
  const payload = buildPanelTicketPayload(row, overrides);

  const [ticketSettingsResult, clinicSettingsResult] = await Promise.allSettled([
    fetchTicketPrintSettings(),
    fetchClinicSettings('clinic'),
  ]);

  const settings =
    ticketSettingsResult.status === 'fulfilled'
      ? normalizeTicketPrintSettings(ticketSettingsResult.value)
      : { ...TICKET_PRINT_SETTINGS_DEFAULTS };

  const branding =
    clinicSettingsResult.status === 'fulfilled'
      ? normalizeClinicBrandingSettings(clinicSettingsResult.value)
      : normalizeClinicBrandingSettings([]);

  return { payload, settings, branding };
}

export async function buildPanelTicketPrintableHtml(row, overrides = {}) {
  const { payload, settings, branding } = await loadPanelTicketRenderContext(row, overrides);
  return renderPanelTicketHtml(payload, settings, branding);
}

export function printPanelTicketInBrowser(row, overrides = {}) {
  const printWindow = window.open('', '_blank', 'width=420,height=720');

  if (!printWindow) {
    return false;
  }

  void (async () => {
    try {
      const html = await buildPanelTicketPrintableHtml(row, overrides);
      finalizePrintableWindow(printWindow, html, logger);
    } catch (error) {
      logger.error('[PanelPrint] Failed to build ticket preview', error);
      try {
        printWindow.close();
      } catch (_closeError) {
        // ignore
      }
    }
  })();

  return true;
}

export async function printPanelTicket(row, overrides = {}) {
  const opened = printPanelTicketInBrowser(row, overrides);
  if (!opened) {
    throw new Error('Браузер заблокировал окно печати. Разрешите всплывающие окна для приложения и повторите печать.');
  }

  const payload = buildPanelTicketPayload(row, overrides);
  logger.info('[PanelPrint] Ticket print dialog opened', {
    queueNumber: payload.queue_number,
    patientName: payload.patient_name,
    specialty: payload.specialty_name,
  });

  return {
    success: true,
    message: 'Открыт системный диалог печати текущего компьютера',
    data: payload,
  };
}

function formatMoney(value, currency = 'UZS') {
  const normalizedValue = typeof value === 'number'
    ? value
    : Number(String(value ?? 0).replace(/[^\d.-]/g, ''));
  const amount = Number.isFinite(normalizedValue) ? normalizedValue : 0;
  return `${new Intl.NumberFormat('ru-RU').format(amount)} ${escapeHtml(currency)}`;
}

export function buildPanelReceiptPrintableHtml(receiptPayload) {
  const payment = receiptPayload?.payment || {};
  const patient = receiptPayload?.patient || {};
  const services = Array.isArray(receiptPayload?.services) ? receiptPayload.services : [];
  const currency = services[0]?.currency || 'UZS';
  const issuedAt = new Date().toLocaleString('ru-RU');

  const serviceRows = services.length > 0
    ? services.map((service) => `
        <tr>
          <td>${escapeHtml(service?.name || 'Услуга')}</td>
          <td class="center">${escapeHtml(service?.quantity || 1)}</td>
          <td class="right">${formatMoney(service?.price, service?.currency || currency)}</td>
          <td class="right">${formatMoney(service?.total, service?.currency || currency)}</td>
        </tr>
      `).join('')
    : `
      <tr>
        <td>${escapeHtml('Услуга')}</td>
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
              <span>${escapeHtml(payment?.status || 'paid')}</span>
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

export function printPanelReceiptInBrowser(receiptPayload) {
  return openPrintableWindow({
    features: 'width=720,height=900',
    html: buildPanelReceiptPrintableHtml(receiptPayload),
    logger,
  });
}
