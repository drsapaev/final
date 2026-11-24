import { Badge } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import { formatLabStatus, getLabStatusVariant } from './labUiLabels';

interface Props {
  appointment: Record<string, unknown> | null;
  report: Record<string, unknown> | null;
  orderId: number | null;
}

export default function LabOrderIdentity({ appointment, report, orderId }: Props) {
  const { t, language } = useTranslation();
  const snapshot = report?.patient_snapshot as Record<string, unknown> | undefined;
  const patientId = appointment?.patient_id ?? report?.patient_id;
  const visits = appointment?.visit_id ?? report?.visit_id;
  const birthDate = snapshot?.birth_date;
  const parsedBirthDate = typeof birthDate === 'string' ? new Date(`${birthDate}T00:00:00Z`) : null;
  const formattedBirthDate = parsedBirthDate && Number.isFinite(parsedBirthDate.getTime())
    ? new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeZone: 'UTC' }).format(parsedBirthDate)
    : appointment?.patient_birth_year;
  const formattedAge = typeof snapshot?.age_years === 'number' && snapshot.age_years > 0
    ? t('labWorkspace.ageYears', { count: snapshot.age_years })
    : typeof snapshot?.age_months === 'number' && snapshot.age_months > 0
      ? t('labWorkspace.ageMonths', { count: snapshot.age_months })
      : typeof snapshot?.age_days === 'number'
        ? t('labWorkspace.ageDays', { count: snapshot.age_days }) : null;
  const barcodes = Array.isArray(appointment?.specimen_barcodes) ? appointment.specimen_barcodes : [];
  const name = appointment?.patient_fio || snapshot?.full_name || t('queue.patient_no_name');

  return (
    <header className="lab-order-identity" aria-labelledby="lab-order-title">
      <h2 id="lab-order-title" tabIndex={-1}>{String(name)}</h2>
      <dl className="lab-order-identifiers">
        <div><dt>{t('labWorkspace.patientId')}</dt><dd>{patientId != null ? `#${String(patientId)}` : '—'}</dd></div>
        <div><dt>{t('labWorkspace.birthDate')}</dt><dd>{formattedBirthDate != null ? String(formattedBirthDate) : '—'}</dd></div>
        {formattedAge && <div><dt>{t('labWorkspace.age')}</dt><dd>{formattedAge}</dd></div>}
        <div><dt>{t('queue.visit')}</dt><dd>{visits != null ? `#${String(visits)}` : '—'}</dd></div>
        <div><dt>{t('labWorkspace.orderId')}</dt><dd>{orderId != null ? `#${orderId}` : '—'}</dd></div>
        {report?.id != null && <div>
          <dt className="sr-only">{t('labWorkspace.reportId')}</dt>
          <dd>{t('labWorkspace.reportId')} #{String(report.id)}</dd>
        </div>}
        {barcodes.length > 0 && <div><dt>{t('labWorkspace.specimens')}</dt><dd>{barcodes.join(', ')}</dd></div>}
      </dl>
      {typeof report?.status === 'string' && (
        <Badge variant={getLabStatusVariant(report.status)}>{formatLabStatus(report.status, t)}</Badge>
      )}
    </header>
  );
}
