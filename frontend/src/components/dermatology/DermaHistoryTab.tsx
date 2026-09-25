
/**
 * DermaHistoryTab — R-15: extracted from DermatologistPanelUnified.
 * Renders the "История" tab: skin examinations + cosmetic procedures history.
 */
import { Calendar } from 'lucide-react';
import { Card, Badge } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import type {
  DermatologyAppointmentHistoryItem,
  DermatologyCosmeticProcedure,
  DermatologySkinExamination,
} from '../../pages/useDermatologyPatientHistory';

interface DermaHistoryTabProps {
  appointments?: DermatologyAppointmentHistoryItem[];
  skinExaminations?: DermatologySkinExamination[];
  cosmeticProcedures?: DermatologyCosmeticProcedure[];
}

export function DermaHistoryTab({
  appointments = [],
  skinExaminations = [],
  cosmeticProcedures = [],
}: DermaHistoryTabProps) {
  const { t } = useTranslation();

  return (
    <div className="derma-flex-col-24">
      <Card className="derma-p-8">
        <h3 className="derma-flex-center">
          <Calendar size={20} className="derma-icon-mr derma-text-secondary" />
          {t('derma.derma_panel_patient_history_title')}
        </h3>

        <div className="derma-grid-auto-350-24">
          <div>
            <h4 style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-3)', color: 'var(--mac-text-primary)' }}>
              {t('derma.derma_panel_patient_history_appointments')} ({appointments.length})
            </h4>
            {appointments.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
                {appointments.map((appointment) => (
                  <div key={appointment.id} style={{ padding: 'var(--mac-spacing-3)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-md)', background: 'var(--mac-surface)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--mac-spacing-2)', marginBottom: 'var(--mac-spacing-1)' }}>
                      <Badge variant="info">{appointment.appointment_date}</Badge>
                      {appointment.appointment_time && (
                        <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                          {appointment.appointment_time}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                      {[appointment.department, appointment.status].filter(Boolean).join(' · ')}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: 'var(--mac-spacing-6)', textAlign: 'center', color: 'var(--mac-text-secondary)' }}>
                {t('derma.derma_panel_patient_history_no_appointments')}
              </div>
            )}
          </div>

          {/* Skin examinations history */}
          <div>
            <h4 style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-3)', color: 'var(--mac-text-primary)' }}>
              {t('derma.derma_panel_patient_history_examinations')} ({skinExaminations.length})
            </h4>
            {skinExaminations.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
                {skinExaminations.map((exam) => (
                  <div key={exam.id} style={{ padding: 'var(--mac-spacing-3)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-md)', background: 'var(--mac-surface)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-1)' }}>
                      <Badge variant="info">{exam.exam_date || exam.examination_date}</Badge>
                      <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                        {exam.skin_type} - {exam.skin_condition}
                      </span>
                    </div>
                    {exam.diagnosis && <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>{exam.diagnosis}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: 'var(--mac-spacing-6)', textAlign: 'center', color: 'var(--mac-text-secondary)' }}>
                {t('derma.derma_panel_patient_history_no_examinations')}
              </div>
            )}
          </div>

          {/* Cosmetic procedures history */}
          <div>
            <h4 style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-3)', color: 'var(--mac-text-primary)' }}>
              {t('derma.derma_panel_patient_history_procedures')} ({cosmeticProcedures.length})
            </h4>
            {cosmeticProcedures.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
                {cosmeticProcedures.map((proc) => (
                  <div key={proc.id} style={{ padding: 'var(--mac-spacing-3)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-md)', background: 'var(--mac-surface)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-1)' }}>
                      <Badge variant="info">{proc.procedure_date}</Badge>
                      <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                        {Number(proc.total_cost || 0).toLocaleString()} UZS
                      </span>
                    </div>
                    {proc.procedure_type && <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>{proc.procedure_type} - {proc.area_treated}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: 'var(--mac-spacing-6)', textAlign: 'center', color: 'var(--mac-text-secondary)' }}>
                {t('derma.derma_panel_patient_history_no_procedures')}
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}


export default DermaHistoryTab;
