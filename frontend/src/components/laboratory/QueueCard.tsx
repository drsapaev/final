
import { memo } from 'react';
import { Badge } from '../ui/macos';
import {
  formatLabStatus,
  formatPaymentStatus,
  formatSpecialtyLabel,
  getLabStatusVariant,
} from './labUiLabels';

import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
import { FileText } from 'lucide-react';

const worklistStatuses = {
  pending: 'info', awaiting_specimen: 'warning', in_progress: 'info', in_review: 'info',
  held: 'warning', partial: 'warning', ready: 'success', canceled: 'default',
} as const;

interface QueueCardAppointment {
  patient_fio?: string;
  patient_id?: string | number;
  patient_phone?: string;
  visit_id?: string | number;
  status?: string;
  specialty?: string;
  payment_status?: string;
  appointment_time?: string;
  report_template_name?: string;
  report_instance_id?: string | number | null;
  service_details?: Array<{ name?: string; code?: string }>;
  service_codes?: string[];
  [key: string]: unknown;
}

interface QueueCardProps {
  appointment: QueueCardAppointment;
  isSelected?: boolean;
  onOpenAppointment: (appointment: QueueCardAppointment) => void;
}

interface MaskedPhoneProps {
  phone?: string;
}
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
function QueueCard({ appointment, isSelected = false, onOpenAppointment }: QueueCardProps) {
  const { t, language } = useTranslation();
  const worklist = typeof appointment.work_date === 'string';
  const worklistStatus = appointment.status as keyof typeof worklistStatuses;
  const progress = appointment.progress as {
    ordered_tests?: number | null; released_tests?: number | null; canceled_tests?: number | null;
    total_reports?: number; released_reports?: number;
  } | undefined;
  const dueAt = typeof appointment.due_at === 'string' ? new Date(appointment.due_at) : null;
  return (
    <div
      role="button"
      tabIndex={0}
      aria-current={isSelected || undefined}
      onClick={() => onOpenAppointment(appointment)}
      onKeyDown={(e: React.KeyboardEvent<HTMLElement>) => {
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
            {appointment.patient_fio || t('queue.patient_no_name')}
          </div>
          <div className="lqw-card-meta">
            {t('queue.visit')}: {appointment.visit_id || t('queue.visit_not_linked')}
            {worklist && appointment.order_id != null && <> · {t('labWorkspace.orderId')} #{String(appointment.order_id)}</>}
            {worklist && appointment.patient_birth_year != null && <> · {String(appointment.patient_birth_year)}</>}
            {!worklist && <> | {t('queue.phone')}: <MaskedPhone phone={appointment.patient_phone} /></>}
          </div>
        </div>
        <Badge variant={worklist ? worklistStatuses[worklistStatus] ?? 'default' : getLabStatusVariant(appointment.status ?? '')}>
          {worklist ? t(`labWorkspace.work_${worklistStatus}`) : formatLabStatus(appointment.status ?? '')}
        </Badge>
      </div>

      <div className="lqw-card-services">
        <strong>{t('queue.services')}:</strong> {formatServices(appointment)}
      </div>

      <div className="lqw-meta-row">
        {!worklist && <Badge variant="primary">{formatSpecialtyLabel(appointment.specialty ?? '')}</Badge>}
        {appointment.payment_status && <Badge variant="info">{t('queue.payment')}: {formatPaymentStatus(appointment.payment_status)}</Badge>}
        {appointment.appointment_time && <Badge variant="default">{appointment.appointment_time}</Badge>}
        {appointment.report_template_name && <Badge variant="info">{appointment.report_template_name ?? ''}</Badge>}
        {worklist && appointment.priority === 'urgent' && <Badge variant="warning">{t('labWorkspace.urgent')}</Badge>}
      </div>

      {worklist && (
        <div className="lqw-card-meta">
          {dueAt && Number.isFinite(dueAt.getTime()) && <div>
            {t('labWorkspace.dueAt')}: {new Intl.DateTimeFormat(language, {
              dateStyle: 'short', timeStyle: 'short', timeZone: 'Asia/Tashkent',
            }).format(dueAt)}
          </div>}
          {progress?.ordered_tests != null ? <div>{t('labWorkspace.progressTests', {
            released: progress.released_tests ?? 0, total: progress.ordered_tests, canceled: progress.canceled_tests ?? 0,
          })}</div> : progress?.total_reports != null && progress.total_reports > 0 && <div>{t('labWorkspace.progressReports', {
            released: progress.released_reports ?? 0, total: progress.total_reports,
          })}</div>}
          {typeof appointment.hold_reason === 'string' && <div>{t(`labWorkspace.hold_${appointment.hold_reason}`)}</div>}
        </div>
      )}

      <div className="lqw-card-bottom">
        <div className="lqw-card-id">
          {/* LABQ-FE-003 (audit 3886): the patient-ID disclosure is a peer
              interactive region — its clicks/keys must not bubble into the
              parent card's open-patient action. */}
          <details
            className="lqw-pii-details"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <summary
              className="lqw-pii-summary"
              aria-label={t('queue.patient_id_aria')}
            >
              {t('queue.patient_id_label')} ▸
            </summary>
            <span className="lqw-pii-value">
              {appointment.patient_id}
            </span>
          </details>
        </div>
        <Badge variant={appointment.report_instance_id ? 'success' : 'info'}>
          <FileText size={12} aria-hidden="true" />
          {appointment.report_instance_id ? t('queue.report_exists') : t('queue.report_new')}
        </Badge>
      </div>
    </div>
  );
}

// Inline MaskedPhone — same as in LabQueueWorkbench, kept here for encapsulation.
function maskPhone(phone?: string) {
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

function MaskedPhone({ phone }: MaskedPhoneProps) {
  if (!phone) return <span className="lqw-masked-phone-empty">{(i18n.t as unknown as (key: string) => string)('pii.phone_not_set')}</span>;
  return (
    <span className="lqw-masked-phone-text">{maskPhone(phone)}</span>
  );
}


function formatServices(appointment: QueueCardAppointment) {
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
  return (i18n.t as unknown as (key: string) => string)('pii.no_services');
}


// React.memo with default shallow comparison — prevents re-render when
// appointment object identity, isSelected, and onOpenAppointment are unchanged.
export default memo(QueueCard);
