import { Edit, Plus, RefreshCw, Search, Stethoscope, Trash2 } from 'lucide-react';
import PropTypes from 'prop-types';

import DoctorModal from './DoctorModal';
import useDoctors from '../../hooks/useDoctors';
import useModal from '../../hooks/useModal.jsx';
import notify from '../../services/notify';
import {
  MacOSBadge,
  MacOSButton,
  MacOSCard,
  MacOSEmptyState,
  MacOSInput,
  MacOSLoadingSkeleton,
  MacOSSelect,
} from '../ui/macos';
import logger from '../../utils/logger';

const departmentOptions = [
  { value: '', label: 'Все отделения' },
  { value: 'cardiology', label: 'Кардиология' },
  { value: 'dermatology', label: 'Дерматология' },
  { value: 'dentistry', label: 'Стоматология' },
  { value: 'stomatology', label: 'Стоматология' },
  { value: 'laboratory', label: 'Лаборатория' },
  { value: 'cosmetology', label: 'Косметология' },
  { value: 'procedures', label: 'Процедуры' },
  { value: 'physiotherapy', label: 'Физиотерапия' },
  { value: 'functional_diagnostics', label: 'Функциональная диагностика' },
  { value: 'general', label: 'Общее' },
];

const statusOptions = [
  { value: '', label: 'Все статусы' },
  { value: 'active', label: 'Активен' },
  { value: 'inactive', label: 'Неактивен' },
];

const departmentLabels = Object.fromEntries(
  departmentOptions.filter((item) => item.value).map((item) => [item.value, item.label])
);

const shellStyle = {
  background: 'var(--mac-bg-primary)',
  border: '1px solid var(--mac-border)',
};

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

const getDoctorName = (doctor) =>
  doctor.user?.full_name || doctor.name || doctor.user?.username || 'Неизвестно';

const getDoctorInitials = (doctor) =>
  getDoctorName(doctor)
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'Д';

const getDepartmentLabel = (department) => departmentLabels[department] || department || 'Не указано';

const IconButton = ({ label, tone = 'default', onClick, children }) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={label}
    title={label}
    style={{
      width: '32px',
      height: '32px',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 0,
      border: '1px solid transparent',
      borderRadius: 'var(--mac-radius-sm)',
      color: tone === 'danger' ? 'var(--mac-error)' : 'var(--mac-text-secondary)',
      backgroundColor: 'transparent',
      cursor: 'pointer',
      transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
    }}
    onMouseEnter={(event) => {
      event.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
    }}
    onMouseLeave={(event) => {
      event.currentTarget.style.backgroundColor = 'transparent';
    }}
  >
    {children}
  </button>
);

IconButton.propTypes = {
  children: PropTypes.node.isRequired,
  label: PropTypes.string.isRequired,
  onClick: PropTypes.func.isRequired,
  tone: PropTypes.oneOf(['default', 'danger']),
};

const AdminDoctors = () => {
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
    const doctorName = getDoctorName(doctor);
    const confirmed = window.confirm(
      `Вы уверены, что хотите деактивировать врача "${doctorName}"?\n\nВрач будет отмечен как неактивный, но останется в базе данных.`
    );

    if (!confirmed) {
      return;
    }

    try {
      await deleteDoctor(doctor.id);
      notify.success(`Врач "${doctorName}" успешно деактивирован`);
    } catch (deleteError) {
      logger.error('Ошибка деактивации врача:', deleteError);
      notify.error(`Ошибка при деактивации врача: ${deleteError.message || 'Неизвестная ошибка'}`);
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard variant="default" shadow="none" style={{ ...shellStyle, padding: '24px' }}>
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
              Управление врачами
            </h2>
            <p
              style={{
                margin: '6px 0 0',
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-sm)',
              }}
            >
              Аккаунты врачей, специализации, кабинеты и онлайн-лимиты.
            </p>
          </div>
          <MacOSButton onClick={handleCreateDoctor} startIcon={<Plus size={16} />}>
            Добавить врача
          </MacOSButton>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(220px, 1fr) minmax(180px, 240px) minmax(180px, 240px) minmax(160px, 200px)',
            gap: '12px',
            marginBottom: '24px',
          }}
        >
          <MacOSInput
            type="text"
            placeholder="Поиск врачей..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            icon={Search}
            iconPosition="left"
            aria-label="Поиск врачей"
          />
          <MacOSInput
            type="text"
            placeholder="Специализация..."
            value={filterSpecialization}
            onChange={(event) => setFilterSpecialization(event.target.value)}
            aria-label="Фильтр по специализации"
          />
          <MacOSSelect
            value={filterDepartment}
            onChange={(event) => setFilterDepartment(event.target.value)}
            options={departmentOptions}
            aria-label="Фильтр по отделению"
          />
          <MacOSSelect
            value={filterStatus}
            onChange={(event) => setFilterStatus(event.target.value)}
            options={statusOptions}
            aria-label="Фильтр по статусу врача"
          />
        </div>

        <div style={{ overflowX: 'auto' }}>
          {loading ? (
            <MacOSLoadingSkeleton type="table" count={5} />
          ) : error ? (
            <MacOSEmptyState
              icon={RefreshCw}
              title="Ошибка загрузки врачей"
              description="Не удалось загрузить список врачей. Проверьте соединение и попробуйте снова."
              action={
                <MacOSButton onClick={refresh} startIcon={<RefreshCw size={16} />}>
                  Обновить
                </MacOSButton>
              }
            />
          ) : doctors.length === 0 ? (
            <MacOSEmptyState
              icon={Stethoscope}
              title="Врачи не найдены"
              description={
                filtersActive
                  ? 'Попробуйте изменить параметры поиска.'
                  : 'В системе пока нет врачей.'
              }
              action={
                <MacOSButton onClick={handleCreateDoctor} startIcon={<Plus size={16} />}>
                  Добавить первого врача
                </MacOSButton>
              }
            />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }} aria-label="Таблица врачей">
              <thead>
                <tr
                  style={{
                    backgroundColor: 'var(--mac-bg-secondary)',
                    borderBottom: '1px solid var(--mac-border)',
                  }}
                >
                  <th scope="col" style={tableHeaderStyle}>Врач</th>
                  <th scope="col" style={tableHeaderStyle}>Специализация</th>
                  <th scope="col" style={tableHeaderStyle}>Отделение</th>
                  <th scope="col" style={tableHeaderStyle}>Опыт</th>
                  <th scope="col" style={tableHeaderStyle}>Статус</th>
                  <th scope="col" style={tableHeaderStyle}>Пациенты</th>
                  <th scope="col" style={tableHeaderStyle}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {doctors.map((doctor) => (
                  <tr
                    key={doctor.id}
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
                    <td
                      aria-label={`Врач ${getDoctorName(doctor)}`}
                      style={{ padding: '12px 16px' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div
                          aria-hidden="true"
                          style={{
                            width: '40px',
                            height: '40px',
                            borderRadius: '50%',
                            backgroundColor: 'var(--mac-accent)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'var(--mac-text-on-accent)',
                            fontSize: 'var(--mac-font-size-sm)',
                            fontWeight: 'var(--mac-font-weight-medium)',
                          }}
                        >
                          {getDoctorInitials(doctor)}
                        </div>
                        <div>
                          <p
                            style={{
                              fontWeight: 'var(--mac-font-weight-medium)',
                              color: 'var(--mac-text-primary)',
                              fontSize: 'var(--mac-font-size-sm)',
                              margin: 0,
                            }}
                          >
                            {getDoctorName(doctor)}
                          </p>
                          <p
                            style={{
                              fontSize: '12px',
                              color: 'var(--mac-text-secondary)',
                              margin: '4px 0 0',
                            }}
                          >
                            {doctor.user?.email || doctor.email || 'Нет email'}
                          </p>
                          {doctor.user?.phone ? (
                            <p
                              style={{
                                fontSize: '11px',
                                color: 'var(--mac-text-tertiary)',
                                margin: '2px 0 0',
                              }}
                            >
                              {doctor.user.phone}
                            </p>
                          ) : null}
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                            <MacOSBadge variant={doctor.user?.is_active === false ? 'warning' : 'success'}>
                              {doctor.user?.is_active === false ? 'Аккаунт неактивен' : 'Аккаунт активен'}
                            </MacOSBadge>
                            <MacOSBadge variant={doctor.cabinet ? 'info' : 'warning'}>
                              {doctor.cabinet ? `Кабинет ${doctor.cabinet}` : 'Кабинет не задан'}
                            </MacOSBadge>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge variant="info">
                        {doctor.specialty || doctor.specialization || 'Не указано'}
                      </MacOSBadge>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge variant="success">
                        {getDepartmentLabel(doctor.specialty || doctor.department)}
                      </MacOSBadge>
                    </td>
                    <td style={textCellStyle}>
                      {doctor.experience ? `${doctor.experience} лет` : 'Не указано'}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge variant={doctor.active ? 'success' : 'warning'}>
                        {doctor.active ? 'Активен' : 'Неактивен'}
                      </MacOSBadge>
                    </td>
                    <td style={textCellStyle}>{doctor.patientsCount || 0} пациентов</td>
                    <td
                      aria-label={`Действия для врача ${getDoctorName(doctor)}`}
                      style={{ padding: '12px 16px' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <IconButton label="Редактировать врача" onClick={() => handleEditDoctor(doctor)}>
                          <Edit size={16} />
                        </IconButton>
                        <IconButton
                          label="Деактивировать врача"
                          tone="danger"
                          onClick={() => handleDeleteDoctor(doctor)}
                        >
                          <Trash2 size={16} />
                        </IconButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
      />
    </div>
  );
};

export default AdminDoctors;
