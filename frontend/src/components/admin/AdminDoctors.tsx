
import { useTranslation } from '../../i18n/useTranslation';
import { Edit, Plus, RefreshCw, Search, Stethoscope, Trash2 } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';

import DoctorModal from './DoctorModal';
import useDoctors from '../../hooks/useDoctors';
import useModal from '../../hooks/useModal';
import notify from '../../services/notify';
import { api } from '../../api/client';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() call.
import { useConfirm } from '../common/ConfirmDialog';
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
import React from "react";

// PR-19: departmentOptions now loaded dynamically from /admin/departments
// (was hardcoded — new departments didn't appear in filter dropdown)
const STATUS_OPTION_KEYS = [
  { value: '', labelKey: 'admin2.ad_status_all' },
  { value: 'active', labelKey: 'admin2.ad_status_active' },
  { value: 'inactive', labelKey: 'admin2.ad_status_inactive' },
];

const getStatusOptions = (t) =>
  STATUS_OPTION_KEYS.map(({ value, labelKey }) => ({
    value,
    label: t(labelKey),
  }));

const getDoctorName = (doctor, t) =>
  doctor.user?.full_name || doctor.name || doctor.user?.username || t('admin2.ad_doctor_unknown');

const getDoctorInitials = (doctor, t) =>
  getDoctorName(doctor, t)
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || t('admin2.ad_doctor_initial');

// PR-19: dynamic department label lookup (was hardcoded)
const getDepartmentLabel = (department, deptList = [], t) => {
  if (!department) return t('admin2.ad_not_specified');
  const found = deptList.find((d) => d.key === department);
  return found ? found.name_ru : department;
};

const AdminDoctors = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const {
    doctors,
    availableUsers,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterSpecialization,
    setFilterSpecialization,
    filterDepartment,
    setFilterDepartment,
    filterStatus,
    setFilterStatus,
    createDoctor,
    updateDoctor,
    deleteDoctor,
    refresh,
    refreshAvailableUsers,
  } = useDoctors();
  const doctorModal = useModal();

  // PR-19: load departments dynamically (was hardcoded)
  const [departments, setDepartments] = useState([]);

  const loadDepartments = useCallback(async () => {
    try {
      const response = await api.get('/admin/departments');
      setDepartments(response.data?.data || []);
    } catch (err) {
      logger.error('Ошибка загрузки отделений:', err);
    }
  }, []);

  useEffect(() => {
    loadDepartments();
  }, [loadDepartments]);

  // PR-19: build departmentOptions dynamically
  const departmentOptions = [
    { value: '', label: t('admin2.ad_department_all') },
    ...departments.map((d) => ({ value: d.key, label: d.name_ru || d.key })),
  ];

  const statusOptions = getStatusOptions(t);

  const filtersActive = Boolean(searchTerm || filterSpecialization || filterDepartment || filterStatus);

  const handleCreateDoctor = () => {
    void refreshAvailableUsers();
    doctorModal.openModal(null);
  };

  const handleEditDoctor = (doctor) => {
    void refreshAvailableUsers(doctor?.id);
    doctorModal.openModal(doctor);
  };

  const handleDeleteDoctor = async (doctor) => {
    const doctorName = getDoctorName(doctor, t);
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const confirmed = await (confirm as unknown as (opts: Record<string, unknown>) => Promise<boolean>)({
      title: t('admin.deactivate_doctor_title'),
      message: t('admin2.ad_deactivate_message', { name: doctorName }),
      description: t('admin2.ad_deactivate_description'),
      confirmLabel: t('admin.deactivate_confirm'),
      cancelLabel: t('admin.cancel'),
      intent: 'warning',
    });

    if (!confirmed) {
      return;
    }

    try {
      await deleteDoctor(doctor.id);
      notify.success(t('admin2.ad_deactivate_success', { name: doctorName }));
    } catch (deleteError) {
      logger.error('Ошибка деактивации врача:', deleteError);
      notify.error(t('admin2.ad_deactivate_error', { error: deleteError.message || t('admin2.ad_error_unknown') }));
    }
  };

  const handleSaveDoctor = async (doctorData) => {
    doctorModal.setModalLoading(true);
    try {
      if (doctorModal.selectedItem) {
        await updateDoctor(doctorModal.selectedItem.id, doctorData);
      } else {
        await createDoctor(doctorData);
      }
      doctorModal.closeModal();
    } catch (saveError) {
      logger.error('Ошибка сохранения врача:', saveError);
      throw saveError;
    } finally {
      doctorModal.setModalLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <MacOSCard variant="default" shadow="none" className="admin-patients-header-card">
        <div
          className="admin-patients-header-row"
        >
          <div>
            <h2
              className="admin-title-20"
            >
              {t('admin2.ad_title')}
            </h2>
            <p
              className="admin-patients-subtitle"
            >
              {t('admin2.ad_subtitle')}
            </p>
          </div>
          <Button onClick={handleCreateDoctor} startIcon={<Plus size={16 as unknown as "small" | "default" | "large" | "xlarge"} />}>
            {t('admin2.ad_add_doctor')}
          </Button>
        </div>

        <div
          className="admin-doctors-filters-grid"
        >
          <Input
            type="text"
            placeholder={t('admin2.ad_search_placeholder')}
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            icon={Search}
            iconPosition="left"
            aria-label={t('admin2.ad_search_aria')}
          />
          {/* UX Audit Admin #4.7: фильтр специализации — Select вместо текстового инпута. */}
          <Select
            value={filterSpecialization}
            onChange={(v: unknown) => setFilterSpecialization(String(v))}
            options={[
              { value: '', label: t('admin2.ad_specialization_all') },
              ...[...new Set(doctors.map((d) => d.specialty).filter(Boolean))].map((s) => ({ value: s, label: s })),
            ]}
            size="large"
            aria-label={t('admin2.ad_filter_specialization_aria')}
          />
          <Select
            value={filterDepartment}
            onChange={(v: unknown) => setFilterDepartment(String(v))}
            options={departmentOptions}
            size="large"
            aria-label={t('admin2.ad_filter_department_aria')}
          />
          <Select
            value={filterStatus}
            onChange={(v: unknown) => setFilterStatus(String(v))}
            options={statusOptions}
            size="large"
            aria-label={t('admin2.ad_filter_status_aria')}
          />
        </div>

        {/* UX Audit Admin #1.1: кнопка «Сбросить» для быстрой очистки фильтров. */}
        {filtersActive && (
          <div style={{ marginBottom: '12px' }}>
            <Button variant="ghost" size="small" onClick={() => {
              setSearchTerm(''); setFilterSpecialization(''); setFilterDepartment(''); setFilterStatus('');
            }} aria-label={t('admin2.ad_reset_filters_aria')}>
              {t('admin2.ad_reset_filters')}
            </Button>
          </div>
        )}

        <div className="admin-overflow-x-auto">
          {loading ? (
            <Skeleton type="table" count={5} />
          ) : error ? (
            <MacOSEmptyState
              icon={RefreshCw}
              title={t('admin2.ad_error_load_title')}
              description={t('admin2.ad_error_load_description')}
              action={
                <Button onClick={refresh} startIcon={<RefreshCw size={16 as unknown as "small" | "default" | "large" | "xlarge"} />}>
                  {t('admin2.ad_refresh')}
                </Button>
              }
            />
          ) : doctors.length === 0 ? (
            <MacOSEmptyState
              icon={Stethoscope}
              title={t('admin2.ad_empty_title')}
              description={
                filtersActive
                  ? t('admin2.ad_empty_filters')
                  : t('admin2.ad_empty_no_doctors')
              }
              action={
                <Button onClick={handleCreateDoctor} startIcon={<Plus size={16 as unknown as "small" | "default" | "large" | "xlarge"} />}>
                  {t('admin2.ad_add_first_doctor')}
                </Button>
              }
            />
          ) : (
            <div className="admin-table-wrapper">
            <table className="admin-w-100pct-bc-collapse" aria-label={t('admin2.ad_table_aria')}>
              <thead>
                <tr
                  className="admin-patients-thead-row"
                >
                  <th scope="col" className="admin-patients-th">{t('admin2.ad_th_doctor')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ad_th_specialization')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ad_th_department')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ad_th_experience')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ad_th_status')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ad_th_patients')}</th>
                  <th scope="col" className="admin-patients-th">{t('admin2.ad_th_actions')}</th>
                </tr>
              </thead>
              <tbody>
                {doctors.map((doctor) => (
                  <tr
                    key={doctor.id}
                    className="admin-patients-tbody-row"
                    >
                    <td
                      aria-label={t('admin2.ad_doctor_aria', { name: getDoctorName(doctor, t) })}
                      className="admin-p-12-16"
                    >
                      <div className="admin-flex-center-12">
                        <div
                          aria-hidden="true"
                          className="admin-patients-avatar"
                        >
                          {getDoctorInitials(doctor, t)}
                        </div>
                        <div>
                          <p
                            className="admin-patients-name"
                          >
                            {getDoctorName(doctor, t)}
                          </p>
                          <p
                            className="admin-patients-email"
                          >
                            {doctor.user?.email || doctor.email || t('admin2.ad_no_email')}
                          </p>
                          {doctor.user?.phone ? (
                            <p
                              className="admin-patients-address"
                            >
                              {doctor.user.phone}
                            </p>
                          ) : null}
                          <div className="admin-doctors-badges-row">
                            <Badge variant={doctor.user?.is_active === false ? 'warning' : 'success'}>
                              {doctor.user?.is_active === false ? t('admin2.ad_account_inactive') : t('admin2.ad_account_active')}
                            </Badge>
                            <Badge variant={doctor.cabinet ? 'info' : 'warning'}>
                              {doctor.cabinet ? t('admin2.ad_cabinet_label', { number: doctor.cabinet }) : t('admin2.ad_cabinet_not_set')}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="admin-p-12-16">
                      <Badge variant="info">
                        {doctor.specialty || doctor.specialization || t('admin2.ad_not_specified')}
                      </Badge>
                    </td>
                    <td className="admin-p-12-16">
                      <Badge variant="success">
                        {getDepartmentLabel(doctor.specialty || doctor.department, departments, t)}
                      </Badge>
                    </td>
                    <td className="admin-patients-td">
                      {doctor.experience ? t('admin2.ad_experience_years', { count: doctor.experience }) : t('admin2.ad_not_specified')}
                    </td>
                    <td className="admin-p-12-16">
                      <Badge variant={doctor.active ? 'success' : 'warning'}>
                        {doctor.active ? t('admin2.ad_status_active') : t('admin2.ad_status_inactive')}
                      </Badge>
                    </td>
                    <td className="admin-patients-td">{t('admin2.ad_patients_count', { count: doctor.patientsCount || 0 })}</td>
                    <td
                      aria-label={t('admin2.ad_actions_aria', { name: getDoctorName(doctor, t) })}
                      className="admin-p-12-16"
                    >
                      <div className="flex items-center justify-center gap-2">
                        <IconButton label={t('admin2.ad_edit_doctor')} onClick={() => handleEditDoctor(doctor)}>
                          <Edit size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
                        </IconButton>
                        <IconButton
                          label={t('admin2.ad_deactivate_doctor_aria')}
                          tone="danger"
                          onClick={() => handleDeleteDoctor(doctor)}
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

      <DoctorModal
        isOpen={doctorModal.isOpen}
        onClose={doctorModal.closeModal}
        doctor={doctorModal.selectedItem}
        onSave={handleSaveDoctor}
        availableUsers={availableUsers}
        loading={doctorModal.loading}
        departments={departmentOptions.filter((d) => d.value)}
      />
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
    </div>
  );
};

export default AdminDoctors;
