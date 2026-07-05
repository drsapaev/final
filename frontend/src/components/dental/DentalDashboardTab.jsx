/**
 * DentalDashboardTab — R-15: extracted from DentistPanelUnified.
 * Renders the "Обзор" (dashboard) tab: quick stats + recent appointments.
 */
import PropTypes from 'prop-types';
import { Card, Button } from '../ui/macos';
import { Calendar, Users, Activity, FileText } from 'lucide-react';

export function DentalDashboardTab({
  appointments = [],
  patients = [],
  onGoToAppointments,
  onGoToPatients,
}) {
  const totalAppointments = appointments.length;
  const waitingCount = appointments.filter(a => ['waiting', 'confirmed', 'pending'].includes(a.status)).length;
  const calledCount = appointments.filter(a => ['called', 'in_progress'].includes(a.status)).length;
  const completedCount = appointments.filter(a => ['completed', 'done'].includes(a.status)).length;

  return (
    <div className="dental-flex-col dental-gap-24">
      <div className="dental-grid-4 dental-gap-16">
        <Card padding="md">
          <div className="dental-flex-between">
            <div>
              <div className="dental-text-desc dental-text-secondary">Всего записей</div>
              <div className="dental-text-value dental-text-primary">{totalAppointments}</div>
            </div>
            <Calendar size={24} className="dental-text-secondary" />
          </div>
        </Card>
        <Card padding="md">
          <div className="dental-flex-between">
            <div>
              <div className="dental-text-desc dental-text-secondary">Ожидают</div>
              <div className="dental-text-value dental-text-primary">{waitingCount}</div>
            </div>
            <Activity size={24} className="dental-text-secondary" />
          </div>
        </Card>
        <Card padding="md">
          <div className="dental-flex-between">
            <div>
              <div className="dental-text-desc dental-text-secondary">Пациентов</div>
              <div className="dental-text-value dental-text-primary">{patients.length}</div>
            </div>
            <Users size={24} className="dental-text-secondary" />
          </div>
        </Card>
        <Card padding="md">
          <div className="dental-flex-between">
            <div>
              <div className="dental-text-desc dental-text-secondary">Принято</div>
              <div className="dental-text-value dental-text-primary">{completedCount}</div>
            </div>
            <FileText size={24} className="dental-text-secondary" />
          </div>
        </Card>
      </div>

      <Card padding="lg">
        <div className="dental-flex-between-16">
          <h3 className="dental-text-primary">Быстрые действия</h3>
        </div>
        <div className="dental-flex dental-gap-12 dental-mt-16">
          <Button onClick={onGoToAppointments}>Записи</Button>
          <Button variant="outline" onClick={onGoToPatients}>Пациенты</Button>
        </div>
      </Card>
    </div>
  );
}

DentalDashboardTab.propTypes = {
  appointments: PropTypes.array,
  patients: PropTypes.array,
  onGoToAppointments: PropTypes.func,
  onGoToPatients: PropTypes.func,
};

export default DentalDashboardTab;
