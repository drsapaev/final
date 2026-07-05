/**
 * QueueProfilesManager - Admin component for managing queue tabs
 * 
 * SSOT: Queue profiles are managed in database, frontend reflects changes.
 * Only Admin role can create/update/delete profiles.
 * 
 * Features:
 * - Statistics cards (total, active, inactive)
 * - Search and filter
 * - CSV Export/Import
 * - Bulk operations (delete, activate/deactivate)
 * - CRUD for individual profiles
 */
import PropTypes from 'prop-types';
import { useState, useEffect, useCallback, useMemo } from 'react';
import {
    Plus,
    Edit2,
    Trash2,
    X,
    Eye,
    EyeOff,
    Heart,
    Activity,
    Sparkles,
    Smile,
    TestTube,
    Stethoscope,
    Users,
    Package,
    AlertCircle,
    Check,
    Search,
    Download,
    Upload,
    RefreshCw,
    CheckSquare,
    Square
} from 'lucide-react';
import api from '../../services/api';
import logger from '../../utils/logger';
import {
  Select,
} from '../ui/macos';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

const STATUS_FILTER_OPTIONS = [
    { value: 'all', label: '\u0412\u0441\u0435' },
    { value: 'active', label: '\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0435' },
    { value: 'inactive', label: '\u0421\u043a\u0440\u044b\u0442\u044b\u0435' },
];

// Available icons for selection
const AVAILABLE_ICONS = [
    { name: 'Heart', component: Heart, label: 'Сердце' },
    { name: 'Activity', component: Activity, label: 'ЭКГ' },
    { name: 'Sparkles', component: Sparkles, label: 'Блеск' },
    { name: 'Smile', component: Smile, label: 'Улыбка' },
    { name: 'TestTube', component: TestTube, label: 'Пробирка' },
    { name: 'Stethoscope', component: Stethoscope, label: 'Стетоскоп' },
    { name: 'Users', component: Users, label: 'Люди' },
    { name: 'Package', component: Package, label: 'Пакет' },
];

// Predefined colors
const PRESET_COLORS = [
    'var(--mac-error)', // Red
    'var(--mac-accent-blue)', // Blue
    '#9F7AEA', // Purple
    '#38A169', // Green
    '#DD6B20', // Orange
    '#718096', // Gray
    '#D53F8C', // Pink
    '#4A5568', // Dark gray
];

const QueueProfilesManager = ({ theme = 'light' }) => {
    // P-013 fix: shared ConfirmDialog hook (replaces 2 window.confirm() calls).
    const [confirm, confirmDialog] = useConfirm();
    const [profiles, setProfiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [editingProfile, setEditingProfile] = useState(null);
    const [showCreateForm, setShowCreateForm] = useState(false);

    // ⭐ New: Search and filter
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'active', 'inactive'

    // ⭐ New: Bulk selection
    const [selectedProfiles, setSelectedProfiles] = useState([]);

    const isDark = theme === 'dark';

    // Load profiles from API
    const loadProfiles = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const response = await api.get('/queues/profiles?active_only=false');
            setProfiles(response.data.profiles || []);
            setSelectedProfiles([]); // Clear selection on reload
            logger.info(`Loaded ${response.data.profiles?.length || 0} queue profiles`);
        } catch (err) {
            logger.error('Error loading queue profiles:', err);
            setError('Ошибка загрузки профилей очередей');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadProfiles();
    }, [loadProfiles]);

    // ⭐ New: Filtered profiles
    const filteredProfiles = useMemo(() => {
        return profiles.filter(profile => {
            // Search filter
            const matchesSearch = searchTerm === '' ||
                profile.key?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                profile.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                profile.title_ru?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                (profile.queue_tags || []).some(tag =>
                    tag.toLowerCase().includes(searchTerm.toLowerCase())
                );

            // Status filter
            const matchesStatus = statusFilter === 'all' ||
                (statusFilter === 'active' && profile.is_active !== false) ||
                (statusFilter === 'inactive' && profile.is_active === false);

            return matchesSearch && matchesStatus;
        });
    }, [profiles, searchTerm, statusFilter]);

    // ⭐ New: Statistics
    const stats = useMemo(() => ({
        total: profiles.length,
        active: profiles.filter(p => p.is_active !== false).length,
        inactive: profiles.filter(p => p.is_active === false).length,
        totalTags: profiles.reduce((sum, p) => sum + (p.queue_tags?.length || 0), 0),
    }), [profiles]);

    // Create new profile
    const handleCreate = async (profileData) => {
        try {
            setSaving(true);
            setError(null);
            await api.post('/queues/profiles', profileData);
            await loadProfiles();
            setShowCreateForm(false);
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
        } catch (err) {
            logger.error('Error creating profile:', err);
            setError(err.response?.data?.detail || 'Ошибка создания профиля');
        } finally {
            setSaving(false);
        }
    };

    // Update existing profile
    const handleUpdate = async (profileKey, profileData) => {
        try {
            setSaving(true);
            setError(null);
            await api.put(`/queues/profiles/${profileKey}`, profileData);
            await loadProfiles();
            setEditingProfile(null);
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
        } catch (err) {
            logger.error('Error updating profile:', err);
            setError(err.response?.data?.detail || 'Ошибка обновления профиля');
        } finally {
            setSaving(false);
        }
    };

    // Delete profile
    const handleDelete = async (profileKey) => {
        // P-013 fix: replaced window.confirm() with shared useConfirm hook.
        const ok = await confirm({
            title: 'Удаление вкладки очереди',
            message: `Удалить вкладку «${profileKey}»?`,
            description: 'Это действие необратимо.',
            confirmLabel: 'Удалить',
            cancelLabel: 'Отмена',
            intent: 'danger',
        });
        if (!ok) {
            return;
        }

        try {
            setSaving(true);
            setError(null);
            await api.delete(`/queues/profiles/${profileKey}`);
            await loadProfiles();
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
        } catch (err) {
            logger.error('Error deleting profile:', err);
            setError(err.response?.data?.detail || 'Ошибка удаления профиля');
        } finally {
            setSaving(false);
        }
    };

    // Toggle active status
    const handleToggleActive = async (profile) => {
        await handleUpdate(profile.key, { is_active: !profile.is_active });
    };

    // ⭐ New: Bulk selection handlers
    const handleSelectAll = (checked) => {
        if (checked) {
            setSelectedProfiles(filteredProfiles.map(p => p.key));
        } else {
            setSelectedProfiles([]);
        }
    };

    const handleSelectProfile = (profileKey, checked) => {
        if (checked) {
            setSelectedProfiles(prev => [...prev, profileKey]);
        } else {
            setSelectedProfiles(prev => prev.filter(k => k !== profileKey));
        }
    };

    // ⭐ New: Bulk delete
    const handleBulkDelete = async () => {
        if (selectedProfiles.length === 0) return;

        // P-013 fix: replaced window.confirm() with shared useConfirm hook.
        const ok = await confirm({
            title: 'Массовое удаление вкладок',
            message: `Удалить ${selectedProfiles.length} вкладок?`,
            description: 'Это действие нельзя отменить.',
            confirmLabel: 'Удалить все',
            cancelLabel: 'Отмена',
            intent: 'destructive',
        });
        if (!ok) {
            return;
        }

        try {
            setSaving(true);
            setError(null);

            for (const key of selectedProfiles) {
                await api.delete(`/queues/profiles/${key}`);
            }

            await loadProfiles();
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
        } catch (err) {
            logger.error('Error bulk deleting profiles:', err);
            setError(err.response?.data?.detail || 'Ошибка массового удаления');
        } finally {
            setSaving(false);
        }
    };

    // ⭐ New: Bulk activate/deactivate
    const handleBulkActivate = async (activate) => {
        if (selectedProfiles.length === 0) return;

        try {
            setSaving(true);
            setError(null);

            for (const key of selectedProfiles) {
                await api.put(`/queues/profiles/${key}`, { is_active: activate });
            }

            await loadProfiles();
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
        } catch (err) {
            logger.error('Error bulk updating profiles:', err);
            setError(err.response?.data?.detail || 'Ошибка массового обновления');
        } finally {
            setSaving(false);
        }
    };

    // ⭐ New: Export to CSV
    const handleExport = () => {
        try {
            const headers = ['key', 'title', 'title_ru', 'queue_tags', 'icon', 'color', 'display_order', 'is_active'];
            const csvContent = [
                headers.join(','),
                ...profiles.map(p => [
                    `"${(p.key || '').replace(/"/g, '""')}"`,
                    `"${(p.title || '').replace(/"/g, '""')}"`,
                    `"${(p.title_ru || '').replace(/"/g, '""')}"`,
                    `"${(p.queue_tags || []).join(';').replace(/"/g, '""')}"`,
                    `"${(p.icon || '').replace(/"/g, '""')}"`,
                    `"${(p.color || '').replace(/"/g, '""')}"`,
                    p.order || 0,
                    p.is_active !== false ? 'true' : 'false'
                ].join(','))
            ].join('\n');

            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `queue_profiles_${new Date().toISOString().split('T')[0]}.csv`;
            link.click();

            logger.info('Exported queue profiles to CSV');
        } catch (err) {
            logger.error('Error exporting profiles:', err);
            setError('Ошибка экспорта');
        }
    };

    // ⭐ New: Import from CSV
    const handleImport = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;

        try {
            const text = await file.text();
            const lines = text.split('\n').filter(line => line.trim());

            if (lines.length < 2) {
                setError('CSV файл должен содержать заголовки и данные');
                return;
            }

            const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim());
            const importedProfiles = [];

            for (let i = 1; i < lines.length; i++) {
                const values = lines[i].split(',').map(v => v.replace(/^"|"$/g, '').replace(/""/g, '"'));
                const profile = {};

                headers.forEach((header, index) => {
                    const value = values[index];
                    switch (header) {
                        case 'queue_tags':
                            profile[header] = value ? value.split(';').filter(Boolean) : [];
                            break;
                        case 'display_order':
                            profile[header] = parseInt(value) || 0;
                            break;
                        case 'is_active':
                            profile[header] = value !== 'false';
                            break;
                        default:
                            profile[header] = value || '';
                    }
                });

                if (profile.key && profile.title) {
                    importedProfiles.push(profile);
                }
            }

            if (importedProfiles.length === 0) {
                setError('Нет валидных профилей для импорта');
                return;
            }

            setSaving(true);
            let imported = 0;
            let updated = 0;

            for (const profile of importedProfiles) {
                try {
                    const existing = profiles.find(p => p.key === profile.key);
                    if (existing) {
                        await api.put(`/queues/profiles/${profile.key}`, profile);
                        updated++;
                    } else {
                        await api.post('/queues/profiles', profile);
                        imported++;
                    }
                } catch (err) {
                    logger.error(`Error importing profile ${profile.key}:`, err);
                }
            }

            await loadProfiles();
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
            setError(null);
            alert(`Импорт завершён: ${imported} создано, ${updated} обновлено`);

        } catch (err) {
            logger.error('Error importing profiles:', err);
            setError('Ошибка импорта CSV');
        } finally {
            setSaving(false);
            event.target.value = '';
        }
    };
    if (loading) {
        return (
            <div className="admin-qp-container">
                <div className="admin-p-24-radius-12-bd-1px-solid-var-mac-bo-ta-center-p-40-bgc-dyn" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}>
                    <RefreshCw size={24} className="admin-anim-spin-1s-linear-infin" />
                    <p className="admin-secondary-mt-12">
                        Загрузка профилей...
                    </p>
                </div>
            </div>
        );
    }

    const isAllSelected = filteredProfiles.length > 0 &&
        filteredProfiles.every(p => selectedProfiles.includes(p.key));

    return (
        <div className="admin-qp-container">
            {/* Statistics Cards */}
            <div className="admin-qp-stats-grid">
                <div className="admin-qp-stat-card" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}>
                    <div className="admin-qp-stat-value">{stats.total}</div>
                    <div className="admin-qp-stat-label">Всего вкладок</div>
                </div>
                <div className="admin-p-16-radius-12-bd-1px-solid-var-mac-bo-ta-center-bgc-dyn" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}>
                    <div className="admin-fs-28-fw-bold-primary-mb-4-var-mac-success-10B9">{stats.active}</div>
                    <div className="admin-qp-stat-label">Активных</div>
                </div>
                <div className="admin-qp-stat-card" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}>
                    <div className="admin-fs-28-fw-bold-primary-mb-4-var-mac-warning-F59E">{stats.inactive}</div>
                    <div className="admin-qp-stat-label">Скрытых</div>
                </div>
                <div className="admin-qp-stat-card" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}>
                    <div className="admin-fs-28-fw-bold-primary-mb-4-var-mac-info-3B82F6">{stats.totalTags}</div>
                    <div className="admin-qp-stat-label">Queue Tags</div>
                </div>
            </div>

            {/* Main Card */}
            <div className="admin-qp-main-card" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}>
                {/* Header */}
                <div className="admin-qp-header">
                    <h2 className="admin-qp-title">Вкладки регистратуры</h2>
                    <div className="admin-qp-toolbar">
                        {/* Search */}
                        <div className="admin-qp-search-wrapper">
                            <Search size={16} className="admin-qp-search-icon" />
                            <input
                                className="admin-qp-search-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-secondary)' }}
                                aria-label="Поиск профилей очереди"
                                placeholder="Поиск..."
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                            />
                        </div>

                        {/* Status filter */}
                        <Select
                            value={statusFilter}
                            onChange={setStatusFilter}
                            options={STATUS_FILTER_OPTIONS}
                            size="large"
                            className="admin-w-160"/>

                        {/* Export */}
                        <button className="admin-qp-button" onClick={handleExport} disabled={saving}>
                            <Download size={16} />
                            Экспорт
                        </button>

                        {/* Import */}
                        <label className="admin-d-flex-ai-center-gap-6-p-8px-14px-bd-1px-solid-var-mac-bo-radius-8-bgc-transparent-primary-cur-pointer-fs-13-fw-500-cur-pointer">
                            <Upload size={16} />
                            Импорт
                            <input
                                type="file"
                                aria-label="Импортировать профили очереди из CSV"
                                accept=".csv"
                                onChange={handleImport}
                                className="admin-d-none"
                                disabled={saving}
                            />
                        </label>

                        {/* Refresh */}
                        <button
                            className="admin-qp-button"
                            onClick={loadProfiles}
                            disabled={saving}
                            aria-label="Обновить профили очереди"
                        >
                            <RefreshCw size={16} />
                        </button>

                        {/* Add */}
                        <button
                            className="admin-qp-primary-button"
                            onClick={() => setShowCreateForm(true)}
                            disabled={saving}
                        >
                            <Plus size={16} />
                            Добавить
                        </button>
                    </div>
                </div>

                {/* Error message */}
                {error && (
                    <div className="admin-qp-error">
                        <AlertCircle size={16} />
                        {error}
                        <button
                            className="admin-ml-auto-bg-none-bd-none-cur-pointer"
                            onClick={() => setError(null)}
                            aria-label="Скрыть сообщение об ошибке"
                        >
                            <X size={16} />
                        </button>
                    </div>
                )}

                {/* Bulk actions bar */}
                {selectedProfiles.length > 0 && (
                    <div className="admin-qp-bulk-actions">
                        <span className="admin-fs-14-primary">
                            Выбрано: {selectedProfiles.length}
                        </span>
                        <button
                            className="admin-d-flex-ai-center-gap-6-p-8px-14px-bd-1px-solid-var-mac-bo-radius-8-bgc-transparent-primary-cur-pointer-fs-13-fw-500-ml-auto"
                            onClick={() => handleBulkActivate(true)}
                            disabled={saving}
                        >
                            <Eye size={16} />
                            Активировать
                        </button>
                        <button
                            className="admin-qp-button"
                            onClick={() => handleBulkActivate(false)}
                            disabled={saving}
                        >
                            <EyeOff size={16} />
                            Скрыть
                        </button>
                        <button
                            className="admin-qp-danger-button"
                            onClick={handleBulkDelete}
                            disabled={saving}
                        >
                            <Trash2 size={16} />
                            Удалить
                        </button>
                    </div>
                )}

                {/* Create form */}
                {showCreateForm && (
                    <ProfileForm
                        onSubmit={handleCreate}
                        onCancel={() => setShowCreateForm(false)}
                        saving={saving}
                        isDark={isDark}
                    />
                )}

                {/* Profiles table */}
                <div className="admin-table-wrapper">
            <table className="admin-qp-table">
                    <thead>
                        <tr>
                            <th className="admin-ta-left-p-12px-8px-bd-b-2px-solid-var-mac-bo-fs-12-fw-600-secondary-tt-uppercase-w-40">
                                <button
                                    className="admin-qp-icon-button"
                                    onClick={() => handleSelectAll(!isAllSelected)}
                                    aria-label={isAllSelected ? 'Снять выбор со всех вкладок очереди' : 'Выбрать все вкладки очереди'}
                                >
                                    {isAllSelected ? <CheckSquare size={18} /> : <Square size={18} />}
                                </button>
                            </th>
                            <th className="admin-qp-th">Порядок</th>
                            <th className="admin-qp-th">Ключ</th>
                            <th className="admin-qp-th">Название</th>
                            <th className="admin-qp-th">Queue Tags</th>
                            <th className="admin-qp-th">Иконка</th>
                            <th className="admin-qp-th">Цвет</th>
                            <th className="admin-qp-th">Статус</th>
                            <th className="admin-qp-th">Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredProfiles.map((profile) => (
                            <tr key={profile.key}>
                                <td className="admin-qp-td">
                                    <button
                                        className="admin-qp-icon-button"
                                        onClick={() => handleSelectProfile(
                                            profile.key,
                                            !selectedProfiles.includes(profile.key)
                                        )}
                                        aria-label={selectedProfiles.includes(profile.key) ? `Снять выбор вкладки ${profile.name}` : `Выбрать вкладку ${profile.name}`}
                                    >
                                        {selectedProfiles.includes(profile.key)
                                            ? <CheckSquare size={18} className="admin-blue" />
                                            : <Square size={18} />
                                        }
                                    </button>
                                </td>
                                <td className="admin-qp-td">
                                    <span className="text-[var(--mac-text-secondary)]">
                                        {profile.order}
                                    </span>
                                </td>
                                <td className="admin-qp-td">
                                    <code className="admin-bgc-bg-tertiary-p-2px-6px-radius-4-fs-12">
                                        {profile.key}
                                    </code>
                                </td>
                                <td className="admin-qp-td">
                                    <div>{profile.title_ru || profile.title}</div>
                                    {profile.title_ru && (
                                        <div className="admin-fs-12-secondary">
                                            {profile.title}
                                        </div>
                                    )}
                                </td>
                                <td className="admin-qp-td">
                                    <div className="admin-d-flex-fw-wrap-gap-4">
                                        {(profile.queue_tags || []).map((tag, idx) => (
                                            <span
                                                key={idx}
                                                className="admin-d-inline-flex-ai-center-gap-4-p-2px-8px-radius-12-fs-11-fw-500-bgc-rgba-59-130-246-0-1-3B82F6"
                                            >
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                </td>
                                <td className="admin-qp-td">
                                    {(() => {
                                        const IconComponent = AVAILABLE_ICONS.find(i => i.name === profile.icon)?.component || Package;
                                        return <IconComponent size={20} className="admin-col-dyn" style={{ '--admin-col0': profile.color || 'var(--mac-text-secondary)' }} />;
                                    })()}
                                </td>
                                <td className="admin-qp-td">
                                    <div
                                        role="img"
                                        aria-label={`Цвет вкладки ${profile.name}: ${profile.color || 'не задан'}`}
                                        className="admin-w-16-h-16-radius-50pct-bd-2px-solid-var-mac-bo-bgc-dyn" style={{ '--admin-bgc0': profile.color || '#718096' }}
                                        title={profile.color}
                                    />
                                </td>
                                <td className="admin-qp-td">
                                    <span
                                        className="admin-d-inline-flex-ai-center-gap-4-p-2px-8px-radius-12-fs-11-fw-500-bgc-dyn-col-dyn" style={{ '--admin-bgc0': profile.is_active !== false
                                                ? 'rgba(16, 185, 129, 0.1)'
                                                : 'var(--mac-error-bg)', '--admin-col1': profile.is_active !== false ? 'var(--mac-success)' : 'var(--mac-error)' }}
                                    >
                                        {profile.is_active !== false ? 'Активен' : 'Скрыт'}
                                    </span>
                                </td>
                                <td className="admin-qp-td">
                                    <div className="admin-d-flex-gap-4">
                                        <button
                                            className="admin-qp-icon-button"
                                            onClick={() => handleToggleActive(profile)}
                                            aria-label={profile.is_active !== false ? `Скрыть вкладку ${profile.name}` : `Показать вкладку ${profile.name}`}
                                            title={profile.is_active !== false ? 'Скрыть' : 'Показать'}
                                            disabled={saving}
                                        >
                                            {profile.is_active !== false ? <EyeOff size={16} /> : <Eye size={16} />}
                                        </button>
                                        <button
                                            className="admin-qp-icon-button"
                                            onClick={() => setEditingProfile(profile)}
                                            aria-label={`Редактировать вкладку ${profile.name}`}
                                            title="Редактировать"
                                            disabled={saving}
                                        >
                                            <Edit2 size={16} />
                                        </button>
                                        <button
                                            className="admin-p-6-bd-none-radius-6-bgc-transparent-cur-pointer-secondary-d-inline-flex-ai-center-jc-center-EF4444"
                                            onClick={() => handleDelete(profile.key)}
                                            aria-label={`Удалить вкладку ${profile.name}`}
                                            title="Удалить"
                                            disabled={saving}
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
          </div>

                {filteredProfiles.length === 0 && (
                    <div className="admin-ta-center-p-40-secondary">
                        {profiles.length === 0
                            ? 'Нет профилей. Нажмите "Добавить" для создания.'
                            : 'Нет профилей, соответствующих фильтрам.'
                        }
                    </div>
                )}

                {/* Edit modal */}
                {editingProfile && (
                    <ProfileForm
                        profile={editingProfile}
                        onSubmit={(data) => handleUpdate(editingProfile.key, data)}
                        onCancel={() => setEditingProfile(null)}
                        saving={saving}
                        isDark={isDark}
                        isEdit
                    />
                )}
                {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
                {confirmDialog}
            </div>
        </div>
    );
};
// Profile form component with show_on_qr_page support
const ProfileForm = ({ profile, onSubmit, onCancel, saving, isDark, isEdit = false }) => {
    const [formData, setFormData] = useState({
        key: profile?.key || '',
        title: profile?.title || '',
        title_ru: profile?.title_ru || '',
        queue_tags: (profile?.queue_tags || []).join(', '),
        department_key: profile?.department_key || '',
        display_order: profile?.order || 0,
        is_active: profile?.is_active !== false,
        show_on_qr_page: profile?.show_on_qr_page !== false, // ⭐ NEW: QR page visibility
        icon: profile?.icon || 'Package',
        color: profile?.color || '#718096',
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit({
            ...formData,
            queue_tags: formData.queue_tags.split(',').map(t => t.trim()).filter(Boolean),
            display_order: parseInt(formData.display_order, 10) || 0,
        });
    };
    const handleActivationKeyDown = (event, action) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            action();
        }
    };

    return (
        <div
            className="admin-qp-overlay"
            role="button"
            tabIndex={0}
            aria-label="Закрыть форму вкладки очереди"
            onClick={onCancel}
            onKeyDown={(event) => handleActivationKeyDown(event, onCancel)}>
            <div className="admin-qp-modal" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-primary)' : 'white' }} onClickCapture={e => e.stopPropagation()}>
                <div className="admin-qp-modal-header">
                    <h3 className="admin-qp-modal-title">
                        {isEdit ? 'Редактирование вкладки' : 'Новая вкладка'}
                    </h3>
                    <button
                        className="admin-qp-close-button"
                        onClick={onCancel}
                        aria-label="Закрыть форму вкладки очереди"
                    >
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    {/* Key (only for create) */}
                    {!isEdit && (
                        <div className="admin-qp-field">
                            <label className="admin-qp-label">Уникальный ключ *</label>
                            <input
                                className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}
                                aria-label="Уникальный ключ вкладки очереди"
                                value={formData.key}
                                onChange={e => setFormData({ ...formData, key: e.target.value })}
                                placeholder="например: cardiology"
                                required
                                pattern="[a-z_]+"
                            />
                            <div className="admin-qp-hint">Только латинские буквы и подчеркивания</div>
                        </div>
                    )}

                    {/* Titles */}
                    <div className="admin-qp-row">
                        <div className="admin-mb-16-flex-1-1">
                            <label className="admin-qp-label">Название (EN) *</label>
                            <input
                                className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}
                                aria-label="Название вкладки очереди на английском"
                                value={formData.title}
                                onChange={e => setFormData({ ...formData, title: e.target.value })}
                                placeholder="Cardiology"
                                required
                            />
                        </div>
                        <div className="admin-mb-16-flex-1">
                            <label className="admin-qp-label">Название (RU)</label>
                            <input
                                className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}
                                aria-label="Название вкладки очереди на русском"
                                value={formData.title_ru}
                                onChange={e => setFormData({ ...formData, title_ru: e.target.value })}
                                placeholder="Кардиология"
                            />
                        </div>
                    </div>

                    {/* Queue Tags */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label">Queue Tags</label>
                        <input
                            className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}
                            aria-label="Queue Tags"
                            value={formData.queue_tags}
                            onChange={e => setFormData({ ...formData, queue_tags: e.target.value })}
                            placeholder="cardio, cardiology, cardiology_common"
                        />
                        <div className="admin-qp-hint">Разделяйте запятыми. Записи с этими тегами появятся на вкладке.</div>
                    </div>

                    {/* Order */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label">Порядок отображения</label>
                        <input
                            className="admin-w-100pct-p-10px-12px-radius-8-bd-1px-solid-var-mac-bo-primary-fs-14-bsz-border-box-w-100-bgc-dyn" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' }}
                            type="number"
                            aria-label="Порядок отображения вкладки очереди"
                            min="0"
                            value={formData.display_order}
                            onChange={e => setFormData({ ...formData, display_order: e.target.value })}
                        />
                    </div>

                    {/* Icon */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label">Иконка</label>
                        <div className="admin-qp-icon-grid">
                            {AVAILABLE_ICONS.map(icon => {
                                const IconComponent = icon.component;
                                const isSelected = formData.icon === icon.name;
                                return (
                                    <button
                                        key={icon.name}
                                        type="button"
                                        className="admin-p-12-bd-2px-solid-var-mac-bo-radius-8-bgc-transparent-cur-pointer-d-flex-fd-column-ai-center-gap-4-tr-all-0-2s-bd-c-dyn-bgc-dyn" style={{ '--admin-bd-c0': isSelected ? 'var(--mac-accent-blue)' : 'var(--mac-border)', '--admin-bgc1': isSelected ? 'var(--mac-accent-bg)' : 'transparent' }}
                                        onClick={() => setFormData({ ...formData, icon: icon.name })}
                                    >
                                        <IconComponent size={24} className="admin-col-dyn" style={{ '--admin-col0': formData.color }} />
                                        <span className="admin-fs-10-secondary">
                                            {icon.label}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Color */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label">Цвет</label>
                        <div className="admin-qp-color-grid">
                            {PRESET_COLORS.map(color => (
                                <button
                                    key={color}
                                    type="button"
                                    className="admin-w-32-h-32-radius-50pct-bd-3px-solid-transparen-cur-pointer-tr-all-0-2s-bgc-dyn-bd-c-dyn-bsh-dyn" style={{ '--admin-bgc0': color, '--admin-bd-c1': formData.color === color ? 'white' : 'transparent', '--admin-bsh2': formData.color === color ? `0 0 0 2px ${color}` : 'none' }}
                                    onClick={() => setFormData({ ...formData, color })}
                                    aria-label={`Выбрать цвет ${color}`}
                                    title={color}
                                />
                            ))}
                            <input
                                type="color"
                                aria-label="Пользовательский цвет вкладки очереди"
                                value={formData.color}
                                onChange={e => setFormData({ ...formData, color: e.target.value })}
                                className="admin-w-32-h-32-bd-none-cur-pointer"
                            />
                        </div>
                    </div>

                    {/* Active */}
                    <div className="admin-qp-field">
                        <label className="admin-d-flex-ai-center-gap-8-cur-pointer">
                            <input
                                type="checkbox"
                                aria-label="Активная вкладка очереди"
                                checked={formData.is_active}
                                onChange={e => setFormData({ ...formData, is_active: e.target.checked })}
                            />
                            <span className="admin-qp-label">Активная вкладка (видна пользователям)</span>
                        </label>
                    </div>

                    {/* ⭐ NEW: Show on QR Page */}
                    <div className="admin-qp-field">
                        <label className="admin-d-flex-ai-center-gap-8-cur-pointer">
                            <input
                                type="checkbox"
                                aria-label="Показывать вкладку на QR-странице"
                                checked={formData.show_on_qr_page}
                                onChange={e => setFormData({ ...formData, show_on_qr_page: e.target.checked })}
                            />
                            <span className="admin-qp-label">Показывать на QR-странице (самозапись пациентов)</span>
                        </label>
                        <div className="admin-fs-12-secondary-mt-4-ml-24">
                            Если включено, пациенты смогут выбрать эту специальность при сканировании QR-кода
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="admin-qp-actions">
                        <button type="button" className="admin-qp-cancel-button" onClick={onCancel}>
                            Отмена
                        </button>
                        <button
                            type="submit"
                            className="admin-qp-submit-button"
                            disabled={saving}
                            aria-label={isEdit ? 'Сохранить вкладку очереди' : 'Создать вкладку очереди'}
                        >
                            {saving ? (
                                <>Сохранение...</>
                            ) : (
                                <>
                                    <Check size={16} />
                                    {isEdit ? 'Сохранить' : 'Создать'}
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

const queueProfileShape = PropTypes.shape({
    key: PropTypes.string,
    title: PropTypes.string,
    title_ru: PropTypes.string,
    queue_tags: PropTypes.oneOfType([
        PropTypes.arrayOf(PropTypes.string),
        PropTypes.string
    ]),
    department_key: PropTypes.string,
    order: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    display_order: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    is_active: PropTypes.bool,
    show_on_qr_page: PropTypes.bool,
    icon: PropTypes.string,
    color: PropTypes.string
});

QueueProfilesManager.propTypes = {
    theme: PropTypes.oneOf(['light', 'dark'])
};

ProfileForm.propTypes = {
    profile: queueProfileShape,
    onSubmit: PropTypes.func,
    onCancel: PropTypes.func,
    saving: PropTypes.bool,
    isDark: PropTypes.bool,
    isEdit: PropTypes.bool
};

export default QueueProfilesManager;
