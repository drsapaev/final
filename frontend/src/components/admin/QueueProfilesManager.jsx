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
import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
    '#E53E3E', // Red
    '#3182CE', // Blue
    '#9F7AEA', // Purple
    '#38A169', // Green
    '#DD6B20', // Orange
    '#718096', // Gray
    '#D53F8C', // Pink
    '#4A5568', // Dark gray
];

const QueueProfilesManager = ({ theme = 'light' }) => {
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
        if (!window.confirm(`Удалить вкладку "${profileKey}"? Это действие необратимо.`)) {
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

        if (!window.confirm(`Удалить ${selectedProfiles.length} вкладок? Это действие необратимо.`)) {
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

    // Styles
    const styles = {
        container: {
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
        },
        statsGrid: {
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '16px',
        },
        statCard: {
            padding: '16px',
            backgroundColor: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
            borderRadius: '12px',
            border: '1px solid var(--mac-border)',
            textAlign: 'center',
        },
        statValue: {
            fontSize: '28px',
            fontWeight: 'bold',
            color: 'var(--mac-text-primary)',
            marginBottom: '4px',
        },
        statLabel: {
            fontSize: '13px',
            color: 'var(--mac-text-secondary)',
        },
        mainCard: {
            padding: '24px',
            backgroundColor: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
            borderRadius: '12px',
            border: '1px solid var(--mac-border)',
        },
        header: {
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '20px',
            flexWrap: 'wrap',
            gap: '12px',
        },
        title: {
            fontSize: '20px',
            fontWeight: '600',
            color: 'var(--mac-text-primary)',
            margin: 0,
        },
        toolbar: {
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexWrap: 'wrap',
        },
        searchInput: {
            padding: '8px 12px 8px 36px',
            borderRadius: '8px',
            border: '1px solid var(--mac-border)',
            backgroundColor: isDark ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-secondary)',
            color: 'var(--mac-text-primary)',
            fontSize: '14px',
            width: '200px',
        },
        select: {
            padding: '8px 12px',
            borderRadius: '8px',
            border: '1px solid var(--mac-border)',
            backgroundColor: isDark ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-secondary)',
            color: 'var(--mac-text-primary)',
            fontSize: '14px',
        },
        button: {
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            border: '1px solid var(--mac-border)',
            borderRadius: '8px',
            backgroundColor: 'transparent',
            color: 'var(--mac-text-primary)',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: '500',
        },
        primaryButton: {
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            backgroundColor: 'var(--mac-accent-blue)',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: '500',
        },
        dangerButton: {
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            backgroundColor: '#EF4444',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: '500',
        },
        bulkActions: {
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            borderRadius: '8px',
            marginBottom: '16px',
        },
        table: {
            width: '100%',
            borderCollapse: 'collapse',
        },
        th: {
            textAlign: 'left',
            padding: '12px 8px',
            borderBottom: '2px solid var(--mac-border)',
            fontSize: '12px',
            fontWeight: '600',
            color: 'var(--mac-text-secondary)',
            textTransform: 'uppercase',
        },
        td: {
            padding: '12px 8px',
            borderBottom: '1px solid var(--mac-border)',
            fontSize: '14px',
            color: 'var(--mac-text-primary)',
        },
        iconButton: {
            padding: '6px',
            border: 'none',
            borderRadius: '6px',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            color: 'var(--mac-text-secondary)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
        },
        badge: {
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 8px',
            borderRadius: '12px',
            fontSize: '11px',
            fontWeight: '500',
        },
        colorDot: {
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            border: '2px solid var(--mac-border)',
        },
        error: {
            padding: '12px 16px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            color: '#EF4444',
            borderRadius: '8px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
        },
        searchWrapper: {
            position: 'relative',
        },
        searchIcon: {
            position: 'absolute',
            left: '10px',
            top: '50%',
            transform: 'translateY(-50%)',
            color: 'var(--mac-text-secondary)',
        },
    };

    if (loading) {
        return (
            <div style={styles.container}>
                <div style={{ ...styles.mainCard, textAlign: 'center', padding: '40px' }}>
                    <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite' }} />
                    <p style={{ color: 'var(--mac-text-secondary)', marginTop: '12px' }}>
                        Загрузка профилей...
                    </p>
                </div>
            </div>
        );
    }

    const isAllSelected = filteredProfiles.length > 0 &&
        filteredProfiles.every(p => selectedProfiles.includes(p.key));

    return (
        <div style={styles.container}>
            {/* Statistics Cards */}
            <div style={styles.statsGrid}>
                <div style={styles.statCard}>
                    <div style={styles.statValue}>{stats.total}</div>
                    <div style={styles.statLabel}>Всего вкладок</div>
                </div>
                <div style={{ ...styles.statCard }}>
                    <div style={{ ...styles.statValue, color: 'var(--mac-success, #10B981)' }}>{stats.active}</div>
                    <div style={styles.statLabel}>Активных</div>
                </div>
                <div style={styles.statCard}>
                    <div style={{ ...styles.statValue, color: 'var(--mac-warning, #F59E0B)' }}>{stats.inactive}</div>
                    <div style={styles.statLabel}>Скрытых</div>
                </div>
                <div style={styles.statCard}>
                    <div style={{ ...styles.statValue, color: 'var(--mac-info, #3B82F6)' }}>{stats.totalTags}</div>
                    <div style={styles.statLabel}>Queue Tags</div>
                </div>
            </div>

            {/* Main Card */}
            <div style={styles.mainCard}>
                {/* Header */}
                <div style={styles.header}>
                    <h2 style={styles.title}>Вкладки регистратуры</h2>
                    <div style={styles.toolbar}>
                        {/* Search */}
                        <div style={styles.searchWrapper}>
                            <Search size={16} style={styles.searchIcon} />
                            <input
                                style={styles.searchInput}
                                placeholder="Поиск..."
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                            />
                        </div>

                        {/* Status filter */}
                        <select
                            style={styles.select}
                            value={statusFilter}
                            onChange={e => setStatusFilter(e.target.value)}
                        >
                            <option value="all">Все</option>
                            <option value="active">Активные</option>
                            <option value="inactive">Скрытые</option>
                        </select>

                        {/* Export */}
                        <button style={styles.button} onClick={handleExport} disabled={saving}>
                            <Download size={16} />
                            Экспорт
                        </button>

                        {/* Import */}
                        <label style={{ ...styles.button, cursor: 'pointer' }}>
                            <Upload size={16} />
                            Импорт
                            <input
                                type="file"
                                accept=".csv"
                                onChange={handleImport}
                                style={{ display: 'none' }}
                                disabled={saving}
                            />
                        </label>

                        {/* Refresh */}
                        <button style={styles.button} onClick={loadProfiles} disabled={saving}>
                            <RefreshCw size={16} />
                        </button>

                        {/* Add */}
                        <button
                            style={styles.primaryButton}
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
                    <div style={styles.error}>
                        <AlertCircle size={16} />
                        {error}
                        <button
                            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer' }}
                            onClick={() => setError(null)}
                        >
                            <X size={16} />
                        </button>
                    </div>
                )}

                {/* Bulk actions bar */}
                {selectedProfiles.length > 0 && (
                    <div style={styles.bulkActions}>
                        <span style={{ fontSize: '14px', color: 'var(--mac-text-primary)' }}>
                            Выбрано: {selectedProfiles.length}
                        </span>
                        <button
                            style={{ ...styles.button, marginLeft: 'auto' }}
                            onClick={() => handleBulkActivate(true)}
                            disabled={saving}
                        >
                            <Eye size={16} />
                            Активировать
                        </button>
                        <button
                            style={styles.button}
                            onClick={() => handleBulkActivate(false)}
                            disabled={saving}
                        >
                            <EyeOff size={16} />
                            Скрыть
                        </button>
                        <button
                            style={styles.dangerButton}
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
                <table style={styles.table}>
                    <thead>
                        <tr>
                            <th style={{ ...styles.th, width: '40px' }}>
                                <button
                                    style={styles.iconButton}
                                    onClick={() => handleSelectAll(!isAllSelected)}
                                >
                                    {isAllSelected ? <CheckSquare size={18} /> : <Square size={18} />}
                                </button>
                            </th>
                            <th style={styles.th}>Порядок</th>
                            <th style={styles.th}>Ключ</th>
                            <th style={styles.th}>Название</th>
                            <th style={styles.th}>Queue Tags</th>
                            <th style={styles.th}>Иконка</th>
                            <th style={styles.th}>Цвет</th>
                            <th style={styles.th}>Статус</th>
                            <th style={styles.th}>Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredProfiles.map((profile) => (
                            <tr key={profile.key}>
                                <td style={styles.td}>
                                    <button
                                        style={styles.iconButton}
                                        onClick={() => handleSelectProfile(
                                            profile.key,
                                            !selectedProfiles.includes(profile.key)
                                        )}
                                    >
                                        {selectedProfiles.includes(profile.key)
                                            ? <CheckSquare size={18} style={{ color: 'var(--mac-accent-blue)' }} />
                                            : <Square size={18} />
                                        }
                                    </button>
                                </td>
                                <td style={styles.td}>
                                    <span style={{ color: 'var(--mac-text-secondary)' }}>
                                        {profile.order}
                                    </span>
                                </td>
                                <td style={styles.td}>
                                    <code style={{
                                        backgroundColor: 'var(--mac-bg-tertiary)',
                                        padding: '2px 6px',
                                        borderRadius: '4px',
                                        fontSize: '12px'
                                    }}>
                                        {profile.key}
                                    </code>
                                </td>
                                <td style={styles.td}>
                                    <div>{profile.title_ru || profile.title}</div>
                                    {profile.title_ru && (
                                        <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
                                            {profile.title}
                                        </div>
                                    )}
                                </td>
                                <td style={styles.td}>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                        {(profile.queue_tags || []).map((tag, idx) => (
                                            <span
                                                key={idx}
                                                style={{
                                                    ...styles.badge,
                                                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                                    color: '#3B82F6',
                                                }}
                                            >
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                </td>
                                <td style={styles.td}>
                                    {(() => {
                                        const IconComponent = AVAILABLE_ICONS.find(i => i.name === profile.icon)?.component || Package;
                                        return <IconComponent size={20} style={{ color: profile.color || 'var(--mac-text-secondary)' }} />;
                                    })()}
                                </td>
                                <td style={styles.td}>
                                    <div
                                        style={{
                                            ...styles.colorDot,
                                            backgroundColor: profile.color || '#718096'
                                        }}
                                        title={profile.color}
                                    />
                                </td>
                                <td style={styles.td}>
                                    <span
                                        style={{
                                            ...styles.badge,
                                            backgroundColor: profile.is_active !== false
                                                ? 'rgba(16, 185, 129, 0.1)'
                                                : 'rgba(239, 68, 68, 0.1)',
                                            color: profile.is_active !== false ? '#10B981' : '#EF4444',
                                        }}
                                    >
                                        {profile.is_active !== false ? 'Активен' : 'Скрыт'}
                                    </span>
                                </td>
                                <td style={styles.td}>
                                    <div style={{ display: 'flex', gap: '4px' }}>
                                        <button
                                            style={styles.iconButton}
                                            onClick={() => handleToggleActive(profile)}
                                            title={profile.is_active !== false ? 'Скрыть' : 'Показать'}
                                            disabled={saving}
                                        >
                                            {profile.is_active !== false ? <EyeOff size={16} /> : <Eye size={16} />}
                                        </button>
                                        <button
                                            style={styles.iconButton}
                                            onClick={() => setEditingProfile(profile)}
                                            title="Редактировать"
                                            disabled={saving}
                                        >
                                            <Edit2 size={16} />
                                        </button>
                                        <button
                                            style={{ ...styles.iconButton, color: '#EF4444' }}
                                            onClick={() => handleDelete(profile.key)}
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

                {filteredProfiles.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '40px', color: 'var(--mac-text-secondary)' }}>
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

    const styles = {
        overlay: {
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
        },
        modal: {
            backgroundColor: isDark ? 'var(--mac-bg-primary)' : 'white',
            borderRadius: '16px',
            padding: '24px',
            width: '500px',
            maxWidth: '90vw',
            maxHeight: '90vh',
            overflow: 'auto',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        },
        header: {
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '24px',
        },
        title: {
            fontSize: '18px',
            fontWeight: '600',
            color: 'var(--mac-text-primary)',
            margin: 0,
        },
        closeButton: {
            padding: '6px',
            border: 'none',
            borderRadius: '6px',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            color: 'var(--mac-text-secondary)',
        },
        field: {
            marginBottom: '16px',
        },
        label: {
            display: 'block',
            fontSize: '14px',
            fontWeight: '500',
            color: 'var(--mac-text-primary)',
            marginBottom: '6px',
        },
        input: {
            width: '100%',
            padding: '10px 12px',
            borderRadius: '8px',
            border: '1px solid var(--mac-border)',
            backgroundColor: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
            color: 'var(--mac-text-primary)',
            fontSize: '14px',
            boxSizing: 'border-box',
        },
        hint: {
            fontSize: '12px',
            color: 'var(--mac-text-secondary)',
            marginTop: '4px',
        },
        row: {
            display: 'flex',
            gap: '16px',
        },
        iconGrid: {
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '8px',
            marginTop: '8px',
        },
        iconOption: {
            padding: '12px',
            border: '2px solid var(--mac-border)',
            borderRadius: '8px',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            transition: 'all 0.2s',
        },
        colorGrid: {
            display: 'flex',
            gap: '8px',
            flexWrap: 'wrap',
            marginTop: '8px',
        },
        colorOption: {
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            border: '3px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.2s',
        },
        actions: {
            display: 'flex',
            gap: '12px',
            marginTop: '24px',
            justifyContent: 'flex-end',
        },
        cancelButton: {
            padding: '10px 20px',
            border: '1px solid var(--mac-border)',
            borderRadius: '8px',
            backgroundColor: 'transparent',
            color: 'var(--mac-text-primary)',
            cursor: 'pointer',
            fontSize: '14px',
        },
        submitButton: {
            padding: '10px 20px',
            border: 'none',
            borderRadius: '8px',
            backgroundColor: 'var(--mac-accent-blue)',
            color: 'white',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
        },
    };

    return (
        <div style={styles.overlay} onClick={onCancel}>
            <div style={styles.modal} onClick={e => e.stopPropagation()}>
                <div style={styles.header}>
                    <h3 style={styles.title}>
                        {isEdit ? 'Редактирование вкладки' : 'Новая вкладка'}
                    </h3>
                    <button style={styles.closeButton} onClick={onCancel}>
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    {/* Key (only for create) */}
                    {!isEdit && (
                        <div style={styles.field}>
                            <label style={styles.label}>Уникальный ключ *</label>
                            <input
                                style={styles.input}
                                value={formData.key}
                                onChange={e => setFormData({ ...formData, key: e.target.value })}
                                placeholder="например: cardiology"
                                required
                                pattern="[a-z_]+"
                            />
                            <div style={styles.hint}>Только латинские буквы и подчеркивания</div>
                        </div>
                    )}

                    {/* Titles */}
                    <div style={styles.row}>
                        <div style={{ ...styles.field, flex: 1 }}>
                            <label style={styles.label}>Название (EN) *</label>
                            <input
                                style={styles.input}
                                value={formData.title}
                                onChange={e => setFormData({ ...formData, title: e.target.value })}
                                placeholder="Cardiology"
                                required
                            />
                        </div>
                        <div style={{ ...styles.field, flex: 1 }}>
                            <label style={styles.label}>Название (RU)</label>
                            <input
                                style={styles.input}
                                value={formData.title_ru}
                                onChange={e => setFormData({ ...formData, title_ru: e.target.value })}
                                placeholder="Кардиология"
                            />
                        </div>
                    </div>

                    {/* Queue Tags */}
                    <div style={styles.field}>
                        <label style={styles.label}>Queue Tags</label>
                        <input
                            style={styles.input}
                            value={formData.queue_tags}
                            onChange={e => setFormData({ ...formData, queue_tags: e.target.value })}
                            placeholder="cardio, cardiology, cardiology_common"
                        />
                        <div style={styles.hint}>Разделяйте запятыми. Записи с этими тегами появятся на вкладке.</div>
                    </div>

                    {/* Order */}
                    <div style={styles.field}>
                        <label style={styles.label}>Порядок отображения</label>
                        <input
                            style={{ ...styles.input, width: '100px' }}
                            type="number"
                            min="0"
                            value={formData.display_order}
                            onChange={e => setFormData({ ...formData, display_order: e.target.value })}
                        />
                    </div>

                    {/* Icon */}
                    <div style={styles.field}>
                        <label style={styles.label}>Иконка</label>
                        <div style={styles.iconGrid}>
                            {AVAILABLE_ICONS.map(icon => {
                                const IconComponent = icon.component;
                                const isSelected = formData.icon === icon.name;
                                return (
                                    <button
                                        key={icon.name}
                                        type="button"
                                        style={{
                                            ...styles.iconOption,
                                            borderColor: isSelected ? 'var(--mac-accent-blue)' : 'var(--mac-border)',
                                            backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                                        }}
                                        onClick={() => setFormData({ ...formData, icon: icon.name })}
                                    >
                                        <IconComponent size={24} style={{ color: formData.color }} />
                                        <span style={{ fontSize: '10px', color: 'var(--mac-text-secondary)' }}>
                                            {icon.label}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Color */}
                    <div style={styles.field}>
                        <label style={styles.label}>Цвет</label>
                        <div style={styles.colorGrid}>
                            {PRESET_COLORS.map(color => (
                                <button
                                    key={color}
                                    type="button"
                                    style={{
                                        ...styles.colorOption,
                                        backgroundColor: color,
                                        borderColor: formData.color === color ? 'white' : 'transparent',
                                        boxShadow: formData.color === color ? `0 0 0 2px ${color}` : 'none',
                                    }}
                                    onClick={() => setFormData({ ...formData, color })}
                                />
                            ))}
                            <input
                                type="color"
                                value={formData.color}
                                onChange={e => setFormData({ ...formData, color: e.target.value })}
                                style={{ width: '32px', height: '32px', border: 'none', cursor: 'pointer' }}
                            />
                        </div>
                    </div>

                    {/* Active */}
                    <div style={styles.field}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                                type="checkbox"
                                checked={formData.is_active}
                                onChange={e => setFormData({ ...formData, is_active: e.target.checked })}
                            />
                            <span style={styles.label}>Активная вкладка (видна пользователям)</span>
                        </label>
                    </div>

                    {/* ⭐ NEW: Show on QR Page */}
                    <div style={styles.field}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                                type="checkbox"
                                checked={formData.show_on_qr_page}
                                onChange={e => setFormData({ ...formData, show_on_qr_page: e.target.checked })}
                            />
                            <span style={styles.label}>Показывать на QR-странице (самозапись пациентов)</span>
                        </label>
                        <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)', marginTop: '4px', marginLeft: '24px' }}>
                            Если включено, пациенты смогут выбрать эту специальность при сканировании QR-кода
                        </div>
                    </div>

                    {/* Actions */}
                    <div style={styles.actions}>
                        <button type="button" style={styles.cancelButton} onClick={onCancel}>
                            Отмена
                        </button>
                        <button type="submit" style={styles.submitButton} disabled={saving}>
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

export default QueueProfilesManager;
