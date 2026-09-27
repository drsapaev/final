
/**
 * VisitTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "Приём" (visit) tab content:
 *   1. Patient info card (name, phone, EMR audit badge from P-019)
 *   2. EMR container (EMRContainerV2 with all sections)
 *   3. Visit actions (completion lives alongside the EMR controls)
 *
 * When no patient is selected, renders an empty state.
 */

import { User, FileText, Calendar, Phone } from 'lucide-react';
import { Button, Card, AppEmpty } from '../ui/macos';
import { EMRContainerV2 } from '../emr-v2/EMRContainerV2';
import { formatRegistrarDate, formatRegistrarDateTime } from '../../utils/dateUtils';
import { useTranslation } from '../../i18n/useTranslation';
import React from 'react';

export function VisitTab({
  selectedPatient,
  emr,
  loading = false,
  onCancel,
  onComplete,
  onCompletionBlocked,
  onGoToAppointments,
  getColor,
  getFontSize,
}: {
  selectedPatient?: {
    patient_name?: string;
    patient?: { full_name?: string; id?: number };
    patient_id?: number;
    number?: string | number;
    phone?: string;
    visit_id?: number | string;
    status?: string | null;
  } | null;
  emr?: {
    id?: number | string;
    status?: string;
    version?: number;
    updated_at?: string;
    signed_at?: string;
    signed_by?: number;
  } | null;
  loading?: boolean;
  onCancel: () => void;
  onComplete: (savedData: Record<string, unknown>) => Promise<void> | void;
  onCompletionBlocked?: () => void;
  onGoToAppointments: () => void;
  getColor: (key: string) => string;
  getFontSize: (key: string) => string;
}): React.JSX.Element | null {
  const { t: rawT } = useTranslation(); const t = rawT;
  const isCompleted = ['served', 'completed', 'done'].includes(String(selectedPatient?.status ?? '').toLowerCase());
  // Empty state: no patient selected
  if (!selectedPatient) {
    return (
      <Card className="cardio-empty-state" style={{ padding: '48px' }}>
        <AppEmpty
          icon={Calendar}
          title={t('cardio.cardio_visit_empty_title')}
          description={t('cardio.cardio_visit_empty_desc')}
          action={
            <Button variant="outline" onClick={onGoToAppointments} style={{ marginTop: 'var(--mac-spacing-4)' }}>
              {t('cardio.cardio_visit_goto_appointments')}
            </Button>
          }
        />
      </Card>
    );
  }

  return (
    <div className="cardio-flex-col-visible" style={{ gap: 'var(--mac-spacing-6)' }}>
      {/* Patient info card */}
      <Card className="cardio-card-padded">
        <h3 className="cardio-section-heading">
          <User size={20} className="cardio-icon-mr cardio-icon-blue" />
          {t('cardio.cardio_visit_patient_label', { name: selectedPatient.patient_name || selectedPatient.patient?.full_name || `№${selectedPatient.number}` })}
        </h3>

        <div className="cardio-grid-auto">
          <div>
            <label className="cardio-form-label-block">{t('cardio.cardio_visit_fio_label')}</label>
            <div className="cardio-patient-name cardio-patient-name-primary">{selectedPatient.patient_name}</div>
          </div>

          {selectedPatient.phone && (
            <div>
              <label className="cardio-form-label-block">{t('common.phone')}</label>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <Phone size={16} style={{ marginRight: '6px', color: 'var(--mac-text-secondary)' }} />
                <span className="cardio-patient-name cardio-patient-name-primary">{selectedPatient.phone}</span>
              </div>
            </div>
          )}
        </div>

        {/* P-019: EMR audit badge */}
        {emr && (
          <div className="cardio-emr-audit-badge" style={{
            marginTop: 'var(--mac-spacing-3)',
            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 'var(--mac-spacing-3)',
            fontSize: getFontSize('sm'),
            color: getColor('textSecondary'),
            background: emr.status === 'signed' ? 'var(--mac-success-bg, #f0fdf4)' : 'var(--mac-surface-secondary, #f8fafc)',
            border: `1px solid ${emr.status === 'signed' ? 'var(--mac-success-border, #bbf7d0)' : getColor('border')}`,
            borderRadius: 'var(--mac-radius-md)',
          }}>
            <span style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: getColor('text') }}>EMR #{emr.id ?? '—'}</span>
            <span style={{
              padding: '2px 8px', borderRadius: 'var(--mac-radius-sm)', fontWeight: 'var(--mac-font-weight-semibold)', fontSize: 'var(--mac-font-size-xs)',
              textTransform: 'uppercase', letterSpacing: '0.5px',
              background: emr.status === 'signed' ? 'var(--mac-success)' : emr.status === 'amended' ? 'var(--mac-warning)' : 'var(--mac-text-secondary)',
              color: 'var(--mac-bg-primary)',
            }}>
              {emr.status || 'draft'}
            </span>
            {emr.version != null && <span title={t('cardio.cardio_visit_emr_version_title')}>v{emr.version}</span>}
            {emr.updated_at && (
              <span title={t('cardio.cardio_visit_emr_updated_title')}>
                {t('cardio.cardio_visit_emr_updated_prefix', { datetime: formatRegistrarDateTime(emr.updated_at, 'ru-RU') })}
              </span>
            )}
            {emr.signed_at && (
              <span title={t('cardio.cardio_visit_emr_signed_title')}>
                {t('cardio.cardio_visit_emr_signed_prefix', { date: formatRegistrarDate(emr.signed_at, 'ru-RU') })}
              </span>
            )}
            {emr.signed_by != null && emr.signed_by > 0 && <span title={t('cardio.cardio_visit_emr_signed_by_title')}>{t('cardio.cardio_visit_doctor_prefix', { id: emr.signed_by })}</span>}
          </div>
        )}
      </Card>

      {/* EMR container */}
      <Card className="cardio-card-padded">
        <h3 className="cardio-section-heading">
          <FileText size={20} className="cardio-icon-mr cardio-icon-blue" />
          {t('cardio.cardio_visit_emr_title')}
        </h3>
        <EMRContainerV2
          visitId={selectedPatient?.visit_id ?? ''}
          patientId={selectedPatient?.patient?.id || selectedPatient?.patient_id}
          specialty="cardiology"
          isReadOnly={isCompleted}
          completionBusy={loading}
          onComplete={isCompleted ? undefined : onComplete}
          onCompletionBlocked={onCompletionBlocked}
        />
      </Card>

      {/* Action buttons */}
      <Card className="cardio-card-padded">
        <div className="flex justify-end" style={{ gap: 'var(--mac-spacing-3)' }}>
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            {t(isCompleted ? 'cardio.cardio_visit_back_to_queue' : 'cardio.cardio_visit_cancel')}
          </Button>
        </div>
      </Card>
    </div>
  );
}


export default VisitTab;
