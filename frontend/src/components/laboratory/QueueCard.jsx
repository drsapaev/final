import { memo } from 'react';
import PropTypes from 'prop-types';
import { Badge, Icon } from '../ui/macos';
import {
  formatLabStatus,
  formatPaymentStatus,
  formatSpecialtyLabel,
  getLabStatusVariant,
} from './labUiLabels';

import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
/**
 * STRAT#28: QueueCard — extracted from LabQueueWorkbench, wrapped in React.memo.
 *
 * Ранее каждая карточка пациента рендерилась inline в LabQueueWorkbench.
 * При вводе в search box ВСЕ карточки re-renderились, даже если их данные
 * не изменились. React.memo предотвращает re-render когда props не изменились
 * (appointment object identity, isSelected boolean, onOpenAppointment callback).
 *
 * Performance impact: при 50+ записях в очереди, typing в search box
 * вызывает re-render только отфильтрованных карточек, а не всех.
 */
function QueueCard({ appointment, isSelected = false, onOpenAppointment }) {
  const { t } = useTranslation();
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpenAppointment(appointment)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpenAppointment(appointment);
        }
      }}
      className={`lqw-queue-card ${isSelected ? 'lqw-queue-card-selected' : ''}`}
    >
      <div className="lqw-card-top">
        <div className="lqw-card-info">
          <div className="lqw-card-name">
            {appointment.patient_fio || i18n.t('queue.patient_no_name')}
          </div>
          <div className="lqw-card-meta">
            {i18n.t('queue.visit')}: {appointment.visit_id || i18n.t('queue.visit_not_linked')} | {i18n.t('queue.phone')}:{' '}
            <MaskedPhone phone={appointment.patient_phone} />
          </div>
        </div>
        <Badge variant={getLabStatusVariant(appointment.status)}>
          {formatLabStatus(appointment.status)}
        </Badge>
      </div>

      <div className="lqw-card-services">
        <strong>{i18n.t('queue.services')}:</strong> {formatServices(appointment)}
      </div>

      <div className="lqw-meta-row">
        <Badge variant="primary">{formatSpecialtyLabel(appointment.specialty)}</Badge>
        {appointment.payment_status && <Badge variant="info">{i18n.t('queue.payment')}: {formatPaymentStatus(appointment.payment_status)}</Badge>}
        {appointment.appointment_time && <Badge variant="default">{appointment.appointment_time}</Badge>}
        {appointment.report_template_name && <Badge variant="info">{appointment.report_template_name}</Badge>}
      </div>

      <div className="lqw-card-bottom">
        <div className="lqw-card-id">
          <details className="lqw-pii-details">
            <summary
              className="lqw-pii-summary"
              aria-label={i18n.t('queue.patient_id_aria')}
            >
              {i18n.t('queue.patient_id_label')} ▸
            </summary>
            <span className="lqw-pii-value">
              {appointment.patient_id}
            </span>
          </details>
        </div>
        <Badge variant={appointment.report_instance_id ? 'success' : 'info'}>
          <Icon name="doc.text" size={12} />
          {appointment.report_instance_id ? i18n.t('queue.report_exists') : i18n.t('queue.report_new')}
        </Badge>
      </div>
    </div>
  );
}

// Inline MaskedPhone — same as in LabQueueWorkbench, kept here for encapsulation.
function maskPhone(phone) {
  if (!phone || typeof phone !== 'string') return '';
  const trimmed = phone.trim();
  if (!trimmed) return '';
  const digits = trimmed.replace(/\D/g, '');
  if (digits.length < 4) return '***';
  const lastTwo = digits.slice(-2);
  const countryMatch = trimmed.match(/^\+\d{1,3}/);
  const country = countryMatch ? countryMatch[0] : '+';
  return `${country} ***-**-${lastTwo}`;
}

function MaskedPhone({ phone }) {
  if (!phone) return <span className="lqw-masked-phone-empty">{i18n.t('pii.phone_not_set')}</span>;
  return (
    <span className="lqw-masked-phone-text">{maskPhone(phone)}</span>
  );
}

MaskedPhone.propTypes = { phone: PropTypes.string };

function formatServices(appointment) {
  const serviceDetails = appointment?.service_details || [];
  if (serviceDetails.length > 0) {
    return serviceDetails
      .map((item) => item?.name || item?.code)
      .filter(Boolean)
      .join(', ');
  }
  const serviceCodes = appointment?.service_codes || [];
  if (serviceCodes.length > 0) {
    return serviceCodes.join(', ');
  }
  return i18n.t('pii.no_services');
}

QueueCard.propTypes = {
  appointment: PropTypes.object.isRequired,
  isSelected: PropTypes.bool,
  onOpenAppointment: PropTypes.func.isRequired,
};

// React.memo with default shallow comparison — prevents re-render when
// appointment object identity, isSelected, and onOpenAppointment are unchanged.
export default memo(QueueCard);
