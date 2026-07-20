
import { useTranslation } from '../../i18n/useTranslation';
import { Edit, Plus, RefreshCw, Search, Trash2, Users } from 'lucide-react';
import PropTypes from 'prop-types';

import PatientModal from './PatientModal';
import usePatients from '../../hooks/usePatients';
import useModal from '../../hooks/useModal';
import notify from '../../services/notify';
import {
  Badge,
  Button,
  MacOSCard,
  MacOSEmptyState,
  Input,
  Skeleton,
  Select,
} from '../ui/macos';
import IconButton from './IconButton';
import logger from '../../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
import React from "react";

const GENDER_OPTION_KEYS = [
  { value: '', labelKey: 'admin2.ap_gender_all' },
  { value: 'male', labelKey: 'admin2.ap_gender_male' },
  { value: 'female', labelKey: 'admin2.ap_gender_female' },
];

const getGenderOptions = (t) =>
  GENDER_OPTION_KEYS.map(({ value, labelKey }) => ({
    value,
    label: t(labelKey),
  }));

const AGE_OPTION_KEYS = [
  { value: '', labelKey: 'admin2.ap_age_all' },
  { value: '0-18', labelKey: 'admin2.ap_age_0_18' },
  { value: '19-35', labelKey: 'admin2.ap_age_19_35' },
  { value: '36-50', labelKey: 'admin2.ap_age_36_50' },
  { value: '51-65', labelKey: 'admin2.ap_age_51_65' },
  { value: '65+', labelKey: 'admin2.ap_age_65_plus' },
];

const getAgeOptions = (t) =>
  AGE_OPTION_KEYS.map(({ value, labelKey }) => ({
    value,
    label: t(labelKey),
  }));

const BLOOD_TYPE_OPTION_VALUES = [
  { value: '', labelKey: 'admin2.ap_blood_type_all' },
  { value: 'A+', label: 'A+' },
  { value: 'A-', label: 'A-' },
  { value: 'B+', label: 'B+' },
  { value: 'B-', label: 'B-' },
  { value: 'AB+', label: 'AB+' },
  { value: 'AB-', label: 'AB-' },
  { value: 'O+', label: 'O+' },
  { value: 'O-', label: 'O-' },
];

const getBloodTypeOptions = (t) =>
  BLOOD_TYPE_OPTION_VALUES.map((opt) => ({
    value: opt.value,
    label: opt.labelKey ? t(opt.labelKey) : opt.label,
  }));

const getPatientName = (patient, t) =>
  [patient.lastName, patient.firstName, patient.middleName].filter(Boolean).join(' ') || t('admin2.ap_patient_no_name');

const getPatientInitials = (patient, t) =>
  [patient.firstName, patient.lastName]
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || t('admin2.ap_initial_fallback');

const getGenderLabel = (gender, t) => {
  const genderMap = {
    male: t('admin2.ap_gender_male'),
    female: t('admin2.ap_gender_female'),
  };
  return genderMap[gender] || t('admin2.ap_not_specified');
};

const formatDate = (value, t) => {
  if (!value) {
    return t('admin2.ap_no_visits');
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return t('admin2.ap_no_visits');
  }

  return parsed.toLocaleDateString('ru-RU');
};

const formatAge = (patient, calculateAge, t) => {
  if (!patient.birthDate) {
    return t('admin2.ap_not_specified');
  }

  const age = calculateAge(patient.birthDate);
  return Number.isFinite(age) && age >= 0 ? t('admin2.ap_age_years', { age }) : t('admin2.ap_not_specified');
};

const AdminPatients = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const genderOptions = getGenderOptions(t);
  const ageOptions = getAgeOptions(t);
  const bloodTypeOptions = getBloodTypeOptions(t);
  const {
    patients,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterGender,
    setFilterGender,
    filterAgeRange,
    setFilterAgeRange,
    filterBloodType,
    setFilterBloodType,
    createPatient,
    updatePatient,
    deletePatient,
    refresh,
    calculateAge,
  } = usePatients();
  const patientModal = useModal();

  const filtersActive = Boolean(searchTerm || filterGender || filterAgeRange || filterBloodType);

  const handleCreatePatient = () => {
    patientModal.openModal(null);
  };

  const handleEditPatient = (patient) => {
    patientModal.openModal(patient);
  };

  const handleDeletePatient = async (patient) => {
    const patientName = getPatientName(patient, t);
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await (confirm as unknown as (opts: Record<string, unknown>) => Promise<boolean>)({
      title: t('admin.delete_patient_title'),
      message: t('admin2.ap_delete_patient_message', { name: patientName }),
      description: t('admin2.ap_delete_patient_description'),
      confirmLabel: t('admin.delete_confirm'),
      cancelLabel: t('admin.cancel'),
      intent: 'danger',
    });

    if (!ok) {
      return;
    }

    try {
      await deletePatient(patient.id);
    } catch (deleteError) {
      logger.error('Ошибка удаления пациента:', deleteError);
      notify.error(t('admin.patient_delete_error'));
    }
  };

  const handleSavePatient = async (patientData) => {
    patientModal.setModalLoading(true);
    try {
      if (patientModal.selectedItem) {
        await updatePatient(patientModal.selectedItem.id, patientData);
      } else {
        await createPatient(patientData);
      }
      patientModal.closeModal();
    } catch (saveError) {
      logger.error('Ошибка сохранения пациента:', saveError);
      throw saveError;
    } finally {
      patientModal.setModalLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <MacOSCard
        variant="default"
        shadow="none"
        className="admin-patients-header-card"
      >
        <div
          className="admin-patients-header-row"
        >
          <div>
            <h2
              className="admin-title-20"
            >
              {t('admin2.ap_page_title')}
            </h2>
            <p
              className="admin-patients-subtitle"
            >
              {t('admin2.ap_page_subtitle')}
            </p>
          </div>
          <Button onClick={handleCreatePatient} startIcon={<Plus size={16 as unknown as "small" | "default" | "large" | "xlarge"} />}>
            {t('admin2.ap_add_patient_btn')}
          </Button>
        </div>

        <div
          className="admin-patients-filters-grid"
        >
          <Input
            type="text"
            placeholder={t('admin2.ap_search_placeholder')}
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            icon={Search}
            iconPosition="left"
            aria-label={t('admin2.ap_search_aria')}
          />
          <Select
            value={filterGender}
            onChange={(v: any) => setFilterGender(String(v))}
            options={genderOptions}
            size="large"
            aria-label={t('admin2.ap_filter_gender_aria')}
          />
          <Select
            value={filterAgeRange}
            onChange={(v: any) => setFilterAgeRange(String(v))}
            options={ageOptions}
            size="large"
            aria-label={t('admin2.ap_filter_age_aria')}
          />
          {/* UX Audit Admin #2.9: blood type filter перемещён в раскрытие.
              Редкий фильтр не должен занимать 25% фильтр-грида. */}
          <details style={{ marginTop: '4px' }}>
            <summary style={{ cursor: 'pointer', fontSize: '13px', color: 'var(--mac-accent-blue, #007aff)', userSelect: 'none' }}>
              {t('admin2.ap_advanced_filters')} {filterBloodType ? `(${filterBloodType})` : ''}
            </summary>
            <div style={{ marginTop: '8px' }}>
              <Select
                value={filterBloodType}
                onChange={(v: any) => setFilterBloodType(String(v))}
                options={bloodTypeOptions}
                size="large"
                aria-label={t('admin2.ap_filter_blood_type_aria')}
              />
            </div>
          </details>
        </div>

        {/* UX Audit Admin #1.1: кнопка «Сбросить» для быстрой очистки фильтров. */}
        {filtersActive && (
          <div style={{ marginBottom: '12px' }}>
            <Button variant="ghost" size="small" onClick={() => {
              setSearchTerm(''); setFilterGender(''); setFilterAgeRange(''); setFilterBloodType('');
            }} aria-label={t('admin2.ap_reset_filters_aria')}>
              {t('admin2.ap_reset_filters_btn')}
            </Button>
          </div>
        )}

        <div className="admin-overflow-x-auto">
          {loading ? (
            <Skeleton type="table" count={5} />
          ) : error ? (
            <MacOSEmptyState
              icon={RefreshCw}
              title={t('admin2.ap_load_error_title')}
              description={t('admin2.ap_load_error_desc')}
              action={
                <Button onClick={refresh} startIcon={<RefreshCw size={16 as unknown as "small" | "default" | "large" | "xlarge"} />}>
                  {t('admin2.ap_refresh_btn')}
                </Button>
              }
            />
          ) : patients.length === 0 ? (
            <MacOSEmptyState
              icon={Users}
              title={t('admin2.ap_empty_title')}
              description={
                filtersActive
                  ? t('admin2.ap_empty_desc_filtered')
                  : t('admin2.ap_empty_desc_initial')
              }
              action={
                <Button onClick={handleCreatePatient} startIcon={<Plus size={16 as unknown as "small" | "default" | "large" | "xlarge"} />}>
                  {t('admin2.ap_add_first_patient_btn')}
                </Button>
              }
            />
          ) : (
            <div className="admin-table-wrapper">
            <table className="admin-w-100pct-bc-collapse" aria-label={t('admin2.ap_table_aria')}>
              <thead>
                <tr
                  className="admin-patients-thead-row"
                >
                  <th scope="col" className="admin-patients-th">{t('admin2.ap_col_patient')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ap_col_age')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ap_col_gender')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ap_col_phone')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ap_col_blood_type')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ap_col_last_visit')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ap_col_visits')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.col_actions')}</th>
                </tr>
              </thead>
              <tbody>
                {/* UX Audit Admin #1.5: indicator for 200-row cap. */}
                {patients.length > 200 && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', padding: '8px', fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
                    {t('admin2.ap_cap_message', { count: patients.length })}
                  </td></tr>
                )}
                {/* PR-41 / High-17: cap rendered rows to 200 to avoid rendering
                    1000+ DOM nodes when the patient list is large. Full
                    virtualization via @tanstack/react-virtual is installed
                    but requires table-layout refactoring — this slice cap
                    is a pragmatic partial fix. */}
                {patients.slice(0, 200).map((patient) => (
                  <tr
                    key={patient.id}
                    className="admin-patients-tbody-row"
                    >
                    <td
                      aria-label={t('admin2.ap_patient_aria', { name: getPatientName(patient, t) })}
                      className="admin-p-12-16"
                    >
                      <div className="admin-flex-center-12">
                        <div
                          aria-hidden="true"
                          className="admin-patients-avatar"
                        >
                          {getPatientInitials(patient, t)}
                        </div>
                        <div>
                          <p
                            className="admin-patients-name"
                          >
                            {getPatientName(patient, t)}
                          </p>
                          <p
                            className="admin-patients-email"
                          >
                            {patient.email || t('admin2.ap_email_not_specified')}
                          </p>
                          {patient.address ? (
                            <p
                              className="admin-patients-address"
                            >
                              {patient.address}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </td>
                    <td className="admin-patients-td">{formatAge(patient, calculateAge, t)}</td>
                    <td className="admin-p-12-16">
                      <Badge variant={patient.gender === 'male' ? 'info' : 'success'}>
                        {getGenderLabel(patient.gender, t)}
                      </Badge>
                    </td>
                    <td className="admin-patients-td">{patient.phone || t('admin2.ap_phone_not_specified')}</td>
                    <td className="admin-p-12-16">
                      {patient.bloodType ? (
                        <Badge variant="warning">{patient.bloodType}</Badge>
                      ) : (
                        <span className="admin-text-sm-tertiary">
                          {t('admin2.ap_not_specified')}
                        </span>
                      )}
                    </td>
                    <td className="admin-patients-td">{formatDate(patient.lastVisit, t)}</td>
                    <td className="admin-patients-td">{t('admin2.ap_visits_count', { count: patient.visitsCount || 0 })}</td>
                    <td
                      aria-label={t('admin2.ap_actions_aria', { name: getPatientName(patient, t) })}
                      className="admin-p-12-16"
                    >
                      <div className="flex items-center justify-center gap-2">
                        <IconButton label={t('admin2.ap_edit_aria')} onClick={() => handleEditPatient(patient)}>
                          <Edit size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
                        </IconButton>
                        <IconButton
                          label={t('admin2.ap_delete_aria')}
                          tone="danger"
                          onClick={() => handleDeletePatient(patient)}
                        >
                          <Trash2 size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
                        </IconButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
        </div>
      </MacOSCard>

      <PatientModal
        isOpen={patientModal.isOpen}
        onClose={patientModal.closeModal}
        patient={patientModal.selectedItem}
        onSave={handleSavePatient}
        loading={patientModal.loading}
      />
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
    </div>
  );
};

export default AdminPatients;
