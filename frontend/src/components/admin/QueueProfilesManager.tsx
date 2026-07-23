import { useTranslation } from '../../i18n/useTranslation';
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
import type { CSSProperties } from "react";
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
  Input,
  Checkbox } from '../ui/macos';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
import { notify } from '../../services/notify';

const getStatusFilterOptions = (t) => [
    { value: 'all', label: t('admin2.qp_filter_all') },
    { value: 'active', label: t('admin2.qp_filter_active') },
    { value: 'inactive', label: t('admin2.qp_filter_hidden') },
];

// Available icons for selection
const getAvailableIcons = (t) => [
    { name: 'Heart', component: Heart, label: t('admin2.qp_icon_heart') },
    { name: 'Activity', component: Activity, label: t('admin2.qp_icon_activity') },
    { name: 'Sparkles', component: Sparkles, label: t('admin2.qp_icon_sparkles') },
    { name: 'Smile', component: Smile, label: t('admin2.qp_icon_smile') },
    { name: 'TestTube', component: TestTube, label: t('admin2.qp_icon_test_tube') },
    { name: 'Stethoscope', component: Stethoscope, label: t('admin2.qp_icon_stethoscope') },
    { name: 'Users', component: Users, label: t('admin2.qp_icon_users') },
    { name: 'Package', component: Package, label: t('admin2.qp_icon_package') },
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
    'var(--mac-text-secondary)', // Dark gray
];

const QueueProfilesManager = ({ theme = 'light' }) => {
    const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
    const statusFilterOptions = getStatusFilterOptions(t);
    const availableIcons = getAvailableIcons(t);
    // P-013 fix: shared ConfirmDialog hook (replaces 2 window.confirm() calls).
    const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
    const [profiles, setProfiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [editingProfile, setEditingProfile] = useState(null);
    const [showCreateForm, setShowCreateForm] = useState(false);
    // PR-21: load departments for department_key Select in ProfileForm
    const [departments, setDepartments] = useState([]);

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
            const response = (await api.get('/queues/profiles?active_only=false')) as import('axios').AxiosResponse<Record<string, unknown>>;
            setProfiles((response.data.profiles as unknown[]) || []);
            setSelectedProfiles([]); // Clear selection on reload
            logger.info(`Loaded ${(response.data?.profiles as unknown[])?.length || 0} queue profiles`);
        } catch (err) {
            logger.error('Error loading queue profiles:', err);
            setError(t('admin2.qp_load_failed'));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadProfiles();
        // PR-21: load departments for department_key Select
        api.get('/admin/departments').then((res: import('axios').AxiosResponse<Record<string, unknown>>) => {
            setDepartments((res.data?.data as unknown[]) || []);
        }).catch(err => logger.error('Failed to load departments:', err));
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
            setError(err.response?.data?.detail || t('admin2.qp_create_error'));
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
            setError(err.response?.data?.detail || t('admin2.qp_update_error'));
        } finally {
            setSaving(false);
        }
    };

    // Delete profile
    const handleDelete = async (profileKey) => {
        // P-013 fix: replaced window.confirm() with shared useConfirm hook.
        const ok = await confirm({
            title: t('admin2.delete_queue_tab_title'),
            message: t('admin2.qp_delete_confirm_msg', { key: profileKey }),
            description: t('admin2.qp_delete_confirm_desc'),
            confirmLabel: t('admin2.delete_confirm'),
            cancelLabel: t('admin2.cancel'),
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
            setError(err.response?.data?.detail || t('admin2.qp_delete_error'));
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
            title: t('admin2.bulk_delete_queue_tabs_title'),
            message: t('admin2.qp_bulk_delete_confirm_msg', { count: selectedProfiles.length }),
            description: t('admin2.qp_bulk_delete_confirm_desc'),
            confirmLabel: t('admin2.delete_all_confirm'),
            cancelLabel: t('admin2.cancel'),
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
            setError(err.response?.data?.detail || t('admin2.qp_bulk_delete_error'));
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
            setError(err.response?.data?.detail || t('admin2.qp_bulk_update_error'));
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
            setError(t('admin2.qp_export_error'));
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
                setError(t('admin2.qp_import_csv_invalid'));
                return;
            }

            const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim());
            const importedProfiles = [];

            for (let i = 1; i < lines.length; i++) {
                const values = lines[i].split(',').map(v => v.replace(/^"|"$/g, '').replace(/""/g, '"'));
                const profile: Record<string, unknown> = {};

                headers.forEach((header: unknown, index: number) => {
                    const value = values[index];
                    switch (header) {
                        case 'queue_tags':
                            profile[header as string] = value ? value.split(';').filter(Boolean) : [];
                            break;
                        case 'display_order':
                            profile[header as string] = parseInt(value) || 0;
                            break;
                        case 'is_active':
                            profile[header as string] = value !== 'false';
                            break;
                        default:
                            profile[header as string] = value || '';
                    }
                });

                if (profile.key && profile.title) {
                    importedProfiles.push(profile);
                }
            }

            if (importedProfiles.length === 0) {
                setError(t('admin2.qp_import_no_valid'));
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
            notify.success(t('admin2.qp_import_success', { imported, updated }));

        } catch (err) {
            logger.error('Error importing profiles:', err);
            setError(t('admin2.qp_import_error'));
        } finally {
            setSaving(false);
            event.target.value = '';
        }
    };
    if (loading) {
        return (
            <div className="admin-qp-container">
                <div className="admin-p-24-radius-12-bd-1px-solid-var-mac-bo-ta-center-p-40-bgc-dyn" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}>
                    <RefreshCw size={24} className="admin-anim-spin-1s-linear-infin" />
                    <p className="admin-secondary-mt-12">
                        {t('admin2.qp_loading')}
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
                <div className="admin-qp-stat-card" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}>
                    <div className="admin-qp-stat-value">{stats.total}</div>
                    <div className="admin-qp-stat-label">{t('admin2.qp_stat_total')}</div>
                </div>
                <div className="admin-p-16-radius-12-bd-1px-solid-var-mac-bo-ta-center-bgc-dyn" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}>
                    <div className="admin-fs-28-fw-bold-primary-mb-4-var-mac-success-10B9">{stats.active}</div>
                    <div className="admin-qp-stat-label">{t('admin2.qp_stat_active')}</div>
                </div>
                <div className="admin-qp-stat-card" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}>
                    <div className="admin-fs-28-fw-bold-primary-mb-4-var-mac-warning-F59E">{stats.inactive}</div>
                    <div className="admin-qp-stat-label">{t('admin2.qp_stat_hidden')}</div>
                </div>
                <div className="admin-qp-stat-card" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}>
                    <div className="admin-fs-28-fw-bold-primary-mb-4-var-mac-info-3B82F6">{stats.totalTags}</div>
                    <div className="admin-qp-stat-label">Queue Tags</div>
                </div>
            </div>

            {/* Main Card */}
            <div className="admin-qp-main-card" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}>
                {/* Header */}
                <div className="admin-qp-header">
                    <h2 className="admin-qp-title">{t('admin2.qp_page_title')}</h2>
                    <div className="admin-qp-toolbar">
                        {/* Search */}
                        <div className="admin-qp-search-wrapper">
                            <Search size={16} className="admin-qp-search-icon" />
                            <Input
                                className="admin-qp-search-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-secondary)' } as CSSProperties}
                                aria-label={t('admin2.qp_search_aria')}
                                placeholder={t('admin2.qp_search_placeholder')}
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                            />
                        </div>

                        {/* Status filter */}
                        <Select
                            value={statusFilter}
                            onChange={(v: unknown) => setStatusFilter(String(v))}
                            options={statusFilterOptions}
                            size="large"
                            className="admin-w-160"/>

                        {/* Export */}
                        <button className="admin-qp-button" onClick={handleExport} disabled={saving}>
                            <Download size={16} />
                            {t('admin2.qp_export_btn')}
                        </button>

                        {/* Import */}
                        <label className="admin-d-flex-ai-center-gap-6-p-8px-14px-bd-1px-solid-var-mac-bo-radius-8-bgc-transparent-primary-cur-pointer-fs-13-fw-500-cur-pointer">
                            <Upload size={16} />
                            {t('admin2.qp_import_btn')}
                            <input
                                type="file"
                                aria-label={t('admin2.qp_import_aria')}
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
                            aria-label={t('admin2.qp_refresh_aria')}
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
                            {t('admin2.qp_add_btn')}
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
                            aria-label={t('admin2.qp_hide_error_aria')}
                        >
                            <X size={16} />
                        </button>
                    </div>
                )}

                {/* Bulk actions bar */}
                {selectedProfiles.length > 0 && (
                    <div className="admin-qp-bulk-actions">
                        <span className="admin-fs-14-primary">
                            {t('admin2.qp_selected_count', { count: selectedProfiles.length })}
                        </span>
                        <button
                            className="admin-d-flex-ai-center-gap-6-p-8px-14px-bd-1px-solid-var-mac-bo-radius-8-bgc-transparent-primary-cur-pointer-fs-13-fw-500-ml-auto"
                            onClick={() => handleBulkActivate(true)}
                            disabled={saving}
                        >
                            <Eye size={16} />
                            {t('admin2.qp_bulk_activate_btn')}
                        </button>
                        <button
                            className="admin-qp-button"
                            onClick={() => handleBulkActivate(false)}
                            disabled={saving}
                        >
                            <EyeOff size={16} />
                            {t('admin2.qp_hide_btn')}
                        </button>
                        <button
                            className="admin-qp-danger-button"
                            onClick={handleBulkDelete}
                            disabled={saving}
                        >
                            <Trash2 size={16} />
                            {t('admin2.qp_delete_btn')}
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
                        departments={departments}
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
                                    aria-label={isAllSelected ? t('admin2.qp_deselect_all_aria') : t('admin2.qp_select_all_aria')}
                                >
                                    {isAllSelected ? <CheckSquare size={18} /> : <Square size={18} />}
                                </button>
                            </th>
                            <th className="admin-qp-th">{t('admin2.qp_col_order')}</th>
                            <th className="admin-qp-th">{t('admin2.qp_col_key')}</th>
                            <th className="admin-qp-th">{t('admin2.qp_col_title')}</th>
                            <th className="admin-qp-th">Queue Tags</th>
                            <th className="admin-qp-th">{t('admin2.qp_col_icon')}</th>
                            <th className="admin-qp-th">{t('admin2.qp_col_color')}</th>
                            <th className="admin-qp-th">{t('admin2.qp_col_status')}</th>
                            <th className="admin-qp-th">{t('admin2.qp_col_actions')}</th>
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
                                        aria-label={selectedProfiles.includes(profile.key) ? t('admin2.qp_deselect_row_aria', { name: profile.name }) : t('admin2.qp_select_row_aria', { name: profile.name })}
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
                                        const IconComponent = availableIcons.find(i => i.name === profile.icon)?.component || Package;
                                        return <IconComponent size={20} className="admin-col-dyn" style={{ '--admin-col0': profile.color || 'var(--mac-text-secondary)' } as CSSProperties} />;
                                    })()}
                                </td>
                                <td className="admin-qp-td">
                                    <div
                                        role="img"
                                        aria-label={t('admin2.qp_color_aria', { name: profile.name, color: profile.color || t('admin2.qp_color_not_set') })}
                                        className="admin-w-16-h-16-radius-50pct-bd-2px-solid-var-mac-bo-bgc-dyn" style={{ '--admin-bgc0': profile.color || '#718096' } as CSSProperties}
                                        title={profile.color}
                                    />
                                </td>
                                <td className="admin-qp-td">
                                    <span
                                        className="admin-d-inline-flex-ai-center-gap-4-p-2px-8px-radius-12-fs-11-fw-500-bgc-dyn-col-dyn" style={{ '--admin-bgc0': profile.is_active !== false
                                                ? 'rgba(16, 185, 129, 0.1)'
                                                : 'var(--mac-error-bg)', '--admin-col1': profile.is_active !== false ? 'var(--mac-success)' : 'var(--mac-error)' } as CSSProperties}
                                    >
                                        {profile.is_active !== false ? t('admin2.qp_status_active') : t('admin2.qp_status_hidden')}
                                    </span>
                                </td>
                                <td className="admin-qp-td">
                                    <div className="admin-d-flex-gap-4">
                                        <button
                                            className="admin-qp-icon-button"
                                            onClick={() => handleToggleActive(profile)}
                                            aria-label={profile.is_active !== false ? t('admin2.qp_hide_row_aria', { name: profile.name }) : t('admin2.qp_show_row_aria', { name: profile.name })}
                                            title={profile.is_active !== false ? t('admin2.qp_hide_btn') : t('admin2.qp_show_btn')}
                                            disabled={saving}
                                        >
                                            {profile.is_active !== false ? <EyeOff size={16} /> : <Eye size={16} />}
                                        </button>
                                        <button
                                            className="admin-qp-icon-button"
                                            onClick={() => setEditingProfile(profile)}
                                            aria-label={t('admin2.qp_edit_row_aria', { name: profile.name })}
                                            title={t('admin2.qp_edit_btn')}
                                            disabled={saving}
                                        >
                                            <Edit2 size={16} />
                                        </button>
                                        <button
                                            className="admin-p-6-bd-none-radius-6-bgc-transparent-cur-pointer-secondary-d-inline-flex-ai-center-jc-center-EF4444"
                                            onClick={() => handleDelete(profile.key)}
                                            aria-label={t('admin2.qp_delete_row_aria', { name: profile.name })}
                                            title={t('admin2.qp_delete_btn')}
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
                            ? t('admin2.qp_empty_state')
                            : t('admin2.qp_empty_filtered')
                        }
                    </div>
                )}

                {/* Edit modal */}
                {editingProfile && (
                    <ProfileForm
                        profile={editingProfile}
                        onSubmit={(data: React.FormEvent<HTMLFormElement>) => handleUpdate(editingProfile.key, data)}
                        onCancel={() => setEditingProfile(null)}
                        saving={saving}
                        isDark={isDark}
                        isEdit
                        departments={departments}
                    />
                )}
                {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
                {confirmDialog as unknown as React.ReactNode}
            </div>
        </div>
    );
};
// Profile form component with show_on_qr_page support
const ProfileForm = ({ profile, onSubmit, onCancel, saving, isDark, isEdit = false, departments = [] }: { profile?: Record<string, unknown>; onSubmit?: (data: unknown) => void; onCancel?: () => void; saving?: boolean; isDark?: boolean; isEdit?: boolean; departments?: unknown[] }) => {
    const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
    const availableIcons = getAvailableIcons(t);
    const [formData, setFormData] = useState<Record<string, unknown>>({
        key: profile?.key || '',
        title: profile?.title || '',
        title_ru: profile?.title_ru || '',
        queue_tags: ((profile?.queue_tags as unknown[]) || []).join(', '),
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
            queue_tags: String(formData.queue_tags || '').split(',').map(t => t.trim()).filter(Boolean),
            display_order: parseInt(String(formData.display_order), 10) || 0,
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
            aria-label={t('admin2.qp_close_form_aria')}
            onClick={onCancel}
            onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleActivationKeyDown(event, onCancel)}>
            <div className="admin-qp-modal" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-primary)' : 'white' } as CSSProperties} onClickCapture={e => e.stopPropagation()}>
                <div className="admin-qp-modal-header">
                    <h3 className="admin-qp-modal-title">
                        {isEdit ? t('admin2.qp_edit_title') : t('admin2.qp_create_title')}
                    </h3>
                    <button
                        className="admin-qp-close-button"
                        onClick={onCancel}
                        aria-label={t('admin2.qp_close_form_aria')}
                    >
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    {/* Key (only for create) */}
                    {!isEdit && (
                        <div className="admin-qp-field">
                            <label className="admin-qp-label">{t('admin2.qp_key_label')}</label>
                            <Input
                                className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}
                                aria-label={t('admin2.qp_key_input_aria')}
                                value={formData.key as string}
                                onChange={e => setFormData({ ...formData, key: e.target.value })}
                                placeholder={t('admin2.qp_key_ph')}
                                required
                                pattern="[a-z_]+"
                            />
                            <div className="admin-qp-hint">{t('admin2.qp_key_hint')}</div>
                        </div>
                    )}

                    {/* Titles */}
                    <div className="admin-qp-row">
                        <div className="admin-mb-16-flex-1-1">
                            <label className="admin-qp-label">{t('admin2.qp_title_en_label')}</label>
                            <Input
                                className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}
                                aria-label={t('admin2.qp_title_en_aria')}
                                value={formData.title as string}
                                onChange={e => setFormData({ ...formData, title: e.target.value })}
                                placeholder="Cardiology"
                                required
                            />
                        </div>
                        <div className="admin-mb-16-flex-1">
                            <label className="admin-qp-label">{t('admin2.qp_title_ru_label')}</label>
                            <Input
                                className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}
                                aria-label={t('admin2.qp_title_ru_aria')}
                                value={formData.title_ru as string}
                                onChange={e => setFormData({ ...formData, title_ru: e.target.value })}
                                placeholder={t('admin2.qp_title_ru_ph')}
                            />
                        </div>
                    </div>

                    {/* Queue Tags */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label">Queue Tags</label>
                        <Input
                            className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}
                            aria-label="Queue Tags"
                            value={formData.queue_tags as string}
                            onChange={e => setFormData({ ...formData, queue_tags: e.target.value })}
                            placeholder="cardio, cardiology, cardiology_common"
                        />
                        <div className="admin-qp-hint">{t('admin2.qp_tags_hint')}</div>
                    </div>

                    {/* PR-21: Department key Select */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label">{t('admin2.qp_department_label')}</label>
                        <select
                            className="admin-w-100pct-p-10px-12px-radius-8-bd-1px-solid-var-mac-bo-primary-fs-14-bsz-border-box-w-100-bgc-dyn"
                            style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}
                            value={formData.department_key as string}
                            onChange={e => setFormData({ ...formData, department_key: e.target.value })}
                        >
                            <option value="">{t('admin2.qp_department_none')}</option>
                            {departments.map((d: { key?: string; name_ru?: string }) => (
                                <option key={d.key} value={d.key}>{d.name_ru || d.key}</option>
                            ))}
                        </select>
                        <div className="admin-qp-hint">{t('admin2.qp_department_hint')}</div>
                    </div>

                    {/* Order */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label">{t('admin2.qp_order_label')}</label>
                        <Input
                            className="admin-w-100pct-p-10px-12px-radius-8-bd-1px-solid-var-mac-bo-primary-fs-14-bsz-border-box-w-100-bgc-dyn" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}
                            type="number"
                            aria-label={t('admin2.qp_order_aria')}
                            min="0"
                            value={formData.display_order as string}
                            onChange={e => setFormData({ ...formData, display_order: e.target.value })}
                        />
                    </div>

                    {/* Icon */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label">{t('admin2.qp_icon_label')}</label>
                        <div className="admin-qp-icon-grid">
                            {availableIcons.map(icon => {
                                const IconComponent = icon.component;
                                const isSelected = formData.icon === icon.name;
                                return (
                                    <button
                                        key={icon.name}
                                        type="button"
                                        className="admin-p-12-bd-2px-solid-var-mac-bo-radius-8-bgc-transparent-cur-pointer-d-flex-fd-column-ai-center-gap-4-tr-all-0-2s-bd-c-dyn-bgc-dyn" style={{ '--admin-bd-c0': isSelected ? 'var(--mac-accent-blue)' : 'var(--mac-border)', '--admin-bgc1': isSelected ? 'var(--mac-accent-bg)' : 'transparent' } as CSSProperties}
                                        onClick={() => setFormData({ ...formData, icon: icon.name })}
                                    >
                                        <IconComponent size={24} className="admin-col-dyn" style={{ '--admin-col0': formData.color } as CSSProperties} />
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
                        <label className="admin-qp-label">{t('admin2.qp_color_label')}</label>
                        <div className="admin-qp-color-grid">
                            {PRESET_COLORS.map(color => (
                                <button
                                    key={color}
                                    type="button"
                                    className="admin-w-32-h-32-radius-50pct-bd-3px-solid-transparen-cur-pointer-tr-all-0-2s-bgc-dyn-bd-c-dyn-bsh-dyn" style={{ '--admin-bgc0': color, '--admin-bd-c1': formData.color === color ? 'white' : 'transparent', '--admin-bsh2': formData.color === color ? `0 0 0 2px ${color}` : 'none' } as CSSProperties}
                                    onClick={() => setFormData({ ...formData, color })}
                                    aria-label={t('admin2.qp_color_pick_aria', { color })}
                                    title={color}
                                />
                            ))}
                            <Input
                                type="color"
                                aria-label={t('admin2.qp_custom_color_aria')}
                                value={formData.color as string}
                                onChange={e => setFormData({ ...formData, color: e.target.value })}
                                className="admin-w-32-h-32-bd-none-cur-pointer"
                            />
                        </div>
                    </div>

                    {/* Active */}
                    <div className="admin-qp-field">
                        <label className="admin-d-flex-ai-center-gap-8-cur-pointer">
                            <Checkbox aria-label={t('admin2.qp_active_checkbox_aria')} checked={Boolean(formData.is_active as boolean)} onChange={(checked: boolean) => setFormData({ ...formData, is_active: checked })}
                            />
                            <span className="admin-qp-label">{t('admin2.qp_active_label')}</span>
                        </label>
                    </div>

                    {/* ⭐ NEW: Show on QR Page */}
                    <div className="admin-qp-field">
                        <label className="admin-d-flex-ai-center-gap-8-cur-pointer">
                            <Checkbox aria-label={t('admin2.qp_qr_checkbox_aria')} checked={Boolean(formData.show_on_qr_page as boolean)} onChange={(checked: boolean) => setFormData({ ...formData, show_on_qr_page: checked })}
                            />
                            <span className="admin-qp-label">{t('admin2.qp_qr_label')}</span>
                        </label>
                        <div className="admin-fs-12-secondary-mt-4-ml-24">
                            {t('admin2.qp_qr_hint')}
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="admin-qp-actions">
                        <button type="button" className="admin-qp-cancel-button" onClick={onCancel}>
                            {t('admin2.qp_cancel_btn')}
                        </button>
                        <button
                            type="submit"
                            className="admin-qp-submit-button"
                            disabled={saving}
                            aria-label={isEdit ? t('admin2.qp_save_aria') : t('admin2.qp_create_aria')}
                        >
                            {saving ? (
                                <>{t('admin2.qp_saving')}</>
                            ) : (
                                <>
                                    <Check size={16} />
                                    {isEdit ? t('admin2.qp_save_btn') : t('admin2.qp_create_btn')}
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
