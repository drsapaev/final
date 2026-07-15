import { t } from '../../i18n/adapter';
import { Edit, Plus, RefreshCw, Search, Stethoscope, Trash2 } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';

import DoctorModal from './DoctorModal';
import useDoctors from '../../hooks/useDoctors';
import useModal from '../../hooks/useModal.jsx';
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

// PR-19: departmentOptions now loaded dynamically from /admin/departments
// (was hardcoded — new departments didn't appear in filter dropdown)
const statusOptions = [
  { value: '', label: 'Все статусы' },
  { value: 'active', label: 'Активен' },
  { value: 'inactive', label: 'Неактивен' },
];

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

// PR-19: dynamic department label lookup (was hardcoded)
const getDepartmentLabel = (department, deptList = []) => {
  if (!department) return 'Не указано';
  const found = deptList.find((d) => d.key === department);
  return found ? found.name_ru : department;
};

const AdminDoctors = () => {
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
    { value: '', label: 'Все отделения' },
    ...departments.map((d) => ({ value: d.key, label: d.name_ru || d.key })),
  ];

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
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const confirmed = await confirm({
      title: t('admin.deactivate_doctor_title'),
      message: `Деактивировать врача «${doctorName}»?`,
      description: 'Врач будет отмечен как неактивный, но останется в базе данных. Записи к этому врачу будут скрыты из расписания.',
      confirmLabel: t('admin.deactivate_confirm'),
      cancelLabel: t('admin.cancel'),
      intent: 'warning',
    });

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
    <div className="flex flex-col gap-6">
      <MacOSCard variant="default" shadow="none" className="admin-patients-header-card">
        <div
          className="admin-patients-header-row"
        >
          <div>
            <h2
              className="admin-title-20"
            >
              Управление врачами
            </h2>
            <p
              className="admin-patients-subtitle"
            >
              Аккаунты врачей, специализации, кабинеты и онлайн-лимиты.
            </p>
          </div>
          <Button onClick={handleCreateDoctor} startIcon={<Plus size={16} />}>
            Добавить врача
          </Button>
        </div>

        <div
          className="admin-doctors-filters-grid"
        >
          <Input
            type="text"
            placeholder="Поиск врачей..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            icon={Search}
            iconPosition="left"
            aria-label="Поиск врачей"
          />
          {/* UX Audit Admin #4.7: фильтр специализации — Select вместо текстового инпута. */}
          <Select
            value={filterSpecialization}
            onChange={setFilterSpecialization}
            options={[
              { value: '', label: 'Все специализации' },
              ...[...new Set(doctors.map((d) => d.specialty).filter(Boolean))].map((s) => ({ value: s, label: s })),
            ]}
            size="large"
            aria-label="Фильтр по специализации"
          />
          <Select
            value={filterDepartment}
            onChange={setFilterDepartment}
            options={departmentOptions}
            size="large"
            aria-label="Фильтр по отделению"
          />
          <Select
            value={filterStatus}
            onChange={setFilterStatus}
            options={statusOptions}
            size="large"
            aria-label="Фильтр по статусу врача"
          />
        </div>

        {/* UX Audit Admin #1.1: кнопка «Сбросить» для быстрой очистки фильтров. */}
        {filtersActive && (
          <div style={{ marginBottom: '12px' }}>
            <Button variant="ghost" size="sm" onClick={() => {
              setSearchTerm(''); setFilterSpecialization(''); setFilterDepartment(''); setFilterStatus('');
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
              title="Ошибка загрузки врачей"
              description="Не удалось загрузить список врачей. Проверьте соединение и попробуйте снова."
              action={
                <Button onClick={refresh} startIcon={<RefreshCw size={16} />}>
                  Обновить
                </Button>
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
                <Button onClick={handleCreateDoctor} startIcon={<Plus size={16} />}>
                  Добавить первого врача
                </Button>
              }
            />
          ) : (
            <div className="admin-table-wrapper">
            <table className="admin-w-100pct-bc-collapse" aria-label="Таблица врачей">
              <thead>
                <tr
                  className="admin-patients-thead-row"
                >
                  <th scope="col" className="admin-patients-th">Врач</th>
                  <th scope="col" className="admin-patients-th">Специализация</th>
                  <th scope="col" className="admin-patients-th">Отделение</th>
                  <th scope="col" className="admin-patients-th">Опыт</th>
                  <th scope="col" className="admin-patients-th">Статус</th>
                  <th scope="col" className="admin-patients-th">Пациенты</th>
                  <th scope="col" className="admin-patients-th">Действия</th>
                </tr>
              </thead>
              <tbody>
                {doctors.map((doctor) => (
                  <tr
                    key={doctor.id}
                    className="admin-patients-tbody-row"
                    >
                    <td
                      aria-label={`Врач ${getDoctorName(doctor)}`}
                      className="admin-p-12-16"
                    >
                      <div className="admin-flex-center-12">
                        <div
                          aria-hidden="true"
                          className="admin-patients-avatar"
                        >
                          {getDoctorInitials(doctor)}
                        </div>
                        <div>
                          <p
                            className="admin-patients-name"
                          >
                            {getDoctorName(doctor)}
                          </p>
                          <p
                            className="admin-patients-email"
                          >
                            {doctor.user?.email || doctor.email || 'Нет email'}
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
                              {doctor.user?.is_active === false ? 'Аккаунт неактивен' : 'Аккаунт активен'}
                            </Badge>
                            <Badge variant={doctor.cabinet ? 'info' : 'warning'}>
                              {doctor.cabinet ? `Кабинет ${doctor.cabinet}` : 'Кабинет не задан'}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="admin-p-12-16">
                      <Badge variant="info">
                        {doctor.specialty || doctor.specialization || 'Не указано'}
                      </Badge>
                    </td>
                    <td className="admin-p-12-16">
                      <Badge variant="success">
                        {getDepartmentLabel(doctor.specialty || doctor.department, departments)}
                      </Badge>
                    </td>
                    <td className="admin-patients-td">
                      {doctor.experience ? `${doctor.experience} лет` : 'Не указано'}
                    </td>
                    <td className="admin-p-12-16">
                      <Badge variant={doctor.active ? 'success' : 'warning'}>
                        {doctor.active ? 'Активен' : 'Неактивен'}
                      </Badge>
                    </td>
                    <td className="admin-patients-td">{doctor.patientsCount || 0} пациентов</td>
                    <td
                      aria-label={`Действия для врача ${getDoctorName(doctor)}`}
                      className="admin-p-12-16"
                    >
                      <div className="flex items-center justify-center gap-2">
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
      {confirmDialog}
    </div>
  );
};

export default AdminDoctors;
