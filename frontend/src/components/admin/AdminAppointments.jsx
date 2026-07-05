import { Calendar, Clock, Edit, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import PropTypes from 'prop-types';

import AppointmentModal from './AppointmentModal';
import useAppointments from '../../hooks/useAppointments';
import useDoctors from '../../hooks/useDoctors';
import usePatients from '../../hooks/usePatients';
import useModal from '../../hooks/useModal.jsx';
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

const statusOptions = [
  { value: '', label: 'Все статусы' },
  { value: 'pending', label: 'Ожидает оплаты' },
  { value: 'confirmed', label: 'Подтверждена' },
  { value: 'paid', label: 'Оплачена' },
  { value: 'in_visit', label: 'На приеме' },
  { value: 'completed', label: 'Завершена' },
  { value: 'cancelled', label: 'Отменена' },
  { value: 'no_show', label: 'Не явился' },
];

const tableHeaderStyle = {
  textAlign: 'left',
  padding: '12px 16px',
  color: 'var(--mac-text-secondary)',
  fontWeight: 'var(--mac-font-weight-semibold)',
  fontSize: 'var(--mac-font-size-sm)',
};

const textCellStyle = {
  padding: '12px 16px',
  fontSize: 'var(--mac-font-size-sm)',
  color: 'var(--mac-text-secondary)',
};

const getAppointmentPatientDisplayName = (appointment) => {
  const rawName =
    appointment?.patientName ||
    appointment?.patient_name ||
    appointment?.patient?.full_name ||
    appointment?.patient?.fio ||
    appointment?.patient?.name ||
    appointment?.patient?.first_name ||
    appointment?.patient?.last_name ||
    'Пациент';

  const normalized = String(rawName).trim();
  return normalized || 'Пациент';
};

const getAppointmentDoctorDisplayName = (appointment) => {
  const rawName =
    appointment?.doctorName ||
    appointment?.doctor_name ||
    appointment?.doctor?.full_name ||
    appointment?.doctor?.name ||
    appointment?.doctor?.user?.full_name ||
    appointment?.doctor?.user?.username ||
    'Врач';

  const normalized = String(rawName).trim();
  return normalized || 'Врач';
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

const getAppointmentStatusLabel = (status) => {
  const statusMap = {
    pending: 'Ожидает оплаты',
    scheduled: 'Запланирована',
    confirmed: 'Подтверждена',
    paid: 'Оплачена',
    in_visit: 'На приеме',
    completed: 'Завершена',
    cancelled: 'Отменена',
    no_show: 'Не явился',
  };
  return statusMap[status] || status || 'Не указан';
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

const formatAppointmentDate = (value) => {
  if (!value) {
    return 'Дата не указана';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString('ru-RU');
};

const getDoctorOptionLabel = (doctor) => {
  const name = doctor.user?.full_name || doctor.name || doctor.user?.username || `Врач #${doctor.id}`;
  const flags = [
    doctor.active === false ? 'неактивен' : null,
    doctor.user?.is_active === false ? 'аккаунт неактивен' : null,
    doctor.cabinet ? `каб. ${doctor.cabinet}` : null,
  ].filter(Boolean);

  return flags.length > 0 ? `${name} • ${flags.join(' • ')}` : name;
};

const StatCard = ({ label, value, icon: Icon, color }) => (
  <MacOSCard className="p-6">
    <div className="admin-d-flex-ai-center-jc-between-gap-16">
      <div>
        <p
          className="admin-fs-sm-fw-med-secondary-m-0"
        >
          {label}
        </p>
        <p
          className="admin-fs-2xl-fw-bold-primary-m-4px-0-0"
        >
          {value}
        </p>
      </div>
      <Icon aria-hidden="true" size={32} className="admin-col-dyn" style={{ '--admin-col0': color }} />
    </div>
  </MacOSCard>
);

StatCard.propTypes = {
  color: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.number.isRequired,
};

const AdminAppointments = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
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
  const doctorOptions = [
    { value: '', label: 'Все врачи' },
    ...allDoctors.map((doctor) => ({
      value: String(doctor.id),
      label: getDoctorOptionLabel(doctor),
    })),
  ];

  const handleCreateAppointment = () => {
    appointmentModal.openModal(null);
  };

  const handleEditAppointment = (appointment) => {
    appointmentModal.openModal(appointment);
  };

  const handleDeleteAppointment = async (appointment) => {
    const patientName = getAppointmentPatientDisplayName(appointment);
    const doctorName = getAppointmentDoctorDisplayName(appointment);
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление записи',
      message: `Удалить запись «${patientName} — ${doctorName}»?`,
      description: 'Это действие необратимо. Запись будет удалена из журнала.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });

    if (!ok) {
      return;
    }

    try {
      await deleteAppointment(appointment.id);
    } catch (deleteError) {
      logger.error('Ошибка удаления записи:', deleteError);
      notify.error('Ошибка при удалении записи');
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
        <StatCard label="Всего записей" value={appointments.length} icon={Calendar} color="var(--mac-accent)" />
        <StatCard label="На сегодня" value={todayAppointments.length} icon={Clock} color="var(--mac-success)" />
        <StatCard label="На завтра" value={tomorrowAppointments.length} icon={Calendar} color="var(--mac-text-primary)" />
        <StatCard label="Ожидают" value={statusStats.pending || 0} icon={Clock} color="var(--mac-warning)" />
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
              Управление записями
            </h2>
            <p
              className="admin-m-6px-0-0-secondary-fs-sm"
            >
              Административный обзор записей, врачей, кабинетов и статусов.
            </p>
          </div>
          <Button onClick={handleCreateAppointment} startIcon={<Plus size={16} />}>
            Создать запись
          </Button>
        </div>

        <div
          className="admin-d-grid-gtc-minmax-220px-1fr-min-gap-12-mb-24"
        >
          <Input
            type="text"
            placeholder="Поиск записей..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            icon={Search}
            iconPosition="left"
            aria-label="Поиск записей"
          />
          <Select
            value={filterStatus}
            onChange={setFilterStatus}
            options={statusOptions}
            size="large"
            aria-label="Фильтр по статусу записи"
          />
          <Input
            type="date"
            value={filterDate}
            onChange={(event) => setFilterDate(event.target.value)}
            aria-label="Фильтр по дате записи"
          />
          <Select
            value={filterDoctor}
            onChange={setFilterDoctor}
            options={doctorOptions}
            size="large"
            aria-label="Фильтр по врачу"
          />
        </div>

        <div className="admin-ovx-auto">
          {loading ? (
            <Skeleton type="table" count={5} />
          ) : error ? (
            <MacOSEmptyState
              icon={RefreshCw}
              title="Ошибка загрузки записей"
              description="Не удалось загрузить список записей. Проверьте соединение и попробуйте снова."
              action={
                <Button onClick={refresh} startIcon={<RefreshCw size={16} />}>
                  Обновить
                </Button>
              }
            />
          ) : appointments.length === 0 ? (
            <MacOSEmptyState
              icon={Calendar}
              title="Записи не найдены"
              description={
                filtersActive
                  ? 'Попробуйте изменить параметры поиска.'
                  : 'В системе пока нет записей.'
              }
              action={
                <Button onClick={handleCreateAppointment} startIcon={<Plus size={16} />}>
                  Создать первую запись
                </Button>
              }
            />
          ) : (
            <div className="admin-table-wrapper">
            <table className="admin-w-100pct-bc-collapse" aria-label="Таблица записей">
              <thead>
                <tr
                  className="admin-bgc-bg-secondary-bd-b-1px-solid-var-mac-bo"
                >
                  <th scope="col" style={tableHeaderStyle}>Пациент</th>
                  <th scope="col" style={tableHeaderStyle}>Врач</th>
                  <th scope="col" style={tableHeaderStyle}>Кабинет</th>
                  <th scope="col" style={tableHeaderStyle}>Дата и время</th>
                  <th scope="col" style={tableHeaderStyle}>Статус</th>
                  <th scope="col" style={tableHeaderStyle}>Связность</th>
                  <th scope="col" style={tableHeaderStyle}>Причина</th>
                  <th scope="col" style={tableHeaderStyle}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map((appointment) => {
                  const patientName = getAppointmentPatientDisplayName(appointment);
                  const doctorName = getAppointmentDoctorDisplayName(appointment);
                  const doctorSpecialization = getAppointmentDoctorSpecialization(appointment);
                  const reason = appointment.reason || '';

                  return (
                    <tr
                      key={appointment.id}
                      className="admin-bd-b-1px-solid-var-mac-bo-tr-background-color-var"
                      onMouseEnter={(event) => {
                        event.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
                      }}
                      onMouseLeave={(event) => {
                        event.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <td aria-label={`Пациент ${patientName}`} className="admin-p-12-16">
                        <div className="admin-flex-center-12">
                          <div
                            aria-hidden="true"
                            className="admin-w-32-h-32-radius-50pct-d-flex-ai-center-jc-center-bg-blue-on-accent-fs-sm-fw-med"
                          >
                            {getInitials(patientName, 'П')}
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
                              ? 'Врач неактивен'
                              : appointment.doctor?.user_active === false
                                ? 'Аккаунт врача неактивен'
                                : 'Связь активна'}
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
                          {appointment.queueCabinet
                            ? `Очередь: ${appointment.queueCabinet}`
                            : appointment.doctorCabinet
                              ? `Врач: ${appointment.doctorCabinet}`
                              : 'Нет связанного кабинета'}
                        </p>
                      </td>
                      <td style={textCellStyle}>
                        <p className="admin-m-0-fw-med">
                          {formatAppointmentDate(appointment.appointmentDate)}
                        </p>
                        <p className="admin-m-4px-0-0">
                          {appointment.appointmentTime || 'Время не указано'} ({appointment.duration || 30} мин)
                        </p>
                      </td>
                      <td className="admin-p-12-16">
                        <Badge variant={getAppointmentStatusVariant(appointment.status)}>
                          {getAppointmentStatusLabel(appointment.status)}
                        </Badge>
                      </td>
                      <td className="admin-p-12-16">
                        {appointment.hasIntegrityWarnings ? (
                          <div className="admin-d-flex-fd-column-gap-4">
                            <Badge variant="warning">Требует проверки</Badge>
                            <p
                              className="admin-fs-xs-secondary-m-0"
                            >
                              {(appointment.integrityWarnings || []).join(', ')}
                            </p>
                          </div>
                        ) : (
                          <Badge variant="success">Связано</Badge>
                        )}
                      </td>
                      <td style={textCellStyle}>
                        {reason.length > 50 ? `${reason.substring(0, 50)}...` : reason || 'Не указана'}
                      </td>
                      <td aria-label={`Действия для записи ${patientName} - ${doctorName}`} className="admin-p-12-16">
                        <div className="flex items-center justify-center gap-2">
                          <IconButton label="Редактировать запись" onClick={() => handleEditAppointment(appointment)}>
                            <Edit size={16} />
                          </IconButton>
                          <IconButton
                            label="Удалить запись"
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
