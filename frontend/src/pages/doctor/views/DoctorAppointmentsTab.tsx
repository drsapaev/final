import { AlertCircle, Calendar, CheckCircle, Clock, Edit, Plus, Search, XCircle } from 'lucide-react';

import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  Input,
  Skeleton,
  AnimatedTransition,
} from '../../../components/ui/macos';
import {
  getDoctorStatusText,
  getDoctorStatusVariant,
  getAppointmentA11yContext,
  type AppointmentDto,
  type TranslateFn,
} from '../doctorStatus';
import logger from '../../../utils/logger';
import type { DoctorStyles } from '../useDoctorStyles';
import DoctorEmptyState from './DoctorEmptyState';

/**
 * PR-UI-15-2: the appointments tab (search/filter toolbar + table + empty
 * states + schedule-next trigger) extracted verbatim from
 * pages/DoctorPanel.tsx (registrar/cashier decomposition precedent).
 */
export default function DoctorAppointmentsTab({
  filteredAppointments,
  loading,
  loadError,
  searchQuery,
  onSearchQueryChange,
  filterStatus,
  onFilterStatusChange,
  onScheduleNext,
  onRetry,
  styles,
  t,
}: {
  filteredAppointments: AppointmentDto[];
  loading: boolean;
  loadError: string | null;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
  filterStatus: string;
  onFilterStatusChange: (status: string) => void;
  onScheduleNext: () => void;
  onRetry: () => void;
  styles: DoctorStyles;
  t: TranslateFn;
}) {
  const { isMobile, patientsTableStyle, tableHeaderStyle, tableStyle } = styles;

  const getStatusVariant = getDoctorStatusVariant;
  const getStatusText = (status: string | undefined) => getDoctorStatusText(status, t);

  return (
    <AnimatedTransition type="fade" delay={100}>
      <Card style={patientsTableStyle}>
        <CardHeader style={tableHeaderStyle}>
          <div className="doctor-section-head">
            <h2 className="doctor-section-title">
              Записи на прием
            </h2>
            <div className="doctor-section-actions">
              <div className="doctor-search-wrap">
                <Search size={20} className="doctor-search-icon" />
                <Input
                  aria-label={t("doctor.aria_search_appointments")}
                  type="text"
                  placeholder={t("doctor.search_appointments_placeholder")}
                  value={searchQuery}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onSearchQueryChange(e.target.value)}
                  className={`doctor-search-input ${isMobile ? 'doctor-search-w-mobile' : 'doctor-search-w-desktop'}`} />

              </div>
              <select
                value={filterStatus}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onFilterStatusChange(e.target.value)}
                className="doctor-filter-select">

                <option value="all">{t("doctor.filter_all_statuses")}</option>
                <option value="scheduled">{t("doctor.filter_scheduled")}</option>
                <option value="in_progress">{t("doctor.filter_in_progress")}</option>
                <option value="completed">{t("doctor.filter_completed")}</option>
                <option value="cancelled">{t("doctor.filter_cancelled")}</option>
              </select>
              <Button
                type="button"
                variant="primary"
                title="Schedule next visit"
                aria-label="Schedule next visit"
                onClick={onScheduleNext}>

                <Plus aria-hidden="true" size={16} />
                {!isMobile && <span>{t("doctor.btn_next_visit")}</span>}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="doctor-card-pad-0">
          {loading ?
          <Skeleton variant="rectangular" width="100%" height={200} /> :
          loadError ?
          <DoctorEmptyState
            icon={AlertCircle}
            title={t('doctor.appointments_not_loaded')}
            description={loadError}
            tone="error"
            action={<Button variant="ghost" onClick={onRetry}>{t("doctor.btn_retry")}</Button>}
          /> :
          filteredAppointments.length === 0 ?
          <DoctorEmptyState
            icon={Calendar}
            title={t('doctor.appointments_not_found')}
            description={searchQuery || filterStatus !== 'all'
              ? t('doctor.no_appointments_filtered')
              : 'Нет реальных записей для отображения. Создайте визит через регистратуру, очередь или кнопку назначения следующего визита.'}
          /> :

          <table style={tableStyle}>
            <thead>
              <tr>
                <th className="doctor-th">{t("doctor.col_time")}</th>
                <th className="doctor-th">{t("doctor.col_patient")}</th>
                <th className="doctor-th">{t("doctor.col_type")}</th>
                <th className="doctor-th">{t("doctor.col_status")}</th>
                <th className="doctor-th">{t("doctor.col_notes")}</th>
                <th className="doctor-th">{t("doctor.col_actions")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredAppointments.map((appointment) =>
          <tr
            key={appointment.id}
            className="doctor-table-row-hover">

                <td className="doctor-td">
                  <div className="doctor-patient-cell">
                    <Clock size={16} className="doctor-patient-meta" />
                    {appointment.time}
                  </div>
                </td>
                <td className="doctor-td">{appointment.patientName || t('doctor.patient_default')}</td>
                <td className="doctor-td">{appointment.type || '—'}</td>
                <td className="doctor-td">
                  <Badge variant={getStatusVariant(appointment.status)} size="default">
                    {getStatusText(appointment.status)}
                  </Badge>
                </td>
                <td className="doctor-td">{appointment.notes || '—'}</td>
                <td className="doctor-td">
                  <button
              aria-label={`Edit ${getAppointmentA11yContext(appointment)}`}
              className="doctor-action-btn doctor-action-btn-primary"
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.stopPropagation();
                logger.log('Edit appointment', appointment.id);
              }}>

                    <Edit size={16} />
                  </button>
                  {/* UX Audit Doctor H-03: Complete/Cancel были заглушки (logger.log only).
                      Disabled до реализации backend API + ConfirmDialog. */}
                  <button
              aria-label={`Complete ${getAppointmentA11yContext(appointment)}`}
              className="doctor-action-btn doctor-action-btn-success"
              disabled
              title={t("doctor.feature_in_development")}
              onClick={(e: React.MouseEvent<HTMLElement>) => e.stopPropagation()}>

                    <CheckCircle size={16} />
                  </button>
                  <button
              aria-label={`Cancel ${getAppointmentA11yContext(appointment)}`}
              className="doctor-action-btn doctor-action-btn-danger"
              disabled
              title={t("doctor.feature_in_development")}
              onClick={(e: React.MouseEvent<HTMLElement>) => e.stopPropagation()}>

                    <XCircle size={16} />
                  </button>
                </td>
              </tr>
          )}
            </tbody>
          </table>
      }
        </CardContent>
      </Card>
    </AnimatedTransition>
  );
}
