import { Button, Card } from '../../../components/ui/macos';
import DentalVisitScreen from '../../../components/dental/DentalVisitScreen';
import type { SelectedPatient } from '../dentistContracts';

/**
 * PR-UI-15-6: the visits tab view — verbatim JSX of the former
 * DentistPanelUnified.renderVisits (registrar/cashier/doctor views
 * decomposition precedent).
 *
 * Queue-selected patient → the single DentalVisitScreen; otherwise point
 * back to the single patient search surface.
 */
export default function DentistVisitsView({
  selectedPatient,
  loading,
  onCompleteVisit,
  onBackToQueue,
  onGoToPatients,
  tI18n,
}: {
  selectedPatient: SelectedPatient | Record<string, unknown> | null;
  loading: boolean;
  onCompleteVisit: () => void;
  onBackToQueue: () => void;
  onGoToPatients: () => void;
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

  // Keep patient search in the Patients tab; do not duplicate patient cards here.
  return (
    <div className="dental-flex-col dental-gap-16">
      <Card padding="large">
        <h2 className="dental-text-primary">{tI18n('dental.dental_panel_visits_title')}</h2>
        <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_visits_subtitle')}</p>
        <div className="dental-flex dental-gap-8 dental-mt-16">
          <Button variant="outline" onClick={onGoToPatients}>{tI18n('dental.dental_dpt_title')}</Button>
          <Button variant="outline" onClick={onBackToQueue}>
            {tI18n('dental.dental_dpt_go_queue')}
          </Button>
        </div>
      </Card>
    </div>);
}
