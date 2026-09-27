/** Patient-specific visit, skin examination, and procedure history. */
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
          <Calendar size={20} className="derma-icon-mr derma-text-secondary" aria-hidden="true" />
          {t('derma.derma_panel_patient_history_title')}
        </h3>

        <div className="derma-grid-auto-350-24">
          <section>
            <h4 className="derma-h4-16-600">
              {t('derma.derma_panel_patient_history_appointments')} ({appointments.length})
            </h4>
            {appointments.length > 0 ? (
              <div className="derma-history-list-scroll">
                {appointments.map((appointment) => (
                  <article key={appointment.id} className="derma-card-p12-bg2-13">
                    <div className="derma-flex-between-top">
                      <Badge variant="info">{appointment.appointment_date}</Badge>
                      {appointment.appointment_time && (
                        <span className="derma-p-14-secondary">{appointment.appointment_time}</span>
                      )}
                    </div>
                    {[appointment.department, appointment.status].filter(Boolean).length > 0 && (
                      <p className="derma-p-14-secondary">
                        {[appointment.department, appointment.status].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <div className="derma-p-24 derma-text-center derma-p-14-secondary">
                {t('derma.derma_panel_patient_history_no_appointments')}
              </div>
            )}
          </section>

          <section>
            <h4 className="derma-h4-16-600">
              {t('derma.derma_panel_patient_history_examinations')} ({skinExaminations.length})
            </h4>
            {skinExaminations.length > 0 ? (
              <div className="derma-history-list-scroll">
                {skinExaminations.map((exam) => (
                  <article key={exam.id} className="derma-card-p12-bg2-13">
                    <div className="derma-flex-between-top">
                      <Badge variant="info">{exam.exam_date || exam.examination_date}</Badge>
                      <span className="derma-p-14-secondary">
                        {[exam.skin_type, exam.skin_condition].filter(Boolean).join(' · ')}
                      </span>
                    </div>
                    {exam.diagnosis && <p className="derma-p-14-secondary">{exam.diagnosis}</p>}
                  </article>
                ))}
              </div>
            ) : (
              <div className="derma-p-24 derma-text-center derma-p-14-secondary">
                {t('derma.derma_panel_patient_history_no_examinations')}
              </div>
            )}
          </section>

          <section>
            <h4 className="derma-h4-16-600">
              {t('derma.derma_panel_patient_history_procedures')} ({cosmeticProcedures.length})
            </h4>
            {cosmeticProcedures.length > 0 ? (
              <div className="derma-history-list-scroll">
                {cosmeticProcedures.map((procedure) => (
                  <article key={procedure.id} className="derma-card-p12-bg2-13">
                    <div className="derma-flex-between-top">
                      <Badge variant="info">{procedure.procedure_date}</Badge>
                    </div>
                    {procedure.procedure_type && (
                      <p className="derma-p-14-secondary">
                        {[procedure.procedure_type, procedure.area_treated].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <div className="derma-p-24 derma-text-center derma-p-14-secondary">
                {t('derma.derma_panel_patient_history_no_procedures')}
              </div>
            )}
          </section>
        </div>
      </Card>
    </div>
  );
}

export default DermaHistoryTab;
