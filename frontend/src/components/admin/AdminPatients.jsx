import { Edit, Plus, RefreshCw, Search, Trash2, Users } from 'lucide-react';
import PropTypes from 'prop-types';

import PatientModal from './PatientModal';
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

const genderOptions = [
  { value: '', label: 'Все полы' },
  { value: 'male', label: 'Мужской' },
  { value: 'female', label: 'Женский' },
];

const ageOptions = [
  { value: '', label: 'Все возрасты' },
  { value: '0-18', label: '0-18 лет' },
  { value: '19-35', label: '19-35 лет' },
  { value: '36-50', label: '36-50 лет' },
  { value: '51-65', label: '51-65 лет' },
  { value: '65+', label: '65+ лет' },
];

const bloodTypeOptions = [
  { value: '', label: 'Все группы крови' },
  { value: 'A+', label: 'A+' },
  { value: 'A-', label: 'A-' },
  { value: 'B+', label: 'B+' },
  { value: 'B-', label: 'B-' },
  { value: 'AB+', label: 'AB+' },
  { value: 'AB-', label: 'AB-' },
  { value: 'O+', label: 'O+' },
  { value: 'O-', label: 'O-' },
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

const getPatientName = (patient) =>
  [patient.lastName, patient.firstName, patient.middleName].filter(Boolean).join(' ') || 'Пациент без имени';

const getPatientInitials = (patient) =>
  [patient.firstName, patient.lastName]
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'П';

const getGenderLabel = (gender) => {
  const genderMap = {
    male: 'Мужской',
    female: 'Женский',
  };
  return genderMap[gender] || 'Не указано';
};

const formatDate = (value) => {
  if (!value) {
    return 'Нет визитов';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'Нет визитов';
  }

  return parsed.toLocaleDateString('ru-RU');
};

const formatAge = (patient, calculateAge) => {
  if (!patient.birthDate) {
    return 'Не указано';
  }

  const age = calculateAge(patient.birthDate);
  return Number.isFinite(age) && age >= 0 ? `${age} лет` : 'Не указано';
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

const AdminPatients = () => {
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
    const patientName = getPatientName(patient);
    const confirmed = window.confirm(`Вы уверены, что хотите удалить пациента "${patientName}"?`);

    if (!confirmed) {
      return;
    }

    try {
      await deletePatient(patient.id);
    } catch (deleteError) {
      logger.error('Ошибка удаления пациента:', deleteError);
      notify.error('Ошибка при удалении пациента');
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
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
              Управление пациентами
            </h2>
            <p
              style={{
                margin: '6px 0 0',
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-sm)',
              }}
            >
              Карточки пациентов, контакты и базовые демографические данные.
            </p>
          </div>
          <MacOSButton onClick={handleCreatePatient} startIcon={<Plus size={16} />}>
            Добавить пациента
          </MacOSButton>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(220px, 1fr) minmax(150px, 190px) minmax(150px, 190px) minmax(150px, 190px)',
            gap: '12px',
            marginBottom: '24px',
          }}
        >
          <MacOSInput
            type="text"
            placeholder="Поиск пациентов..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            icon={Search}
            iconPosition="left"
            aria-label="Поиск пациентов"
          />
          <Select
            value={filterGender}
            onChange={setFilterGender}
            options={genderOptions}
            size="large"
            aria-label="Фильтр по полу"
          />
          <Select
            value={filterAgeRange}
            onChange={setFilterAgeRange}
            options={ageOptions}
            size="large"
            aria-label="Фильтр по возрасту"
          />
          <Select
            value={filterBloodType}
            onChange={setFilterBloodType}
            options={bloodTypeOptions}
            size="large"
            aria-label="Фильтр по группе крови"
          />
        </div>

        <div style={{ overflowX: 'auto' }}>
          {loading ? (
            <MacOSLoadingSkeleton type="table" count={5} />
          ) : error ? (
            <MacOSEmptyState
              icon={RefreshCw}
              title="Ошибка загрузки пациентов"
              description="Не удалось загрузить список пациентов. Проверьте соединение и попробуйте снова."
              action={
                <MacOSButton onClick={refresh} startIcon={<RefreshCw size={16} />}>
                  Обновить
                </MacOSButton>
              }
            />
          ) : patients.length === 0 ? (
            <MacOSEmptyState
              icon={Users}
              title="Пациенты не найдены"
              description={
                filtersActive
                  ? 'Попробуйте изменить параметры поиска.'
                  : 'В системе пока нет пациентов.'
              }
              action={
                <MacOSButton onClick={handleCreatePatient} startIcon={<Plus size={16} />}>
                  Добавить первого пациента
                </MacOSButton>
              }
            />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }} aria-label="Таблица пациентов">
              <thead>
                <tr
                  style={{
                    backgroundColor: 'var(--mac-bg-secondary)',
                    borderBottom: '1px solid var(--mac-border)',
                  }}
                >
                  <th scope="col" style={tableHeaderStyle}>Пациент</th>
                  <th scope="col" style={tableHeaderStyle}>Возраст</th>
                  <th scope="col" style={tableHeaderStyle}>Пол</th>
                  <th scope="col" style={tableHeaderStyle}>Телефон</th>
                  <th scope="col" style={tableHeaderStyle}>Группа крови</th>
                  <th scope="col" style={tableHeaderStyle}>Последний визит</th>
                  <th scope="col" style={tableHeaderStyle}>Визиты</th>
                  <th scope="col" style={tableHeaderStyle}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => (
                  <tr
                    key={patient.id}
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
                      aria-label={`Пациент ${getPatientName(patient)}`}
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
                          {getPatientInitials(patient)}
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
                            {getPatientName(patient)}
                          </p>
                          <p
                            style={{
                              fontSize: '12px',
                              color: 'var(--mac-text-secondary)',
                              margin: '4px 0 0',
                            }}
                          >
                            {patient.email || 'Email не указан'}
                          </p>
                          {patient.address ? (
                            <p
                              style={{
                                fontSize: '11px',
                                color: 'var(--mac-text-tertiary)',
                                margin: '2px 0 0',
                              }}
                            >
                              {patient.address}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </td>
                    <td style={textCellStyle}>{formatAge(patient, calculateAge)}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge variant={patient.gender === 'male' ? 'info' : 'success'}>
                        {getGenderLabel(patient.gender)}
                      </MacOSBadge>
                    </td>
                    <td style={textCellStyle}>{patient.phone || 'Не указан'}</td>
                    <td style={{ padding: '12px 16px' }}>
                      {patient.bloodType ? (
                        <MacOSBadge variant="warning">{patient.bloodType}</MacOSBadge>
                      ) : (
                        <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-tertiary)' }}>
                          Не указано
                        </span>
                      )}
                    </td>
                    <td style={textCellStyle}>{formatDate(patient.lastVisit)}</td>
                    <td style={textCellStyle}>{patient.visitsCount || 0} визитов</td>
                    <td
                      aria-label={`Действия для пациента ${getPatientName(patient)}`}
                      style={{ padding: '12px 16px' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <IconButton label="Редактировать пациента" onClick={() => handleEditPatient(patient)}>
                          <Edit size={16} />
                        </IconButton>
                        <IconButton
                          label="Удалить пациента"
                          tone="danger"
                          onClick={() => handleDeletePatient(patient)}
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

      <PatientModal
        isOpen={patientModal.isOpen}
        onClose={patientModal.closeModal}
        patient={patientModal.selectedItem}
        onSave={handleSavePatient}
        loading={patientModal.loading}
      />
    </div>
  );
};

export default AdminPatients;
