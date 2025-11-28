/**
 * DepartmentManagement Component
<<<<<<< HEAD
 * Управление отделениями, вкладками и интеграциями очередей/услуг
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
    Plus,
    RefreshCw,
    Save,
    Trash2,
    Search,
    ShieldCheck,
    AlertTriangle,
    CheckCircle,
    Download,
    Upload,
    Edit2,
    X,
    XCircle,
} from 'lucide-react';
import {
    MacOSCard,
    MacOSButton,
    MacOSBadge,
    MacOSInput,
    MacOSSelect,
    MacOSTextarea,
    MacOSCheckbox,
    MacOSPagination,
    MacOSModal,
    MacOSAlert,
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DEFAULT_STATS = {
    appointments_today: 0,
    visits_today: 0,
    queue_entries_today: 0,
    services: 0,
    doctors: 0,
};

const DEFAULT_TOTALS = {
    departments: 0,
    active: 0,
    queue_enabled: 0,
    appointments_today: 0,
    visits_today: 0,
};

const DEFAULT_FORM = {
    name_ru: '',
    name_uz: '',
    key: '',
    description: '',
    color: '#0066cc',
    icon: '🏥',
    display_order: 999,
    active: true,
};

const DEFAULT_INTEGRATION_OPTIONS = {
    queue_prefix: '',
    start_number: '',
    max_daily_queue: '',
    service_name: '',
    service_code: '',
    service_category_code: '',
    service_price: '',
    service_currency: 'UZS',
};

const CATEGORY_OPTIONS = [
    { value: '', label: 'Категория (авто)' },
    { value: 'K', label: 'Кардиология (K)' },
    { value: 'D', label: 'Дерматология (D)' },
    { value: 'S', label: 'Стоматология (S)' },
    { value: 'L', label: 'Лаборатория (L)' },
    { value: 'O', label: 'Процедуры (O)' },
];

const STATUS_OPTIONS = [
    { value: 'all', label: 'Все' },
    { value: 'active', label: 'Активные' },
    { value: 'inactive', label: 'Неактивные' },
];
=======
 * Manages departments/specialties in the system
 */

import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Save, X } from 'lucide-react';
import { Card, Button, Badge, Input } from '../ui/macos';
import { toast } from 'react-toastify';

const API_BASE = import.meta?.env?.VITE_API_BASE_URL || 'http://localhost:8000';
>>>>>>> origin/main

const DepartmentManagement = () => {
    const [departments, setDepartments] = useState([]);
    const [loading, setLoading] = useState(true);
<<<<<<< HEAD
    const [error, setError] = useState(null);

    const [formData, setFormData] = useState(DEFAULT_FORM);
    const [integrationForm, setIntegrationForm] = useState(DEFAULT_INTEGRATION_OPTIONS);
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
    const [syncingId, setSyncingId] = useState(null);
    const [totals, setTotals] = useState(DEFAULT_TOTALS);

    const broadcastDepartmentsUpdate = useCallback(() => {
        window.dispatchEvent(
            new CustomEvent('departments:updated', { detail: { updatedAt: Date.now() } }),
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
                api.get('/admin/departments/overview'),
            ]);

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
                    integrations: stats.integrations || {},
                };
            });

            setDepartments(enriched);
            setTotals({
                ...DEFAULT_TOTALS,
                ...(overview.totals || {}),
            });
        } catch (err) {
            console.error('Ошибка загрузки отделений:', err);
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
        [departments],
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
                integration: sanitizeIntegrationPayload(integrationForm),
            };
            await api.post('/admin/departments', payload);
            toast.success('Отделение создано и синхронизировано');
            setShowAddForm(false);
            setFormData(DEFAULT_FORM);
            setIntegrationForm(DEFAULT_INTEGRATION_OPTIONS);
            await loadDepartments();
            broadcastDepartmentsUpdate();
        } catch (err) {
            console.error('Ошибка создания отделения:', err);
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
            color: dept.color || '#0066cc',
            icon: dept.icon || '🏥',
            display_order: dept.display_order || 999,
            active: dept.active ?? true,
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
            setShowEditModal(false);
            setEditingDepartment(null);
            await loadDepartments();
            broadcastDepartmentsUpdate();
        } catch (err) {
            console.error('Ошибка обновления отделения:', err);
            toast.error(err.response?.data?.detail || 'Не удалось обновить отделение');
        }
    };

    const handleDeleteDepartment = async (id) => {
        if (!window.confirm('Удалить отделение? Это действие необратимо.')) return;
        try {
            await api.delete(`/admin/departments/${id}`);
            toast.success('Отделение удалено');
            await loadDepartments();
            broadcastDepartmentsUpdate();
        } catch (err) {
            console.error('Ошибка удаления отделения:', err);
            toast.error(err.response?.data?.detail || 'Не удалось удалить отделение');
        }
    };

    const runIntegration = async (department) => {
        setSyncingId(department.id);
        try {
            const payload = sanitizeIntegrationPayload({
                queue_prefix: department.integrations?.queue_prefix,
                start_number: department.integrations?.start_number,
                max_daily_queue: department.integrations?.max_per_day,
            });
            await api.post(`/admin/departments/${department.id}/initialize`, payload);
            toast.success('Интеграция обновлена');
            await loadDepartments();
            broadcastDepartmentsUpdate();
        } catch (err) {
            console.error('Ошибка синхронизации отделения:', err);
            toast.error(err.response?.data?.detail || 'Не удалось обновить интеграцию');
        } finally {
            setSyncingId(null);
        }
    };

    // Фильтрация и сортировка отделений
    const filteredDepartments = departments
        .filter(dept => {
            const matchesSearch = searchTerm === '' ||
                dept.name_ru?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                dept.name_uz?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                dept.key?.toLowerCase().includes(searchTerm.toLowerCase());

            const matchesStatus = statusFilter === 'all' ||
                (statusFilter === 'active' && dept.active !== false) ||
                (statusFilter === 'inactive' && dept.active === false);

            return matchesSearch && matchesStatus;
        })
        .sort((a, b) => {
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
                    aValue = a.display_order || 999;
                    bValue = b.display_order || 999;
                    break;
                default:
                    aValue = a.name_ru || a.name || '';
                    bValue = b.name_ru || b.name || '';
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
                ...departments.map(dept => [
                    `"${(dept.name_ru || '').replace(/"/g, '""')}"`,
                    `"${(dept.name_uz || '').replace(/"/g, '""')}"`,
                    `"${(dept.key || '').replace(/"/g, '""')}"`,
                    `"${(dept.description || '').replace(/"/g, '""')}"`,
                    `"${(dept.color || '#0066cc').replace(/"/g, '""')}"`,
                    `"${(dept.icon || '🏥').replace(/"/g, '""')}"`,
                    dept.display_order || 999,
                    dept.active !== false ? 'true' : 'false'
                ].join(','))
            ].join('\n');

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
            console.error('Ошибка экспорта:', error);
            toast.error('Ошибка при экспорте отделений');
        }
    };

    // Функция импорта отделений из CSV
    const handleImport = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        try {
            const text = await file.text();
            const lines = text.split('\n').filter(line => line.trim());

            if (lines.length < 2) {
                toast.error('CSV файл должен содержать заголовки и данные');
                return;
            }

            const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim());
            const requiredHeaders = ['name_ru', 'key'];

            // Проверка обязательных заголовков
            const missingHeaders = requiredHeaders.filter(h => !headers.includes(h));
            if (missingHeaders.length > 0) {
                toast.error(`Отсутствуют обязательные столбцы: ${missingHeaders.join(', ')}`);
                return;
            }

            const importedDepartments = [];
            const errors = [];

            for (let i = 1; i < lines.length; i++) {
                try {
                    const values = lines[i].split(',').map(v => v.replace(/^"|"$/g, '').replace(/""/g, '"'));
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
                } catch (error) {
                    errors.push(`Строка ${i + 1}: Ошибка парсинга данных`);
                }
            }

            if (errors.length > 0) {
                toast.error(`Найдены ошибки в ${errors.length} строках. Проверьте данные и попробуйте снова.`);
                console.error('Ошибки импорта:', errors);
                return;
            }

            if (importedDepartments.length === 0) {
                toast.warning('Нет данных для импорта');
                return;
            }

            // Импорт данных
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments/bulk`, {
=======
    const [editingId, setEditingId] = useState(null);
    const [showAddForm, setShowAddForm] = useState(false);
    const [formData, setFormData] = useState({
        name_ru: '',
        name_uz: '',
        key: '',
        description: '',
        color: '#0066cc',
        icon: '🏥',
        display_order: 999,
        active: true
    });

    useEffect(() => {
        loadDepartments();
    }, []);

    const loadDepartments = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const result = await response.json();
                // Backend returns {success: true, data: [...], count: N}
                setDepartments(result.data || []);
            } else {
                toast.error('Не удалось загрузить отделения');
            }
        } catch (error) {
            console.error('Error loading departments:', error);
            toast.error('Ошибка загрузки отделений');
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = async () => {
        if (!formData.name_ru || !formData.key) {
            toast.error('Заполните обязательные поля');
            return;
        }

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments`, {
>>>>>>> origin/main
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
<<<<<<< HEAD
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
            console.error('Ошибка импорта:', error);
            toast.error('Ошибка при чтении файла');
        }

        // Очистка input
        event.target.value = '';
    };

    // Функции массовых операций
    const handleSelectAll = (checked) => {
        setSelectAll(checked);
        if (checked) {
            setSelectedDepartments(paginatedDepartments.map(dept => dept.id));
        } else {
            setSelectedDepartments([]);
        }
    };

    const handleSelectDepartment = (deptId, checked) => {
        if (checked) {
            setSelectedDepartments(prev => [...prev, deptId]);
        } else {
            setSelectedDepartments(prev => prev.filter(id => id !== deptId));
            setSelectAll(false);
        }
    };

    const handleBulkDelete = async () => {
        if (selectedDepartments.length === 0) {
            toast.warning('Выберите отделения для удаления');
            return;
        }

        const confirmed = window.confirm(
            `Вы уверены, что хотите удалить ${selectedDepartments.length} отделений? Это действие нельзя отменить.`
        );

        if (!confirmed) return;

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments/bulk-delete`, {
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
            console.error('Ошибка массового удаления:', error);
            toast.error('Ошибка при удалении отделений');
        }
    };

    const handleBulkActivate = async (activate) => {
        if (selectedDepartments.length === 0) {
            toast.warning('Выберите отделения');
            return;
        }

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments/bulk-activate`, {
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
            console.error('Ошибка массовой активации:', error);
            toast.error(`Ошибка при ${activate ? 'активации' : 'деактивации'} отделений`);
        }
    };

    // Расчет статистики отделений
    const departmentStats = {
        total: departments.length,
        active: departments.filter(dept => dept.active !== false).length,
        inactive: departments.filter(dept => dept.active === false).length,
        withDoctors: departments.filter(dept => (dept.doctor_count || 0) > 0).length,
        withoutDoctors: departments.filter(dept => !(dept.doctor_count || 0) > 0).length
    };

    if (loading) {
        return (
            <MacOSCard>
=======
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                toast.success('Отделение добавлено');
                setShowAddForm(false);
                setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                loadDepartments();
            } else {
                toast.error('Ошибка при добавлении отделения');
            }
        } catch (error) {
            console.error('Error adding department:', error);
            toast.error('Ошибка при добавлении отделения');
        }
    };

    const handleEdit = (dept) => {
        setEditingId(dept.id);
        setFormData({
            name_ru: dept.name_ru || dept.name,
            name_uz: dept.name_uz || '',
            key: dept.key || dept.code,
            description: dept.description || '',
            color: dept.color || '#0066cc',
            icon: dept.icon || '🏥',
            display_order: dept.display_order || 999,
            active: dept.active !== undefined ? dept.active : true
        });
    };

    const handleUpdate = async (id) => {
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments/${id}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                toast.success('Отделение обновлено');
                setEditingId(null);
                setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                loadDepartments();
            } else {
                toast.error('Ошибка при обновлении отделения');
            }
        } catch (error) {
            console.error('Error updating department:', error);
            toast.error('Ошибка при обновлении отделения');
        }
    };

    const handleDelete = async (id) => {
        if (!confirm('Вы уверены, что хотите удалить это отделение?')) {
            return;
        }

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                toast.success('Отделение удалено');
                loadDepartments();
            } else {
                toast.error('Ошибка при удалении отделения');
            }
        } catch (error) {
            console.error('Error deleting department:', error);
            toast.error('Ошибка при удалении отделения');
        }
    };

    if (loading) {
        return (
            <Card>
>>>>>>> origin/main
                <div style={{ padding: '40px', textAlign: 'center' }}>
                    <div className="spinner" style={{ margin: '0 auto 16px' }}></div>
                    <p style={{ color: 'var(--mac-text-secondary)' }}>Загрузка отделений...</p>
                </div>
<<<<<<< HEAD
            </MacOSCard>
=======
            </Card>
>>>>>>> origin/main
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
<<<<<<< HEAD
            {/* Статистика отделений */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '16px',
                marginBottom: '16px'
            }}>
                <MacOSCard style={{ padding: '16px' }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{
                            fontSize: '24px',
                            fontWeight: 'bold',
                            color: 'var(--mac-text-primary)',
                            marginBottom: '4px'
                        }}>
                            {departmentStats.total}
                        </div>
                        <div style={{
                            fontSize: '14px',
                            color: 'var(--mac-text-secondary)'
                        }}>
                            Всего отделений
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard style={{ padding: '16px' }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{
                            fontSize: '24px',
                            fontWeight: 'bold',
                            color: 'var(--mac-success)',
                            marginBottom: '4px'
                        }}>
                            {departmentStats.active}
                        </div>
                        <div style={{
                            fontSize: '14px',
                            color: 'var(--mac-text-secondary)'
                        }}>
                            Активных
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard style={{ padding: '16px' }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{
                            fontSize: '24px',
                            fontWeight: 'bold',
                            color: 'var(--mac-warning)',
                            marginBottom: '4px'
                        }}>
                            {departmentStats.inactive}
                        </div>
                        <div style={{
                            fontSize: '14px',
                            color: 'var(--mac-text-secondary)'
                        }}>
                            Неактивных
                        </div>
                    </div>
                </MacOSCard>

                <MacOSCard style={{ padding: '16px' }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{
                            fontSize: '24px',
                            fontWeight: 'bold',
                            color: 'var(--mac-info)',
                            marginBottom: '4px'
                        }}>
                            {departmentStats.withDoctors}
                        </div>
                        <div style={{
                            fontSize: '14px',
                            color: 'var(--mac-text-secondary)'
                        }}>
                            С врачами
                        </div>
                    </div>
                </MacOSCard>
            </div>

            <MacOSCard>
=======
            <Card>
>>>>>>> origin/main
                <div style={{ padding: '24px' }}>
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '24px'
                    }}>
                        <h2 style={{
                            fontSize: '20px',
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)',
                            margin: 0
                        }}>
                            Управление отделениями
                        </h2>
<<<<<<< HEAD
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <MacOSButton
                                variant="primary"
                                size="default"
                                onClick={() => setShowAddForm(!showAddForm)}
                            >
                                <Plus size={16} style={{ marginRight: '8px' }} />
                                Добавить отделение
                            </MacOSButton>

                            <MacOSButton
                                variant="secondary"
                                size="default"
                                onClick={handleExport}
                                title="Экспортировать отделения в CSV"
                            >
                                <Download size={16} style={{ marginRight: '8px' }} />
                                Экспорт
                            </MacOSButton>

                            <label style={{ position: 'relative' }}>
                                <MacOSButton
                                    variant="secondary"
                                    size="default"
                                    as="span"
                                    style={{ cursor: 'pointer' }}
                                    title="Импортировать отделения из CSV"
                                >
                                    <Upload size={16} style={{ marginRight: '8px' }} />
                                    Импорт
                                </MacOSButton>
                                <input
                                    type="file"
                                    accept=".csv"
                                    onChange={handleImport}
                                    style={{
                                        position: 'absolute',
                                        top: 0,
                                        left: 0,
                                        width: '100%',
                                        height: '100%',
                                        opacity: 0,
                                        cursor: 'pointer'
                                    }}
                                />
                            </label>
                        </div>
                    </div>

                    {/* Панель поиска и фильтров */}
                    <div style={{
                        display: 'flex',
                        gap: '16px',
                        alignItems: 'center',
                        marginBottom: '24px',
                        flexWrap: 'wrap'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '200px' }}>
                            <Search size={16} style={{ color: 'var(--mac-text-secondary)' }} />
                            <MacOSInput
                                placeholder="Поиск по названию или ключу..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                style={{ flex: 1 }}
                            />
                        </div>

                        <MacOSSelect
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                            style={{ minWidth: '120px' }}
                        >
                            <option value="all">Все статусы</option>
                            <option value="active">Активные</option>
                            <option value="inactive">Неактивные</option>
                        </MacOSSelect>

                        <MacOSSelect
                            value={sortBy}
                            onChange={(e) => setSortBy(e.target.value)}
                            style={{ minWidth: '140px' }}
                        >
                            <option value="name">По названию</option>
                            <option value="key">По ключу</option>
                            <option value="order">По порядку</option>
                        </MacOSSelect>

                        <MacOSButton
                            variant="secondary"
                            size="sm"
                            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                            title={sortOrder === 'asc' ? 'По возрастанию' : 'По убыванию'}
                        >
                            {sortOrder === 'asc' ? '↑' : '↓'}
                        </MacOSButton>
=======
                        <Button
                            variant="primary"
                            size="default"
                            onClick={() => setShowAddForm(!showAddForm)}
                        >
                            <Plus size={16} style={{ marginRight: '8px' }} />
                            Добавить отделение
                        </Button>
>>>>>>> origin/main
                    </div>

                    {showAddForm && (
                        <div style={{
                            padding: '20px',
                            background: 'var(--mac-bg-tertiary)',
                            borderRadius: 'var(--mac-radius-md)',
                            marginBottom: '24px'
                        }}>
                            <h3 style={{
                                fontSize: '16px',
                                fontWeight: '600',
                                marginBottom: '16px',
                                color: 'var(--mac-text-primary)'
                            }}>
                                Новое отделение
                            </h3>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
<<<<<<< HEAD
                                <div>
                                    <MacOSInput
                                        placeholder="Название (русский)"
                                        value={formData.name_ru}
                                        onChange={(e) => setFormData({ ...formData, name_ru: e.target.value })}
                                        style={{ borderColor: validationErrors.name_ru ? 'var(--mac-error)' : undefined }}
                                    />
                                    {validationErrors.name_ru && (
                                        <div style={{
                                            color: 'var(--mac-error)',
                                            fontSize: '12px',
                                            marginTop: '4px'
                                        }}>
                                            {validationErrors.name_ru}
                                        </div>
                                    )}
                                </div>
                                <div>
                                    <MacOSInput
                                        placeholder="Название (узбекский)"
                                        value={formData.name_uz}
                                        onChange={(e) => setFormData({ ...formData, name_uz: e.target.value })}
                                        style={{ borderColor: validationErrors.name_uz ? 'var(--mac-error)' : undefined }}
                                    />
                                    {validationErrors.name_uz && (
                                        <div style={{
                                            color: 'var(--mac-error)',
                                            fontSize: '12px',
                                            marginTop: '4px'
                                        }}>
                                            {validationErrors.name_uz}
                                        </div>
                                    )}
                                </div>
                                <div>
                                    <MacOSInput
                                        placeholder="Ключ (например, cardio)"
                                        value={formData.key}
                                        onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                                        style={{
                                            gridColumn: '1',
                                            borderColor: validationErrors.key ? 'var(--mac-error)' : undefined
                                        }}
                                    />
                                    {validationErrors.key && (
                                        <div style={{
                                            color: 'var(--mac-error)',
                                            fontSize: '12px',
                                            marginTop: '4px'
                                        }}>
                                            {validationErrors.key}
                                        </div>
                                    )}
                                </div>
                                <div>
                                    <MacOSInput
                                        type="number"
                                        placeholder="Порядок отображения"
                                        value={formData.display_order}
                                        onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) })}
                                        style={{
                                            gridColumn: '2',
                                            borderColor: validationErrors.display_order ? 'var(--mac-error)' : undefined
                                        }}
                                    />
                                    {validationErrors.display_order && (
                                        <div style={{
                                            color: 'var(--mac-error)',
                                            fontSize: '12px',
                                            marginTop: '4px'
                                        }}>
                                            {validationErrors.display_order}
                                        </div>
                                    )}
                                </div>
                                <div>
                                    <MacOSInput
                                        placeholder="Иконка (emoji)"
                                        value={formData.icon}
                                        onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                                        style={{
                                            gridColumn: '1',
                                            borderColor: validationErrors.icon ? 'var(--mac-error)' : undefined
                                        }}
                                    />
                                    {validationErrors.icon && (
                                        <div style={{
                                            color: 'var(--mac-error)',
                                            fontSize: '12px',
                                            marginTop: '4px'
                                        }}>
                                            {validationErrors.icon}
                                        </div>
                                    )}
                                </div>
                                <div>
                                    <MacOSInput
                                        type="color"
                                        value={formData.color}
                                        onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                                        style={{ gridColumn: '2' }}
                                    />
                                    <div style={{ gridColumn: '1 / -1' }}>
                                        <MacOSTextarea
                                            placeholder="Описание отделения (опционально)"
                                            value={formData.description || ''}
                                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                            rows={3}
                                            style={{ borderColor: validationErrors.description ? 'var(--mac-error)' : undefined }}
                                        />
                                        {validationErrors.description && (
                                            <div style={{
                                                color: 'var(--mac-error)',
                                                fontSize: '12px',
                                                marginTop: '4px'
                                            }}>
                                                {validationErrors.description}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                                <MacOSButton variant="primary" onClick={handleAddDepartment}>
                                    <Save size={16} style={{ marginRight: '8px' }} />
                                    Сохранить
                                </MacOSButton>
                                <MacOSButton variant="secondary" onClick={() => {
=======
                                <Input
                                    placeholder="Название (русский)"
                                    value={formData.name_ru}
                                    onChange={(e) => setFormData({ ...formData, name_ru: e.target.value })}
                                />
                                <Input
                                    placeholder="Название (узбекский)"
                                    value={formData.name_uz}
                                    onChange={(e) => setFormData({ ...formData, name_uz: e.target.value })}
                                />
                                <Input
                                    placeholder="Ключ (например, cardio)"
                                    value={formData.key}
                                    onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                                    style={{ gridColumn: '1' }}
                                />
                                <Input
                                    type="number"
                                    placeholder="Порядок отображения"
                                    value={formData.display_order}
                                    onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) })}
                                    style={{ gridColumn: '2' }}
                                />
                                <Input
                                    placeholder="Иконка (emoji)"
                                    value={formData.icon}
                                    onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                                    style={{ gridColumn: '1' }}
                                />
                                <Input
                                    type="color"
                                    value={formData.color}
                                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                                    style={{ gridColumn: '2' }}
                                />
                            </div>
                            <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                                <Button variant="primary" onClick={handleAdd}>
                                    <Save size={16} style={{ marginRight: '8px' }} />
                                    Сохранить
                                </Button>
                                <Button variant="secondary" onClick={() => {
>>>>>>> origin/main
                                    setShowAddForm(false);
                                    setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                                }}>
                                    <X size={16} style={{ marginRight: '8px' }} />
                                    Отмена
<<<<<<< HEAD
                                </MacOSButton>
=======
                                </Button>
>>>>>>> origin/main
                            </div>
                        </div>
                    )}

<<<<<<< HEAD
                    {/* Панель массовых операций */}
                    {selectedDepartments.length > 0 && (
                        <div style={{
                            padding: '12px',
                            background: 'var(--mac-bg-tertiary)',
                            borderRadius: 'var(--mac-radius-md)',
                            border: '1px solid var(--mac-border)',
                            marginBottom: '16px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            flexWrap: 'wrap'
                        }}>
                            <span style={{
                                fontSize: '14px',
                                color: 'var(--mac-text-secondary)',
                                fontWeight: '500'
                            }}>
                                Выбрано: {selectedDepartments.length}
                            </span>

                            <MacOSButton
                                variant="danger"
                                size="sm"
                                onClick={handleBulkDelete}
                            >
                                <Trash2 size={14} style={{ marginRight: '6px' }} />
                                Удалить
                            </MacOSButton>

                            <MacOSButton
                                variant="success"
                                size="sm"
                                onClick={() => handleBulkActivate(true)}
                            >
                                <CheckCircle size={14} style={{ marginRight: '6px' }} />
                                Активировать
                            </MacOSButton>

                            <MacOSButton
                                variant="warning"
                                size="sm"
                                onClick={() => handleBulkActivate(false)}
                            >
                                <XCircle size={14} style={{ marginRight: '6px' }} />
                                Деактивировать
                            </MacOSButton>

                            <MacOSButton
                                variant="secondary"
                                size="sm"
                                onClick={() => {
                                    setSelectedDepartments([]);
                                    setSelectAll(false);
                                }}
                            >
                                <X size={14} style={{ marginRight: '6px' }} />
                                Очистить
                            </MacOSButton>
                        </div>
                    )}

                    {/* Заголовок с чекбоксом "Выбрать все" */}
                    <div style={{
                        padding: '12px 16px',
                        background: 'var(--mac-bg-secondary)',
                        border: '1px solid var(--mac-border)',
                        borderRadius: 'var(--mac-radius-md)',
                        marginBottom: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        fontSize: '14px',
                        fontWeight: '600',
                        color: 'var(--mac-text-primary)'
                    }}>
                        <MacOSCheckbox
                            checked={selectAll}
                            onChange={(e) => handleSelectAll(e.target.checked)}
                            label={`Выбрать все (${paginatedDepartments.length})`}
                        />
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {paginatedDepartments.map((dept) => (
=======
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {departments.map((dept) => (
>>>>>>> origin/main
                            <div
                                key={dept.id}
                                style={{
                                    padding: '16px',
                                    background: 'var(--mac-bg-secondary)',
                                    border: '1px solid var(--mac-border)',
                                    borderRadius: 'var(--mac-radius-md)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between'
                                }}
                            >
<<<<<<< HEAD
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '12px',
                                    flex: 1
                                }}>
                                    <MacOSCheckbox
                                        checked={selectedDepartments.includes(dept.id)}
                                        onChange={(e) => handleSelectDepartment(dept.id, e.target.checked)}
                                    />
=======
                                {editingId === dept.id ? (
                                    <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                                        <Input
                                            placeholder="Название (RU)"
                                            value={formData.name_ru}
                                            onChange={(e) => setFormData({ ...formData, name_ru: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Название (UZ)"
                                            value={formData.name_uz}
                                            onChange={(e) => setFormData({ ...formData, name_uz: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Ключ"
                                            value={formData.key}
                                            onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                                        />
                                    </div>
                                ) : (
>>>>>>> origin/main
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
                                        <div
                                            style={{
                                                width: '48px',
                                                height: '48px',
                                                borderRadius: 'var(--mac-radius-md)',
                                                background: dept.color || '#0066cc',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                fontSize: '24px'
                                            }}
                                        >
                                            {dept.icon || '🏥'}
                                        </div>
<<<<<<< HEAD
                                        <div style={{ flex: 1 }}>
=======
                                        <div>
>>>>>>> origin/main
                                            <h4 style={{
                                                fontSize: '16px',
                                                fontWeight: '600',
                                                margin: '0 0 4px 0',
                                                color: 'var(--mac-text-primary)'
                                            }}>
                                                {dept.name_ru || dept.name}
                                            </h4>
<<<<<<< HEAD
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                                <MacOSBadge variant="secondary">{dept.key || dept.code}</MacOSBadge>
                                                {dept.active === false && <MacOSBadge variant="danger">Неактивно</MacOSBadge>}
                                                {dept.description && (
                                                    <span style={{
                                                        fontSize: '12px',
                                                        color: 'var(--mac-text-secondary)',
                                                        maxWidth: '200px',
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                        whiteSpace: 'nowrap'
                                                    }}>
                                                        {dept.description}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div style={{ display: 'flex', gap: '8px' }}>
                                    <MacOSButton
                                        size="sm"
                                        variant="secondary"
                                        onClick={() => openEditModal(dept)}
                                        title="Редактировать отделение"
                                    >
                                        <Edit2 size={16} />
                                    </MacOSButton>
                                    <MacOSButton
                                        size="sm"
                                        variant="danger"
                                        onClick={() => handleDeleteDepartment(dept.id)}
                                        title="Удалить отделение"
                                    >
                                        <Trash2 size={16} />
                                    </MacOSButton>
=======
                                            <Badge variant="secondary">{dept.key || dept.code}</Badge>
                                            {dept.active === false && <Badge variant="danger" style={{ marginLeft: '8px' }}>Неактивно</Badge>}
                                        </div>
                                    </div>
                                )}

                                <div style={{ display: 'flex', gap: '8px' }}>
                                    {editingId === dept.id ? (
                                        <>
                                            <Button
                                                size="sm"
                                                variant="primary"
                                                onClick={() => handleUpdate(dept.id)}
                                            >
                                                <Save size={16} />
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="secondary"
                                                onClick={() => {
                                                    setEditingId(null);
                                                    setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                                                }}
                                            >
                                                <X size={16} />
                                            </Button>
                                        </>
                                    ) : (
                                        <>
                                            <Button
                                                size="sm"
                                                variant="secondary"
                                                onClick={() => handleEdit(dept)}
                                            >
                                                <Edit2 size={16} />
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="danger"
                                                onClick={() => handleDelete(dept.id)}
                                            >
                                                <Trash2 size={16} />
                                            </Button>
                                        </>
                                    )}
>>>>>>> origin/main
                                </div>
                            </div>
                        ))}
                    </div>

                    {departments.length === 0 && (
                        <div style={{
                            padding: '40px',
                            textAlign: 'center',
                            color: 'var(--mac-text-secondary)'
                        }}>
                            <p>Нет отделений. Добавьте первое отделение.</p>
                        </div>
                    )}
<<<<<<< HEAD

                    {departments.length > 0 && filteredDepartments.length === 0 && (
                        <div style={{
                            padding: '40px',
                            textAlign: 'center',
                            color: 'var(--mac-text-secondary)'
                        }}>
                            <p>По вашему запросу ничего не найдено.</p>
                        </div>
                    )}

                    {/* Пагинация */}
                    {totalPages > 1 && (
                        <div style={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            gap: '16px',
                            marginTop: '24px',
                            paddingTop: '16px',
                            borderTop: '1px solid var(--mac-border)'
                        }}>
                            <MacOSPagination
                                currentPage={currentPage}
                                totalPages={totalPages}
                                onPageChange={setCurrentPage}
                            />
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{ fontSize: '14px', color: 'var(--mac-text-secondary)' }}>
                                    Показывать:
                                </span>
                                <MacOSSelect
                                    value={itemsPerPage}
                                    onChange={(e) => {
                                        setItemsPerPage(Number(e.target.value));
                                        setCurrentPage(1);
                                    }}
                                    style={{ width: '70px' }}
                                >
                                    <option value={5}>5</option>
                                    <option value={10}>10</option>
                                    <option value={20}>20</option>
                                    <option value={50}>50</option>
                                </MacOSSelect>
                                <span style={{ fontSize: '14px', color: 'var(--mac-text-secondary)' }}>
                                    из {totalItems}
                                </span>
                            </div>
                        </div>
                    )}
                </div>
            </MacOSCard>

            {/* Модальное окно редактирования отделения */}
            <MacOSModal
                isOpen={showEditModal}
                onClose={() => {
                    setShowEditModal(false);
                    setEditingDepartment(null);
                    setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                    clearValidationErrors();
                }}
                title="Редактирование отделения"
                size="large"
            >
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    <div>
                        <MacOSInput
                            label="Название (русский)"
                            placeholder="Название (русский)"
                            value={formData.name_ru}
                            onChange={(e) => setFormData({ ...formData, name_ru: e.target.value })}
                            style={{ borderColor: validationErrors.name_ru ? 'var(--mac-error)' : undefined }}
                        />
                        {validationErrors.name_ru && (
                            <div style={{
                                color: 'var(--mac-error)',
                                fontSize: '12px',
                                marginTop: '4px'
                            }}>
                                {validationErrors.name_ru}
                            </div>
                        )}
                    </div>
                    <div>
                        <MacOSInput
                            label="Название (узбекский)"
                            placeholder="Название (узбекский)"
                            value={formData.name_uz}
                            onChange={(e) => setFormData({ ...formData, name_uz: e.target.value })}
                            style={{ borderColor: validationErrors.name_uz ? 'var(--mac-error)' : undefined }}
                        />
                        {validationErrors.name_uz && (
                            <div style={{
                                color: 'var(--mac-error)',
                                fontSize: '12px',
                                marginTop: '4px'
                            }}>
                                {validationErrors.name_uz}
                            </div>
                        )}
                    </div>
                    <div>
                        <MacOSInput
                            label="Ключ"
                            placeholder="Ключ (например, cardio)"
                            value={formData.key}
                            onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                            style={{
                                gridColumn: '1',
                                borderColor: validationErrors.key ? 'var(--mac-error)' : undefined
                            }}
                        />
                        {validationErrors.key && (
                            <div style={{
                                color: 'var(--mac-error)',
                                fontSize: '12px',
                                marginTop: '4px'
                            }}>
                                {validationErrors.key}
                            </div>
                        )}
                    </div>
                    <div>
                        <MacOSInput
                            label="Порядок отображения"
                            type="number"
                            placeholder="Порядок отображения"
                            value={formData.display_order}
                            onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) })}
                            style={{
                                gridColumn: '2',
                                borderColor: validationErrors.display_order ? 'var(--mac-error)' : undefined
                            }}
                        />
                        {validationErrors.display_order && (
                            <div style={{
                                color: 'var(--mac-error)',
                                fontSize: '12px',
                                marginTop: '4px'
                            }}>
                                {validationErrors.display_order}
                            </div>
                        )}
                    </div>
                    <div>
                        <MacOSInput
                            label="Иконка"
                            placeholder="Иконка (emoji)"
                            value={formData.icon}
                            onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                            style={{
                                gridColumn: '1',
                                borderColor: validationErrors.icon ? 'var(--mac-error)' : undefined
                            }}
                        />
                        {validationErrors.icon && (
                            <div style={{
                                color: 'var(--mac-error)',
                                fontSize: '12px',
                                marginTop: '4px'
                            }}>
                                {validationErrors.icon}
                            </div>
                        )}
                    </div>
                    <div>
                        <MacOSInput
                            label="Цвет"
                            type="color"
                            value={formData.color}
                            onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                            style={{ gridColumn: '2' }}
                        />
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                        <MacOSTextarea
                            label="Описание"
                            placeholder="Описание отделения (опционально)"
                            value={formData.description || ''}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                            rows={4}
                            style={{ borderColor: validationErrors.description ? 'var(--mac-error)' : undefined }}
                        />
                        {validationErrors.description && (
                            <div style={{
                                color: 'var(--mac-error)',
                                fontSize: '12px',
                                marginTop: '4px'
                            }}>
                                {validationErrors.description}
                            </div>
                        )}
                    </div>
                </div>

                <div style={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: '12px',
                    marginTop: '24px',
                    paddingTop: '16px',
                    borderTop: '1px solid var(--mac-border)'
                }}>
                    <MacOSButton
                        variant="secondary"
                        onClick={() => {
                            setShowEditModal(false);
                            setEditingDepartment(null);
                            setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                            clearValidationErrors();
                        }}
                    >
                        Отмена
                    </MacOSButton>
                    <MacOSButton
                        variant="primary"
                        onClick={handleUpdateDepartment}
                    >
                        <Save size={16} style={{ marginRight: '8px' }} />
                        Сохранить изменения
                    </MacOSButton>
                </div>
            </MacOSModal>
=======
                </div>
            </Card>
>>>>>>> origin/main
        </div>
    );
};

export default DepartmentManagement;
