import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import ServiceAuditHistory from './ServiceAuditHistory';
import ServiceChangesPreview from './ServiceChangesPreview';
import ServiceBatchEdit from './ServiceBatchEdit';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
import {
  Package,
  Plus,
  Search,
  Filter,
  Edit,
  Trash2,
  Save,
  X,
  RefreshCw,
  AlertCircle,
  Heart,
  Scissors,
  Stethoscope,
  TestTube,
  Users,
  History,
  CheckSquare
} from 'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Select,
  Table,
  MacOSEmptyState,
  Alert,
  Checkbox,
} from '../ui/macos';
import {
  normalizeServiceCode,
  formatServiceCodeInput,
  isValidServiceCode } from '../../utils/serviceCodeUtils';
import { notify } from '../../services/notify.js';

const SERVICE_GROUP_PREFIXES = {
  cardiology: ['K'],
  ecg: ['K'],
  dermatology: ['D'],
  dental: ['S'],
  laboratory: ['L'],
  procedures: ['C', 'P', 'O']
};

const SERVICE_GROUP_LABELS = {
  cardiology: 'Кардиология',
  ecg: 'ЭКГ',
  dermatology: 'Дерматология',
  dental: 'Стоматология',
  laboratory: 'Лаборатория',
  procedures: 'Процедуры'
};

const SERVICE_GROUP_ALIASES = {
  cardio: 'cardiology',
  cardiology: 'cardiology',
  derma: 'dermatology',
  dermatology: 'dermatology',
  dental: 'dental',
  dentistry: 'dental',
  stomatology: 'dental',
  lab: 'laboratory',
  laboratory: 'laboratory',
  ecg: 'ecg',
  echokg: 'ecg',
  procedure: 'procedures',
  procedures: 'procedures',
  physio: 'procedures',
  physiotherapy: 'procedures',
  cosmetology: 'procedures'
};

const resolveServiceGroup = ({ queueTag, departmentKey, categorySpecialty }) => {
  for (const rawValue of [queueTag, departmentKey, categorySpecialty]) {
    if (!rawValue) continue;
    const normalized = String(rawValue).trim().toLowerCase();
    if (!normalized) continue;
    if (SERVICE_GROUP_PREFIXES[normalized]) return normalized;
    if (SERVICE_GROUP_ALIASES[normalized]) {
      return SERVICE_GROUP_ALIASES[normalized];
    }
  }

  return null;
};

const getAllowedPrefixesForGroup = (groupKey) => SERVICE_GROUP_PREFIXES[groupKey] || [];

const ServiceCatalog = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces native confirm()).
  const [confirm, confirmDialog] = useConfirm();
  const [loading, setLoading] = useState(true);
  const [services, setServices] = useState([]);
  const [categories, setCategories] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [departments, setDepartments] = useState([]);
  // ⭐ SSOT: Queue profiles for dynamic queue_tag selection
  const [queueProfiles, setQueueProfiles] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSpecialty, setSelectedSpecialty] = useState('all');
  const [selectedDepartment, setSelectedDepartment] = useState('all');
  const [editingService, setEditingService] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showHistory, setShowHistory] = useState(null); // { serviceId, serviceName }
  const [showBatchEdit, setShowBatchEdit] = useState(false);
  const [selectedServiceIds, setSelectedServiceIds] = useState(new Set());
  const [message, setMessage] = useState({ type: '', text: '' });

  // Иконки специальностей
  const specialtyIcons = {
    cardiology: Heart,
    dermatology: Stethoscope,
    stomatology: Scissors,
    laboratory: TestTube,
    physiotherapy: Package // Можно заменить на более подходящую иконку
  };

  const specialtyColors = {
    cardiology: 'var(--mac-error)',
    dermatology: 'var(--mac-warning)',
    stomatology: 'var(--mac-info)',
    laboratory: 'var(--mac-success)',
    physiotherapy: 'var(--mac-accent)'
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);

      // Загружаем услуги, категории, врачей, отделения и профили очередей параллельно
      const [servicesRes, categoriesRes, doctorsRes, departmentsRes, queueProfilesRes] = await Promise.allSettled([
      api.get('/services'),
      api.get('/services/categories'),
      api.get('/services/admin/doctors'),
      api.get('/departments'),
      api.get('/queues/profiles?active_only=false') // ⭐ SSOT: Load queue profiles
      ]);

      if (servicesRes.status === 'fulfilled') {
        setServices(servicesRes.value.data);
      } else {
        logger.error('Ошибка загрузки услуг:', servicesRes.reason);
      }

      if (categoriesRes.status === 'fulfilled') {
        setCategories(categoriesRes.value.data);
      } else {
        logger.error('Ошибка загрузки категорий:', categoriesRes.reason);
      }

      if (doctorsRes.status === 'fulfilled') {
        setDoctors(doctorsRes.value.data);
      } else {
        logger.error('Ошибка загрузки врачей:', doctorsRes.reason);
      }

      if (departmentsRes.status === 'fulfilled') {
        // Backend returns {success: true, data: [...], count: N}
        setDepartments(departmentsRes.value.data?.data || []);
      } else {
        logger.error('Ошибка загрузки отделений:', departmentsRes.reason);
      }

      // ⭐ SSOT: Load queue profiles for queue_tag selection
      if (queueProfilesRes.status === 'fulfilled') {
        setQueueProfiles(queueProfilesRes.value.data?.profiles || []);
      } else {
        logger.error('Ошибка загрузки профилей очередей:', queueProfilesRes.reason);
      }

    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки данных' });
    } finally {
      setLoading(false);
    }
  };

  const filteredServices = services.filter((service) => {
    const matchesSearch = service.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || service.category_id === parseInt(selectedCategory);
    const matchesSpecialty = selectedSpecialty === 'all' ||
    categories.find((cat) => cat.id === service.category_id)?.specialty === selectedSpecialty;
    const matchesDepartment = selectedDepartment === 'all' || service.department_key === selectedDepartment;

    return matchesSearch && matchesCategory && matchesSpecialty && matchesDepartment;
  });

  const handleSaveService = async (serviceData) => {
    try {
      logger.log('🔄 Отправляем данные услуги:', serviceData);

      let savedService;
      if (editingService) {
        // ✅ ОПТИМИСТИЧНОЕ ОБНОВЛЕНИЕ: Обновляем UI сразу
        const optimisticService = { ...editingService, ...serviceData };
        setServices(prevServices =>
          prevServices.map(s => s.id === editingService.id ? optimisticService : s)
        );

        try {
          const response = await api.put(`/services/${editingService.id}`, serviceData);
          savedService = response.data;

          // Обновляем с реальными данными от сервера
          setServices(prevServices =>
            prevServices.map(s => s.id === savedService.id ? savedService : s)
          );
        } catch (error) {
          // ❌ ОТКАТ: Возвращаем старое состояние при ошибке
          setServices(prevServices =>
            prevServices.map(s => s.id === editingService.id ? editingService : s)
          );
          throw error;
        }
      } else {
        const response = await api.post('/services', serviceData);
        savedService = response.data;

        // ✅ ОПТИМИСТИЧНОЕ ДОБАВЛЕНИЕ: Добавляем в список сразу
        setServices(prevServices => [savedService, ...prevServices]);
      }

      setMessage({
        type: 'success',
        text: editingService ? 'Услуга обновлена' : 'Услуга создана'
      });
      setEditingService(null);
      setShowAddForm(false);
    } catch (error) {
      logger.error('Ошибка сохранения:', error);

      // ✅ ПАРСИНГ ДЕТАЛЬНЫХ ОШИБОК ОТ BACKEND
      let errorMessage = 'Ошибка сохранения услуги';
      const errorData = error.response?.data || {};

      if (errorData.detail) {
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          // Pydantic validation errors
          const errors = errorData.detail.map((err) => {
            const field = err.loc ? err.loc.join('.') : 'unknown';
            return `${field}: ${err.msg}`;
          }).join('; ');
          errorMessage = `Ошибка валидации: ${errors}`;
        } else if (errorData.detail.message) {
          errorMessage = errorData.detail.message;
        }
      } else if (error.response?.status === 409) {
        errorMessage = 'Услуга с таким кодом уже существует';
      } else if (error.response?.status === 422) {
        errorMessage = 'Неверный формат данных. Проверьте коды услуг';
      } else if (error.message) {
        errorMessage = error.message;
      }

      setMessage({ type: 'error', text: errorMessage });
    }
  };

  const handleDeleteService = async (serviceId) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление услуги',
      message: 'Удалить услугу?',
      description: 'Услуга будет деактивирована. При необходимости её можно восстановить через администратора.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });
    if (!ok) return;

    // Сохраняем старое состояние для отката
    const oldServices = [...services];
    const serviceToDelete = services.find(s => s.id === serviceId);

    try {
      // ✅ ОПТИМИСТИЧНОЕ УДАЛЕНИЕ: Деактивируем в UI сразу
      setServices(prevServices =>
        prevServices.map(s => s.id === serviceId ? { ...s, active: false } : s)
      );

      const response = await api.delete(`/services/${serviceId}`);

      // Обновляем с реальными данными от сервера
      if (response.data.active === false) {
        setServices(prevServices =>
          prevServices.map(s => s.id === serviceId ? { ...s, active: false } : s)
        );
      }

      setMessage({ type: 'success', text: response.data.message || 'Услуга удалена' });
    } catch (error) {
      // ❌ ОТКАТ: Возвращаем старое состояние при ошибке
      setServices(oldServices);

      logger.error('Ошибка удаления:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Ошибка удаления услуги' });
    }
  };

  const getCategoryName = (categoryId) => {
    const category = categories.find((cat) => cat.id === categoryId);
    return category?.name_ru || 'Без категории';
  };

  const getCategorySpecialty = (categoryId) => {
    const category = categories.find((cat) => cat.id === categoryId);
    return category?.specialty;
  };

  const getSpecialtyIcon = (specialty) => {
    const IconComponent = specialtyIcons[specialty] || Package;
    return IconComponent;
  };

  const toggleServiceSelection = (serviceId) => {
    const newSelected = new Set(selectedServiceIds);
    if (newSelected.has(serviceId)) {
      newSelected.delete(serviceId);
    } else {
      newSelected.add(serviceId);
    }
    setSelectedServiceIds(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedServiceIds.size === filteredServices.length) {
      setSelectedServiceIds(new Set());
    } else {
      setSelectedServiceIds(new Set(filteredServices.map(s => s.id)));
    }
  };

  const handleBatchEditComplete = () => {
    setShowBatchEdit(false);
    setSelectedServiceIds(new Set());
    loadData();
  };

  if (loading) {
    return (
      <MacOSCard
        variant="default"
        className="p-6">

        <div className="admin-flex-center-justify">
          <RefreshCw className="admin-spinner-20-mr-8" size={20} />
          <span className="admin-load-text-primary">Загрузка справочника услуг...</span>
        </div>
      </MacOSCard>);

  }

  return (
    <div className="flex flex-col gap-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="admin-page-h2-xl-semi-primary-m0">
            Справочник услуг
          </h2>
          <p className="admin-header-p-mt-4-sm-secondary">
            Управление услугами и ценами по специальностям
          </p>
        </div>

        <div className="admin-form-row-gap-12">
          {selectedServiceIds.size > 0 && (
            <Button
              variant="outline"
              onClick={() => setShowBatchEdit(true)}
              className="admin-btn-filter-active-catalog"
            >
              <CheckSquare size={16} className="mr-2" />
              Редактировать ({selectedServiceIds.size})
            </Button>
          )}
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className="mr-2" />
            Обновить
          </Button>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus size={16} className="mr-2" />
            Добавить услугу
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text &&
      <Alert
        type={message.type === 'success' ? 'success' : 'error'}
        title={message.text}
        onClose={() => setMessage({ type: '', text: '' })} />

      }

      {/* Фильтры */}
      <MacOSCard
        variant="default"
        className="p-6">

        <div className="admin-grid-auto-250-12">
          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              Поиск по названию
            </label>
            <Input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Введите название услуги..."
              icon={Search}
              iconPosition="left" />
          </div>

          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              Специальность
            </label>
            <Select
              value={selectedSpecialty}
              onChange={(value) => setSelectedSpecialty(value)}
              options={[
              { value: 'all', label: 'Все специальности' },
              { value: 'cardiology', label: 'Кардиология' },
              { value: 'dermatology', label: 'Дерматология' },
              { value: 'stomatology', label: 'Стоматология' },
              { value: 'laboratory', label: 'Лаборатория' },
              { value: 'physiotherapy', label: 'Физиотерапия' }]
              } />
          </div>

          <div>
            <label className="admin-label-14-500-primary-mb-8">
              Категория
            </label>
            <Select
              value={selectedCategory}
              onChange={(value) => setSelectedCategory(value)}
              options={[
              { value: 'all', label: 'Все категории' },
              ...categories.map((category) => ({
                value: category.id,
                label: category.name_ru
              }))]
              } />
          </div>

          <div>
            <label className="admin-label-14-500-primary-mb-8">
              Отделение
            </label>
            <Select
              value={selectedDepartment}
              onChange={(value) => setSelectedDepartment(value)}
              options={[
              { value: 'all', label: 'Все отделения' },
              ...departments.map((dept) => ({
                value: dept.key,
                label: dept.name_ru
              }))]
              } />
          </div>
        </div>
      </MacOSCard>

      {/* Статистика */}
      <div className="admin-grid-auto-200">
        <MacOSCard
          variant="default"
          className="p-6">

          <div className="text-center">
            <div className="admin-stat-num-xl-bold-dynamic-m0" style={{ '--admin-stat-color': 'var(--mac-info)' }}>
              {services.length}
            </div>
            <div className="admin-stat-label-sm-secondary-mt-4">
              Всего услуг
            </div>
          </div>
        </MacOSCard>
        <MacOSCard
          variant="default"
          className="p-6">

          <div className="text-center">
            <div className="admin-stat-num-xl-bold-dynamic-m0" style={{ '--admin-stat-color': 'var(--mac-success)' }}>
              {services.filter((s) => s.active).length}
            </div>
            <div className="admin-stat-label-sm-secondary-mt-4">
              Активных
            </div>
          </div>
        </MacOSCard>
        <MacOSCard
          variant="default"
          className="p-6">

          <div className="text-center">
            <div className="admin-stat-num-xl-bold-dynamic-m0" style={{ '--admin-stat-color': 'var(--mac-warning)' }}>
              {categories.length}
            </div>
            <div className="admin-stat-label-sm-secondary-mt-4">
              Категорий
            </div>
          </div>
        </MacOSCard>
        <MacOSCard
          variant="default"
          className="p-6">

          <div className="text-center">
            <div className="admin-stat-num-xl-bold-dynamic-m0" style={{ '--admin-stat-color': 'var(--mac-accent)' }}>
              {filteredServices.length}
            </div>
            <div className="admin-stat-label-sm-secondary-mt-4">
              Найдено
            </div>
          </div>
        </MacOSCard>
      </div>

      {/* Таблица услуг */}
      <MacOSCard
        variant="default"
        className="admin-card-p-0-overflow-hidden">

        <Table
          columns={[
          {
            key: 'select',
            title: (
              <Checkbox aria-label="Select all filtered services" checked={selectedServiceIds.size === filteredServices.length && filteredServices.length > 0}
                onChange={toggleSelectAll}
                className="admin-checkbox-cursor-pointer"
              />
            ),
            width: '40px'
          },
          { key: 'service', title: 'Услуга', width: '23%' },
          { key: 'category', title: 'Категория', width: '14%' },
          { key: 'price', title: 'Цена', width: '13%' },
          { key: 'duration', title: 'Длительность', width: '10%' },
          { key: 'doctor', title: 'Врач', width: '12%' },
          { key: 'status', title: 'Статус', width: '10%' },
          { key: 'actions', title: 'Действия', width: '12%' }]
          }
          data={filteredServices.map((service) => {
              const specialty = getCategorySpecialty(service.category_id);
              const SpecialtyIcon = getSpecialtyIcon(specialty);
              const doctor = doctors.find((d) => d.id === service.doctor_id);
              const canonicalCode = service.service_code || service.code;
              const hasLegacyCodeMismatch =
                service.code &&
                service.service_code &&
                service.code !== service.service_code;

            return {
              id: service.id,
              select:
              <Checkbox aria-label={`Select service ${service.name || service.id}`} checked={selectedServiceIds.has(service.id)} onChange={() => toggleServiceSelection(service.id)}
                className="admin-checkbox-cursor-pointer"
              />,
              service:
              <div className="flex items-center justify-center">
                  <SpecialtyIcon
                  size={20}
                  className="admin-specialty-icon-20"
                  style={{ '--admin-icon-color': specialtyColors[specialty] || 'var(--mac-text-tertiary)' }} />

                  <div>
                    <div className="admin-service-name">
                      {service.name}
                    </div>
                    {canonicalCode &&
                  <div className="admin-service-code">
                        Код: {canonicalCode}
                      </div>
                    }
                    {hasLegacyCodeMismatch &&
                  <div className="admin-service-legacy-code">
                        Legacy code: {service.code}
                      </div>
                  }
                  </div>
                </div>,

              category:
              <Badge variant="outline">
                  {getCategoryName(service.category_id)}
                </Badge>,

              price:
              <div className="admin-service-price">
                  {service.price ? `${service.price.toLocaleString()} ${service.currency || 'UZS'}` : 'Не указана'}
                </div>,

              duration:
              <div className="admin-service-duration">
                  {service.duration_minutes ? `${service.duration_minutes} мин` : '—'}
                </div>,

              doctor:
              <div className="admin-service-doctor">
                  {doctor ? doctor.user?.full_name || `Врач #${doctor.id}` : '—'}
                </div>,

              status:
              <Badge variant={service.active ? 'success' : 'error'}>
                  {service.active ? 'Активна' : 'Неактивна'}
                </Badge>,

              actions:
              <div className="admin-form-row-gap-8">
                  <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-label={`View change history for ${service.name}`}
                  onClick={() => setShowHistory({ serviceId: service.id, serviceName: service.name })}
                  className="admin-icon-square-btn"
                  title="История изменений">
                    <History aria-hidden="true" size={14} />
                  </Button>
                  <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-label={`Edit service ${service.name}`}
                  onClick={() => setEditingService(service)}
                  className="admin-icon-square-btn"
                  title="Редактировать">
                    <Edit aria-hidden="true" size={14} />
                  </Button>
                  <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-label={`Delete service ${service.name}`}
                  onClick={() => handleDeleteService(service.id)}
                  className="admin-icon-square-btn-error"
                  title="Удалить">
                    <Trash2 aria-hidden="true" size={14} />
                  </Button>
                </div>

            };
          })}
          emptyState={
          <MacOSEmptyState
                icon={Package}
                title="Услуги не найдены"
                description={searchTerm || selectedCategory !== 'all' || selectedSpecialty !== 'all' || selectedDepartment !== 'all' ?
                'Попробуйте изменить критерии поиска' :
                'Добавьте первую услугу в справочник'}
                action={
                <Button onClick={() => setShowAddForm(true)}>
                      <Plus className="w-4 h-4 mr-2" />
                      Добавить услугу
                    </Button>
                } />
          } />

      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {(showAddForm || editingService) &&
      <ServiceForm
        service={editingService}
        categories={categories}
        doctors={doctors}
        departments={departments}
        queueProfiles={queueProfiles}
        setMessage={setMessage}
        onSave={handleSaveService}
        onCancel={() => {
          setShowAddForm(false);
          setEditingService(null);
        }} />

      }

      {/* История изменений */}
      {showHistory && (
        <div className="admin-modal-overlay">
          <div className="admin-modal-body-catalog">
            <Button
              type="button"
              variant="outline"
              title="Close service history"
              aria-label="Close service history"
              onClick={() => setShowHistory(null)}
              className="admin-modal-close-btn-catalog"
            >
              <X aria-hidden="true" size={16} />
            </Button>
            <ServiceAuditHistory
              serviceId={showHistory.serviceId}
              serviceName={showHistory.serviceName}
            />
          </div>
        </div>
      )}

      {/* Batch редактирование */}
      {showBatchEdit && (
        <div className="admin-modal-overlay">
          <div className="admin-modal-body-catalog-700">
            <ServiceBatchEdit
              selectedServices={services.filter(s => selectedServiceIds.has(s.id))}
              categories={categories}
              onComplete={handleBatchEditComplete}
              onCancel={() => setShowBatchEdit(false)}
            />
          </div>
        </div>
      )}
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>);

};

// Компонент формы услуги с вкладками
// ⭐ SSOT: Redesigned with tabs for better UX, removed duplicate fields
const ServiceForm = ({ service, categories, doctors, queueProfiles = [], setMessage, onSave, onCancel }) => {
  const [activeTab, setActiveTab] = useState('basic'); // 'basic', 'queue', 'options'
  const [showPreview, setShowPreview] = useState(false); // ✅ PREVIEW: Show changes preview
  const [formData, setFormData] = useState({
    name: service?.name || '',
    code: service?.code || service?.service_code || '', // Unified: use code as primary
    category_id: service?.category_id || '',
    price: service?.price || '',
    currency: service?.currency || 'UZS',
    duration_minutes: service?.duration_minutes || 30,
    doctor_id: service?.doctor_id || '',
    active: service?.active !== undefined ? service.active : true,
    department_key: service?.department_key || '',
    queue_tag: service?.queue_tag || '',
    requires_doctor: service?.requires_doctor || false,
    is_consultation: service?.is_consultation || false,
    allow_doctor_price_override: service?.allow_doctor_price_override || false
  });

  // State для проверки дубликатов
  const [codeWarning, setCodeWarning] = useState('');
  const [checkingDuplicates, setCheckingDuplicates] = useState(false);

  // Async проверка дубликатов для code
  useEffect(() => {
    if (!formData.code || formData.code.length < 2) {
      setCodeWarning('');
      return;
    }

    const normalizedCode = normalizeServiceCode(formData.code);
    if (!isValidServiceCode(normalizedCode)) {
      setCodeWarning('');
      return;
    }

    const timeoutId = setTimeout(async () => {
      try {
        setCheckingDuplicates(true);
        const response = await api.get('/services');
        const services = response.data;
        const duplicate = services.find(
          (s) => (s.code === normalizedCode || s.service_code === normalizedCode) && s.id !== service?.id
        );
        if (duplicate) {
          setCodeWarning(`⚠️ Код "${normalizedCode}" уже используется: ${duplicate.name}`);
        } else {
          setCodeWarning('');
        }
      } catch (error) {
        logger.error('Ошибка проверки дубликатов:', error);
      } finally {
        setCheckingDuplicates(false);
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [formData.code, service?.id]);

  const selectedFormCategory = categories.find(
    (category) => category.id === parseInt(formData.category_id, 10)
  );
  const selectedServiceGroup = resolveServiceGroup({
    queueTag: formData.queue_tag,
    departmentKey: formData.department_key,
    categorySpecialty: selectedFormCategory?.specialty
  });
  const allowedPrefixes = getAllowedPrefixesForGroup(selectedServiceGroup);
  const normalizedCode = formData.code ? normalizeServiceCode(formData.code) : '';
  const codePrefix = normalizedCode ? normalizedCode.charAt(0).toUpperCase() : '';
  const codePrefixMismatch =
    Boolean(
      normalizedCode &&
      isValidServiceCode(normalizedCode) &&
      allowedPrefixes.length &&
      codePrefix &&
      !allowedPrefixes.includes(codePrefix)
    );
  const expectedPrefixLabel = allowedPrefixes.length ? allowedPrefixes.join(' / ') : '';
  const selectedGroupLabel = selectedServiceGroup
    ? SERVICE_GROUP_LABELS[selectedServiceGroup] || selectedServiceGroup
    : '';

  // Auto-extract category_code from code prefix (guarded by prefix alignment checks)
  const derivedCategoryCode = formData.code ? formData.code.charAt(0).toUpperCase() : '';

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      notify.warning('Введите название услуги');
      return;
    }

    if (codePrefixMismatch) {
      const errorText = selectedGroupLabel
        ? `Код ${normalizedCode} не подходит для группы "${selectedGroupLabel}". Допустимые префиксы: ${expectedPrefixLabel}`
        : `Код ${normalizedCode} не подходит для выбранной категории услуги. Допустимые префиксы: ${expectedPrefixLabel}`;
      logger.warn('[FIX:ADM-06] Blocking mismatched service code before save:', {
        normalizedCode,
        selectedServiceGroup,
        allowedPrefixes,
        category_id: formData.category_id,
        queue_tag: formData.queue_tag,
        department_key: formData.department_key
      });
      setMessage({ type: 'error', text: errorText });
      return;
    }

    // ✅ PREVIEW: Show changes preview for editing (not for new services)
    if (service) {
      setShowPreview(true);
    } else {
      // For new services, save directly
      handleConfirmSave();
    }
  };

  const handleConfirmSave = () => {
    // Подготавливаем данные для API
    const canonicalCode = normalizedCode || null;
    const apiData = {
      ...formData,
      price: formData.price ? parseFloat(formData.price) : null,
      category_id: formData.category_id ? parseInt(formData.category_id) : null,
      doctor_id: formData.doctor_id ? parseInt(formData.doctor_id) : null,
      duration_minutes: parseInt(formData.duration_minutes) || 30,
      code: canonicalCode,
      service_code: canonicalCode, // Sync for backwards compatibility
      category_code: derivedCategoryCode || null // Auto-derived from code
    };

    // Убираем пустые строки
    Object.keys(apiData).forEach((key) => {
      if (apiData[key] === '' || apiData[key] === 'null') {
        apiData[key] = null;
      }
    });

    logger.log('📝 Подготовленные данные для API:', apiData);
    setShowPreview(false);
    onSave(apiData);
  };

  const handleChange = (field, value) => {
    let normalizedValue = value;

    if (field === 'code') {
      normalizedValue = formatServiceCodeInput(value, formData[field]);
    }

    // ⭐ SSOT: Sync queue_tag with department_key
    if (field === 'queue_tag' && normalizedValue) {
      const matchingProfile = queueProfiles.find((p) =>
      (p.queue_tags || []).includes(normalizedValue) || p.key === normalizedValue
      );

      if (matchingProfile) {
        setFormData((prev) => ({ ...prev, [field]: normalizedValue, department_key: matchingProfile.key }));
        return;
      }
    }

    setFormData((prev) => ({ ...prev, [field]: normalizedValue }));
  };

  const tabs = [
  { key: 'basic', label: 'Основное', icon: Package },
  { key: 'queue', label: 'Очередь', icon: Users },
  { key: 'options', label: 'Опции', icon: Filter }];


  return (
    <MacOSCard variant="default" className="p-6">
      <h3 className="admin-h3-18-600-primary-mb-20">
        {service ? 'Редактирование услуги' : 'Добавление услуги'}
      </h3>

      {/* Tab Navigation */}
      <div className="admin-tab-bar-catalog">
        {tabs.map((tab) => {
          const TabIcon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className="admin-tab-btn-catalog"
              style={{
                '--admin-tab-border': isActive ? '2px solid var(--mac-accent)' : '2px solid transparent',
                '--admin-tab-color': isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                '--admin-tab-weight': isActive ? '600' : '500'
              }}>

              <TabIcon size={16} />
              {tab.label}
            </button>);

        })}
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">

        {/* TAB: Основное */}
        {activeTab === 'basic' &&
        <div className="admin-grid-auto-250-12">
            <div>
              <label className="admin-label-14-500-primary-mb-8">
                Название услуги *
              </label>
              <Input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              required />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                Код услуги (K01, D02...)
              </label>
              <Input
              type="text"
              value={formData.code}
              onChange={(e) => handleChange('code', e.target.value)}
              placeholder="K01"
              maxLength={3} />

              {formData.code && !isValidServiceCode(formData.code) &&
            <div className="admin-hint-12-warning-mt-4">
                  Формат: 1 буква + 2 цифры
                </div>
            }
              {codeWarning &&
            <div className="admin-hint-12-error-mt-4-flex">
                  <AlertCircle size={14} />
                  {codeWarning}
                </div>
            }
              {checkingDuplicates && !codeWarning &&
            <div className="admin-hint-12-tertiary-mt-4">
                  Проверка...
                </div>
            }
              {derivedCategoryCode &&
            <div className="admin-hint-12-secondary-mt-4">
                  Префикс кода: {derivedCategoryCode}
                </div>
            }
              {selectedGroupLabel && !codePrefixMismatch &&
            <div className="admin-hint-12-secondary-mt-4">
                  Ожидаемый префикс для {selectedGroupLabel}: {expectedPrefixLabel}
                </div>
            }
              {codePrefixMismatch &&
            <div className="admin-hint-12-warning-mt-4-flex">
                  <AlertCircle size={14} />
                  {selectedGroupLabel
                    ? `Код ${normalizedCode} не подходит для группы "${selectedGroupLabel}".`
                    : `Код ${normalizedCode} не подходит для выбранной группы.`}
                </div>
            }
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                Категория *
              </label>
              <Select
              value={formData.category_id}
              onChange={(value) => handleChange('category_id', value)}
              options={[
              { value: '', label: 'Выберите категорию' },
              ...categories.map((category) => ({
                value: category.id,
                label: `${category.name_ru} (${category.specialty})`
              }))]
              } />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                Цена
              </label>
              <div className="admin-form-row-gap-8">
                <Input
                type="number"
                value={formData.price}
                onChange={(e) => handleChange('price', parseFloat(e.target.value) || '')}
                min="0"
                step="0.01"
                className="admin-input-flex-1" />

                <Select
                value={formData.currency}
                onChange={(value) => handleChange('currency', value)}
                options={[
                { value: 'UZS', label: 'UZS' },
                { value: 'USD', label: 'USD' }]
                }
                className="admin-input-min-w-80" />
              </div>
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                Длительность (мин)
              </label>
              <Input
              type="number"
              value={formData.duration_minutes}
              onChange={(e) => handleChange('duration_minutes', parseInt(e.target.value) || 30)}
              min="5"
              step="5" />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                Врач (опционально)
              </label>
              <Select
              value={formData.doctor_id}
              onChange={(value) => handleChange('doctor_id', value)}
              options={[
              { value: '', label: 'Все врачи' },
              ...doctors.map((doctor) => ({
                value: doctor.id,
                label: `${doctor.user?.full_name || `Врач #${doctor.id}`} (${doctor.specialty})`
              }))]
              } />
            </div>
          </div>
        }

        {/* TAB: Очередь */}
        {activeTab === 'queue' &&
        <div className="flex flex-col gap-4">
            <div className="admin-info-banner-catalog">
              <p className="admin-p-14-secondary-m0">
                Выберите вкладку регистратуры, на которой будет отображаться эта услуга.
                Это определяет, в какую очередь попадёт пациент.
              </p>
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                Вкладка регистратуры
              </label>
              <Select
              value={formData.queue_tag}
              onChange={(value) => handleChange('queue_tag', value)}
              options={[
              { value: '', label: 'Без очереди (услуга не появится в регистратуре)' },
              ...queueProfiles.
              filter((profile) => profile.is_active !== false).
              map((profile) => ({
                value: profile.queue_tags?.[0] || profile.key,
                label: profile.title_ru || profile.title
              }))]
              } />
            </div>

            {formData.queue_tag &&
          <div className="admin-success-banner-catalog">
                <p className="admin-p-14-success-m0">
                  ✓ Услуга будет отображаться на вкладке с тегом: <strong>{formData.queue_tag}</strong>
                </p>
              </div>
          }
          </div>
        }

        {/* TAB: Опции */}
        {activeTab === 'options' &&
        <div className="flex flex-col gap-4">
            <div className="admin-grid-auto-200-12">
              <Checkbox
              id="active"
              checked={formData.active}
              onChange={(checked) => handleChange('active', checked)}
              label="Услуга активна" />

              <Checkbox
              id="requires_doctor"
              checked={formData.requires_doctor}
              onChange={(checked) => handleChange('requires_doctor', checked)}
              label="Требует врача" />

              <Checkbox
              id="is_consultation"
              checked={formData.is_consultation}
              onChange={(checked) => handleChange('is_consultation', checked)}
              label="Это консультация" />

              <Checkbox
              id="allow_doctor_price_override"
              checked={formData.allow_doctor_price_override}
              onChange={(checked) => handleChange('allow_doctor_price_override', checked)}
              label="Врач может изменить цену" />

            </div>

            <div className="admin-bg-secondary-box-catalog">
              <h5 className="admin-h5-14-600-primary-mb-8">
                Подсказки:
              </h5>
              <ul className="admin-ul-13-secondary-pl-20">
                <li><strong>Требует врача</strong> — для ЭхоКГ, сложных процедур</li>
                <li><strong>Консультация</strong> — участвует в расчёте льгот и повторных визитов</li>
                <li><strong>Врач может изменить цену</strong> — для индивидуальных случаев</li>
              </ul>
            </div>
          </div>
        }

        {/* Кнопки */}
        <div className="admin-form-actions-catalog">
          <div className="admin-progress-indicator-catalog">
            {activeTab === 'basic' && '1 / 3'}
            {activeTab === 'queue' && '2 / 3'}
            {activeTab === 'options' && '3 / 3'}
          </div>
          <div className="admin-form-row-gap-12">
            <Button type="button" variant="outline" onClick={onCancel}>
              <X size={16} className="mr-2" />
              Отменить
            </Button>
            <Button type="submit">
              <Save size={16} className="mr-2" />
              Сохранить
            </Button>
          </div>
        </div>
      </form>

      {/* ✅ PREVIEW: Changes preview modal */}
      {showPreview && (
        <div className="admin-modal-overlay">
          <div className="admin-modal-body-catalog-800">
            <ServiceChangesPreview
              oldService={service}
              newService={formData}
              onConfirm={handleConfirmSave}
              onCancel={() => setShowPreview(false)}
            />
          </div>
        </div>
      )}
    </MacOSCard>);

};

ServiceForm.propTypes = {
  service: PropTypes.object,
  categories: PropTypes.array,
  doctors: PropTypes.array,
  queueProfiles: PropTypes.array,
  setMessage: PropTypes.func,
  onSave: PropTypes.func,
  onCancel: PropTypes.func
};

export default ServiceCatalog;
