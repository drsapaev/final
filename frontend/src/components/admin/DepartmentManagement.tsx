import { useTranslation } from '../../i18n/useTranslation';
/**
 * DepartmentManagement Component
 * Управление отделениями, вкладками и интеграциями очередей/услуг
 */

import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
import {
  Plus,

  Save,
  Trash2,
  Search,


  CheckCircle,
  Download,
  Upload,
  Edit2,
  X,
  XCircle } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Textarea,
  Checkbox,
  MacOSPagination,
  Modal,
  Select,
  Switch,
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';
import { getApiOrigin } from '../../api/runtime';
// NOTE: IconSelector.jsx was removed as dead code (Step 1, PR #1827). This file is now live (Step 3 wire-in) as a tab in ClinicManagement. Icon selection uses a plain text input below; a richer icon picker can be re-added later if needed.
// import IconSelector, { iconMap } from './IconSelector';

import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
const API_BASE = getApiOrigin();

const DEFAULT_STATS = {
  appointments_today: 0,
  visits_today: 0,
  queue_entries_today: 0,
  services: 0,
  doctors: 0
};

const DEFAULT_TOTALS = {
  departments: 0,
  active: 0,
  queue_enabled: 0,
  appointments_today: 0,
  visits_today: 0
};

const DEFAULT_FORM = {
  name_ru: '',
  name_uz: '',
  key: '',
  description: '',
  color: 'var(--mac-accent-blue)',
  icon: 'Package', // ✅ ИЗМЕНЕНО: Используем имя иконки из iconMap вместо emoji
  display_order: 999,
  active: true
};

// ✅ НОВОЕ: Форма для настройки маппинга услуг
const DEFAULT_SERVICE_MAPPING = {
  create_service: false,
  service_category_code: '',
  service_code_pattern: '',
  service_name: '',
  service_price: '',
  queue_tag: ''
};

const DEFAULT_INTEGRATION_OPTIONS = {
  queue_prefix: '',
  start_number: '',
  max_daily_queue: '',
  service_name: '',
  service_code: '',
  service_category_code: '',
  service_price: '',
  service_currency: 'UZS'
};

const getCategoryOptions = (t) => [
{ value: '', label: t('admin2.dept_cat_auto') },
{ value: 'K', label: t('admin2.dept_cat_cardio') },
{ value: 'D', label: t('admin2.dept_cat_derm') },
{ value: 'S', label: t('admin2.dept_cat_dental') },
{ value: 'L', label: t('admin2.dept_cat_lab') },
{ value: 'O', label: t('admin2.dept_cat_proc') }];








const getStatusFilterOptions = (t) => [
{ value: 'all', label: t('admin2.dept_filter_all') },
{ value: 'active', label: t('admin2.dept_filter_active') },
{ value: 'inactive', label: t('admin2.dept_filter_inactive') }];

const getSortOptions = (t) => [
{ value: 'name', label: t('admin2.dept_sort_name') },
{ value: 'key', label: t('admin2.dept_sort_key') },
{ value: 'order', label: t('admin2.dept_sort_order') }];

const PAGE_SIZE_OPTIONS = [
{ value: 5, label: '5' },
{ value: 10, label: '10' },
{ value: 20, label: '20' },
{ value: 50, label: '50' }];

const DepartmentManagement = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 2 window.confirm() calls).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;

  // Reactive label option arrays (depend on current language via t).
  const categoryOptions = getCategoryOptions(t);
  const statusFilterOptions = getStatusFilterOptions(t);
  const sortOptions = getSortOptions(t);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [, setError] = useState(null as any);

  const [formData, setFormData] = useState(DEFAULT_FORM);
  const [integrationForm, setIntegrationForm] = useState(DEFAULT_INTEGRATION_OPTIONS);
  const [serviceMapping, setServiceMapping] = useState(DEFAULT_SERVICE_MAPPING);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingDepartment, setEditingDepartment] = useState(null as any);
  const [validationErrors, setValidationErrors] = useState({} as any);

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('display_order');
  const [sortOrder, setSortOrder] = useState('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  const [selectedDepartments, setSelectedDepartments] = useState([]);
  const [selectAll, setSelectAll] = useState(false);
  const [, setTotals] = useState(DEFAULT_TOTALS);

  const broadcastDepartmentsUpdate = useCallback(() => {
    window.dispatchEvent(
      new CustomEvent('departments:updated', { detail: { updatedAt: Date.now() } })
    );
  }, []);

  const sanitizeIntegrationPayload = useCallback((payload) => {
    if (!payload) return undefined;
    const sanitized = {};
    Object.entries(payload).forEach(([key, value]) => {
      if (value === '' || value === null || value === undefined) return;
      if (['start_number', 'max_daily_queue'].includes(key)) {
        const numeric = Number(value);
        if (!Number.isNaN(numeric)) {
          sanitized[key] = numeric;
        }
        return;
      }
      if (key === 'service_price') {
        const price = Number(value);
        if (!Number.isNaN(price)) {
          sanitized[key] = price;
        }
        return;
      }
      sanitized[key] = value;
    });
    return Object.keys(sanitized).length ? sanitized : undefined;
  }, []);

  const loadDepartments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [listResponse, overviewResponse] = await Promise.all([
      api.get('/admin/departments'),
      api.get('/admin/departments/overview')]
      );

      const list = listResponse.data?.data ?? [];
      const overview = overviewResponse.data?.data ?? {};
      const statsMap = {};
      (overview.departments || []).forEach((item) => {
        statsMap[item.key] = item;
      });

      const enriched = list.map((dept) => {
        const stats = statsMap[dept.key] || {};
        return {
          ...dept,
          stats: stats.stats || DEFAULT_STATS,
          integrations: stats.integrations || {}
        };
      });

      setDepartments(enriched);
      setTotals({
        ...DEFAULT_TOTALS,
        ...(overview.totals || {})
      });
    } catch (err) {
      logger.error('Ошибка загрузки отделений:', err);
      setError(t('admin2.dept_load_failed'));
      toast.error(t('admin2.dept_load_failed'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDepartments();
  }, [loadDepartments]);

  useEffect(() => {
    const handleExternalUpdate = () => loadDepartments();
    window.addEventListener('departments:updated', handleExternalUpdate);
    return () => window.removeEventListener('departments:updated', handleExternalUpdate);
  }, [loadDepartments]);

  const validateDepartment = useCallback(
    (data: any, currentId: any = null) => {
      const errors: Record<string, string> = {};
      if (!data.name_ru || data.name_ru.trim().length < 2) {
        errors.name_ru = t('admin2.dept_err_name_required');
      }
      if (!data.key || data.key.trim().length < 2) {
        errors.key = t('admin2.dept_err_key_required');
      } else {
        const duplicate = departments.find((dept) => dept.key === data.key && dept.id !== currentId);
        if (duplicate) {
          errors.key = t('admin2.dept_err_key_duplicate');
        }
      }
      return errors;
    },
    [departments]
  );

  const clearValidationErrors = useCallback(() => {
    setValidationErrors({});
  }, []);

  const handleAddDepartment = async () => {
    const errors = validateDepartment(formData);
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      toast.error(t('admin2.dept_err_fix_form'));
      return;
    }
    setValidationErrors({});

    try {
      const payload = {
        ...formData,
        display_order: Number(formData.display_order) || 999,
        integration: sanitizeIntegrationPayload(integrationForm)
      };
      await api.post('/admin/departments', payload);
      toast.success(t('admin2.dept_created_synced'));
      setShowAddForm(false);
      setFormData(DEFAULT_FORM);
      setIntegrationForm(DEFAULT_INTEGRATION_OPTIONS);
      setServiceMapping(DEFAULT_SERVICE_MAPPING);

      // PR-20: Removed frontend POST /services call — backend's
      // _ensure_department_integrations already creates a default service
      // with name "Консультация {department.name_ru}". The frontend call
      // was causing DOUBLE service creation (one from frontend, one from
      // backend). If admin wants a custom service, they can create it
      // separately in ServiceCatalog after the department is created.

      await loadDepartments();
      broadcastDepartmentsUpdate();
    } catch (err) {
      logger.error('Ошибка создания отделения:', err);
      toast.error(err.response?.data?.detail || t('admin2.dept_create_failed'));
    }
  };


  const openEditModal = (dept) => {
    setEditingDepartment(dept);
    setFormData({
      name_ru: dept.name_ru || '',
      name_uz: dept.name_uz || '',
      key: dept.key || '',
      description: dept.description || '',
      color: dept.color || 'var(--mac-accent-blue)',
      icon: dept.icon || '🏥',
      display_order: dept.display_order || 999,
      active: dept.active ?? true
    });
    setValidationErrors({});
    setShowEditModal(true);
  };

  const handleUpdateDepartment = async () => {
    if (!editingDepartment) return;
    const errors = validateDepartment(formData, editingDepartment.id);
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      toast.error(t('admin2.dept_err_fix_form'));
      return;
    }
    try {
      await api.put(`/admin/departments/${editingDepartment.id}`, formData);
      toast.success(t('admin2.dept_updated'));

      // PR-20: Removed frontend POST /services call (same as create handler).
      // Backend already handles default service via _ensure_department_integrations.

      setShowEditModal(false);
      setEditingDepartment(null);
      setServiceMapping(DEFAULT_SERVICE_MAPPING);
      await loadDepartments();
      broadcastDepartmentsUpdate();
    } catch (err) {
      logger.error('Ошибка обновления отделения:', err);
      toast.error(err.response?.data?.detail || t('admin2.dept_update_failed'));
    }
  };

  // ✅ НОВОЕ: Быстрое переключение статуса отделения
  const handleToggleActive = async (dept, newActive) => {
    try {
      await api.put(`/admin/departments/${dept.id}`, { active: newActive });
      toast.success(newActive ? t('admin2.dept_activated') : t('admin2.dept_deactivated'));
      await loadDepartments();
      broadcastDepartmentsUpdate();
    } catch (err) {
      logger.error('Ошибка обновления статуса:', err);
      toast.error(err.response?.data?.detail || t('admin2.dept_status_update_failed'));
    }
  };

  // ✅ НОВОЕ: Быстрое обновление порядка
  const handleUpdateOrder = async (dept, newOrder) => {
    try {
      await api.put(`/admin/departments/${dept.id}`, { display_order: newOrder });
      await loadDepartments();
      broadcastDepartmentsUpdate();
    } catch (err) {
      logger.error('Ошибка обновления порядка:', err);
      toast.error(err.response?.data?.detail || t('admin2.dept_order_update_failed'));
    }
  };

  const handleDeleteDepartment = async (id) => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.delete_department_title'),
      message: t('admin2.dept_delete_confirm_msg'),
      description: t('admin2.dept_delete_confirm_desc'),
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'danger',
    });
    if (!ok) return;
    try {
      await api.delete(`/admin/departments/${id}`);
      toast.success(t('admin2.dept_deleted'));
      await loadDepartments();
      broadcastDepartmentsUpdate();
    } catch (err) {
      logger.error('Ошибка удаления отделения:', err);
      toast.error(err.response?.data?.detail || t('admin2.dept_delete_failed'));
    }
  };





















  // Фильтрация и сортировка отделений
  // ✅ ИСПРАВЛЕНО: Сортировка по display_order по умолчанию
  const filteredDepartments = departments.
  filter((dept) => {
    const matchesSearch = searchTerm === '' ||
    dept.name_ru?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    dept.name_uz?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    dept.key?.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = statusFilter === 'all' ||
    statusFilter === 'active' && dept.active !== false ||
    statusFilter === 'inactive' && dept.active === false;

    return matchesSearch && matchesStatus;
  }).
  sort((a, b) => {
    let aValue, bValue;

    switch (sortBy) {
      case 'name':
        aValue = a.name_ru || a.name || '';
        bValue = b.name_ru || b.name || '';
        break;
      case 'key':
        aValue = a.key || a.code || '';
        bValue = b.key || b.code || '';
        break;
      case 'order':
      default: // ✅ По умолчанию сортируем по display_order
        aValue = a.display_order || 999;
        bValue = b.display_order || 999;
        break;
    }

    if (sortOrder === 'asc') {
      return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
    } else {
      return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
    }
  });

  // Пагинация
  const totalItems = filteredDepartments.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedDepartments = filteredDepartments.slice(startIndex, endIndex);

  // Сброс на первую страницу при изменении фильтров
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, statusFilter, sortBy, sortOrder]);

  // Функция экспорта отделений в CSV
  const handleExport = () => {
    try {
      const headers = ['name_ru', 'name_uz', 'key', 'description', 'color', 'icon', 'display_order', 'active'];
      const csvContent = [
      headers.join(','),
      ...departments.map((dept) => [
      `"${(dept.name_ru || '').replace(/"/g, '""')}"`,
      `"${(dept.name_uz || '').replace(/"/g, '""')}"`,
      `"${(dept.key || '').replace(/"/g, '""')}"`,
      `"${(dept.description || '').replace(/"/g, '""')}"`,
      `"${(dept.color || 'var(--mac-accent-blue)').replace(/"/g, '""')}"`,
      `"${(dept.icon || '🏥').replace(/"/g, '""')}"`,
      dept.display_order || 999,
      dept.active !== false ? 'true' : 'false'].
      join(','))].
      join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `departments_${new Date().toISOString().split('T')[0]}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast.success(t('admin2.dept_export_success'));
    } catch (error: unknown) {
      logger.error('Ошибка экспорта:', error);
      toast.error(t('admin2.dept_export_failed'));
    }
  };

  // Функция импорта отделений из CSV
  const handleImport = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    try {
      const text = await file.text();
      const lines = text.split('\n').filter((line) => line.trim());

      if (lines.length < 2) {
        toast.error(t('admin2.dept_csv_empty'));
        return;
      }

      const headers = lines[0].split(',').map((h) => h.replace(/"/g, '').trim());
      const requiredHeaders = ['name_ru', 'key'];

      // Проверка обязательных заголовков
      const missingHeaders = requiredHeaders.filter((h) => !headers.includes(h));
      if (missingHeaders.length > 0) {
        toast.error(t('admin2.dept_csv_missing_cols', { cols: missingHeaders.join(', ') }));
        return;
      }

      const importedDepartments = [];
      const errors = [];

      for (let i = 1; i < lines.length; i++) {
        try {
          const values = lines[i].split(',').map((v) => v.replace(/^"|"$/g, '').replace(/""/g, '"'));
          const dept = {};

          headers.forEach((header, index) => {
            const value = values[index];
            switch (header) {
              case 'display_order':
                dept[header] = value ? parseInt(value) : 999;
                break;
              case 'active':
                dept[header] = value !== 'false';
                break;
              default:
                dept[header] = value || '';
            }
          });

          // Валидация импортируемых данных
          const validationErrors = validateDepartment(dept, false);
          if (Object.keys(validationErrors).length > 0) {
            errors.push(t('admin2.dept_csv_row_errors', { row: i + 1, errors: Object.values(validationErrors).join(', ') }));
            continue;
          }

          importedDepartments.push(dept);
        } catch {
          errors.push(t('admin2.dept_csv_row_parse_error', { row: i + 1 }));
        }
      }

      if (errors.length > 0) {
        toast.error(t('admin2.dept_csv_errors_found', { count: errors.length }));
        logger.error('Ошибки импорта:', errors);
        return;
      }

      if (importedDepartments.length === 0) {
        toast.warning(t('admin2.dept_no_import_data'));
        return;
      }

      // Импорт данных
      const token = tokenManager.getAccessToken();
      const response = await fetch('admin/departments/bulk', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ departments: importedDepartments })
      });

      if (response.ok) {
        toast.success(t('admin2.dept_import_success', { count: importedDepartments.length }));
        loadDepartments();
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || t('admin2.dept_import_failed'));
      }

    } catch (error: unknown) {
      logger.error('Ошибка импорта:', error);
      toast.error(t('admin2.dept_read_file_failed'));
    }

    // Очистка input
    event.target.value = '';
  };

  // Функции массовых операций
  const handleSelectAll = (checked) => {
    setSelectAll(checked);
    if (checked) {
      setSelectedDepartments(paginatedDepartments.map((dept) => dept.id));
    } else {
      setSelectedDepartments([]);
    }
  };

  const handleSelectDepartment = (deptId, checked) => {
    if (checked) {
      setSelectedDepartments((prev) => [...prev, deptId]);
    } else {
      setSelectedDepartments((prev) => prev.filter((id) => id !== deptId));
      setSelectAll(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedDepartments.length === 0) {
      toast.warning(t('admin2.dept_select_for_delete'));
      return;
    }

    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const confirmed = await confirm({
      title: t('admin2.bulk_delete_departments_title'),
      message: t('admin2.dept_bulk_delete_msg', { count: selectedDepartments.length }),
      description: t('admin2.dept_bulk_delete_desc'),
      confirmLabel: t('admin2.delete_all_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'destructive',
    });

    if (!confirmed) return;

    try {
      const token = tokenManager.getAccessToken();
      const response = await fetch('admin/departments/bulk-delete', {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ ids: selectedDepartments })
      });

      if (response.ok) {
        toast.success(t('admin2.dept_bulk_deleted', { count: selectedDepartments.length }));
        setSelectedDepartments([]);
        setSelectAll(false);
        loadDepartments();
      } else {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
        toast.error(t('admin2.dept_bulk_delete_error', { error: errorMessage }));
      }
    } catch (error: unknown) {
      logger.error('Ошибка массового удаления:', error);
      toast.error(t('admin2.dept_bulk_delete_failed'));
    }
  };

  const handleBulkActivate = async (activate) => {
    if (selectedDepartments.length === 0) {
      toast.warning(t('admin2.dept_select_departments'));
      return;
    }

    try {
      const token = tokenManager.getAccessToken();
      const response = await fetch('admin/departments/bulk-activate', {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ids: selectedDepartments,
          active: activate
        })
      });

      if (response.ok) {
        toast.success(activate ? t('admin2.dept_bulk_activated', { count: selectedDepartments.length }) : t('admin2.dept_bulk_deactivated', { count: selectedDepartments.length }));
        setSelectedDepartments([]);
        setSelectAll(false);
        loadDepartments();
      } else {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
        toast.error(activate ? t('admin2.dept_bulk_activate_error_on', { error: errorMessage }) : t('admin2.dept_bulk_activate_error_off', { error: errorMessage }));
      }
    } catch (error: unknown) {
      logger.error('Ошибка массовой активации:', error);
      toast.error(activate ? t('admin2.dept_bulk_activate_failed_on') : t('admin2.dept_bulk_activate_failed_off'));
    }
  };

  // Расчет статистики отделений
  const departmentStats = {
    total: departments.length,
    active: departments.filter((dept) => dept.active !== false).length,
    inactive: departments.filter((dept) => dept.active === false).length,
    withDoctors: departments.filter((dept) => (dept.doctor_count || 0) > 0).length,
    withoutDoctors: departments.filter((dept) => (dept.doctor_count || 0) === 0).length
  };

  if (loading) {
    return (
      <MacOSCard>
                <div className="admin-loading-p-40-center">
                    <div className="spinner admin-spinner-mb-16"></div>
                    <p className="text-[var(--mac-text-secondary)]">{t('admin2.dept_loading')}</p>
                </div>
            </MacOSCard>);

  }

  return (
    <div className="admin-flex-col-20">
            {/* Статистика отделений */}
            <div className="admin-grid-auto-200-mb-16">
                <MacOSCard className="p-4">
                    <div className="text-center">
                        <div className="admin-stat-number-mb-4">
                            {departmentStats.total}
                        </div>
                        <div className="admin-stat-label">
                            {t('admin2.dept_stat_total')}
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard className="p-4">
                    <div className="text-center">
                        <div className="admin-stat-number-success-mb-4">
                            {departmentStats.active}
                        </div>
                        <div className="admin-stat-label">
                            {t('admin2.dept_stat_active')}
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard className="p-4">
                    <div className="text-center">
                        <div className="admin-stat-number-warning-mb-4">
                            {departmentStats.inactive}
                        </div>
                        <div className="admin-stat-label">
                            {t('admin2.dept_stat_inactive')}
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard className="p-4">
                    <div className="text-center">
                        <div className="admin-stat-number-info-mb-4">
                            {departmentStats.withDoctors}
                        </div>
                        <div className="admin-stat-label">
                            {t('admin2.dept_stat_with_doctors')}
                        </div>
                    </div>
                </MacOSCard>
            </div>

            <MacOSCard>
                <div className="p-6">
                    <div className="admin-flex-between-mb-24">
                        <h2 className="admin-title-20">
                            {t('admin2.dept_title')}
                        </h2>
                        <div className="admin-flex-gap-8">
                            <Button
                variant="primary"
                size="default"
                onClick={() => setShowAddForm(!showAddForm)}>
                
                                <Plus size={16 as never} className="mr-2" />
                                {t('admin2.dept_add_btn')}
                            </Button>

                            <Button
                variant="secondary"
                size="default"
                onClick={handleExport}
                title={t('admin2.dept_export_title')}>
                
                                <Download size={16 as never} className="mr-2" />
                                {t('admin2.dept_export_btn')}
                            </Button>

                            <label className="admin-position-relative">
                                <Button
                  variant="secondary"
                  size="default"
                  as="span"
                  className="admin-cursor-pointer"
                  title={t('admin2.dept_import_title')}>
                  
                                    <Upload size={16 as never} className="mr-2" />
                                    {t('admin2.dept_import_btn')}
                                </Button>
                                <input
                  type="file"
                  aria-label="Import departments from CSV"
                  accept=".csv"
                  onChange={handleImport}
                  className="admin-file-input-overlay" />
                
                            </label>
                        </div>
                    </div>

                    {/* Панель поиска и фильтров */}
                    <div className="admin-flex-gap-16-wrap-mb-24">
                        <div className="admin-flex-search-row">
                            <Search size={16 as never} className="text-[var(--mac-text-secondary)]" />
                            <Input
                placeholder={t('admin2.dept_search_placeholder')}
                value={searchTerm}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchTerm(e.target.value)}
                className="admin-flex-1" />
                        </div>

                        <Select
              value={statusFilter}
              onChange={(value: unknown) => setStatusFilter(String(value))}
              options={statusFilterOptions}
              className="admin-min-w-120" />

                        <Select
              value={sortBy}
              onChange={(value: unknown) => setSortBy(String(value))}
              options={sortOptions}
              className="admin-min-w-140" />

                        <Button
              variant="secondary"
              size="small"
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              title={sortOrder === 'asc' ? t('admin2.dept_sort_asc') : t('admin2.dept_sort_desc')}>
              
                            {sortOrder === 'asc' ? '↑' : '↓'}
                        </Button>
                    </div>

                    {showAddForm &&
          <div className="admin-form-panel-tertiary-mb-24">
                            <h3 className="admin-title-16-mb-16">
                                {t('admin2.dept_new_title')}
                            </h3>
                            <div className="admin-grid-2col">
                                <div>
                                    <Input
                  placeholder={t('admin2.dept_name_ru_ph')}
                  value={formData.name_ru}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, name_ru: e.target.value })}
                  className={validationErrors.name_ru ? 'admin-input-error' : undefined} />
                
                                    {validationErrors.name_ru &&
                <div className="admin-error-text-mt">
                                            {validationErrors.name_ru}
                                        </div>
                }
                                </div>
                                <div>
                                    <Input
                  placeholder={t('admin2.dept_name_uz_ph')}
                  value={formData.name_uz}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, name_uz: e.target.value })}
                  className={validationErrors.name_uz ? 'admin-input-error' : undefined} />
                
                                    {validationErrors.name_uz &&
                <div className="admin-error-text-mt">
                                            {validationErrors.name_uz}
                                        </div>
                }
                                </div>
                                <div>
                                    <Input
                  placeholder={t('admin2.dept_key_ph')}
                  value={formData.key}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, key: e.target.value })}
                  className={`admin-grid-col-1${validationErrors.key ? ' admin-input-error' : ''}`} />
                
                                    {validationErrors.key &&
                <div className="admin-error-text-mt">
                                            {validationErrors.key}
                                        </div>
                }
                                </div>
                                <div>
                                    <Input
                  type="number"
                  placeholder={t('admin2.dept_order_ph')}
                  value={formData.display_order}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, display_order: parseInt(e.target.value) })}
                  className={`admin-grid-col-2${validationErrors.display_order ? ' admin-input-error' : ''}`} />
                
                                    {validationErrors.display_order &&
                <div className="admin-error-text-mt">
                                            {validationErrors.display_order}
                                        </div>
                }
                                </div>
                                <div className="admin-grid-span-all">
                                    <Input value={formData.icon} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, icon: e.target.value })} placeholder={t('admin2.dept_icon_ph')} />
                
                                    {validationErrors.icon &&
                <div className="admin-error-text-mt">
                                            {validationErrors.icon}
                                        </div>
                }
                                </div>
                                <div>
                                    <Input
                  type="color"
                  value={formData.color}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, color: e.target.value })}
                  className="admin-grid-col-1" />
                
                                    <label className="admin-label-hint">
                                        {t('admin2.dept_tab_color_label')}
                                    </label>
                                </div>
                                <div className="admin-grid-span-all">
                                    <Textarea
                  placeholder={t('admin2.dept_desc_ph')}
                  value={formData.description || ''}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                  className={validationErrors.description ? 'admin-input-error' : undefined} />
                
                                    {validationErrors.description &&
                <div className="admin-error-text-mt">
                                            {validationErrors.description}
                                        </div>
                }
                                </div>
                            </div>

                            {/* ✅ НОВОЕ: Секция настройки маппинга услуг */}
                            <div className="admin-form-panel-secondary">
                                <h4 className="admin-title-16-mb-16">
                                    {t('admin2.dept_service_settings_title')}
                                </h4>

                                <div className="mb-4">
                                    <Checkbox
                  checked={serviceMapping.create_service}
                  onChange={(checked: boolean) => setServiceMapping({ ...serviceMapping, create_service: checked })}
                  label={t('admin2.dept_create_service_label')} />
                
                                </div>

                                {serviceMapping.create_service &&
              <div className="admin-grid-2col">
                                        <div>
                                            <Input
                    placeholder={t('admin2.dept_service_name_ph')}
                    value={serviceMapping.service_name}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setServiceMapping({ ...serviceMapping, service_name: e.target.value })} />
                  
                                        </div>
                                        <div>
                                            <Select
                    value={serviceMapping.service_category_code}
                    onChange={(value: unknown) => setServiceMapping({ ...serviceMapping, service_category_code: String(value) })}
                    options={categoryOptions} />
                                        </div>
                                        <div>
                                            <Input
                    placeholder={t('admin2.dept_service_code_ph')}
                    value={serviceMapping.service_code_pattern}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setServiceMapping({ ...serviceMapping, service_code_pattern: e.target.value.toUpperCase() })} />
                  
                                        </div>
                                        <div>
                                            <Input
                    type="number"
                    placeholder={t('admin2.dept_service_price_ph')}
                    value={serviceMapping.service_price}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setServiceMapping({ ...serviceMapping, service_price: e.target.value })} />
                  
                                        </div>
                                        <div className="admin-grid-span-all">
                                            <Input
                    placeholder={t('admin2.dept_queue_tag_ph')}
                    value={serviceMapping.queue_tag}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setServiceMapping({ ...serviceMapping, queue_tag: e.target.value })} />
                  
                                            <div className="admin-hint-text-12-secondary-mt-4">
                                                {t('admin2.dept_service_mapping_hint', { key: formData.key || '...' })}
                                            </div>
                                        </div>
                                    </div>
              }

                                {!serviceMapping.create_service &&
              <div className="admin-hint-box-tertiary">
                                        {t('admin2.dept_service_mapping_hint_box_prefix')}<code>department_key=&quot;{formData.key || '...'}&quot;</code>{t('admin2.dept_service_mapping_hint_box_middle')}<code>category_code</code>.
                                    </div>
              }
                            </div>

                            <div className="admin-flex-gap-12-mt-16">
                                <Button variant="primary" onClick={handleAddDepartment}>
                                    <Save size={16 as never} className="mr-2" />
                                    {t('admin2.dept_save_btn')}
                                </Button>
                                <Button variant="secondary" onClick={() => {
                setShowAddForm(false);
                setFormData(DEFAULT_FORM);
                setServiceMapping(DEFAULT_SERVICE_MAPPING);
              }}>
                                    <X size={16 as never} className="mr-2" />
                                    {t('admin2.dept_cancel_btn')}
                                </Button>
                            </div>
                        </div>
          }

                    {/* Панель массовых операций */}
                    {selectedDepartments.length > 0 &&
          <div className="admin-bulk-action-bar">
                            <span className="admin-selected-count">
                                {t('admin2.dept_selected_count', { count: selectedDepartments.length })}
                            </span>

                            <Button
              variant="danger"
              size="small"
              onClick={handleBulkDelete}>
              
                                <Trash2 size={14 as never} className="admin-mr-6" />
                                {t('admin2.dept_delete_btn')}
                            </Button>

                            <Button
              variant="success"
              size="small"
              onClick={() => handleBulkActivate(true)}>
              
                                <CheckCircle size={14 as never} className="admin-mr-6" />
                                {t('admin2.dept_activate_btn')}
                            </Button>

                            <Button
              variant="warning"
              size="small"
              onClick={() => handleBulkActivate(false)}>
              
                                <XCircle size={14 as never} className="admin-mr-6" />
                                {t('admin2.dept_deactivate_btn')}
                            </Button>

                            <Button
              variant="secondary"
              size="small"
              onClick={() => {
                setSelectedDepartments([]);
                setSelectAll(false);
              }}>
              
                                <X size={14 as never} className="admin-mr-6" />
                                {t('admin2.dept_clear_btn')}
                            </Button>
                        </div>
          }

                    {/* ✅ ТАБЛИЧНЫЙ ВИД ОТДЕЛЕНИЙ */}
                    <div className="admin-table-container">
                        <div className="admin-table-wrapper">
            <table className="admin-table-full">
                            <thead>
                                <tr className="admin-table-head">
                                    <th className="admin-th-w-40">
                                        <Checkbox
                      checked={selectAll}
                      onChange={(checked: boolean) => handleSelectAll(checked)} />
                    
                                    </th>
                                    <th className="admin-th-w-60">
                                        {t('admin2.dept_col_icon')}
                                    </th>
                                    <th className="admin-th">
                                        {t('admin2.dept_col_name')}
                                    </th>
                                    <th className="admin-th-w-120">
                                        {t('admin2.dept_col_key')}
                                    </th>
                                    <th className="admin-th-w-100">
                                        {t('admin2.dept_col_order')}
                                    </th>
                                    <th className="admin-th-center">
                                        {t('admin2.dept_col_status')}
                                    </th>
                                    <th className="admin-th-right">
                                        {t('admin2.dept_col_actions')}
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {paginatedDepartments.map((dept) => {
                  const IconComponent = null; // IconSelector.jsx removed (Step 1); icon picker is a plain text Input. Icon rendering in table rows disabled until a icon-map helper is re-added.
                  return (
                    <tr
                      key={dept.id}
                      className="admin-tr-hover">
                      
                                            <td className="admin-td-padded">
                                                <Checkbox
                          checked={selectedDepartments.includes(dept.id)}
                          onChange={(checked: boolean) => handleSelectDepartment(dept.id, checked)} />
                        
                                            </td>
                                            <td className="admin-td-padded">
                                                <div className="admin-icon-cell-40" style={{ '--admin-icon-bg': dept.color || 'var(--mac-accent-blue)' } as CSSProperties}>
                                                    {IconComponent ?
                          <IconComponent size={20 as never} /> :

                          <span className="admin-icon-fallback-20">{dept.icon || '🏥'}</span>
                          }
                                                </div>
                                            </td>
                                            <td className="admin-td-padded">
                                                <div>
                                                    <div className="admin-cell-name">
                                                        {dept.name_ru || dept.name}
                                                    </div>
                                                    {dept.description &&
                          <div className="admin-cell-desc-truncate">
                                                            {dept.description}
                                                        </div>
                          }
                                                </div>
                                            </td>
                                            <td className="admin-td-padded">
                                                <Badge variant="secondary">{dept.key || dept.code}</Badge>
                                            </td>
                                            <td className="admin-td-padded">
                                                <Input
                          type="number"
                          value={dept.display_order || 999}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                            const newOrder = parseInt(e.target.value) || 999;
                            handleUpdateOrder(dept, newOrder);
                          }}
                          className="admin-input-mini-80" />
                        
                                            </td>
                                            <td className="admin-td-center">
                                                <Switch
                          checked={dept.active !== false}
                          onChange={(checked) => handleToggleActive(dept, checked)} />
                        
                                            </td>
                                            <td className="admin-td-right">
                                                <div className="admin-flex-end-center-8">
                                                    <Button
                            size="small"
                            variant="secondary"
                            aria-label={`Edit department ${dept.name_ru || dept.name || dept.key}`}
                            onClick={() => openEditModal(dept)}
                            title={t('admin2.dept_edit_title')}>
                            
                                                        <Edit2 size={16 as never} />
                                                    </Button>
                                                    <Button
                            size="small"
                            variant="danger"
                            aria-label={`Delete department ${dept.name_ru || dept.name || dept.key}`}
                            onClick={() => handleDeleteDepartment(dept.id)}
                            title={t('admin2.dept_delete_action_title')}>
                            
                                                        <Trash2 size={16 as never} />
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>);

                })}
                            </tbody>
                        </table>
          </div>
                    </div>

                    {departments.length === 0 &&
          <div className="admin-empty-p-40-center-secondary">
                            <p>{t('admin2.dept_empty')}</p>
                        </div>
          }

                    {departments.length > 0 && filteredDepartments.length === 0 &&
          <div className="admin-empty-p-40-center-secondary">
                            <p>{t('admin2.dept_no_results')}</p>
                        </div>
          }

                    {/* Пагинация */}
                    {totalPages > 1 &&
          <div className="admin-pagination-bar">
                            <MacOSPagination
              className=""
              style={{} as CSSProperties}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage} />
            
                            <div className="flex items-center justify-center gap-2">
                                <span className="admin-text-14-secondary">
                                    {t('admin2.dept_showing')}
                                </span>
                                <Select
                value={itemsPerPage}
                onChange={(value) => {
                  setItemsPerPage(Number(value));
                  setCurrentPage(1);
                }}
                options={PAGE_SIZE_OPTIONS}
                className="admin-w-70" />
                                <span className="admin-text-14-secondary">
                                    {t('admin2.dept_of_total', { total: totalItems })}
                                </span>
                            </div>
                        </div>
          }
                </div>
            </MacOSCard>

            {/* Модальное окно редактирования отделения */}
            <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingDepartment(null);
          setFormData(DEFAULT_FORM);
          setServiceMapping(DEFAULT_SERVICE_MAPPING);
          clearValidationErrors();
        }}
        title={t('admin2.dept_edit_modal_title')}
        size="large">
        
                <div className="admin-grid-2col">
                    <div>
                        <Input
              label={t('admin2.dept_name_ru_ph')}
              placeholder={t('admin2.dept_name_ru_ph')}
              value={formData.name_ru}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, name_ru: e.target.value })}
              className={validationErrors.name_ru ? 'admin-input-error' : undefined} />
            
                        {validationErrors.name_ru &&
            <div className="admin-error-text-mt">
                                {validationErrors.name_ru}
                            </div>
            }
                    </div>
                    <div>
                        <Input
              label={t('admin2.dept_name_uz_ph')}
              placeholder={t('admin2.dept_name_uz_ph')}
              value={formData.name_uz}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, name_uz: e.target.value })}
              className={validationErrors.name_uz ? 'admin-input-error' : undefined} />
            
                        {validationErrors.name_uz &&
            <div className="admin-error-text-mt">
                                {validationErrors.name_uz}
                            </div>
            }
                    </div>
                    <div>
                        <Input
              label={t('admin2.dept_key_label')}
              placeholder={t('admin2.dept_key_ph')}
              value={formData.key}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, key: e.target.value })}
              className={`admin-grid-col-1${validationErrors.key ? ' admin-input-error' : ''}`} />
            
                        {validationErrors.key &&
            <div className="admin-error-text-mt">
                                {validationErrors.key}
                            </div>
            }
                    </div>
                    <div>
                        <Input
              label={t('admin2.dept_order_ph')}
              type="number"
              placeholder={t('admin2.dept_order_ph')}
              value={formData.display_order}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, display_order: parseInt(e.target.value) })}
              className={`admin-grid-col-2${validationErrors.display_order ? ' admin-input-error' : ''}`} />
            
                        {validationErrors.display_order &&
            <div className="admin-error-text-mt">
                                {validationErrors.display_order}
                            </div>
            }
                    </div>
                    <div className="admin-grid-span-all">
                        <Input value={formData.icon} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, icon: e.target.value })} placeholder={t('admin2.dept_icon_ph')} />
            
                        {validationErrors.icon &&
            <div className="admin-error-text-mt">
                                {validationErrors.icon}
                            </div>
            }
                    </div>
                    <div>
                        <Input
              label={t('admin2.dept_color_label')}
              type="color"
              value={formData.color}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, color: e.target.value })}
              className="admin-grid-col-2" />
            
                    </div>
                    <div className="admin-grid-span-all">
                        <Textarea
              label={t('admin2.dept_desc_label')}
              placeholder={t('admin2.dept_desc_ph')}
              value={formData.description || ''}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setFormData({ ...formData, description: e.target.value })}
              rows={4}
              className={validationErrors.description ? 'admin-input-error' : undefined} />
            
                        {validationErrors.description &&
            <div className="admin-error-text-mt">
                                {validationErrors.description}
                            </div>
            }
                    </div>
                </div>

                {/* ✅ НОВОЕ: Секция настройки маппинга услуг в модальном окне */}
                <div className="admin-form-panel-secondary">
                    <h4 className="admin-title-16-mb-16">
                        {t('admin2.dept_service_settings_title')}
                    </h4>

                    <div className="mb-4">
                        <Checkbox
              checked={serviceMapping.create_service}
              onChange={(checked: boolean) => setServiceMapping({ ...serviceMapping, create_service: checked })}
              label={t('admin2.dept_create_service_short')} />
            
                    </div>

                    {serviceMapping.create_service &&
          <div className="admin-grid-2col">
                            <div>
                                <Input
                label={t('admin2.dept_service_name_label')}
                placeholder={t('admin2.dept_service_name_label')}
                value={serviceMapping.service_name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setServiceMapping({ ...serviceMapping, service_name: e.target.value })} />
              
                            </div>
                            <div>
                                <label className="admin-label-block-md">
                                    {t('admin2.dept_service_cat_label')}
                                </label>
                                <Select
                value={serviceMapping.service_category_code}
                onChange={(value: unknown) => setServiceMapping({ ...serviceMapping, service_category_code: String(value) })}
                options={categoryOptions} />
                            </div>
                            <div>
                                <Input
                label={t('admin2.dept_service_code_label')}
                placeholder={t('admin2.dept_service_code_ph')}
                value={serviceMapping.service_code_pattern}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setServiceMapping({ ...serviceMapping, service_code_pattern: e.target.value.toUpperCase() })} />
              
                            </div>
                            <div>
                                <Input
                label={t('admin2.dept_service_price_label')}
                type="number"
                placeholder={t('admin2.dept_service_price_label')}
                value={serviceMapping.service_price}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setServiceMapping({ ...serviceMapping, service_price: e.target.value })} />
              
                            </div>
                            <div className="admin-grid-span-all">
                                <Input
                label={t('admin2.dept_queue_tag_label')}
                placeholder={t('admin2.dept_queue_tag_ph_modal')}
                value={serviceMapping.queue_tag}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setServiceMapping({ ...serviceMapping, queue_tag: e.target.value })} />
              
                                <div className="admin-hint-text-12-secondary-mt-4">
                                    {t('admin2.dept_service_mapping_hint', { key: formData.key || '...' })}
                                </div>
                            </div>
                        </div>
          }

                    {!serviceMapping.create_service &&
          <div className="admin-hint-box-tertiary">
                            {t('admin2.dept_service_mapping_hint_box_prefix')}<code>department_key=&quot;{formData.key || '...'}&quot;</code>{t('admin2.dept_service_mapping_hint_box_middle')}<code>category_code</code>.
                        </div>
          }
                </div>

                <div className="admin-modal-footer">
                    <Button
            variant="secondary"
            onClick={() => {
              setShowEditModal(false);
              setEditingDepartment(null);
              setFormData(DEFAULT_FORM);
              setServiceMapping(DEFAULT_SERVICE_MAPPING);
              clearValidationErrors();
            }}>
            
                        {t('admin2.dept_cancel_btn')}
                    </Button>
                    <Button
            variant="primary"
            onClick={handleUpdateDepartment}>
            
                        <Save size={16 as never} className="mr-2" />
                        {t('admin2.dept_save_changes_btn')}
                    </Button>
                </div>
            </Modal>
            {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
            {confirmDialog as unknown as React.ReactNode}
        </div>
      );

};

export default DepartmentManagement;
