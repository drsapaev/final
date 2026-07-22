import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import type { CSSProperties } from "react";
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
  Activity,
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
import { notify } from '../../services/notify';

const SERVICE_GROUP_PREFIXES = {
  cardiology: ['K'],
  ecg: ['K'],
  dermatology: ['D'],
  dental: ['S'],
  laboratory: ['L'],
  procedures: ['C', 'P', 'O']
};

const SERVICE_GROUP_LABELS = {
  cardiology: 'sc_group_cardiology',
  ecg: 'sc_group_ecg',
  dermatology: 'sc_group_dermatology',
  dental: 'sc_group_dental',
  laboratory: 'sc_group_laboratory',
  procedures: 'sc_group_procedures'
};

const getServiceGroupLabel = (groupKey, t) => {
  if (!groupKey) return '';
  const labelKey = SERVICE_GROUP_LABELS[groupKey];
  return labelKey ? t(`admin2.${labelKey}`) : groupKey;
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
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
  // UX Audit Admin #3.9: унифицированы ключи с SERVICE_GROUP_LABELS.
  const specialtyIcons = {
    cardiology: Heart,
    ecg: Activity,
    dermatology: Stethoscope,
    dental: Scissors,
    stomatology: Scissors, // alias для обратной совместимости
    laboratory: TestTube,
    procedures: Package,
    physiotherapy: Package, // alias для обратной совместимости
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
      api.get('/admin/departments'),
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
      setMessage({ type: 'error', text: t('admin2.sc_load_error') });
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
          const response = (await api.put(`/services/${editingService.id}`, serviceData)) as import('axios').AxiosResponse<Record<string, unknown>>;
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
        const response = (await api.post('/services', serviceData)) as import('axios').AxiosResponse<Record<string, unknown>>;
        savedService = response.data;

        // ✅ ОПТИМИСТИЧНОЕ ДОБАВЛЕНИЕ: Добавляем в список сразу
        setServices(prevServices => [savedService, ...prevServices]);
      }

      setMessage({
        type: 'success',
        text: editingService ? t('admin2.sc_service_updated') : t('admin2.sc_service_created')
      });
      setEditingService(null);
      setShowAddForm(false);
    } catch (error) {
      logger.error('Ошибка сохранения:', error);

      // ✅ ПАРСИНГ ДЕТАЛЬНЫХ ОШИБОК ОТ BACKEND
      let errorMessage = t('admin2.sc_save_error_default');
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
          errorMessage = t('admin2.sc_validation_error', { errors });
        } else if (errorData.detail.message) {
          errorMessage = errorData.detail.message;
        }
      } else if (error.response?.status === 409) {
        errorMessage = t('admin2.sc_code_conflict');
      } else if (error.response?.status === 422) {
        errorMessage = t('admin2.sc_invalid_format');
      } else if (error.message) {
        errorMessage = error.message;
      }

      setMessage({ type: 'error', text: errorMessage });
    }
  };

  const handleDeleteService = async (serviceId) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.delete_service_title'),
      message: t('admin2.sc_delete_message'),
      description: t('admin2.sc_delete_description'),
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
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

      const response = (await api.delete(`/services/${serviceId}`)) as import('axios').AxiosResponse<Record<string, unknown>>;

      // Обновляем с реальными данными от сервера
      if (response.data.active === false) {
        setServices(prevServices =>
          prevServices.map(s => s.id === serviceId ? { ...s, active: false } : s)
        );
      }

      setMessage({ type: 'success', text: String(response.data.message || t('admin2.sc_service_deleted')) });
    } catch (error) {
      // ❌ ОТКАТ: Возвращаем старое состояние при ошибке
      setServices(oldServices);

      logger.error('Ошибка удаления:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || t('admin2.sc_delete_error_default') });
    }
  };

  const getCategoryName = (categoryId) => {
    const category = categories.find((cat) => cat.id === categoryId);
    return category?.name_ru || t('admin2.sc_no_category');
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
          <span className="admin-load-text-primary">{t('admin2.sc_loading_catalog')}</span>
        </div>
      </MacOSCard>);

  }

  return (
    <div className="flex flex-col gap-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="admin-page-h2-xl-semi-primary-m0">
            {t('admin2.sc_page_title')}
          </h2>
          <p className="admin-header-p-mt-4-sm-secondary">
            {t('admin2.sc_page_subtitle')}
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
              {t('admin2.sc_edit_count_btn', { count: selectedServiceIds.size })}
            </Button>
          )}
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className="mr-2" />
            {t('admin2.sc_refresh_btn')}
          </Button>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus size={16} className="mr-2" />
            {t('admin2.sc_add_btn')}
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
              {t('admin2.sc_filter_search_label')}
            </label>
            <Input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={t('admin2.sc_filter_search_ph')}
              icon={Search}
              iconPosition="left" />
          </div>

          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              {t('admin2.sc_filter_specialty_label')}
            </label>
            <Select
              value={selectedSpecialty}
              onChange={(value: unknown) => setSelectedSpecialty(String(value))}
              options={[
              { value: 'all', label: t('admin2.sc_filter_specialty_all') },
              { value: 'cardiology', label: t('admin2.sc_filter_specialty_cardiology') },
              { value: 'dermatology', label: t('admin2.sc_filter_specialty_dermatology') },
              { value: 'stomatology', label: t('admin2.sc_filter_specialty_stomatology') },
              { value: 'laboratory', label: t('admin2.sc_filter_specialty_laboratory') },
              { value: 'physiotherapy', label: t('admin2.sc_filter_specialty_physiotherapy') }]
              } />
          </div>

          <div>
            <label className="admin-label-14-500-primary-mb-8">
              {t('admin2.sc_filter_category_label')}
            </label>
            <Select
              value={selectedCategory}
              onChange={(value: unknown) => setSelectedCategory(String(value))}
              options={[
              { value: 'all', label: t('admin2.sc_filter_category_all') },
              ...categories.map((category: { id?: string | number; name_ru?: string; specialty?: string }) => ({
                value: category.id,
                label: category.name_ru
              }))]
              } />
          </div>

          <div>
            <label className="admin-label-14-500-primary-mb-8">
              {t('admin2.sc_filter_department_label')}
            </label>
            <Select
              value={selectedDepartment}
              onChange={(value: unknown) => setSelectedDepartment(String(value))}
              options={[
              { value: 'all', label: t('admin2.sc_filter_department_all') },
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
            <div className="admin-stat-num-xl-bold-dynamic-m0 admin-stat-info">
              {services.length}
            </div>
            <div className="admin-stat-label-sm-secondary-mt-4">
              {t('admin2.sc_stat_total')}
            </div>
          </div>
        </MacOSCard>
        <MacOSCard
          variant="default"
          className="p-6">

          <div className="text-center">
            <div className="admin-stat-num-xl-bold-dynamic-m0 admin-stat-success">
              {services.filter((s) => s.active).length}
            </div>
            <div className="admin-stat-label-sm-secondary-mt-4">
              {t('admin2.sc_stat_active')}
            </div>
          </div>
        </MacOSCard>
        <MacOSCard
          variant="default"
          className="p-6">

          <div className="text-center">
            <div className="admin-stat-num-xl-bold-dynamic-m0 admin-stat-warning">
              {categories.length}
            </div>
            <div className="admin-stat-label-sm-secondary-mt-4">
              {t('admin2.sc_stat_categories')}
            </div>
          </div>
        </MacOSCard>
        <MacOSCard
          variant="default"
          className="p-6">

          <div className="text-center">
            <div className="admin-stat-num-xl-bold-dynamic-m0 admin-stat-accent">
              {filteredServices.length}
            </div>
            <div className="admin-stat-label-sm-secondary-mt-4">
              {t('admin2.sc_stat_filtered')}
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
          { key: 'service', title: t('admin2.col_service'), width: '23%' },
          { key: 'category', title: t('admin2.col_category'), width: '14%' },
          { key: 'price', title: t('admin2.col_price'), width: '13%' },
          { key: 'duration', title: t('admin2.col_duration'), width: '10%' },
          { key: 'doctor', title: t('admin2.col_doctor'), width: '12%' },
          { key: 'status', title: t('admin2.col_active'), width: '10%' },
          { key: 'actions', title: t('admin2.col_actions'), width: '12%' }]
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
                  style={{ '--admin-icon-color': specialtyColors[specialty] || 'var(--mac-text-tertiary)' } as CSSProperties} />

                  <div>
                    <div className="admin-service-name">
                      {service.name}
                    </div>
                    {canonicalCode &&
                  <div className="admin-service-code">
                        {t('admin2.sc_cell_code', { code: canonicalCode })}
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
                  {service.price ? `${service.price.toLocaleString()} ${service.currency || 'UZS'}` : t('admin2.sc_cell_price_not_set')}
                </div>,

              duration:
              <div className="admin-service-duration">
                  {service.duration_minutes ? t('admin2.sc_cell_duration', { minutes: service.duration_minutes }) : '—'}
                </div>,

              doctor:
              <div className="admin-service-doctor">
                  {doctor ? doctor.user?.full_name || t('admin2.sc_cell_doctor_default', { id: doctor.id }) : '—'}
                </div>,

              status:
              <Badge variant={service.active ? 'success' : 'error'}>
                  {service.active ? t('admin2.sc_status_active') : t('admin2.sc_status_inactive')}
                </Badge>,

              actions:
              <div className="admin-form-row-gap-8">
                  <Button
                  type="button"
                  size="small"
                  variant="outline"
                  aria-label={`View change history for ${service.name}`}
                  onClick={() => setShowHistory({ serviceId: service.id, serviceName: service.name })}
                  className="admin-icon-square-btn"
                  title={t('admin2.sc_action_history_title')}>
                    <History aria-hidden="true" size={14} />
                  </Button>
                  <Button
                  type="button"
                  size="small"
                  variant="outline"
                  aria-label={`Edit service ${service.name}`}
                  onClick={() => setEditingService(service)}
                  className="admin-icon-square-btn"
                  title={t('admin2.sc_action_edit_title')}>
                    <Edit aria-hidden="true" size={14} />
                  </Button>
                  <Button
                  type="button"
                  size="small"
                  variant="outline"
                  aria-label={`Delete service ${service.name}`}
                  onClick={() => handleDeleteService(service.id)}
                  className="admin-icon-square-btn-error"
                  title={t('admin2.sc_action_delete_title')}>
                    <Trash2 aria-hidden="true" size={14} />
                  </Button>
                </div>

            };
          })}
          emptyState={
          <MacOSEmptyState
                icon={Package}
                title={t('admin2.sc_empty_title')}
                description={searchTerm || selectedCategory !== 'all' || selectedSpecialty !== 'all' || selectedDepartment !== 'all' ?
                t('admin2.sc_empty_desc_filtered') :
                t('admin2.sc_empty_desc_initial')}
                action={
                <Button onClick={() => setShowAddForm(true)}>
                      <Plus className="w-4 h-4 mr-2" />
                      {t('admin2.sc_add_btn')}
                    </Button>
                } />
          } />

      </MacOSCard>

      {/* UX Audit Admin #1.4: форма в modal overlay вместо inline внизу страницы. */}
      {(showAddForm || editingService) &&
      <div className="admin-modal-overlay">
        <div className="admin-modal-body-catalog-700">
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
        </div>
      </div>

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
      {confirmDialog as unknown as React.ReactNode}
    </div>);

};

// Компонент формы услуги с вкладками
// ⭐ SSOT: Redesigned with tabs for better UX, removed duplicate fields
const ServiceForm = ({ service, categories, doctors, queueProfiles = [], setMessage, onSave, onCancel, departments }: { service?: Record<string, unknown>; categories?: unknown[]; doctors?: unknown[]; queueProfiles?: unknown[]; setMessage?: (msg: { type: string; text: string }) => void; onSave?: (serviceData: Record<string, unknown>) => Promise<void>; onCancel?: () => void; departments?: unknown[] }) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [activeTab, setActiveTab] = useState('basic'); // 'basic', 'queue', 'options'
  const [showPreview, setShowPreview] = useState(false); // ✅ PREVIEW: Show changes preview
  const [formData, setFormData] = useState<Record<string, unknown>>({
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
    if (!formData.code || String(formData.code ?? '').length < 2) {
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
        const response = (await api.get('/services')) as import('axios').AxiosResponse<Record<string, unknown>>;
        const services = (response.data as unknown as Array<{ code?: string; service_code?: string; id?: string | number; name?: string }>) || [];
        const duplicate = services.find(
          (s) => (s.code === normalizedCode || s.service_code === normalizedCode) && s.id !== service?.id
        );
        if (duplicate) {
          setCodeWarning(t('admin2.sc_code_duplicate_warning', { code: normalizedCode, name: duplicate.name }));
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
  }, [formData.code, service?.id, t]);

  const selectedFormCategory = categories.find(
    (category: unknown) => (category as { id?: number })?.id === parseInt(String(formData.category_id), 10)
  ) as { specialty?: string } | undefined;
  const selectedServiceGroup = resolveServiceGroup({
    queueTag: formData.queue_tag,
    departmentKey: formData.department_key,
    categorySpecialty: selectedFormCategory?.specialty
  });
  const allowedPrefixes = getAllowedPrefixesForGroup(selectedServiceGroup);
  const normalizedCode = formData.code ? normalizeServiceCode(String(formData.code)) : '';
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
    ? getServiceGroupLabel(selectedServiceGroup, t)
    : '';

  // Auto-extract category_code from code prefix (guarded by prefix alignment checks)
  const derivedCategoryCode = formData.code ? String(formData.code).charAt(0).toUpperCase() : '';

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!String(formData.name ?? '').trim()) {
      notify.warning(t('admin2.service_name_required'));
      return;
    }

    if (codePrefixMismatch) {
      const errorText = selectedGroupLabel
        ? t('admin2.sc_code_mismatch_error_with_group', { code: normalizedCode, group: selectedGroupLabel, prefixes: expectedPrefixLabel })
        : t('admin2.sc_code_mismatch_error_no_group', { code: normalizedCode, prefixes: expectedPrefixLabel });
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
      price: formData.price ? parseFloat(String(formData.code ?? '')) : null,
      category_id: formData.category_id ? parseInt(String(formData.code ?? '')) : null,
      doctor_id: formData.doctor_id ? parseInt(String(formData.code ?? '')) : null,
      duration_minutes: parseInt(String(formData.code ?? '')) || 30,
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
      normalizedValue = formatServiceCodeInput(value);
    }

    // ⭐ SSOT: Sync queue_tag with department_key
    if (field === 'queue_tag' && normalizedValue) {
      const matchingProfile = queueProfiles.find((p: unknown) => {
        const profile = p as { queue_tags?: string[]; key?: string };
        return (profile.queue_tags || []).includes(normalizedValue) || profile.key === normalizedValue;
      });

      if (matchingProfile) {
        setFormData((prev) => ({ ...prev, [field]: normalizedValue, department_key: (matchingProfile as { key?: string })?.key }));
        return;
      }
    }

    setFormData((prev) => ({ ...prev, [field]: normalizedValue }));
  };

  const tabs = [
  { key: 'basic', label: t('admin2.sc_tab_basic'), icon: Package },
  { key: 'queue', label: t('admin2.sc_tab_queue'), icon: Users },
  { key: 'options', label: t('admin2.sc_tab_options'), icon: Filter }];


  return (
    <MacOSCard variant="default" className="p-6">
      <h3 className="admin-h3-18-600-primary-mb-20">
        {service ? t('admin2.sc_form_title_edit') : t('admin2.sc_form_title_add')}
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
              } as CSSProperties}>

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
                {t('admin2.sc_form_name_label')}
              </label>
              <Input
              type="text"
              value={formData.name as string}
              onChange={(e) => handleChange('name', e.target.value)}
              required />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t('admin2.sc_form_code_label')}
              </label>
              <Input
              type="text"
              value={formData.code as string}
              onChange={(e) => handleChange('code', e.target.value)}
              placeholder="K01"
              maxLength={3} />

              {/* UX Audit Admin #2.3: unified status block — 6 подсказок → 1 с приоритетом. */}
              {(() => {
                const codeHint = codePrefixMismatch
                  ? { type: 'error', text: selectedGroupLabel
                      ? t('admin2.sc_code_mismatch_inline_with_group', { code: normalizedCode, group: selectedGroupLabel, prefixes: expectedPrefixLabel })
                      : t('admin2.sc_code_mismatch_inline_no_group', { code: normalizedCode }) }
                  : codeWarning
                  ? { type: 'error', text: codeWarning }
                  : checkingDuplicates
                  ? { type: 'info', text: t('admin2.sc_code_checking') }
                  : (formData.code && !isValidServiceCode(formData.code))
                  ? { type: 'warning', text: t('admin2.sc_code_format_hint') }
                  : (derivedCategoryCode && selectedGroupLabel)
                  ? { type: 'info', text: t('admin2.sc_code_prefix_hint_with_group', { prefix: derivedCategoryCode, expected: expectedPrefixLabel, group: selectedGroupLabel }) }
                  : derivedCategoryCode
                  ? { type: 'info', text: t('admin2.sc_code_prefix_hint_no_group', { prefix: derivedCategoryCode }) }
                  : null;

                if (!codeHint) return null;

                const hintClass = codeHint.type === 'error'
                  ? 'admin-hint-12-error-mt-4-flex'
                  : codeHint.type === 'warning'
                  ? 'admin-hint-12-warning-mt-4'
                  : 'admin-hint-12-tertiary-mt-4';

                return (
                  <div className={hintClass}>
                    {codeHint.type === 'error' && <AlertCircle size={14} />}
                    {codeHint.text}
                  </div>
                );
              })()}
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t('admin2.sc_form_category_label')}
              </label>
              <Select
              value={formData.category_id as string}
              onChange={(value: unknown) => handleChange('category_id', String(value))}
              options={[
              { value: '', label: t('admin2.sc_form_category_ph') },
              ...categories.map((category: { id?: string | number; name_ru?: string; specialty?: string }) => ({
                value: category.id,
                label: `${category.name_ru} (${category.specialty})`
              }))]
              } />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t('admin2.sc_form_price_label')}
              </label>
              <div className="admin-form-row-gap-8">
                <Input
                type="number"
                value={formData.price as string}
                onChange={(e) => handleChange('price', parseFloat(e.target.value) || '')}
                min="0"
                step="0.01"
                className="admin-input-flex-1" />

                <Select
                value={formData.currency as string}
                onChange={(value: unknown) => handleChange('currency', String(value))}
                options={[
                { value: 'UZS', label: 'UZS' },
                { value: 'USD', label: 'USD' }]
                }
                className="admin-input-min-w-80" />
              </div>
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t('admin2.sc_form_duration_label')}
              </label>
              <Input
              type="number"
              value={formData.duration_minutes as string}
              onChange={(e) => handleChange('duration_minutes', parseInt(e.target.value) || 30)}
              min="5"
              step="5" />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t('admin2.sc_form_doctor_label')}
              </label>
              <Select
              value={formData.doctor_id as string}
              onChange={(value: unknown) => handleChange('doctor_id', String(value))}
              options={[
              { value: '', label: t('admin2.sc_form_doctor_all') },
              ...doctors.map((doctor: { id?: string | number; user?: { id?: string | number; full_name?: string }; specialty?: string; full_name?: string }) => ({
                value: doctor.id,
                label: `${doctor.user?.full_name || t('admin2.sc_cell_doctor_default', { id: doctor.id })} (${doctor.specialty})`
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
                {t('admin2.sc_form_queue_banner_desc')}
              </p>
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t('admin2.sc_form_queue_tag_label')}
              </label>
              <Select
              value={formData.queue_tag as string}
              onChange={(value: unknown) => handleChange('queue_tag', String(value))}
              options={[
              { value: '', label: t('admin2.sc_form_queue_no_queue') },
              ...queueProfiles.
              filter((profile: { is_active?: boolean; queue_tags?: string[]; key?: string; title_ru?: string; title?: string }) => profile.is_active !== false).
              map((profile: { is_active?: boolean; queue_tags?: string[]; key?: string; title_ru?: string; title?: string }) => ({
                value: profile.queue_tags?.[0] || profile.key,
                label: profile.title_ru || profile.title
              }))]
              } />
            </div>

            {formData.queue_tag &&
          <div className="admin-success-banner-catalog">
                <p className="admin-p-14-success-m0">
                  {t('admin2.sc_form_queue_active_hint_prefix')} <strong>{String(formData.queue_tag ?? '')}</strong>
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
              checked={Boolean(formData.active as boolean)}
              onChange={(checked) => handleChange('active', checked)}
              label={t('admin2.sc_form_active_label')} />

              <Checkbox
              id="requires_doctor"
              checked={Boolean(formData.requires_doctor as boolean)}
              onChange={(checked) => handleChange('requires_doctor', checked)}
              label={t('admin2.sc_form_requires_doctor_label')} />

              <Checkbox
              id="is_consultation"
              checked={Boolean(formData.is_consultation as boolean)}
              onChange={(checked) => handleChange('is_consultation', checked)}
              label={t('admin2.sc_form_is_consultation_label')} />

              <Checkbox
              id="allow_doctor_price_override"
              checked={Boolean(formData.allow_doctor_price_override as boolean)}
              onChange={(checked) => handleChange('allow_doctor_price_override', checked)}
              label={t('admin2.sc_form_allow_override_label')} />

            </div>

            <div className="admin-bg-secondary-box-catalog">
              <h5 className="admin-h5-14-600-primary-mb-8">
                {t('admin2.sc_form_hints_heading')}
              </h5>
              <ul className="admin-ul-13-secondary-pl-20">
                <li><strong>{t('admin2.sc_form_requires_doctor_label')}</strong>{t('admin2.sc_form_hint_requires_doctor')}</li>
                <li><strong>{t('admin2.sc_form_hint_consultation_term')}</strong>{t('admin2.sc_form_hint_consultation')}</li>
                <li><strong>{t('admin2.sc_form_allow_override_label')}</strong>{t('admin2.sc_form_hint_allow_override')}</li>
              </ul>
            </div>
          </div>
        }

        {/* Кнопки */}
        <div className="admin-form-actions-catalog">
          {/* UX Audit Admin #2.2: fake progress indicator «1/3, 2/3, 3/3» удалён.
              Табы свободные (можно кликнуть любую), индикатор вводил в заблуждение,
              имитируя wizard с последовательным продвижением. */}
          <div className="admin-form-row-gap-12">
            <Button type="button" variant="outline" onClick={onCancel}>
              <X size={16} className="mr-2" />
              {t('admin2.sc_form_cancel_btn')}
            </Button>
            <Button type="submit">
              <Save size={16} className="mr-2" />
              {t('admin2.sc_form_save_btn')}
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
