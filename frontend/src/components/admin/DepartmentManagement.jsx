/**
 * DepartmentManagement Component
 * Управление отделениями, вкладками и интеграциями очередей/услуг
 */

import { useState, useEffect, useCallback } from 'react';
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

const CATEGORY_OPTIONS = [
{ value: '', label: 'Категория (авто)' },
{ value: 'K', label: 'Кардиология (K)' },
{ value: 'D', label: 'Дерматология (D)' },
{ value: 'S', label: 'Стоматология (S)' },
{ value: 'L', label: 'Лаборатория (L)' },
{ value: 'O', label: 'Процедуры (O)' }];








const STATUS_FILTER_OPTIONS = [
{ value: 'all', label: 'Все статусы' },
{ value: 'active', label: 'Активные' },
{ value: 'inactive', label: 'Неактивные' }];

const SORT_OPTIONS = [
{ value: 'name', label: 'По названию' },
{ value: 'key', label: 'По ключу' },
{ value: 'order', label: 'По порядку' }];

const PAGE_SIZE_OPTIONS = [
{ value: 5, label: '5' },
{ value: 10, label: '10' },
{ value: 20, label: '20' },
{ value: 50, label: '50' }];

const DepartmentManagement = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 2 window.confirm() calls).
  const [confirm, confirmDialog] = useConfirm();
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [, setError] = useState(null);

  const [formData, setFormData] = useState(DEFAULT_FORM);
  const [integrationForm, setIntegrationForm] = useState(DEFAULT_INTEGRATION_OPTIONS);
  const [serviceMapping, setServiceMapping] = useState(DEFAULT_SERVICE_MAPPING);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingDepartment, setEditingDepartment] = useState(null);
  const [validationErrors, setValidationErrors] = useState({});

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
      setError('Не удалось загрузить отделения');
      toast.error('Не удалось загрузить отделения');
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
    (data, currentId = null) => {
      const errors = {};
      if (!data.name_ru || data.name_ru.trim().length < 2) {
        errors.name_ru = 'Название обязательно и должно быть длиннее 2 символов';
      }
      if (!data.key || data.key.trim().length < 2) {
        errors.key = 'Ключ обязателен (минимум 2 символа)';
      } else {
        const duplicate = departments.find((dept) => dept.key === data.key && dept.id !== currentId);
        if (duplicate) {
          errors.key = 'Отделение с таким ключом уже существует';
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
      toast.error('Исправьте ошибки в форме');
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
      toast.success('Отделение создано и синхронизировано');
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
      toast.error(err.response?.data?.detail || 'Не удалось создать отделение');
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
      toast.error('Исправьте ошибки в форме');
      return;
    }
    try {
      await api.put(`/admin/departments/${editingDepartment.id}`, formData);
      toast.success('Отделение обновлено');

      // PR-20: Removed frontend POST /services call (same as create handler).
      // Backend already handles default service via _ensure_department_integrations.

      setShowEditModal(false);
      setEditingDepartment(null);
      setServiceMapping(DEFAULT_SERVICE_MAPPING);
      await loadDepartments();
      broadcastDepartmentsUpdate();
    } catch (err) {
      logger.error('Ошибка обновления отделения:', err);
      toast.error(err.response?.data?.detail || 'Не удалось обновить отделение');
    }
  };

  // ✅ НОВОЕ: Быстрое переключение статуса отделения
  const handleToggleActive = async (dept, newActive) => {
    try {
      await api.put(`/admin/departments/${dept.id}`, { active: newActive });
      toast.success(`Отделение ${newActive ? 'активировано' : 'деактивировано'}`);
      await loadDepartments();
      broadcastDepartmentsUpdate();
    } catch (err) {
      logger.error('Ошибка обновления статуса:', err);
      toast.error(err.response?.data?.detail || 'Не удалось обновить статус');
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
      toast.error(err.response?.data?.detail || 'Не удалось обновить порядок');
    }
  };

  const handleDeleteDepartment = async (id) => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление отделения',
      message: 'Удалить отделение?',
      description: 'Это действие необратимо. Все связанные сервисы будут отвязаны.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });
    if (!ok) return;
    try {
      await api.delete(`/admin/departments/${id}`);
      toast.success('Отделение удалено');
      await loadDepartments();
      broadcastDepartmentsUpdate();
    } catch (err) {
      logger.error('Ошибка удаления отделения:', err);
      toast.error(err.response?.data?.detail || 'Не удалось удалить отделение');
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

      toast.success('Отделения успешно экспортированы');
    } catch (error) {
      logger.error('Ошибка экспорта:', error);
      toast.error('Ошибка при экспорте отделений');
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
        toast.error('CSV файл должен содержать заголовки и данные');
        return;
      }

      const headers = lines[0].split(',').map((h) => h.replace(/"/g, '').trim());
      const requiredHeaders = ['name_ru', 'key'];

      // Проверка обязательных заголовков
      const missingHeaders = requiredHeaders.filter((h) => !headers.includes(h));
      if (missingHeaders.length > 0) {
        toast.error(`Отсутствуют обязательные столбцы: ${missingHeaders.join(', ')}`);
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
            errors.push(`Строка ${i + 1}: ${Object.values(validationErrors).join(', ')}`);
            continue;
          }

          importedDepartments.push(dept);
        } catch {
          errors.push(`Строка ${i + 1}: Ошибка парсинга данных`);
        }
      }

      if (errors.length > 0) {
        toast.error(`Найдены ошибки в ${errors.length} строках. Проверьте данные и попробуйте снова.`);
        logger.error('Ошибки импорта:', errors);
        return;
      }

      if (importedDepartments.length === 0) {
        toast.warning('Нет данных для импорта');
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
        toast.success(`Успешно импортировано ${importedDepartments.length} отделений`);
        loadDepartments();
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Ошибка при импорте отделений');
      }

    } catch (error) {
      logger.error('Ошибка импорта:', error);
      toast.error('Ошибка при чтении файла');
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
      toast.warning('Выберите отделения для удаления');
      return;
    }

    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const confirmed = await confirm({
      title: 'Массовое удаление отделений',
      message: `Удалить ${selectedDepartments.length} отделений?`,
      description: 'Это действие нельзя отменить. Все связанные сервисы будут отвязаны.',
      confirmLabel: 'Удалить все',
      cancelLabel: 'Отмена',
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
        toast.success(`Удалено ${selectedDepartments.length} отделений`);
        setSelectedDepartments([]);
        setSelectAll(false);
        loadDepartments();
      } else {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
        toast.error(`Ошибка при удалении: ${errorMessage}`);
      }
    } catch (error) {
      logger.error('Ошибка массового удаления:', error);
      toast.error('Ошибка при удалении отделений');
    }
  };

  const handleBulkActivate = async (activate) => {
    if (selectedDepartments.length === 0) {
      toast.warning('Выберите отделения');
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
        toast.success(`${selectedDepartments.length} отделений ${activate ? 'активированы' : 'деактивированы'}`);
        setSelectedDepartments([]);
        setSelectAll(false);
        loadDepartments();
      } else {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
        toast.error(`Ошибка при ${activate ? 'активации' : 'деактивации'}: ${errorMessage}`);
      }
    } catch (error) {
      logger.error('Ошибка массовой активации:', error);
      toast.error(`Ошибка при ${activate ? 'активации' : 'деактивации'} отделений`);
    }
  };

  // Расчет статистики отделений
  const departmentStats = {
    total: departments.length,
    active: departments.filter((dept) => dept.active !== false).length,
    inactive: departments.filter((dept) => dept.active === false).length,
    withDoctors: departments.filter((dept) => (dept.doctor_count || 0) > 0).length,
    withoutDoctors: departments.filter((dept) => !(dept.doctor_count || 0) > 0).length
  };

  if (loading) {
    return (
      <MacOSCard>
                <div className="admin-loading-p-40-center">
                    <div className="spinner admin-spinner-mb-16"></div>
                    <p className="text-[var(--mac-text-secondary)]">Загрузка отделений...</p>
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
                            Всего отделений
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard className="p-4">
                    <div className="text-center">
                        <div className="admin-stat-number-success-mb-4">
                            {departmentStats.active}
                        </div>
                        <div className="admin-stat-label">
                            Активных
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard className="p-4">
                    <div className="text-center">
                        <div className="admin-stat-number-warning-mb-4">
                            {departmentStats.inactive}
                        </div>
                        <div className="admin-stat-label">
                            Неактивных
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard className="p-4">
                    <div className="text-center">
                        <div className="admin-stat-number-info-mb-4">
                            {departmentStats.withDoctors}
                        </div>
                        <div className="admin-stat-label">
                            С врачами
                        </div>
                    </div>
                </MacOSCard>
            </div>

            <MacOSCard>
                <div className="p-6">
                    <div className="admin-flex-between-mb-24">
                        <h2 className="admin-title-20">
                            Управление отделениями
                        </h2>
                        <div className="admin-flex-gap-8">
                            <Button
                variant="primary"
                size="default"
                onClick={() => setShowAddForm(!showAddForm)}>
                
                                <Plus size={16} className="mr-2" />
                                Добавить отделение
                            </Button>

                            <Button
                variant="secondary"
                size="default"
                onClick={handleExport}
                title="Экспортировать отделения в CSV">
                
                                <Download size={16} className="mr-2" />
                                Экспорт
                            </Button>

                            <label className="admin-position-relative">
                                <Button
                  variant="secondary"
                  size="default"
                  as="span"
                  className="admin-cursor-pointer"
                  title="Импортировать отделения из CSV">
                  
                                    <Upload size={16} className="mr-2" />
                                    Импорт
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
                            <Search size={16} className="text-[var(--mac-text-secondary)]" />
                            <Input
                placeholder="Поиск по названию или ключу..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="admin-flex-1" />
                        </div>

                        <Select
              value={statusFilter}
              onChange={(value) => setStatusFilter(value)}
              options={STATUS_FILTER_OPTIONS}
              className="admin-min-w-120" />

                        <Select
              value={sortBy}
              onChange={(value) => setSortBy(value)}
              options={SORT_OPTIONS}
              className="admin-min-w-140" />

                        <Button
              variant="secondary"
              size="sm"
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              title={sortOrder === 'asc' ? 'По возрастанию' : 'По убыванию'}>
              
                            {sortOrder === 'asc' ? '↑' : '↓'}
                        </Button>
                    </div>

                    {showAddForm &&
          <div className="admin-form-panel-tertiary-mb-24">
                            <h3 className="admin-title-16-mb-16">
                                Новое отделение
                            </h3>
                            <div className="admin-grid-2col">
                                <div>
                                    <Input
                  placeholder="Название (русский)"
                  value={formData.name_ru}
                  onChange={(e) => setFormData({ ...formData, name_ru: e.target.value })}
                  className={validationErrors.name_ru ? 'admin-input-error' : undefined} />
                
                                    {validationErrors.name_ru &&
                <div className="admin-error-text-mt">
                                            {validationErrors.name_ru}
                                        </div>
                }
                                </div>
                                <div>
                                    <Input
                  placeholder="Название (узбекский)"
                  value={formData.name_uz}
                  onChange={(e) => setFormData({ ...formData, name_uz: e.target.value })}
                  className={validationErrors.name_uz ? 'admin-input-error' : undefined} />
                
                                    {validationErrors.name_uz &&
                <div className="admin-error-text-mt">
                                            {validationErrors.name_uz}
                                        </div>
                }
                                </div>
                                <div>
                                    <Input
                  placeholder="Ключ (например, cardio)"
                  value={formData.key}
                  onChange={(e) => setFormData({ ...formData, key: e.target.value })}
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
                  placeholder="Порядок отображения"
                  value={formData.display_order}
                  onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) })}
                  className={`admin-grid-col-2${validationErrors.display_order ? ' admin-input-error' : ''}`} />
                
                                    {validationErrors.display_order &&
                <div className="admin-error-text-mt">
                                            {validationErrors.display_order}
                                        </div>
                }
                                </div>
                                <div className="admin-grid-span-all">
                                    <Input value={formData.icon} onChange={(e) => setFormData({ ...formData, icon: e.target.value })} placeholder="Имя иконки (например: Package, Heart, Stethoscope)" />
                
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
                  onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                  className="admin-grid-col-1" />
                
                                    <label className="admin-label-hint">
                                        Цвет вкладки
                                    </label>
                                </div>
                                <div className="admin-grid-span-all">
                                    <Textarea
                  placeholder="Описание отделения (опционально)"
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
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
                                    Настройка услуг для вкладки
                                </h4>

                                <div className="mb-4">
                                    <Checkbox
                  checked={serviceMapping.create_service}
                  onChange={(e) => setServiceMapping({ ...serviceMapping, create_service: e.target.checked })}
                  label="Создать новую услугу при создании отделения" />
                
                                </div>

                                {serviceMapping.create_service &&
              <div className="admin-grid-2col">
                                        <div>
                                            <Input
                    placeholder="Название услуги"
                    value={serviceMapping.service_name}
                    onChange={(e) => setServiceMapping({ ...serviceMapping, service_name: e.target.value })} />
                  
                                        </div>
                                        <div>
                                            <Select
                    value={serviceMapping.service_category_code}
                    onChange={(value) => setServiceMapping({ ...serviceMapping, service_category_code: value })}
                    options={CATEGORY_OPTIONS} />
                                        </div>
                                        <div>
                                            <Input
                    placeholder="Код услуги (например, K01, L01)"
                    value={serviceMapping.service_code_pattern}
                    onChange={(e) => setServiceMapping({ ...serviceMapping, service_code_pattern: e.target.value.toUpperCase() })} />
                  
                                        </div>
                                        <div>
                                            <Input
                    type="number"
                    placeholder="Цена услуги"
                    value={serviceMapping.service_price}
                    onChange={(e) => setServiceMapping({ ...serviceMapping, service_price: e.target.value })} />
                  
                                        </div>
                                        <div className="admin-grid-span-all">
                                            <Input
                    placeholder="Queue tag (опционально, например: ecg, cardiology_common)"
                    value={serviceMapping.queue_tag}
                    onChange={(e) => setServiceMapping({ ...serviceMapping, queue_tag: e.target.value })} />
                  
                                            <div className="admin-hint-text-12-secondary-mt-4">
                                                Услуги с department_key=&quot;{formData.key || '...'}&quot; будут отображаться в этой вкладке мастера регистрации
                                            </div>
                                        </div>
                                    </div>
              }

                                {!serviceMapping.create_service &&
              <div className="admin-hint-box-tertiary">
                                        💡 Для отображения услуг в этой вкладке мастера регистрации, убедитесь, что услуги имеют <code>department_key=&quot;{formData.key || '...'}&quot;</code> или соответствующий <code>category_code</code>.
                                    </div>
              }
                            </div>

                            <div className="admin-flex-gap-12-mt-16">
                                <Button variant="primary" onClick={handleAddDepartment}>
                                    <Save size={16} className="mr-2" />
                                    Сохранить
                                </Button>
                                <Button variant="secondary" onClick={() => {
                setShowAddForm(false);
                setFormData(DEFAULT_FORM);
                setServiceMapping(DEFAULT_SERVICE_MAPPING);
              }}>
                                    <X size={16} className="mr-2" />
                                    Отмена
                                </Button>
                            </div>
                        </div>
          }

                    {/* Панель массовых операций */}
                    {selectedDepartments.length > 0 &&
          <div className="admin-bulk-action-bar">
                            <span className="admin-selected-count">
                                Выбрано: {selectedDepartments.length}
                            </span>

                            <Button
              variant="danger"
              size="sm"
              onClick={handleBulkDelete}>
              
                                <Trash2 size={14} className="admin-mr-6" />
                                Удалить
                            </Button>

                            <Button
              variant="success"
              size="sm"
              onClick={() => handleBulkActivate(true)}>
              
                                <CheckCircle size={14} className="admin-mr-6" />
                                Активировать
                            </Button>

                            <Button
              variant="warning"
              size="sm"
              onClick={() => handleBulkActivate(false)}>
              
                                <XCircle size={14} className="admin-mr-6" />
                                Деактивировать
                            </Button>

                            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setSelectedDepartments([]);
                setSelectAll(false);
              }}>
              
                                <X size={14} className="admin-mr-6" />
                                Очистить
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
                      onChange={(e) => handleSelectAll(e.target.checked)} />
                    
                                    </th>
                                    <th className="admin-th-w-60">
                                        Иконка
                                    </th>
                                    <th className="admin-th">
                                        Название
                                    </th>
                                    <th className="admin-th-w-120">
                                        Ключ
                                    </th>
                                    <th className="admin-th-w-100">
                                        Порядок
                                    </th>
                                    <th className="admin-th-center">
                                        Статус
                                    </th>
                                    <th className="admin-th-right">
                                        Действия
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
                          onChange={(e) => handleSelectDepartment(dept.id, e.target.checked)} />
                        
                                            </td>
                                            <td className="admin-td-padded">
                                                <div className="admin-icon-cell-40" style={{ '--admin-icon-bg': dept.color || 'var(--mac-accent-blue)' }}>
                                                    {IconComponent ?
                          <IconComponent size={20} /> :

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
                          onChange={(e) => {
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
                            size="sm"
                            variant="secondary"
                            aria-label={`Edit department ${dept.name_ru || dept.name || dept.key}`}
                            onClick={() => openEditModal(dept)}
                            title="Редактировать отделение">
                            
                                                        <Edit2 size={16} />
                                                    </Button>
                                                    <Button
                            size="sm"
                            variant="danger"
                            aria-label={`Delete department ${dept.name_ru || dept.name || dept.key}`}
                            onClick={() => handleDeleteDepartment(dept.id)}
                            title="Удалить отделение">
                            
                                                        <Trash2 size={16} />
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
                            <p>Нет отделений. Добавьте первое отделение.</p>
                        </div>
          }

                    {departments.length > 0 && filteredDepartments.length === 0 &&
          <div className="admin-empty-p-40-center-secondary">
                            <p>По вашему запросу ничего не найдено.</p>
                        </div>
          }

                    {/* Пагинация */}
                    {totalPages > 1 &&
          <div className="admin-pagination-bar">
                            <MacOSPagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage} />
            
                            <div className="flex items-center justify-center gap-2">
                                <span className="admin-text-14-secondary">
                                    Показывать:
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
                                    из {totalItems}
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
        title="Редактирование отделения"
        size="large">
        
                <div className="admin-grid-2col">
                    <div>
                        <Input
              label="Название (русский)"
              placeholder="Название (русский)"
              value={formData.name_ru}
              onChange={(e) => setFormData({ ...formData, name_ru: e.target.value })}
              className={validationErrors.name_ru ? 'admin-input-error' : undefined} />
            
                        {validationErrors.name_ru &&
            <div className="admin-error-text-mt">
                                {validationErrors.name_ru}
                            </div>
            }
                    </div>
                    <div>
                        <Input
              label="Название (узбекский)"
              placeholder="Название (узбекский)"
              value={formData.name_uz}
              onChange={(e) => setFormData({ ...formData, name_uz: e.target.value })}
              className={validationErrors.name_uz ? 'admin-input-error' : undefined} />
            
                        {validationErrors.name_uz &&
            <div className="admin-error-text-mt">
                                {validationErrors.name_uz}
                            </div>
            }
                    </div>
                    <div>
                        <Input
              label="Ключ"
              placeholder="Ключ (например, cardio)"
              value={formData.key}
              onChange={(e) => setFormData({ ...formData, key: e.target.value })}
              className={`admin-grid-col-1${validationErrors.key ? ' admin-input-error' : ''}`} />
            
                        {validationErrors.key &&
            <div className="admin-error-text-mt">
                                {validationErrors.key}
                            </div>
            }
                    </div>
                    <div>
                        <Input
              label="Порядок отображения"
              type="number"
              placeholder="Порядок отображения"
              value={formData.display_order}
              onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) })}
              className={`admin-grid-col-2${validationErrors.display_order ? ' admin-input-error' : ''}`} />
            
                        {validationErrors.display_order &&
            <div className="admin-error-text-mt">
                                {validationErrors.display_order}
                            </div>
            }
                    </div>
                    <div className="admin-grid-span-all">
                        <Input value={formData.icon} onChange={(e) => setFormData({ ...formData, icon: e.target.value })} placeholder="Имя иконки (например: Package, Heart, Stethoscope)" />
            
                        {validationErrors.icon &&
            <div className="admin-error-text-mt">
                                {validationErrors.icon}
                            </div>
            }
                    </div>
                    <div>
                        <Input
              label="Цвет"
              type="color"
              value={formData.color}
              onChange={(e) => setFormData({ ...formData, color: e.target.value })}
              className="admin-grid-col-2" />
            
                    </div>
                    <div className="admin-grid-span-all">
                        <Textarea
              label="Описание"
              placeholder="Описание отделения (опционально)"
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
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
                        Настройка услуг для вкладки
                    </h4>

                    <div className="mb-4">
                        <Checkbox
              checked={serviceMapping.create_service}
              onChange={(e) => setServiceMapping({ ...serviceMapping, create_service: e.target.checked })}
              label="Создать новую услугу" />
            
                    </div>

                    {serviceMapping.create_service &&
          <div className="admin-grid-2col">
                            <div>
                                <Input
                label="Название услуги"
                placeholder="Название услуги"
                value={serviceMapping.service_name}
                onChange={(e) => setServiceMapping({ ...serviceMapping, service_name: e.target.value })} />
              
                            </div>
                            <div>
                                <label className="admin-label-block-md">
                                    Категория услуги
                                </label>
                                <Select
                value={serviceMapping.service_category_code}
                onChange={(value) => setServiceMapping({ ...serviceMapping, service_category_code: value })}
                options={CATEGORY_OPTIONS} />
                            </div>
                            <div>
                                <Input
                label="Код услуги"
                placeholder="Код услуги (например, K01, L01)"
                value={serviceMapping.service_code_pattern}
                onChange={(e) => setServiceMapping({ ...serviceMapping, service_code_pattern: e.target.value.toUpperCase() })} />
              
                            </div>
                            <div>
                                <Input
                label="Цена услуги"
                type="number"
                placeholder="Цена услуги"
                value={serviceMapping.service_price}
                onChange={(e) => setServiceMapping({ ...serviceMapping, service_price: e.target.value })} />
              
                            </div>
                            <div className="admin-grid-span-all">
                                <Input
                label="Queue tag (опционально)"
                placeholder="Queue tag (например: ecg, cardiology_common)"
                value={serviceMapping.queue_tag}
                onChange={(e) => setServiceMapping({ ...serviceMapping, queue_tag: e.target.value })} />
              
                                <div className="admin-hint-text-12-secondary-mt-4">
                                    Услуги с department_key=&quot;{formData.key || '...'}&quot; будут отображаться в этой вкладке мастера регистрации
                                </div>
                            </div>
                        </div>
          }

                    {!serviceMapping.create_service &&
          <div className="admin-hint-box-tertiary">
                            💡 Для отображения услуг в этой вкладке мастера регистрации, убедитесь, что услуги имеют <code>department_key=&quot;{formData.key || '...'}&quot;</code> или соответствующий <code>category_code</code>.
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
            
                        Отмена
                    </Button>
                    <Button
            variant="primary"
            onClick={handleUpdateDepartment}>
            
                        <Save size={16} className="mr-2" />
                        Сохранить изменения
                    </Button>
                </div>
            </Modal>
            {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
            {confirmDialog}
        </div>
      );

};

export default DepartmentManagement;
