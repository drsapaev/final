import { Edit, Plus, RefreshCw, Search, Trash2, Users } from 'lucide-react';
import PropTypes from 'prop-types';

import PatientModal from './PatientModal';
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

const AdminPatients = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
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
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление пациента',
      message: `Удалить пациента «${patientName}»?`,
      description: 'Это действие необратимо. Все связанные записи будут помечены как удалённые.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });

    if (!ok) {
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
              Управление пациентами
            </h2>
            <p
              className="admin-patients-subtitle"
            >
              Карточки пациентов, контакты и базовые демографические данные.
            </p>
          </div>
          <Button onClick={handleCreatePatient} startIcon={<Plus size={16} />}>
            Добавить пациента
          </Button>
        </div>

        <div
          className="admin-patients-filters-grid"
        >
          <Input
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

        {/* UX Audit Admin #1.1: кнопка «Сбросить» для быстрой очистки фильтров. */}
        {filtersActive && (
          <div style={{ marginBottom: '12px' }}>
            <Button variant="ghost" size="sm" onClick={() => {
              setSearchTerm(''); setFilterGender(''); setFilterAgeRange(''); setFilterBloodType('');
            }} aria-label="Сбросить все фильтры">
              ✕ Сбросить фильтры
            </Button>
          </div>
        )}

        <div className="admin-overflow-x-auto">
          {loading ? (
            <Skeleton type="table" count={5} />
          ) : error ? (
            <MacOSEmptyState
              icon={RefreshCw}
              title="Ошибка загрузки пациентов"
              description="Не удалось загрузить список пациентов. Проверьте соединение и попробуйте снова."
              action={
                <Button onClick={refresh} startIcon={<RefreshCw size={16} />}>
                  Обновить
                </Button>
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
                <Button onClick={handleCreatePatient} startIcon={<Plus size={16} />}>
                  Добавить первого пациента
                </Button>
              }
            />
          ) : (
            <div className="admin-table-wrapper">
            <table className="admin-w-100pct-bc-collapse" aria-label="Таблица пациентов">
              <thead>
                <tr
                  className="admin-patients-thead-row"
                >
                  <th scope="col" className="admin-patients-th">Пациент</th>
                  <th scope="col" className="admin-patients-th">Возраст</th>
                  <th scope="col" className="admin-patients-th">Пол</th>
                  <th scope="col" className="admin-patients-th">Телефон</th>
                  <th scope="col" className="admin-patients-th">Группа крови</th>
                  <th scope="col" className="admin-patients-th">Последний визит</th>
                  <th scope="col" className="admin-patients-th">Визиты</th>
                  <th scope="col" className="admin-patients-th">Действия</th>
                </tr>
              </thead>
              <tbody>
                {/* PR-41 / High-17: cap rendered rows to 200 to avoid rendering
                    1000+ DOM nodes when the patient list is large. Full
                    virtualization via @tanstack/react-virtual is installed
                    but requires table-layout refactoring — this slice cap
                    is a pragmatic partial fix. */}
                {patients.slice(0, 200).map((patient) => (
                  <tr
                    key={patient.id}
                    className="admin-patients-tbody-row"
                    onMouseEnter={(event) => {
                      event.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
                    }}
                    onMouseLeave={(event) => {
                      event.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <td
                      aria-label={`Пациент ${getPatientName(patient)}`}
                      className="admin-p-12-16"
                    >
                      <div className="admin-flex-center-12">
                        <div
                          aria-hidden="true"
                          className="admin-patients-avatar"
                        >
                          {getPatientInitials(patient)}
                        </div>
                        <div>
                          <p
                            className="admin-patients-name"
                          >
                            {getPatientName(patient)}
                          </p>
                          <p
                            className="admin-patients-email"
                          >
                            {patient.email || 'Email не указан'}
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
                    <td className="admin-patients-td">{formatAge(patient, calculateAge)}</td>
                    <td className="admin-p-12-16">
                      <Badge variant={patient.gender === 'male' ? 'info' : 'success'}>
                        {getGenderLabel(patient.gender)}
                      </Badge>
                    </td>
                    <td className="admin-patients-td">{patient.phone || 'Не указан'}</td>
                    <td className="admin-p-12-16">
                      {patient.bloodType ? (
                        <Badge variant="warning">{patient.bloodType}</Badge>
                      ) : (
                        <span className="admin-text-sm-tertiary">
                          Не указано
                        </span>
                      )}
                    </td>
                    <td className="admin-patients-td">{formatDate(patient.lastVisit)}</td>
                    <td className="admin-patients-td">{patient.visitsCount || 0} визитов</td>
                    <td
                      aria-label={`Действия для пациента ${getPatientName(patient)}`}
                      className="admin-p-12-16"
                    >
                      <div className="flex items-center justify-center gap-2">
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
      {confirmDialog}
    </div>
  );
};

export default AdminPatients;
