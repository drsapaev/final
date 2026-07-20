
import { useState } from 'react';
import {
  Badge, Button, Icon, Input, Textarea,
} from '../ui/macos';
import { api } from '../../api/client';
import {
  readTelegramMiniAppInitData,
  getDefaultAppointmentDate,
  getTodayDateInputValue,
  splitBookingServices,
  describePatientError,
} from './patientUtils';
import PanelEmptyState from './PanelEmptyState';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";

/**
 * L-H-4 fix: PatientBookingPanel выделен в отдельный файл (~120 строк).
 *
 * L-H-1 fix: все строки на русском (были на английском).
 * L-H-2 fix: Tailwind classes заменены на CSS-классы .pp-*
 * L-H-5 fix: добавлен skeleton-loading при preview/create.
 * L-H-8 fix: lucide-direct icons заменены на macos <Icon>.
 * L-M-11 fix: date-input имеет min=today (запрет past-dates на клиенте).
 *
 * Форма записи на приём через Telegram Mini App identity.
 * Поток: preview → review summary → create booking.
 */
function PatientBookingPanel() {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [bookingForm, setBookingForm] = useState(() => ({
    appointmentDate: getDefaultAppointmentDate(),
    appointmentTime: '',
    department: '',
    servicesText: '',
    notes: '',
  }));
  const [bookingStatus, setBookingStatus] = useState('idle');
  const [bookingPreview, setBookingPreview] = useState(null);
  const [createdBooking, setCreatedBooking] = useState(null);
  const [bookingError, setBookingError] = useState('');
  const initData = readTelegramMiniAppInitData();
  const isBusy = bookingStatus === 'previewing' || bookingStatus === 'creating';
  const appointment = bookingPreview?.appointment || createdBooking?.preview?.appointment || null;

  if (!initData) {
    return (
      <PanelEmptyState
        icon="calendar"
        title={t('patient.pat_book_missing_init_title')}
        description={t('patient.pat_book_missing_init_desc')}
      />
    );
  }

  const handleChange = (field, value) => {
    setBookingForm((current) => ({
      ...current,
      [field]: value,
    }));
    setBookingError('');
  };

  const buildBookingPayload = () => ({
    initData,
    appointmentDate: bookingForm.appointmentDate,
    appointmentTime: bookingForm.appointmentTime || null,
    department: bookingForm.department.trim() || null,
    notes: bookingForm.notes.trim() || null,
    services: splitBookingServices(bookingForm.servicesText),
  });

  const previewBooking = async () => {
    setBookingStatus('previewing');
    setBookingError('');
    setCreatedBooking(null);

    try {
      const response = await api.post('/telegram/mini-app/appointments/preview', buildBookingPayload());
      setBookingPreview(response.data);
      setBookingStatus('preview-ready');
    } catch (err) {
      const reason = err?.response?.data?.detail?.reason || 'booking_preview_failed';
      setBookingError(describePatientError('booking', reason));
      setBookingStatus('error');
    }
  };

  const createBooking = async () => {
    setBookingStatus('creating');
    setBookingError('');

    try {
      const response = await api.post('/telegram/mini-app/appointments', buildBookingPayload());
      setCreatedBooking(response.data);
      setBookingPreview(response.data?.preview || null);
      setBookingStatus('created');
    } catch (err) {
      const reason = err?.response?.data?.detail?.reason || 'booking_create_failed';
      setBookingError(describePatientError('booking', reason));
      setBookingStatus('error');
    }
  };

  return (
    <div className="pp-booking-root">
      <div className="pp-card">
        <div className="pp-card-header">
          <div>
            <div className="pp-card-title">{t('patient.pat_book_title')}</div>
            <p className="pp-card-subtitle">{t('patient.pat_book_subtitle')}</p>
          </div>
          <Badge variant={createdBooking ? 'success' : 'info'}>
            {createdBooking ? t('patient.pat_book_status_created') : t('patient.pat_book_status_secure')}
          </Badge>
        </div>
        <div className="pp-card-body pp-grid-2">
          <Input
            type="date"
            label={t('patient.pat_book_label_date')}
            value={bookingForm.appointmentDate}
            disabled={isBusy}
            // L-M-11 fix: min=today — запрещаем past-dates на клиенте
            min={getTodayDateInputValue()}
            required
            onChange={(event) => handleChange('appointmentDate', event.target.value)}
          />
          <Input
            type="time"
            label={t('patient.pat_book_label_time')}
            value={bookingForm.appointmentTime}
            disabled={isBusy}
            onChange={(event) => handleChange('appointmentTime', event.target.value)}
          />
          <Input
            label={t('patient.pat_book_label_department')}
            value={bookingForm.department}
            disabled={isBusy}
            maxLength={64}
            placeholder={t('patient.pat_book_placeholder_department')}
            onChange={(event) => handleChange('department', event.target.value)}
          />
          <Input
            label={t('patient.pat_book_label_services')}
            value={bookingForm.servicesText}
            disabled={isBusy}
            placeholder={t('patient.pat_book_placeholder_services')}
            onChange={(event) => handleChange('servicesText', event.target.value)}
          />
          <div className="pp-grid-span-2">
            <Textarea
              label={t('patient.pat_book_label_notes')}
              value={bookingForm.notes}
              disabled={isBusy}
              minRows={3}
              maxRows={6}
              maxLength={1000}
              placeholder={t('patient.pat_book_placeholder_notes')}
              onChange={(event) => handleChange('notes', event.target.value)}
            />
          </div>

          {appointment && (
            <div className="pp-grid-span-2 pp-booking-summary">
              <div className="pp-summary-title">{t('patient.pat_book_summary_title')}</div>
              <div className="pp-summary-grid">
                <div>{t('patient.pat_book_summary_date', { value: appointment.appointment_date })}</div>
                <div>{t('patient.pat_book_summary_time', { value: appointment.appointment_time || t('patient.pat_book_summary_time_pending') })}</div>
                <div>{t('patient.pat_book_summary_department', { value: appointment.department || t('patient.pat_book_summary_department_pending') })}</div>
                <div>{t('patient.pat_book_summary_payment', { type: appointment.payment_type, currency: appointment.payment_currency })}</div>
              </div>
              {Array.isArray(appointment.services) && appointment.services.length > 0 && (
                <div className="pp-summary-services">{t('patient.pat_book_summary_services', { value: appointment.services.join(', ') })}</div>
              )}
            </div>
          )}

          {createdBooking && (
            <div className="pp-grid-span-2 pp-message pp-message--success" role="status">
              <Icon name="checkmark.circle" size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
              {t('patient.pat_book_created', { id: createdBooking.appointment_id })}
            </div>
          )}
          {bookingError && (
            <div className="pp-grid-span-2 pp-message pp-message--error" role="alert">
              <Icon name="exclamationmark.triangle" size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
              {bookingError}
            </div>
          )}

          <div className="pp-grid-span-2 pp-actions-row">
            <Button
              variant="outline"
              size="small"
              disabled={isBusy || !bookingForm.appointmentDate}
              loading={bookingStatus === 'previewing'}
              onClick={previewBooking}
            >
              <Icon name="doc.text" size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
              {t('patient.pat_book_preview_button')}
            </Button>
            <Button
              variant="primary"
              size="small"
              disabled={isBusy || !bookingForm.appointmentDate}
              loading={bookingStatus === 'creating'}
              onClick={createBooking}
            >
              <Icon name="calendar" size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
              {t('patient.pat_book_book_button')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PatientBookingPanel;
