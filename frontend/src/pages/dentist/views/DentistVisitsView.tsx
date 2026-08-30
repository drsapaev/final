import { Card } from '../../../components/ui/macos';
import DentalVisitScreen from '../../../components/dental/DentalVisitScreen';
import type { SelectedPatient } from '../dentistContracts';
import { dentalCardKeyDown } from '../dentistCardA11y';

/**
 * PR-UI-15-6: the visits tab view — verbatim JSX of the former
 * DentistPanelUnified.renderVisits (registrar/cashier/doctor views
 * decomposition precedent).
 *
 * Queue-selected patient → the minimal DentalVisitScreen; otherwise the
 * patient-pick grid that opens the EMR v2 visit protocol.
 */
export default function DentistVisitsView({
  selectedPatient,
  patients,
  loading,
  onCompleteVisit,
  onVisitProtocol,
  onBackToQueue,
  tI18n,
}: {
  selectedPatient: SelectedPatient | Record<string, unknown> | null;
  patients: SelectedPatient[];
  loading: boolean;
  onCompleteVisit: () => void;
  onVisitProtocol: (patient: SelectedPatient | Record<string, unknown> | null) => void;
  onBackToQueue: () => void;
  tI18n: (key: string, params?: Record<string, unknown>) => string;
}) {
  // Если выбран пациент из очереди - показываем минималистичный DentalVisitScreen
  if (selectedPatient) {
    return (
      <DentalVisitScreen
        patient={selectedPatient as Record<string, unknown>}
        onCompleteVisit={onCompleteVisit}
        onBackToQueue={onBackToQueue}
        loading={loading}
      />
    );
  }

  // Иначе показываем список пациентов для выбора протокола
  return (
    <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_visits_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_visits_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
          <div
            key={patient.id}
            role="button"
            tabIndex={0}
            aria-label={tI18n('dental.dental_panel_aria_visit')}
            className="dental-card-btn"
            onClick={() => onVisitProtocol(patient)}
            onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => dentalCardKeyDown(event, () => onVisitProtocol(patient))}
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
              e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            }}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
              e.currentTarget.style.background = 'transparent';
            }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-purple dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_visit_action')}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>);
}
