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
  const { t } = useTranslation();
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
        title="Откройте из Telegram"
        description="Защищённая запись требует Telegram Mini App identity перед созданием визита."
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
            <div className="pp-card-title">Заявка на запись</div>
            <p className="pp-card-subtitle">Создайте защищённую заявку на запись, привязанную к вашему Telegram-профилю пациента.</p>
          </div>
          <Badge variant={createdBooking ? 'success' : 'info'}>
            {createdBooking ? 'Создана' : 'Mini App защищено'}
          </Badge>
        </div>
        <div className="pp-card-body pp-grid-2">
          <Input
            type="date"
            label="Дата"
            value={bookingForm.appointmentDate}
            disabled={isBusy}
            // L-M-11 fix: min=today — запрещаем past-dates на клиенте
            min={getTodayDateInputValue()}
            required
            onChange={(event) => handleChange('appointmentDate', event.target.value)}
          />
          <Input
            type="time"
            label="Предпочтительное время"
            value={bookingForm.appointmentTime}
            disabled={isBusy}
            onChange={(event) => handleChange('appointmentTime', event.target.value)}
          />
          <Input
            label="Отделение"
            value={bookingForm.department}
            disabled={isBusy}
            maxLength={64}
            placeholder="Например: Кардиология"
            onChange={(event) => handleChange('department', event.target.value)}
          />
          <Input
            label="Услуги"
            value={bookingForm.servicesText}
            disabled={isBusy}
            placeholder="Консультация, анализы"
            onChange={(event) => handleChange('servicesText', event.target.value)}
          />
          <div className="pp-grid-span-2">
            <Textarea
              label="Комментарий"
              value={bookingForm.notes}
              disabled={isBusy}
              minRows={3}
              maxRows={6}
              maxLength={1000}
              placeholder="Необязательный комментарий для регистратуры"
              onChange={(event) => handleChange('notes', event.target.value)}
            />
          </div>

          {appointment && (
            <div className="pp-grid-span-2 pp-booking-summary">
              <div className="pp-summary-title">Сводка записи</div>
              <div className="pp-summary-grid">
                <div>Дата: {appointment.appointment_date}</div>
                <div>Время: {appointment.appointment_time || 'Регистратура подтвердит'}</div>
                <div>Отделение: {appointment.department || 'Не указано'}</div>
                <div>Оплата: {appointment.payment_type} / {appointment.payment_currency}</div>
              </div>
              {Array.isArray(appointment.services) && appointment.services.length > 0 && (
                <div className="pp-summary-services">Услуги: {appointment.services.join(', ')}</div>
              )}
            </div>
          )}

          {createdBooking && (
            <div className="pp-grid-span-2 pp-message pp-message--success" role="status">
              <Icon name="checkmark.circle" size={16} />
              Заявка на визит #{createdBooking.appointment_id} создана.
            </div>
          )}
          {bookingError && (
            <div className="pp-grid-span-2 pp-message pp-message--error" role="alert">
              <Icon name="exclamationmark.triangle" size={16} />
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
              <Icon name="doc.text" size={16} />
              Проверить заявку
            </Button>
            <Button
              variant="primary"
              size="small"
              disabled={isBusy || !bookingForm.appointmentDate}
              loading={bookingStatus === 'creating'}
              onClick={createBooking}
            >
              <Icon name="calendar" size={16} />
              Записаться
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PatientBookingPanel;
