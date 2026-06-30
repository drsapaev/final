import { Calendar, Clock, Edit, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import PropTypes from 'prop-types';

import AppointmentModal from './AppointmentModal';
import useAppointments from '../../hooks/useAppointments';
import useDoctors from '../../hooks/useDoctors';
import usePatients from '../../hooks/usePatients';
import useModal from '../../hooks/useModal.jsx';
import notify from '../../services/notify';
import {
  MacOSBadge,
  MacOSButton,
  MacOSCard,
  MacOSEmptyState,
  MacOSInput,
  MacOSLoadingSkeleton,
  Button,
  Select,
} from '../ui/macos';
import logger from '../../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

const statusOptions = [
  { value: '', label: 'Все статусы' },
  { value: 'pending', label: 'Ожидает' },
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

const IconButton = ({ label, tone = 'default', onClick, children }) => (
  <Button
    type="button"
    variant="ghost"
    size="small"
    onClick={onClick}
    aria-label={label}
    title={label}
    style={{
      width: '32px',
      height: '32px',
      padding: 0,
      borderRadius: 'var(--mac-radius-sm)',
      color: tone === 'danger' ? 'var(--mac-error)' : 'var(--mac-text-secondary)',
    }}
  >
    {children}
  </Button>
);

IconButton.propTypes = {
  children: PropTypes.node.isRequired,
  label: PropTypes.string.isRequired,
  onClick: PropTypes.func.isRequired,
  tone: PropTypes.oneOf(['default', 'danger']),
};

const StatCard = ({ label, value, icon: Icon, color }) => (
  <MacOSCard style={{ padding: '24px' }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
      <div>
        <p
          style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-secondary)',
            margin: 0,
          }}
        >
          {label}
        </p>
        <p
          style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-text-primary)',
            margin: '4px 0 0',
          }}
        >
          {value}
        </p>
      </div>
      <Icon aria-hidden="true" size={32} style={{ color }} />
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
        }}
      >
        <StatCard label="Всего записей" value={appointments.length} icon={Calendar} color="var(--mac-accent)" />
        <StatCard label="На сегодня" value={todayAppointments.length} icon={Clock} color="var(--mac-success)" />
        <StatCard label="На завтра" value={tomorrowAppointments.length} icon={Calendar} color="var(--mac-text-primary)" />
        <StatCard label="Ожидают" value={statusStats.pending || 0} icon={Clock} color="var(--mac-warning)" />
      </div>

      <MacOSCard
        variant="default"
        shadow="none"
        style={{
          background: 'var(--mac-bg-primary)',
          border: '1px solid var(--mac-border)',
          padding: '24px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            marginBottom: '24px',
            flexWrap: 'wrap',
          }}
        >
          <div>
            <h2
              style={{
                fontSize: 'var(--mac-font-size-xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                margin: 0,
              }}
            >
              Управление записями
            </h2>
            <p
              style={{
                margin: '6px 0 0',
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-sm)',
              }}
            >
              Административный обзор записей, врачей, кабинетов и статусов.
            </p>
          </div>
          <MacOSButton onClick={handleCreateAppointment} startIcon={<Plus size={16} />}>
            Создать запись
          </MacOSButton>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(220px, 1fr) minmax(150px, 190px) minmax(150px, 190px) minmax(180px, 240px)',
            gap: '12px',
            marginBottom: '24px',
          }}
        >
          <MacOSInput
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
          <MacOSInput
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

        <div style={{ overflowX: 'auto' }}>
          {loading ? (
            <MacOSLoadingSkeleton type="table" count={5} />
          ) : error ? (
            <MacOSEmptyState
              icon={RefreshCw}
              title="Ошибка загрузки записей"
              description="Не удалось загрузить список записей. Проверьте соединение и попробуйте снова."
              action={
                <MacOSButton onClick={refresh} startIcon={<RefreshCw size={16} />}>
                  Обновить
                </MacOSButton>
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
                <MacOSButton onClick={handleCreateAppointment} startIcon={<Plus size={16} />}>
                  Создать первую запись
                </MacOSButton>
              }
            />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }} aria-label="Таблица записей">
              <thead>
                <tr
                  style={{
                    backgroundColor: 'var(--mac-bg-secondary)',
                    borderBottom: '1px solid var(--mac-border)',
                  }}
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
                      style={{
                        borderBottom: '1px solid var(--mac-border)',
                        transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                      }}
                      onMouseEnter={(event) => {
                        event.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
                      }}
                      onMouseLeave={(event) => {
                        event.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <td aria-label={`Пациент ${patientName}`} style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div
                            aria-hidden="true"
                            style={{
                              width: '32px',
                              height: '32px',
                              borderRadius: '50%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              background: 'var(--mac-accent-blue)',
                              color: 'var(--mac-text-on-accent)',
                              fontSize: 'var(--mac-font-size-sm)',
                              fontWeight: 'var(--mac-font-weight-medium)',
                            }}
                          >
                            {getInitials(patientName, 'П')}
                          </div>
                          <div>
                            <p
                              style={{
                                fontWeight: 'var(--mac-font-weight-medium)',
                                color: 'var(--mac-text-primary)',
                                margin: 0,
                              }}
                            >
                              {patientName}
                            </p>
                            {appointment.phone ? (
                              <p
                                style={{
                                  fontSize: 'var(--mac-font-size-sm)',
                                  color: 'var(--mac-text-secondary)',
                                  margin: '4px 0 0',
                                }}
                              >
                                {appointment.phone}
                              </p>
                            ) : null}
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <p
                          style={{
                            fontWeight: 'var(--mac-font-weight-medium)',
                            color: 'var(--mac-text-primary)',
                            margin: 0,
                          }}
                        >
                          {doctorName}
                        </p>
                        <p
                          style={{
                            fontSize: 'var(--mac-font-size-sm)',
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0',
                          }}
                        >
                          {doctorSpecialization || '—'}
                        </p>
                        <div style={{ marginTop: '4px' }}>
                          <MacOSBadge
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
                          </MacOSBadge>
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <p
                          style={{
                            fontWeight: 'var(--mac-font-weight-medium)',
                            color: 'var(--mac-text-primary)',
                            margin: 0,
                          }}
                        >
                          {appointment.effectiveCabinet || '—'}
                        </p>
                        <p
                          style={{
                            fontSize: 'var(--mac-font-size-xs)',
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0',
                          }}
                        >
                          {appointment.queueCabinet
                            ? `Очередь: ${appointment.queueCabinet}`
                            : appointment.doctorCabinet
                              ? `Врач: ${appointment.doctorCabinet}`
                              : 'Нет связанного кабинета'}
                        </p>
                      </td>
                      <td style={textCellStyle}>
                        <p style={{ margin: 0, fontWeight: 'var(--mac-font-weight-medium)' }}>
                          {formatAppointmentDate(appointment.appointmentDate)}
                        </p>
                        <p style={{ margin: '4px 0 0' }}>
                          {appointment.appointmentTime || 'Время не указано'} ({appointment.duration || 30} мин)
                        </p>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <MacOSBadge variant={getAppointmentStatusVariant(appointment.status)}>
                          {getAppointmentStatusLabel(appointment.status)}
                        </MacOSBadge>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        {appointment.hasIntegrityWarnings ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <MacOSBadge variant="warning">Требует проверки</MacOSBadge>
                            <p
                              style={{
                                fontSize: 'var(--mac-font-size-xs)',
                                color: 'var(--mac-text-secondary)',
                                margin: 0,
                              }}
                            >
                              {(appointment.integrityWarnings || []).join(', ')}
                            </p>
                          </div>
                        ) : (
                          <MacOSBadge variant="success">Связано</MacOSBadge>
                        )}
                      </td>
                      <td style={textCellStyle}>
                        {reason.length > 50 ? `${reason.substring(0, 50)}...` : reason || 'Не указана'}
                      </td>
                      <td aria-label={`Действия для записи ${patientName} - ${doctorName}`} style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
