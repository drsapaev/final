import { Calendar, Clock, Edit, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import PropTypes from 'prop-types';

import AppointmentModal from './AppointmentModal';
import useAppointments from '../../hooks/useAppointments';
import useDoctors from '../../hooks/useDoctors';
import usePatients from '../../hooks/usePatients';
import useModal from '../../hooks/useModal.jsx';
import notify from '../../services/notify';
import { useTranslation } from '../../i18n/useTranslation';
import {
  Badge,
  Button,
  MacOSCard,
  MacOSStatCard,
  MacOSEmptyState,
  Input,
  Skeleton,
  Select,
} from '../ui/macos';
import IconButton from './IconButton';
import logger from '../../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

const getStatusOptions = (t) => [
  { value: '', label: t('admin2.appt_filter_all_statuses') },
  { value: 'pending', label: t('admin2.appt_status_pending') },
  { value: 'confirmed', label: t('admin2.appt_status_confirmed') },
  { value: 'paid', label: t('admin2.appt_status_paid') },
  { value: 'in_visit', label: t('admin2.appt_status_in_visit') },
  { value: 'completed', label: t('admin2.appt_status_completed') },
  { value: 'cancelled', label: t('admin2.appt_status_cancelled') },
  { value: 'no_show', label: t('admin2.appt_status_no_show') },
];

const tableHeaderStyle = {
  textAlign: 'left',
  padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
  color: 'var(--mac-text-secondary)',
  fontWeight: 'var(--mac-font-weight-semibold)',
  fontSize: 'var(--mac-font-size-sm)',
};

const textCellStyle = {
  padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
  fontSize: 'var(--mac-font-size-sm)',
  color: 'var(--mac-text-secondary)',
};

const getAppointmentPatientDisplayName = (appointment, t) => {
  const rawName =
    appointment?.patientName ||
    appointment?.patient_name ||
    appointment?.patient?.full_name ||
    appointment?.patient?.fio ||
    appointment?.patient?.name ||
    appointment?.patient?.first_name ||
    appointment?.patient?.last_name ||
    t('admin2.appt_patient_default');

  const normalized = String(rawName).trim();
  return normalized || t('admin2.appt_patient_default');
};

const getAppointmentDoctorDisplayName = (appointment, t) => {
  const rawName =
    appointment?.doctorName ||
    appointment?.doctor_name ||
    appointment?.doctor?.full_name ||
    appointment?.doctor?.name ||
    appointment?.doctor?.user?.full_name ||
    appointment?.doctor?.user?.username ||
    t('admin2.appt_doctor_default');

  const normalized = String(rawName).trim();
  return normalized || t('admin2.appt_doctor_default');
};

const getAppointmentDoctorSpecialization = (appointment) => {
  const rawValue =
    appointment?.doctorSpecialization ||
    appointment?.doctor_specialization ||
    appointment?.specialization ||
    appointment?.doctor?.specialization ||
    appointment?.doctor?.specialty ||
    '';

  return String(rawValue).trim();
};

const getAppointmentStatusLabel = (status, t) => {
  const statusMap = {
    pending: t('admin2.appt_status_pending'),
    scheduled: t('admin2.appt_status_scheduled'),
    confirmed: t('admin2.appt_status_confirmed'),
    paid: t('admin2.appt_status_paid'),
    in_visit: t('admin2.appt_status_in_visit'),
    completed: t('admin2.appt_status_completed'),
    cancelled: t('admin2.appt_status_cancelled'),
    no_show: t('admin2.appt_status_no_show'),
  };
  return statusMap[status] || status || t('admin2.appt_status_not_specified');
};

const getAppointmentStatusVariant = (status) => {
  const variantMap = {
    pending: 'warning',
    scheduled: 'warning',
    confirmed: 'info',
    paid: 'success',
    in_visit: 'primary',
    completed: 'success',
    cancelled: 'error',
    no_show: 'secondary',
  };
  return variantMap[status] || 'secondary';
};

const getInitials = (value, fallback) =>
  String(value || fallback)
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || fallback;

const formatAppointmentDate = (value, t) => {
  if (!value) {
    return t('admin2.appt_date_not_specified');
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString('ru-RU');
};

const getDoctorOptionLabel = (doctor, t) => {
  const name = doctor.user?.full_name || doctor.name || doctor.user?.username || t('admin2.appt_doctor_with_id', { id: doctor.id });
  const flags = [
    doctor.active === false ? t('admin2.appt_doctor_inactive_flag') : null,
    doctor.user?.is_active === false ? t('admin2.appt_doctor_account_inactive_flag') : null,
    doctor.cabinet ? t('admin2.appt_doctor_cabinet_flag', { cabinet: doctor.cabinet }) : null,
  ].filter(Boolean);

  return flags.length > 0 ? `${name} • ${flags.join(' • ')}` : name;
};

// UX Audit Admin #3.6: локальный StatCard заменён на MacOSStatCard (统一 API).
// Старый StatCard удалён, используется MacOSStatCard напрямую в render.


const AdminAppointments = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const { t } = useTranslation();
  const { allDoctors } = useDoctors();
  const { patients } = usePatients();
  const {
    appointments,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterStatus,
    setFilterStatus,
    filterDate,
    setFilterDate,
    filterDoctor,
    setFilterDoctor,
    createAppointment,
    updateAppointment,
    deleteAppointment,
    refresh,
    getStatusStats,
    getTodayAppointments,
    getTomorrowAppointments,
  } = useAppointments(allDoctors);
  const appointmentModal = useModal();

  const statusStats = getStatusStats();
  const todayAppointments = getTodayAppointments();
  const tomorrowAppointments = getTomorrowAppointments();
  const filtersActive = Boolean(searchTerm || filterStatus || filterDate || filterDoctor);
  const statusOptions = getStatusOptions(t);
  const doctorOptions = [
    { value: '', label: t('admin2.appt_filter_all_doctors') },
    ...allDoctors.map((doctor) => ({
      value: String(doctor.id),
      label: getDoctorOptionLabel(doctor, t),
    })),
  ];

  const handleCreateAppointment = () => {
    appointmentModal.openModal(null);
  };

  const handleEditAppointment = (appointment) => {
    appointmentModal.openModal(appointment);
  };

  const handleDeleteAppointment = async (appointment) => {
    const patientName = getAppointmentPatientDisplayName(appointment, t);
    const doctorName = getAppointmentDoctorDisplayName(appointment, t);
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin.delete_appointment_title'),
      message: t('admin2.appt_delete_appointment_message', { patient: patientName, doctor: doctorName }),
      description: t('admin2.appt_delete_appointment_description'),
      confirmLabel: t('admin.delete_confirm'),
      cancelLabel: t('admin.cancel'),
      intent: 'danger',
    });

    if (!ok) {
      return;
    }

    try {
      await deleteAppointment(appointment.id);
    } catch (deleteError) {
      logger.error('Ошибка удаления записи:', deleteError);
      notify.error(t('admin.appointment_delete_error'));
    }
  };

  const handleSaveAppointment = async (appointmentData) => {
    appointmentModal.setModalLoading(true);
    try {
      if (appointmentModal.selectedItem) {
        await updateAppointment(appointmentModal.selectedItem.id, appointmentData);
      } else {
        await createAppointment(appointmentData);
      }
      appointmentModal.closeModal();
    } catch (saveError) {
      logger.error('Ошибка сохранения записи:', saveError);
      throw saveError;
    } finally {
      appointmentModal.setModalLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div
        className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16"
      >
        <MacOSStatCard title={t('admin2.appt_stat_total')} value={appointments.length} icon={Calendar} color="blue" />
        <MacOSStatCard title={t('admin2.appt_stat_today')} value={todayAppointments.length} icon={Clock} color="green" />
        <MacOSStatCard title={t('admin2.appt_stat_tomorrow')} value={tomorrowAppointments.length} icon={Calendar} color="purple" />
        <MacOSStatCard title={t('admin2.appt_stat_pending')} value={statusStats.pending || 0} icon={Clock} color="orange" />
      </div>

      <MacOSCard
        variant="default"
        shadow="none"
        className="admin-bg-bg-primary-bd-1px-solid-var-mac-bo-p-24"
      >
        <div
          className="admin-d-flex-ai-center-jc-between-gap-16-mb-24-fw-wrap"
        >
          <div>
            <h2
              className="admin-fs-xl-fw-semi-primary-m-0"
            >
              {t('admin2.appt_page_title')}
            </h2>
            <p
              className="admin-m-6px-0-0-secondary-fs-sm"
            >
              {t('admin2.appt_page_subtitle')}
            </p>
          </div>
          <Button onClick={handleCreateAppointment} startIcon={<Plus size={16} />}>
            {t('admin2.appt_create_btn')}
          </Button>
        </div>

        <div
          className="admin-d-grid-gtc-minmax-220px-1fr-min-gap-12-mb-24"
        >
          <Input
            type="text"
            placeholder={t('admin2.appt_search_ph')}
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            icon={Search}
            iconPosition="left"
            aria-label={t('admin2.appt_search_aria')}
          />
          <Select
            value={filterStatus}
            onChange={setFilterStatus}
            options={statusOptions}
            size="large"
            aria-label={t('admin2.appt_filter_status_aria')}
          />
          <Input
            type="date"
            value={filterDate}
            onChange={(event) => setFilterDate(event.target.value)}
            aria-label={t('admin2.appt_filter_date_aria')}
          />
          <Select
            value={filterDoctor}
            onChange={setFilterDoctor}
            options={doctorOptions}
            size="large"
            aria-label={t('admin2.appt_filter_doctor_aria')}
          />
        </div>

        {/* UX Audit Admin #1.1: кнопка «Сбросить» для быстрой очистки фильтров. */}
        {filtersActive && (
          <div style={{ marginBottom: '12px' }}>
            <Button variant="ghost" size="sm" onClick={() => {
              setSearchTerm(''); setFilterStatus(''); setFilterDate(''); setFilterDoctor('');
            }} aria-label={t('admin2.appt_reset_filters_aria')}>
              ✕ {t('admin2.appt_reset_filters_btn')}
            </Button>
          </div>
        )}

        {/* UX Audit Admin #2.7: quick filter chips для частых статусов. */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
          {[
            { value: 'completed', label: t('admin2.appt_chip_completed') },
            { value: 'cancelled', label: t('admin2.appt_chip_cancelled') },
            { value: 'pending', label: t('admin2.appt_chip_pending') },
          ].map((chip) => (
            <button
              key={chip.value}
              type="button"
              onClick={() => setFilterStatus(filterStatus === chip.value ? '' : chip.value)}
              style={{
                padding: '4px 12px',
                borderRadius: '16px',
                border: `1px solid ${filterStatus === chip.value ? 'var(--mac-accent-blue, #007aff)' : 'var(--mac-border, #d8dde8)'}`,
                background: filterStatus === chip.value ? 'color-mix(in srgb, var(--mac-accent-blue, #007aff), transparent 88%)' : 'transparent',
                color: filterStatus === chip.value ? 'var(--mac-accent-blue, #007aff)' : 'var(--mac-text-secondary, #6b7280)',
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}>
              {chip.label}
            </button>
          ))}
        </div>

        <div className="admin-ovx-auto">
          {loading ? (
            <Skeleton type="table" count={5} />
          ) : error ? (
            <MacOSEmptyState
              icon={RefreshCw}
              title={t('admin2.appt_load_error_title')}
              description={t('admin2.appt_load_error_desc')}
              action={
                <Button onClick={refresh} startIcon={<RefreshCw size={16} />}>
                  {t('admin2.appt_refresh_btn')}
                </Button>
              }
            />
          ) : appointments.length === 0 ? (
            <MacOSEmptyState
              icon={Calendar}
              title={t('admin2.appt_empty_title')}
              description={
                filtersActive
                  ? t('admin2.appt_empty_filtered_desc')
                  : t('admin2.appt_empty_desc')
              }
              action={
                <Button onClick={handleCreateAppointment} startIcon={<Plus size={16} />}>
                  {t('admin2.appt_create_first_btn')}
                </Button>
              }
            />
          ) : (
            <div className="admin-table-wrapper">
            <table className="admin-w-100pct-bc-collapse" aria-label={t('admin2.appt_table_aria')}>
              <thead>
                <tr
                  className="admin-bgc-bg-secondary-bd-b-1px-solid-var-mac-bo"
                >
                  <th scope="col" style={tableHeaderStyle}>{t('admin2.appt_th_patient')}</th>
                  <th scope="col" style={tableHeaderStyle}>{t('admin2.appt_th_doctor')}</th>
                  <th scope="col" style={tableHeaderStyle}>{t('admin2.appt_th_cabinet')}</th>
                  <th scope="col" style={tableHeaderStyle}>{t('admin2.appt_th_datetime')}</th>
                  <th scope="col" style={tableHeaderStyle}>{t('admin2.appt_th_status')}</th>
                  <th scope="col" style={tableHeaderStyle}>{t('admin2.appt_th_integrity')}</th>
                  <th scope="col" style={tableHeaderStyle}>{t('admin2.appt_th_reason')}</th>
                  <th scope="col" style={tableHeaderStyle}>{t('admin2.appt_th_actions')}</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map((appointment) => {
                  const patientName = getAppointmentPatientDisplayName(appointment, t);
                  const doctorName = getAppointmentDoctorDisplayName(appointment, t);
                  const doctorSpecialization = getAppointmentDoctorSpecialization(appointment);
                  const reason = appointment.reason || '';

                  return (
                    <tr
                      key={appointment.id}
                      className="admin-bd-b-1px-solid-var-mac-bo-tr-background-color-var"
                      >
                      <td aria-label={t('admin2.appt_patient_aria', { name: patientName })} className="admin-p-12-16">
                        <div className="admin-flex-center-12">
                          <div
                            aria-hidden="true"
                            className="admin-w-32-h-32-radius-50pct-d-flex-ai-center-jc-center-bg-blue-on-accent-fs-sm-fw-med"
                          >
                            {getInitials(patientName, t('admin2.appt_initials_patient'))}
                          </div>
                          <div>
                            <p
                              className="admin-fw-med-primary-m-0"
                            >
                              {patientName}
                            </p>
                            {appointment.phone ? (
                              <p
                                className="admin-fs-sm-secondary-m-4px-0-0-1"
                              >
                                {appointment.phone}
                              </p>
                            ) : null}
                          </div>
                        </div>
                      </td>
                      <td className="admin-p-12-16">
                        <p
                          className="admin-fw-med-primary-m-0"
                        >
                          {doctorName}
                        </p>
                        <p
                          className="admin-fs-sm-secondary-m-4px-0-0"
                        >
                          {doctorSpecialization || '—'}
                        </p>
                        <div className="admin-mt-4">
                          <Badge
                            variant={
                              appointment.doctor?.active === false || appointment.doctor?.user_active === false
                                ? 'warning'
                                : 'success'
                            }
                            size="sm"
                          >
                            {appointment.doctor?.active === false
                              ? t('admin2.appt_doctor_inactive')
                              : appointment.doctor?.user_active === false
                                ? t('admin2.appt_doctor_account_inactive')
                                : t('admin2.appt_link_active')}
                          </Badge>
                        </div>
                      </td>
                      <td className="admin-p-12-16">
                        <p
                          className="admin-fw-med-primary-m-0"
                        >
                          {appointment.effectiveCabinet || '—'}
                        </p>
                        <p
                          className="admin-fs-xs-secondary-m-4px-0-0"
                        >
                          {/* UX Audit Admin #2.8: унифицированный формат кабинета. */}
                          {appointment.queueCabinet
                            ? t('admin2.appt_source_queue', { cabinet: appointment.queueCabinet })
                            : appointment.doctorCabinet
                              ? t('admin2.appt_source_doctor', { cabinet: appointment.doctorCabinet })
                              : t('admin2.appt_cabinet_not_specified')}
                        </p>
                      </td>
                      <td style={textCellStyle}>
                        <p className="admin-m-0-fw-med">
                          {formatAppointmentDate(appointment.appointmentDate, t)}
                        </p>
                        <p className="admin-m-4px-0-0">
                          {appointment.appointmentTime || t('admin2.appt_time_not_specified')} ({appointment.duration || 30} {t('admin2.appt_min_short')})
                        </p>
                      </td>
                      <td className="admin-p-12-16">
                        <Badge variant={getAppointmentStatusVariant(appointment.status)}>
                          {getAppointmentStatusLabel(appointment.status, t)}
                        </Badge>
                      </td>
                      <td className="admin-p-12-16">
                        {appointment.hasIntegrityWarnings ? (
                          <div className="admin-d-flex-fd-column-gap-4">
                            <Badge variant="warning">{t('admin2.appt_requires_check')}</Badge>
                            <p
                              className="admin-fs-xs-secondary-m-0"
                            >
                              {(appointment.integrityWarnings || []).join(', ')}
                            </p>
                          </div>
                        ) : (
                          <Badge variant="success">{t('admin2.appt_linked')}</Badge>
                        )}
                      </td>
                      <td style={textCellStyle} title={reason || ''}>
                        {/* UX Audit Admin #1.6: tooltip для обрезанного reason. */}
                        {reason.length > 50 ? `${reason.substring(0, 50)}...` : reason || t('admin2.appt_reason_not_specified')}
                      </td>
                      <td aria-label={t('admin2.appt_actions_aria', { patient: patientName, doctor: doctorName })} className="admin-p-12-16">
                        <div className="flex items-center justify-center gap-2">
                          <IconButton label={t('admin2.appt_edit_btn')} onClick={() => handleEditAppointment(appointment)}>
                            <Edit size={16} />
                          </IconButton>
                          <IconButton
                            label={t('admin2.appt_delete_btn')}
                            tone="danger"
                            onClick={() => handleDeleteAppointment(appointment)}
                          >
                            <Trash2 size={16} />
                          </IconButton>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          )}
        </div>
      </MacOSCard>

      <AppointmentModal
        isOpen={appointmentModal.isOpen}
        onClose={appointmentModal.closeModal}
        appointment={appointmentModal.selectedItem}
        onSave={handleSaveAppointment}
        loading={appointmentModal.loading}
        doctors={allDoctors}
        patients={patients}
      />
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>
  );
};

export default AdminAppointments;
