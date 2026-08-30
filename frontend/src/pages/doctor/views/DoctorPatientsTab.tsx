import type { CSSProperties } from 'react';
import { AlertCircle, Edit, Eye, Plus, Search, Trash2, Users } from 'lucide-react';

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
  getPatientA11yContext,
  type PatientRecord,
  type TranslateFn,
} from '../doctorStatus';
import type { DoctorStyles } from '../useDoctorStyles';
import DoctorEmptyState from './DoctorEmptyState';

/**
 * PR-UI-15-2: the patients tab (search/filter toolbar + table + empty
 * states) extracted verbatim from pages/DoctorPanel.tsx
 * (registrar/cashier decomposition precedent).
 */
export default function DoctorPatientsTab({
  filteredPatients,
  loading,
  loadError,
  searchQuery,
  onSearchQueryChange,
  filterStatus,
  onFilterStatusChange,
  onPatientClick,
  onRetry,
  styles,
  t,
}: {
  filteredPatients: PatientRecord[];
  loading: boolean;
  loadError: string | null;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
  filterStatus: string;
  onFilterStatusChange: (status: string) => void;
  onPatientClick: (patient: PatientRecord | Record<string, unknown> | null) => void;
  onRetry: () => void;
  styles: DoctorStyles;
  t: TranslateFn;
}) {
  const { isMobile, primaryColor, getColor, patientsTableStyle, tableHeaderStyle, tableStyle } = styles;

  const getStatusVariant = getDoctorStatusVariant;
  const getStatusText = (status: string | undefined) => getDoctorStatusText(status, t);

  return (
    <AnimatedTransition type="fade" delay={100}>
      <Card style={patientsTableStyle}>
        <CardHeader style={tableHeaderStyle}>
          <div className="doctor-section-head">
            <h2 className="doctor-section-title">
              Пациенты
            </h2>
            <div className="doctor-section-actions">
              <div className="doctor-search-wrap">
                <Search size={20} className="doctor-search-icon" />
                <Input
                  aria-label={t("doctor.aria_search_patients")}
                  type="text"
                  placeholder={t("doctor.search_patients_placeholder")}
                  value={searchQuery}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onSearchQueryChange(e.target.value)}
                  className={`doctor-search-input ${isMobile ? 'doctor-search-w-mobile' : 'doctor-search-w-desktop'}`} />

              </div>
              <select
                value={filterStatus}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onFilterStatusChange(e.target.value)}
                className="doctor-filter-select">

                <option value="all">{t("doctor.filter_all_statuses")}</option>
                <option value="active">{t("doctor.filter_active")}</option>
                <option value="recovery">{t("doctor.filter_recovery")}</option>
                <option value="critical">{t("doctor.filter_critical")}</option>
              </select>
              <Button
                type="button"
                variant="primary"
                title="Add patient"
                aria-label={t("doctor.aria_add_patient")}>
                <Plus aria-hidden="true" size={16} />
                {!isMobile && <span>{t("doctor.btn_add")}</span>}
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
            title={t('doctor.doctor_data_not_loaded')}
            description={loadError}
            tone="error"
            action={<Button variant="ghost" onClick={onRetry}>{t("doctor.btn_retry")}</Button>}
          /> :
          filteredPatients.length === 0 ?
          <DoctorEmptyState
            icon={Users}
            title={t('doctor.patients_not_found')}
            description={searchQuery || filterStatus !== 'all'
              ? t('doctor.no_patients_filtered')
              : t('doctor.no_patients_empty')}
          /> :

          <div className="admin-table-wrapper">
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th className="doctor-th">{t("doctor.col_patient")}</th>
                  <th className="doctor-th">{t("doctor.col_age")}</th>
                  <th className="doctor-th">{t("doctor.col_phone")}</th>
                  <th className="doctor-th">{t("doctor.col_diagnosis")}</th>
                  <th className="doctor-th">{t("doctor.col_status")}</th>
                  <th className="doctor-th">{t("doctor.col_actions")}</th>
                </tr>
              </thead>
              <tbody>
                {filteredPatients.map((patient) =>
            <tr
              key={patient.id}
              className="doctor-table-row-hover"
              aria-label={`Open ${getPatientA11yContext(patient)}`}
              onClick={() => onPatientClick(patient)}>

                    <td className="doctor-td" aria-label={getPatientA11yContext(patient)}>
                      <div className="doctor-patient-cell">
                        <div className="doctor-avatar-sm" style={{ '--doctor-gradient-from': primaryColor, '--doctor-gradient-to': getColor('primary', 600) } as CSSProperties}>
                          {String(patient.name || t('doctor.patient_default')).split(' ').map((n) => n[0]).join('')}
                        </div>
                        <div>
                          <div className="doctor-patient-name">
                            {patient.name || t('doctor.patient_default')}
                          </div>
                          <div className="doctor-patient-meta">
                            {patient.gender}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="doctor-td">{patient.age ? t('doctor.age_years', { count: patient.age }) : '—'}</td>
                    <td className="doctor-td">{patient.phone || '—'}</td>
                    <td className="doctor-td">{patient.diagnosis || '—'}</td>
                    <td className="doctor-td" aria-label={`${getPatientA11yContext(patient)} status`}>
                      <Badge variant={getStatusVariant(patient.status)} size="default">
                        {getStatusText(patient.status)}
                      </Badge>
                    </td>
                    <td className="doctor-td" aria-label={`${getPatientA11yContext(patient)} actions`}>
                      <button
                  aria-label={`Edit ${getPatientA11yContext(patient)}`}
                  className="doctor-action-btn doctor-action-btn-primary"
                  onClick={(e: React.MouseEvent<HTMLElement>) => {
                    e.stopPropagation();
                    onPatientClick(patient);
                  }}>

                        <Edit size={16} />
                      </button>
                      {/* UX Audit Doctor H-02: View/Delete были заглушки (logger.log only).
                          View → открывает модалку (дублирует клик по строке — оставляем).
                          Delete → disabled (нет backend API + нужен ConfirmDialog). */}
                      <button
                  aria-label={`View ${getPatientA11yContext(patient)}`}
                  className="doctor-action-btn doctor-action-btn-success"
                  onClick={(e: React.MouseEvent<HTMLElement>) => {
                    e.stopPropagation();
                    onPatientClick(patient);
                  }}>

                        <Eye size={16} />
                      </button>
                      <button
                  aria-label={`Delete ${getPatientA11yContext(patient)}`}
                  className="doctor-action-btn doctor-action-btn-danger"
                  disabled
                  title={t("doctor.feature_in_development")}
                  onClick={(e: React.MouseEvent<HTMLElement>) => e.stopPropagation()}>

                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
          )}
              </tbody>
            </table>
          </div>
          }
        </CardContent>
      </Card>
    </AnimatedTransition>
  );
}
