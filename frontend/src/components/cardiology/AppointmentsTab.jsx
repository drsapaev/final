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
import { useTranslation } from '../../i18n/adapter';

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
  return (
    <div style={{ width: '100%', maxWidth: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard className="cardio-card-fullwidth">
        <div className="cardio-appointments-header">
          <h3 className="cardio-appointments-title">
            <Calendar size={20} className="cardio-icon-mr" style={{ marginRight: 'var(--mac-spacing-3)', color: 'var(--mac-accent)' }} />
            Записи к кардиологу
          </h3>
          <AppointmentSummaryBar
            ariaLabel="Сводка записей кардиолога"
            items={appointmentSummaryItems}
            onRefresh={onRefresh}
            refreshDisabled={appointmentsLoading}
            buttonProps={{ variant: 'outline' }}
          />
        </div>

        {appointmentsLoading ? (
          <Skeleton type="table" count={5} />
        ) : appointments.length === 0 ? (
          <MacOSEmptyState type="calendar" title="Записи не найдены" description="В системе пока нет записей к кардиологу" />
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
