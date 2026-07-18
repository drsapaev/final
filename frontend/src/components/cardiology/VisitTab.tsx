
/**
 * VisitTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "Приём" (visit) tab content:
 *   1. Patient info card (name, phone, EMR audit badge from P-019)
 *   2. EMR container (EMRContainerV2 with all sections)
 *   3. Action buttons (Cancel + Complete visit)
 *
 * When no patient is selected, renders an empty state.
 */

import PropTypes from 'prop-types';
import { User, FileText, RefreshCw, Save, Calendar, Phone } from 'lucide-react';
import { Button, MacOSCard, MacOSEmptyState as MacOSEmptyStateRaw } from '../ui/macos';
import { EMRContainerV2 } from '../emr-v2/EMRContainerV2';
import { formatRegistrarDate, formatRegistrarDateTime } from '../../utils/dateUtils';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
const MacOSEmptyState = MacOSEmptyStateRaw as unknown as React.ComponentType<Record<string, unknown>>;

export function VisitTab({
  selectedPatient,
  emr,
  loading = false,
  onCancel,
  onComplete,
  onGoToAppointments,
  getColor,
  getFontSize,
}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // Empty state: no patient selected
  if (!selectedPatient) {
    return (
      <MacOSCard className="cardio-empty-state" style={{ padding: '48px' }}>
        <MacOSEmptyState
          icon={Calendar}
          title={t('cardio.cardio_visit_empty_title')}
          description={t('cardio.cardio_visit_empty_desc')}
          action={
            <Button variant="outline" onClick={onGoToAppointments} style={{ marginTop: 'var(--mac-spacing-4)' }}>
              {t('cardio.cardio_visit_goto_appointments')}
            </Button>
          }
        />
      </MacOSCard>
    );
  }

  return (
    <div className="cardio-flex-col-visible" style={{ gap: 'var(--mac-spacing-6)' }}>
      {/* Patient info card */}
      <MacOSCard className="cardio-card-padded">
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
      </MacOSCard>

      {/* EMR container */}
      <MacOSCard className="cardio-card-padded">
        <h3 className="cardio-section-heading">
          <FileText size={20} className="cardio-icon-mr cardio-icon-blue" />
          {t('cardio.cardio_visit_emr_title')}
        </h3>
        <EMRContainerV2
          visitId={selectedPatient?.visit_id}
          patientId={selectedPatient?.patient?.id || selectedPatient?.patient_id}
          specialty="cardiology"
        />
      </MacOSCard>

      {/* Action buttons */}
      <MacOSCard className="cardio-card-padded">
        <div className="flex justify-end" style={{ gap: 'var(--mac-spacing-3)' }}>
          <Button variant="outline" onClick={onCancel}>{t('cardio.cardio_visit_cancel')}</Button>
          <Button onClick={onComplete} disabled={loading}>
            {loading ? <RefreshCw size={16} className="cardio-icon-mr" /> : <Save size={16} className="cardio-icon-mr" />}
            {t('cardio.cardio_visit_complete')}
          </Button>
        </div>
      </MacOSCard>
    </div>
  );
}

VisitTab.propTypes = {
  selectedPatient: PropTypes.object,
  emr: PropTypes.object,
  loading: PropTypes.bool,
  onCancel: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
  onGoToAppointments: PropTypes.func.isRequired,
  getColor: PropTypes.func.isRequired,
  getFontSize: PropTypes.func.isRequired,
};

export default VisitTab;
