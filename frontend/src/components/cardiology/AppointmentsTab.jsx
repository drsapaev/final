/**
 * AppointmentsTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "Записи" (appointments) tab content:
 *   1. Header with AppointmentSummaryBar (total/waiting/called/completed + refresh)
 *   2. EnhancedAppointmentsTable or Skeleton or empty state
 *
 * All state and handlers stay in the parent.
 */

import PropTypes from 'prop-types';
import { Calendar } from 'lucide-react';
import { MacOSCard, Skeleton, MacOSEmptyState } from '../ui/macos';
import AppointmentSummaryBar from '../doctor/AppointmentSummaryBar';
import EnhancedAppointmentsTable from '../tables/EnhancedAppointmentsTable';
import { useTranslation } from '../../i18n/useTranslation';

export function AppointmentsTab({
  appointments = [],
  appointmentsLoading = false,
  appointmentSummaryItems = [],
  onRefresh,
  onRowClick,
  onActionClick,
  services = {},
  isDark = false,
}) {
  const { t } = useTranslation();
  return (
    <div style={{ width: '100%', maxWidth: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard className="cardio-card-fullwidth">
        <div className="cardio-appointments-header">
          <h3 className="cardio-appointments-title">
            <Calendar size={20} className="cardio-icon-mr" style={{ marginRight: 'var(--mac-spacing-3)', color: 'var(--mac-accent)' }} />
            {t('cardio.cardio_appt_title')}
          </h3>
          <AppointmentSummaryBar
            ariaLabel={t('cardio.cardio_appt_summary_aria')}
            items={appointmentSummaryItems}
            onRefresh={onRefresh}
            refreshDisabled={appointmentsLoading}
            buttonProps={{ variant: 'outline' }}
          />
        </div>

        {appointmentsLoading ? (
          <Skeleton type="table" count={5} />
        ) : appointments.length === 0 ? (
          <MacOSEmptyState type="calendar" title={t('cardio.cardio_appt_empty_title')} description={t('cardio.cardio_appt_empty_desc')} />
        ) : (
          <EnhancedAppointmentsTable
            data={appointments}
            loading={appointmentsLoading}
            theme={isDark ? 'dark' : 'light'}
            language="ru"
            selectedRows={new Set()}
            outerBorder={false}
            services={services}
            showCheckboxes={false}
            view="doctor"
            onRowClick={onRowClick}
            onActionClick={onActionClick}
          />
        )}
      </MacOSCard>
    </div>
  );
}

AppointmentsTab.propTypes = {
  appointments: PropTypes.array,
  appointmentsLoading: PropTypes.bool,
  appointmentSummaryItems: PropTypes.array,
  onRefresh: PropTypes.func.isRequired,
  onRowClick: PropTypes.func,
  onActionClick: PropTypes.func,
  services: PropTypes.object,
  isDark: PropTypes.bool,
};

export default AppointmentsTab;
