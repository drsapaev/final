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
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { CSSProperties } from 'react';
import {
    Plus,
    Edit2,
    Trash2,
    X,
    Archive,
    ArchiveRestore,
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
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  Select,
  Input,
  Checkbox } from '../ui/macos';
import Dialog from '../ui/macos/Dialog';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
import { notify } from '../../services/notify';
import { mapQueueProfileParentRepairPreviewDto } from '../../api/mappers/queue';
import type { QueueProfileParentRepairPreview } from '../../types/domain/queue';
import {
  QUEUE_PROFILES_CSV_BLOCKING_ISSUES,
  buildQueueProfilesCsv,
  parseQueueProfilesCsv,
  queueProfileToCsvPayload,
} from './queueProfilesCsv';
import type { QueueProfilesCsvRow } from './queueProfilesCsv';
import { QUEUE_PROFILE_COLOR_PRESETS } from './queueProfileColors';

interface QueueProfileDto {
    key: string;
    title?: string;
    title_ru?: string;
    queue_tags?: string[];
    department_key?: string;
    icon?: string;
    color?: string;
    order?: number | string;
    display_order?: number | string;
    is_active?: boolean;
    show_on_qr_page?: boolean;
    effective_availability?: {
        is_available?: boolean;
        state?: 'available' | 'unavailable' | 'conflict';
        reason_codes?: string[];
        parent_department_key?: string | null;
        parent_active?: boolean | null;
    };
    name?: string;
    [key: string]: unknown;
}

interface DepartmentDto {
    key?: string;
    name_ru?: string;
    [key: string]: unknown;
}

type QueueProfileOperationStatus = 'completed' | 'refused' | 'not_started' | 'unverified';

interface QueueProfileOperationRowResult {
    key: string;
    status: QueueProfileOperationStatus;
    message?: string;
    requestedQrPublication?: boolean;
}

interface CsvImportTask {
    row: QueueProfilesCsvRow;
    mode?: 'create' | 'update';
    requestedQrPublication: boolean;
}

type QueueProfileOperation =
    | { kind: 'delete'; keys: string[] }
    | { kind: 'set-active'; keys: string[]; active: boolean }
    | { kind: 'csv-import'; rows: CsvImportTask[]; warnings: string[]; previewSnapshot: Record<string, string> };

interface QueueProfileOperationReport {
    kind: QueueProfileOperation['kind'];
    rows: QueueProfileOperationRowResult[];
    warnings: string[];
}

const PENDING_CSV_PUBLICATION_STORAGE_KEY = 'admin.queueProfiles.pendingCsvPublication.v1';

const readPendingCsvPublicationKeys = (): string[] => {
    if (typeof window === 'undefined') return [];
    try {
        const parsed: unknown = JSON.parse(window.sessionStorage.getItem(PENDING_CSV_PUBLICATION_STORAGE_KEY) || '[]');
        return Array.isArray(parsed)
            ? Array.from(new Set(parsed.filter((key): key is string => typeof key === 'string' && key.trim().length > 0)))
            : [];
    } catch {
        return [];
    }
};

const DENTAL_QUEUE_TAG_FAMILY = new Set(['dentistry', 'dental', 'stomatology', 'dentist']);
const DENTAL_QUEUE_TAG_VARIANTS = Array.from(DENTAL_QUEUE_TAG_FAMILY).sort();

const canonicalQueueTagsForCsvComparison = (value: unknown, profileKey: string): string[] | null => {
    if (!Array.isArray(value) || value.some((tag) => typeof tag !== 'string')) return null;

    // Keep this equivalent to backend/app/core/specialties.py's
    // expand_queue_tags() and _queue_profiles.py's profile-key fallback.
    const submittedTags = (value as string[]).filter(Boolean);
    if (submittedTags.length === 0) submittedTags.push(profileKey);
    const keyIsDental = DENTAL_QUEUE_TAG_FAMILY.has(profileKey.trim().toLowerCase());
    const submittedDentalTag = submittedTags.some((tag) => DENTAL_QUEUE_TAG_FAMILY.has(tag.trim().toLowerCase()));
    if (keyIsDental && !submittedDentalTag) submittedTags.push(profileKey);

    const expanded: string[] = [];
    for (const tag of submittedTags) {
        const trimmed = tag.trim();
        if (!trimmed) continue;
        const variants = DENTAL_QUEUE_TAG_FAMILY.has(trimmed.toLowerCase())
            ? DENTAL_QUEUE_TAG_VARIANTS
            : [trimmed];
        for (const variant of variants) {
            if (!expanded.includes(variant)) expanded.push(variant);
        }
    }
    for (const tag of submittedTags) {
        const trimmed = tag.trim();
        if (trimmed && !expanded.includes(trimmed)) expanded.push(trimmed);
    }
    return expanded;
};

const profileMatchesCsvPayload = (
    profile: QueueProfileDto,
    payload: Record<string, unknown>,
    ignorePublication = false,
): boolean => Object.entries(payload).every(([field, expected]) => {
    if (ignorePublication && field === 'show_on_qr_page') return true;
    const actual = field === 'display_order'
        ? profile.display_order ?? profile.order
        : profile[field];
    if (field === 'queue_tags' && Array.isArray(expected)) {
        const expectedTags = canonicalQueueTagsForCsvComparison(expected, profile.key);
        const actualTags = canonicalQueueTagsForCsvComparison(actual, profile.key);
        return expectedTags !== null
            && actualTags !== null
            && expectedTags.length === actualTags.length
            && expectedTags.every((tag, index) => tag === actualTags[index]);
    }
    return actual === expected;
});

const csvPayloadForImportTask = (task: CsvImportTask): Record<string, unknown> => {
    const payload = queueProfileToCsvPayload(task.row);
    if (task.mode === 'create') {
        // New profiles remain hidden until the administrator publishes them separately.
        payload.show_on_qr_page = false;
    } else if (task.requestedQrPublication) {
        // A CSV's true value is review intent, never a publication command.
        // Omitting it from this partial update also avoids a hidden-to-public
        // transition if another administrator changes state after our read.
        delete payload.show_on_qr_page;
    }
    return payload;
};

const queueProfilePreviewSnapshot = (profile: QueueProfileDto | undefined): string => JSON.stringify(profile ? {
    key: profile.key,
    title: profile.title ?? null,
    title_ru: profile.title_ru ?? null,
    queue_tags: profile.queue_tags ?? null,
    department_key: profile.department_key ?? null,
    icon: profile.icon ?? null,
    color: profile.color ?? null,
    display_order: profile.display_order ?? profile.order ?? null,
    is_active: profile.is_active ?? null,
    show_on_qr_page: profile.show_on_qr_page ?? null,
} : null);

const getStatusFilterOptions = (t: (key: string, options?: Record<string, unknown>) => string) => [
    { value: 'all', label: t('admin2.qp_filter_all') },
    { value: 'active', label: t('admin2.qp_filter_active') },
    { value: 'inactive', label: t('admin2.qp_filter_hidden') },
];

// Available icons for selection
const getAvailableIcons = (t: (key: string, options?: Record<string, unknown>) => string) => [
    { name: 'Heart', component: Heart, label: t('admin2.qp_icon_heart') },
    { name: 'Activity', component: Activity, label: t('admin2.qp_icon_activity') },
    { name: 'Sparkles', component: Sparkles, label: t('admin2.qp_icon_sparkles') },
    { name: 'Smile', component: Smile, label: t('admin2.qp_icon_smile') },
    { name: 'TestTube', component: TestTube, label: t('admin2.qp_icon_test_tube') },
    { name: 'Stethoscope', component: Stethoscope, label: t('admin2.qp_icon_stethoscope') },
    { name: 'Users', component: Users, label: t('admin2.qp_icon_users') },
    { name: 'Package', component: Package, label: t('admin2.qp_icon_package') },
];

const apiErrorMessage = (error: unknown, fallback: string): string => {
    if (typeof error !== 'object' || error === null) return fallback;
    const response = (error as { response?: unknown }).response;
    if (typeof response !== 'object' || response === null) return fallback;
    const data = (response as { data?: unknown }).data;
    if (typeof data !== 'object' || data === null) return fallback;
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (typeof detail !== 'object' || detail === null) return fallback;

    const message = (detail as { message?: unknown }).message;
    const blockedFields = (detail as { blocked_fields?: unknown }).blocked_fields;
    const parts = [typeof message === 'string' ? message : ''];
    if (Array.isArray(blockedFields)) {
        const fields = blockedFields.filter(
            (field): field is string => typeof field === 'string',
        );
        if (fields.length > 0) parts.push(`Заблокированные поля: ${fields.join(', ')}`);
    }
    return parts.filter(Boolean).join(' ') || fallback;
};

const apiErrorReason = (error: unknown): string | null => {
    if (typeof error !== 'object' || error === null) return null;
    const response = (error as { response?: unknown }).response;
    if (typeof response !== 'object' || response === null) return null;
    const data = (response as { data?: unknown }).data;
    if (typeof data !== 'object' || data === null) return null;
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail !== 'object' || detail === null) return null;
    const reason = (detail as { reason?: unknown }).reason;
    return typeof reason === 'string' ? reason : null;
};

const getQueueProfileDisplayName = (profile: QueueProfileDto): string =>
    profile.name?.trim() || profile.title_ru?.trim() || profile.title?.trim() || profile.key;

const QueueProfilesManager = ({ theme = 'light' }: { theme?: 'light' | 'dark' }) => {
    const { t: rawT } = useTranslation();
  const t = rawT;
    const tRef = useRef(t);
    useEffect(() => {
        tRef.current = t;
    }, [t]);
    const statusFilterOptions = getStatusFilterOptions(t);
    const availableIcons = getAvailableIcons(t);
    // P-013 fix: shared ConfirmDialog hook (replaces 2 window.confirm() calls).
    const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
    const [profiles, setProfiles] = useState<QueueProfileDto[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [editingProfile, setEditingProfile] = useState<QueueProfileDto | null>(null);
    const [showCreateForm, setShowCreateForm] = useState(false);
    // PR-21: load departments for department_key Select in ProfileForm
    const [departments, setDepartments] = useState<DepartmentDto[]>([]);
    const [operationReport, setOperationReport] = useState<QueueProfileOperationReport | null>(null);
    const [retryOperation, setRetryOperation] = useState<QueueProfileOperation | null>(null);
    const [pendingCsvPublicationKeys, setPendingCsvPublicationKeys] = useState<string[]>(readPendingCsvPublicationKeys);
    const [parentRepairProfileKey, setParentRepairProfileKey] = useState<string | null>(null);
    const [parentRepairPreview, setParentRepairPreview] = useState<QueueProfileParentRepairPreview | null>(null);
    const [parentRepairLoading, setParentRepairLoading] = useState(false);
    const [parentRepairApplying, setParentRepairApplying] = useState(false);
    const [parentRepairError, setParentRepairError] = useState<string | null>(null);
    const [parentRepairSuccess, setParentRepairSuccess] = useState<string | null>(null);
    const [confirmParentRepairTarget, setConfirmParentRepairTarget] = useState(false);
    const [confirmParentRepairServices, setConfirmParentRepairServices] = useState(false);
    const [confirmParentRepairPublicAccess, setConfirmParentRepairPublicAccess] = useState(false);
    const parentRepairRequestSequence = useRef(0);

    // ⭐ New: Search and filter
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'active', 'inactive'

    // ⭐ New: Bulk selection
    const [selectedProfiles, setSelectedProfiles] = useState<string[]>([]);

    const isDark = theme === 'dark';

    // Load profiles from API
    const loadProfiles = useCallback(async (options: { silent?: boolean; clearSelection?: boolean } = {}): Promise<QueueProfileDto[] | null> => {
        try {
            setError(null);
            if (!options.silent) setLoading(true);
            const response = (await api.get('/queues/profiles?active_only=false')) as import('axios').AxiosResponse<Record<string, unknown>>;
            const loadedProfiles = ((response.data.profiles as unknown[]) || []) as unknown as QueueProfileDto[];
            setProfiles(loadedProfiles);
            if (options.clearSelection !== false) setSelectedProfiles([]);
            logger.info(`Loaded ${loadedProfiles.length} queue profiles`);
            return loadedProfiles;
        } catch (err) {
            logger.error('Error loading queue profiles:', err);
            setError(tRef.current('admin2.qp_load_failed'));
            return null;
        } finally {
            if (!options.silent) setLoading(false);
        }
    }, []);

    useEffect(() => {
        try {
            window.sessionStorage.setItem(PENDING_CSV_PUBLICATION_STORAGE_KEY, JSON.stringify(pendingCsvPublicationKeys));
        } catch {
            // The in-memory reminder remains visible for this page if browser storage is unavailable.
        }
    }, [pendingCsvPublicationKeys]);

    useEffect(() => {
        loadProfiles();
        // PR-21: load departments for department_key Select
        api.get('/admin/departments').then((res: import('axios').AxiosResponse<Record<string, unknown>>) => {
            setDepartments(((res.data?.data as unknown[]) || []) as unknown as DepartmentDto[]);
        }).catch(err => logger.error('Failed to load departments:', err));
    }, [loadProfiles]);

    const loadParentRepairPreview = async (
        profileKey: string,
        options: { preserveError?: boolean } = {},
    ) => {
        const requestSequence = ++parentRepairRequestSequence.current;
        setParentRepairLoading(true);
        if (!options.preserveError) setParentRepairError(null);
        setConfirmParentRepairTarget(false);
        setConfirmParentRepairServices(false);
        setConfirmParentRepairPublicAccess(false);
        try {
            const response = (await api.get(
                `/queues/profiles/${encodeURIComponent(profileKey)}/parent-repair-preview`,
            )) as import('axios').AxiosResponse<QueueProfileParentRepairPreview>;
            if (requestSequence !== parentRepairRequestSequence.current) return;
            setParentRepairPreview(mapQueueProfileParentRepairPreviewDto(response.data));
        } catch (err) {
            if (requestSequence !== parentRepairRequestSequence.current) return;
            const reason = apiErrorReason(err);
            setParentRepairPreview(null);
            setParentRepairError(reason === 'parent_repair_stale'
                ? tRef.current('admin2.qp_parent_repair_stale')
                : apiErrorMessage(err, tRef.current('admin2.qp_parent_repair_load_failed')));
        } finally {
            if (requestSequence === parentRepairRequestSequence.current) {
                setParentRepairLoading(false);
            }
        }
    };

    const openParentRepair = (profileKey: string) => {
        setParentRepairProfileKey(profileKey);
        setParentRepairPreview(null);
        setParentRepairError(null);
        setParentRepairSuccess(null);
        void loadParentRepairPreview(profileKey);
    };

    const closeParentRepair = () => {
        parentRepairRequestSequence.current += 1;
        setParentRepairProfileKey(null);
        setParentRepairPreview(null);
        setParentRepairError(null);
        setParentRepairLoading(false);
        setParentRepairApplying(false);
    };

    const applyParentRepair = async () => {
        const target = parentRepairPreview?.target;
        if (
            !parentRepairProfileKey
            || !parentRepairPreview?.can_apply
            || !parentRepairPreview.preview_token
            || !target
            || !confirmParentRepairTarget
            || (parentRepairPreview.service_scope_confirmation_required && !confirmParentRepairServices)
            || (parentRepairPreview.public_access_confirmation_required && !confirmParentRepairPublicAccess)
        ) return;
        setParentRepairApplying(true);
        setParentRepairError(null);
        try {
            await api.post(
                `/queues/profiles/${encodeURIComponent(parentRepairProfileKey)}/parent-repair`,
                {
                    target_department_key: target.department_key,
                    preview_token: parentRepairPreview.preview_token,
                    confirm_target: true,
                    confirm_service_scope_change: confirmParentRepairServices,
                    confirm_public_access: confirmParentRepairPublicAccess,
                    reason_code: 'resolve_parent_conflict_to_own_key',
                },
            );
            const refreshedProfiles = await loadProfiles({ silent: true, clearSelection: false });
            if (!refreshedProfiles) {
                setError(tRef.current('admin2.qp_parent_repair_saved_refresh_failed'));
            }
            setParentRepairSuccess(tRef.current('admin2.qp_parent_repair_success'));
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
            closeParentRepair();
        } catch (err) {
            const reason = apiErrorReason(err);
            if (reason === 'parent_repair_stale') {
                setParentRepairError(tRef.current('admin2.qp_parent_repair_stale'));
                await loadParentRepairPreview(parentRepairProfileKey, { preserveError: true });
            } else if (reason === 'parent_repair_confirmation_required') {
                setParentRepairError(tRef.current('admin2.qp_parent_repair_confirmation_required'));
            } else if (reason === 'parent_repair_not_applicable') {
                setParentRepairError(tRef.current('admin2.qp_parent_repair_not_applicable'));
                await loadParentRepairPreview(parentRepairProfileKey, { preserveError: true });
            } else {
                setParentRepairError(apiErrorMessage(err, tRef.current('admin2.qp_parent_repair_apply_failed')));
            }
        } finally {
            setParentRepairApplying(false);
        }
    };

    // ⭐ New: Filtered profiles
    const filteredProfiles = useMemo(() => {
        return profiles.filter((profile: QueueProfileDto) => {
            // Search filter
            const matchesSearch = searchTerm === '' ||
                profile.key?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                profile.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                profile.title_ru?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                (profile.queue_tags || []).some((tag: string) =>
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
        active: profiles.filter((p: QueueProfileDto) => p.is_active !== false).length,
        inactive: profiles.filter((p: QueueProfileDto) => p.is_active === false).length,
        totalTags: profiles.reduce((sum: number, p: QueueProfileDto) => sum + (p.queue_tags?.length || 0), 0),
    }), [profiles]);

    const runQueueProfileOperation = async (
        requestedOperation: QueueProfileOperation,
        previousReport: QueueProfileOperationReport | null = null,
    ) => {
        setSaving(true);
        setError(null);
        try {
            // Re-read immediately before every initial write or retry. A retry
            // never trusts the list shown before the previous refusal.
            const currentProfiles = await loadProfiles({ silent: true, clearSelection: false });
            if (!currentProfiles) return;

            if (requestedOperation.kind === 'csv-import' && !previousReport) {
                const previewBecameStale = requestedOperation.rows.some((task) => {
                    const current = currentProfiles.find((profile) => profile.key === task.row.key);
                    return requestedOperation.previewSnapshot[task.row.key] !== queueProfilePreviewSnapshot(current);
                });
                if (previewBecameStale) {
                    setOperationReport({
                        kind: 'csv-import',
                        rows: requestedOperation.rows.map((task) => ({
                            key: task.row.key,
                            status: 'not_started',
                            message: t('admin2.qp_operation_stale_preview'),
                            requestedQrPublication: task.requestedQrPublication,
                        })),
                        warnings: requestedOperation.warnings,
                    });
                    setRetryOperation(null);
                    return;
                }
            }

            const operation: QueueProfileOperation = requestedOperation.kind === 'csv-import'
                ? {
                    ...requestedOperation,
                    rows: requestedOperation.rows.map((task) => ({
                        ...task,
                        mode: task.mode ?? (currentProfiles.some((profile) => profile.key === task.row.key) ? 'update' : 'create'),
                    })),
                }
                : requestedOperation;
            setRetryOperation(operation);

            const keys = operation.kind === 'csv-import'
                ? operation.rows.map((task) => task.row.key)
                : operation.keys;
            const priorByKey = new Map((previousReport?.rows ?? []).map((row) => [row.key, row]));
            const rowResults = new Map<string, QueueProfileOperationRowResult>();
            for (const key of keys) {
                rowResults.set(key, priorByKey.get(key) ?? { key, status: 'not_started' });
            }
            const retryableStatuses = new Set<QueueProfileOperationStatus>(['refused', 'not_started', 'unverified']);
            const candidateKeys = previousReport
                ? keys.filter((key) => retryableStatuses.has(priorByKey.get(key)?.status ?? 'not_started'))
                : keys;
            const attempted = new Set<string>();
            const writeErrors = new Map<string, string>();
            const skippedMessages = new Map<string, string>();
            const alreadySatisfiedMessages = new Map<string, string>();

            for (const key of candidateKeys) {
                const profile = currentProfiles.find((item) => item.key === key);
                if (operation.kind === 'delete' && !profile) {
                    alreadySatisfiedMessages.set(key, t('admin2.qp_operation_already_absent'));
                    rowResults.set(key, { key, status: 'completed' });
                    continue;
                }
                if (operation.kind === 'set-active' && profile && (profile.is_active !== false) === operation.active) {
                    alreadySatisfiedMessages.set(key, t('admin2.qp_operation_already_satisfied'));
                    rowResults.set(key, { key, status: 'completed' });
                    continue;
                }

                let csvTask: CsvImportTask | undefined;
                let csvPayload: Record<string, unknown> | undefined;
                if (operation.kind === 'csv-import') {
                    csvTask = operation.rows.find((task) => task.row.key === key);
                    if (!csvTask) {
                        skippedMessages.set(key, t('admin2.qp_operation_not_found'));
                        continue;
                    }
                    csvPayload = csvPayloadForImportTask(csvTask);
                    if (csvTask.mode === 'create') {
                        if (profile) {
                            const matchesCreate = profileMatchesCsvPayload(profile, csvPayload, csvTask.requestedQrPublication);
                            if (matchesCreate) {
                                alreadySatisfiedMessages.set(key, t('admin2.qp_operation_already_created'));
                                rowResults.set(key, { key, status: 'completed', requestedQrPublication: csvTask.requestedQrPublication });
                                continue;
                            }
                            skippedMessages.set(key, t('admin2.qp_operation_key_conflict'));
                            continue;
                        }
                    } else {
                        if (!profile) {
                            skippedMessages.set(key, t('admin2.qp_operation_profile_missing'));
                            continue;
                        }
                        if (csvPayload && profileMatchesCsvPayload(profile, csvPayload)) {
                            alreadySatisfiedMessages.set(key, t('admin2.qp_operation_already_satisfied'));
                            rowResults.set(key, { key, status: 'completed' });
                            continue;
                        }
                        if (previousReport
                            && operation.previewSnapshot[key] !== queueProfilePreviewSnapshot(profile)) {
                            skippedMessages.set(key, t('admin2.qp_operation_stale_preview'));
                            continue;
                        }
                    }
                } else if (!profile) {
                    skippedMessages.set(key, t('admin2.qp_operation_profile_missing'));
                    continue;
                }

                attempted.add(key);
                try {
                    if (operation.kind === 'delete') {
                        await api.delete(`/queues/profiles/${key}`);
                    } else if (operation.kind === 'set-active') {
                        await api.put(`/queues/profiles/${key}`, { is_active: operation.active });
                    } else if (csvTask && csvPayload) {
                        if (csvTask.mode === 'create') {
                            await api.post('/queues/profiles', csvPayload);
                        } else {
                            await api.put(`/queues/profiles/${key}`, csvPayload);
                        }
                    }
                } catch (operationError) {
                    // Keep the server's structured refusal text; do not log
                    // arbitrary CSV rows or raw request/response payloads.
                    writeErrors.set(key, apiErrorMessage(operationError, t('admin2.qp_operation_row_failed')));
                }
            }

            // Always verify actual persisted state, including after a rejected
            // write or a lost response. If this read fails, report uncertainty.
            const refreshedProfiles = await loadProfiles({ silent: true, clearSelection: false });
            if (!refreshedProfiles) {
                for (const key of candidateKeys) {
                    const wasAttempted = attempted.has(key);
                    rowResults.set(key, {
                        key,
                        status: wasAttempted ? 'unverified' : 'not_started',
                        message: t('admin2.qp_operation_unverified'),
                        requestedQrPublication: operation.kind === 'csv-import'
                            ? operation.rows.find((task) => task.row.key === key)?.requestedQrPublication
                            : undefined,
                    });
                }
            } else {
                for (const key of candidateKeys) {
                    const profile = refreshedProfiles.find((item) => item.key === key);
                    const csvTask = operation.kind === 'csv-import'
                        ? operation.rows.find((task) => task.row.key === key)
                        : undefined;
                    let completed = false;
                    if (operation.kind === 'delete') completed = !profile;
                    else if (operation.kind === 'set-active') completed = Boolean(profile && (profile.is_active !== false) === operation.active);
                    else if (csvTask && profile) {
                        const payload = csvPayloadForImportTask(csvTask);
                        // A successful create must be confirmed hidden; only
                        // a pre-existing row can ignore requested publication.
                        completed = profileMatchesCsvPayload(profile, payload);
                    }

                    if (completed) {
                        rowResults.set(key, {
                            key,
                            status: 'completed',
                            message: alreadySatisfiedMessages.get(key),
                            requestedQrPublication: csvTask?.requestedQrPublication,
                        });
                    } else if (skippedMessages.has(key)) {
                        rowResults.set(key, {
                            key,
                            status: 'refused',
                            message: skippedMessages.get(key),
                            requestedQrPublication: csvTask?.requestedQrPublication,
                        });
                    } else if (writeErrors.has(key)) {
                        rowResults.set(key, {
                            key,
                            status: 'refused',
                            message: writeErrors.get(key),
                            requestedQrPublication: csvTask?.requestedQrPublication,
                        });
                    } else if (attempted.has(key)) {
                        rowResults.set(key, {
                            key,
                            status: 'refused',
                            message: t('admin2.qp_operation_state_changed'),
                            requestedQrPublication: csvTask?.requestedQrPublication,
                        });
                    } else {
                        rowResults.set(key, { key, status: 'not_started', requestedQrPublication: csvTask?.requestedQrPublication });
                    }
                }

                if (operation.kind === 'csv-import') {
                    const pendingKeys = operation.rows
                        .filter((task) => task.requestedQrPublication)
                        .filter((task) => {
                            const profile = refreshedProfiles.find((item) => item.key === task.row.key);
                            return rowResults.get(task.row.key)?.status === 'completed'
                                && !(profile?.show_on_qr_page === true && profile.effective_availability?.is_available === true);
                        })
                        .map((task) => task.row.key);
                    const completedPublications = new Set(operation.rows
                        .filter((task) => task.requestedQrPublication)
                        .filter((task) => {
                            const profile = refreshedProfiles.find((item) => item.key === task.row.key);
                            return profile?.show_on_qr_page === true && profile.effective_availability?.is_available === true;
                        })
                        .map((task) => task.row.key));
                    setPendingCsvPublicationKeys((previous) => Array.from(new Set([
                        ...previous.filter((key) => !completedPublications.has(key)),
                        ...pendingKeys,
                    ])));
                }

                if ([...rowResults.values()].some((row) => row.status === 'completed')) {
                    window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
                }
            }

            if (operation.kind === 'delete' && refreshedProfiles) {
                const completedDeletes = candidateKeys.filter((key) => rowResults.get(key)?.status === 'completed');
                if (completedDeletes.length > 0) {
                    setPendingCsvPublicationKeys((previous) => previous.filter((key) => !completedDeletes.includes(key)));
                }
            }

            const report: QueueProfileOperationReport = {
                kind: operation.kind,
                rows: keys.map((key) => rowResults.get(key) ?? { key, status: 'not_started' }),
                warnings: operation.kind === 'csv-import' ? operation.warnings : [],
            };
            setOperationReport(report);
            setRetryOperation(operation);
            setSelectedProfiles([]);

            const completedCount = report.rows.filter((row) => row.status === 'completed').length;
            const refused = report.rows.filter((row) => row.status === 'refused' || row.status === 'unverified' || row.status === 'not_started').length;
            if (refused > 0) {
                notify.warning(t('admin2.qp_operation_partial', { completed: completedCount, refused }));
            } else if (operation.kind === 'csv-import') {
                const imported = operation.rows.filter((task) => task.mode === 'create' && rowResults.get(task.row.key)?.status === 'completed').length;
                const updated = operation.rows.filter((task) => task.mode === 'update'
                    && rowResults.get(task.row.key)?.status === 'completed'
                    && attempted.has(task.row.key)).length;
                const unchanged = operation.rows.filter((task) => task.mode === 'update'
                    && rowResults.get(task.row.key)?.status === 'completed'
                    && !attempted.has(task.row.key)).length;
                const deferredPublication = refreshedProfiles
                    ? operation.rows.filter((task) => {
                        if (!task.requestedQrPublication || rowResults.get(task.row.key)?.status !== 'completed') return false;
                        const profile = refreshedProfiles.find((item) => item.key === task.row.key);
                        return !(profile?.show_on_qr_page === true && profile.effective_availability?.is_available === true);
                    }).length
                    : 0;
                if (deferredPublication > 0) {
                    notify.warning(t('admin2.qp_import_publication_deferred', {
                        imported,
                        updated,
                        unchanged,
                        failed: 0,
                        deferred: deferredPublication,
                    }), { autoClose: 8000 });
                } else if (report.warnings.length > 0) {
                    notify.warning(t('admin2.qp_operation_warnings', { count: report.warnings.length }));
                } else {
                    notify.success(t('admin2.qp_import_success', { imported, updated, unchanged }));
                }
            } else if (completedCount > 0) {
                notify.success(t('admin2.qp_operation_complete', { count: completedCount }));
            }
        } finally {
            setSaving(false);
        }
    };

    const removePendingCsvPublication = (key: string) => {
        setPendingCsvPublicationKeys((current) => current.filter((pendingKey) => pendingKey !== key));
    };

    // Create new profile
    const handleCreate = async (profileData: Record<string, unknown>) => {
        try {
            setSaving(true);
            setError(null);
            await api.post('/queues/profiles', { ...profileData, show_on_qr_page: false });
            await loadProfiles();
            setShowCreateForm(false);
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
        } catch (err) {
            logger.error('Error creating profile:', err);
            setError(String((err as Record<string, unknown> & { response?: { data?: { detail?: string } } })?.response?.data?.detail || t('admin2.qp_create_error')));
        } finally {
            setSaving(false);
        }
    };

    // Update existing profile
    const handleUpdate = async (profileKey: string, profileData: Record<string, unknown>) => {
        try {
            setSaving(true);
            setError(null);
            await api.put(`/queues/profiles/${profileKey}`, profileData);
            const refreshedProfiles = await loadProfiles();
            if (profileData.show_on_qr_page === true
                && refreshedProfiles?.find((profile) => profile.key === profileKey)?.effective_availability?.is_available === true) {
                removePendingCsvPublication(profileKey);
            }
            setEditingProfile(null);
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
        } catch (err) {
            logger.error('Error updating profile:', err);
            setError(apiErrorMessage(err, t('admin2.qp_update_error')));
        } finally {
            setSaving(false);
        }
    };

    // Delete profile
    const handleDelete = async (profileKey: string) => {
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
            removePendingCsvPublication(profileKey);
            window.dispatchEvent(new CustomEvent('queue-profiles:updated'));
        } catch (err) {
            logger.error('Error deleting profile:', err);
            setError(apiErrorMessage(err, t('admin2.qp_delete_error')));
        } finally {
            setSaving(false);
        }
    };

    // Toggle active status
    const handleToggleActive = async (profile: QueueProfileDto) => {
        await handleUpdate(profile.key, { is_active: !profile.is_active });
    };

    // ⭐ New: Bulk selection handlers
    const handleSelectAll = (checked: boolean) => {
        if (checked) {
            setSelectedProfiles(filteredProfiles.map((p: QueueProfileDto) => p.key));
        } else {
            setSelectedProfiles([]);
        }
    };

    const handleSelectProfile = (profileKey: string, checked: boolean) => {
        if (checked) {
            setSelectedProfiles(prev => [...prev, profileKey]);
        } else {
            setSelectedProfiles(prev => prev.filter((k: string) => k !== profileKey));
        }
    };

    // ⭐ New: Bulk delete
    const handleBulkDelete = async () => {
        if (selectedProfiles.length === 0) return;
        const keys = [...selectedProfiles];

        // P-013 fix: replaced window.confirm() with shared useConfirm hook.
        const ok = await confirm({
            title: t('admin2.bulk_delete_queue_tabs_title'),
            message: t('admin2.qp_bulk_delete_confirm_msg', { count: keys.length }),
            description: t('admin2.qp_bulk_delete_confirm_desc'),
            confirmLabel: t('admin2.delete_all_confirm'),
            cancelLabel: t('admin2.cancel'),
            intent: 'destructive',
        });
        if (ok) await runQueueProfileOperation({ kind: 'delete', keys });
    };

    // ⭐ New: Bulk activate/deactivate
    const handleBulkActivate = async (activate: boolean) => {
        if (selectedProfiles.length === 0) return;
        const keys = [...selectedProfiles];
        const ok = await confirm({
            title: t('admin2.qp_bulk_preview_title'),
            message: t(activate ? 'admin2.qp_bulk_activate_preview' : 'admin2.qp_bulk_archive_preview', { count: keys.length }),
            description: t('admin2.qp_bulk_preview_desc'),
            confirmLabel: t('admin2.qp_bulk_preview_confirm'),
            cancelLabel: t('admin2.cancel'),
            intent: 'default',
        });
        if (ok) await runQueueProfileOperation({ kind: 'set-active', keys, active: activate });
    };

    // ⭐ New: Export to CSV — RQ-26.a: full current contract (F-22), all fields quoted.
    const handleExport = () => {
        try {
            const csvContent = buildQueueProfilesCsv(profiles);

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

    // CSV rows are parsed and previewed before any write. New rows always
    // remain hidden; requested publication is retained as a separate review.
    const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        try {
            const text = await file.text();
            const knownDepartmentKeys = new Set(
                departments
                    .map((d: DepartmentDto) => String(d.key ?? '').trim())
                    .filter(Boolean)
            );
            const { rows, issues } = parseQueueProfilesCsv(text, { knownDepartmentKeys });

            const blockingIssues = issues.filter((issue) => QUEUE_PROFILES_CSV_BLOCKING_ISSUES.has(issue.code));
            if (blockingIssues.length > 0) {
                const rowList = Array.from(new Set(blockingIssues.map((issue) => issue.row).filter((row) => row > 0)))
                    .slice(0, 8)
                    .join(', ');
                setError(t('admin2.qp_import_row_issues', { count: blockingIssues.length, rows: rowList }));
                return;
            }

            if (rows.length === 0) {
                setError(t('admin2.qp_import_no_valid'));
                return;
            }

            const beforePreview = await loadProfiles({ silent: true, clearSelection: false });
            if (!beforePreview) return;
            const createCount = rows.filter((row) => !beforePreview.some((profile) => profile.key === row.key)).length;
            const updateCount = rows.length - createCount;
            const requestedPublicationCount = rows.filter((row) => {
                if (row.showOnQrPage !== true) return false;
                const existingProfile = beforePreview.find((profile) => profile.key === row.key);
                return !(existingProfile?.show_on_qr_page === true
                    && existingProfile.effective_availability?.is_available === true);
            }).length;
            const previewSnapshot = Object.fromEntries(rows.map((row) => [
                row.key,
                queueProfilePreviewSnapshot(beforePreview.find((profile) => profile.key === row.key)),
            ]));
            const accepted = await confirm({
                title: t('admin2.qp_import_preview_title'),
                message: t('admin2.qp_import_preview_msg', {
                    create: createCount,
                    update: updateCount,
                    publication: requestedPublicationCount,
                }),
                description: t('admin2.qp_import_preview_desc'),
                confirmLabel: t('admin2.qp_import_preview_confirm'),
                cancelLabel: t('admin2.cancel'),
                intent: 'default',
            });
            if (!accepted) return;

            const warnings = issues.flatMap((issue) => {
                if (issue.code === 'unknown_department') {
                    return [t('admin2.qp_import_unknown_department_row', { row: issue.row, key: issue.key })];
                }
                return [];
            });
            const unknownColumns = Array.from(new Set(issues
                .filter((issue) => issue.code === 'unknown_column' && issue.column)
                .map((issue) => issue.column as string)));
            if (unknownColumns.length > 0) {
                warnings.push(t('admin2.qp_import_unknown_columns', { columns: unknownColumns.join(', ') }));
            }

            await runQueueProfileOperation({
                kind: 'csv-import',
                rows: rows.map((row) => ({ row, requestedQrPublication: row.showOnQrPage === true })),
                warnings,
                previewSnapshot,
            });

        } catch (err) {
            logger.error('Error importing profiles:', err);
            setError(t('admin2.qp_import_error'));
        } finally {
            setSaving(false);
            event.target.value = '';
        }
    };

    const handleRetryRemaining = async () => {
        if (!retryOperation || !operationReport) return;
        await runQueueProfileOperation(retryOperation, operationReport);
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
        filteredProfiles.every((p: QueueProfileDto) => selectedProfiles.includes(p.key));

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
                            onValueChange={(value) => setStatusFilter(String(value))}
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
                            onClick={() => { void loadProfiles(); }}
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

                {parentRepairSuccess && (
                    <div
                        className="admin-p-12-bg-success-bg-bd-1solidvar-mac-success-border-radius-var--mac-radius-md admin-d-flex-ai-center-gap-8-mb-12"
                        role="status"
                        aria-live="polite"
                    >
                        <Check size={16} />
                        {parentRepairSuccess}
                    </div>
                )}

                {(operationReport || pendingCsvPublicationKeys.length > 0) && (
                    <section
                        className="admin-p-16-radius-12-bd-1px-solid-var-mac-bo-mb-16"
                        role="region"
                        aria-label={t('admin2.qp_operation_results')}
                    >
                        <h3 className="admin-fs-16-fw-600-primary-mt-0">{t('admin2.qp_operation_results')}</h3>
                        {operationReport && (
                            <>
                                <p role="status" aria-live="polite" aria-atomic="true">
                                    {t('admin2.qp_operation_summary', {
                                        completed: operationReport.rows.filter((row) => row.status === 'completed').length,
                                        refused: operationReport.rows.filter((row) => row.status === 'refused').length,
                                        notStarted: operationReport.rows.filter((row) => row.status === 'not_started').length,
                                        unverified: operationReport.rows.filter((row) => row.status === 'unverified').length,
                                    })}
                                </p>
                                {operationReport.warnings.length > 0 && (
                                    <ul aria-label={t('admin2.qp_operation_warnings_label')}>
                                        {operationReport.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}
                                    </ul>
                                )}
                                <ul>
                                    {operationReport.rows.map((row) => (
                                        <li key={row.key}>
                                            <strong>{row.key}</strong>: {t(`admin2.qp_operation_status_${row.status}`)}
                                            {row.message ? ` — ${row.message}` : ''}
                                        </li>
                                    ))}
                                </ul>
                                {retryOperation && operationReport.rows.some((row) => row.status === 'refused' || row.status === 'not_started' || row.status === 'unverified') && (
                                    <button className="admin-qp-button" onClick={handleRetryRemaining} disabled={saving}>
                                        {t('admin2.qp_operation_retry')}
                                    </button>
                                )}
                            </>
                        )}
                        {pendingCsvPublicationKeys.length > 0 && (
                            <div>
                                <p>{t('admin2.qp_pending_csv_publication_help')}</p>
                                <ul aria-label={t('admin2.qp_pending_csv_publication_label')}>
                                    {pendingCsvPublicationKeys.map((key) => {
                                        const profile = profiles.find((item) => item.key === key);
                                        return (
                                            <li key={key}>
                                                <strong>{key}</strong>
                                                <button
                                                    className="admin-qp-button"
                                                    onClick={() => profile && setEditingProfile(profile)}
                                                    disabled={!profile || saving}
                                                    aria-label={t('admin2.qp_pending_csv_publication_review_aria', { key })}
                                                >
                                                    {t('admin2.qp_pending_csv_publication_review')}
                                                </button>
                                                <button
                                                    className="admin-ml-8-bg-none-bd-none-cur-pointer-secondary"
                                                    onClick={() => removePendingCsvPublication(key)}
                                                    disabled={saving}
                                                    aria-label={t('admin2.qp_pending_csv_publication_dismiss_aria', { key })}
                                                >
                                                    {t('admin2.qp_pending_csv_publication_dismiss')}
                                                </button>
                                            </li>
                                        );
                                    })}
                                </ul>
                            </div>
                        )}
                    </section>
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
                            <ArchiveRestore size={16} />
                            {t('admin2.qp_bulk_activate_btn')}
                        </button>
                        <button
                            className="admin-qp-button"
                            onClick={() => handleBulkActivate(false)}
                            disabled={saving}
                        >
                            <Archive size={16} />
                            {t('admin2.qp_bulk_archive_btn')}
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
                        {filteredProfiles.map((profile: QueueProfileDto) => (
                            <tr key={profile.key}>
                                <td className="admin-qp-td">
                                    <button
                                        className="admin-qp-icon-button"
                                        onClick={() => handleSelectProfile(
                                            profile.key,
                                            !selectedProfiles.includes(profile.key)
                                        )}
                                        aria-label={selectedProfiles.includes(profile.key) ? t('admin2.qp_deselect_row_aria', { name: getQueueProfileDisplayName(profile) }) : t('admin2.qp_select_row_aria', { name: getQueueProfileDisplayName(profile) })}
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
                                        {(profile.queue_tags || []).map((tag: string, idx: number) => (
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
                                        aria-label={t('admin2.qp_color_aria', { name: getQueueProfileDisplayName(profile), color: profile.color || t('admin2.qp_color_not_set') })}
                                        className="admin-w-16-h-16-radius-50pct-bd-2px-solid-var-mac-bo-bgc-dyn" style={{ '--admin-bgc0': profile.color || '#718096' } as CSSProperties}
                                        title={profile.color}
                                    />
                                </td>
                                <td className="admin-qp-td">
                                    <span
                                        className="admin-d-inline-flex-ai-center-gap-4-p-2px-8px-radius-12-fs-11-fw-500-bgc-dyn-col-dyn"
                                        style={{ '--admin-bgc0': profile.is_active !== false
                                                ? 'rgba(16, 185, 129, 0.1)'
                                                : 'var(--mac-error-bg)', '--admin-col1': profile.is_active !== false ? 'var(--mac-success)' : 'var(--mac-error)' } as CSSProperties}
                                    >
                                        {profile.is_active !== false ? t('admin2.qp_status_active') : t('admin2.qp_status_hidden')}
                                    </span>{' '}
                                    {profile.effective_availability?.reason_codes?.includes('parent_conflict') && (
                                        <span
                                            className="admin-field-error-xs"
                                            role="status"
                                        >
                                            {t('admin2.qp_parent_repair_status_conflict')}
                                        </span>
                                    )}{' '}
                                    <span
                                        className="admin-d-inline-flex-ai-center-gap-4-p-2px-8px-radius-12-fs-11-fw-500-bgc-dyn-col-dyn"
                                        style={{ '--admin-bgc0': profile.show_on_qr_page === true
                                            ? 'var(--mac-info-bg, transparent)'
                                            : 'var(--mac-bg-tertiary, transparent)', '--admin-col1': profile.show_on_qr_page === true ? 'var(--mac-info, currentColor)' : 'var(--mac-text-secondary, currentColor)' } as CSSProperties}
                                    >
                                        {profile.show_on_qr_page === true
                                            ? t('admin2.qp_status_qr_configured')
                                            : t('admin2.qp_status_qr_unpublished')}
                                    </span>
                                    {profile.show_on_qr_page === true && (() => {
                                        const isAvailable = profile.effective_availability?.is_available;
                                        const availabilityLabel = isAvailable === true
                                            ? t('admin2.qp_status_effective_available')
                                            : isAvailable === false
                                                ? t('admin2.qp_status_effective_unavailable')
                                                : t('admin2.qp_status_effective_unknown');
                                        const availabilityStyle = isAvailable === true
                                            ? { '--admin-bgc0': 'var(--mac-success-bg, transparent)', '--admin-col1': 'var(--mac-success, currentColor)' }
                                            : isAvailable === false
                                                ? { '--admin-bgc0': 'var(--mac-error-bg, transparent)', '--admin-col1': 'var(--mac-error, currentColor)' }
                                                : { '--admin-bgc0': 'var(--mac-bg-tertiary, transparent)', '--admin-col1': 'var(--mac-text-secondary, currentColor)' };

                                        return (
                                            <span
                                                className="admin-d-inline-flex-ai-center-gap-4-p-2px-8px-radius-12-fs-11-fw-500-bgc-dyn-col-dyn"
                                                style={availabilityStyle as CSSProperties}
                                                title={t('admin2.qp_status_effective_availability_help')}
                                            >
                                                {availabilityLabel}
                                            </span>
                                        );
                                    })()}
                                </td>
                                <td className="admin-qp-td">
                                    <div className="admin-d-flex-gap-4">
                                        <button
                                            className="admin-qp-icon-button"
                                            onClick={() => handleToggleActive(profile)}
                                            aria-label={profile.is_active !== false ? t('admin2.qp_archive_row_aria', { name: getQueueProfileDisplayName(profile) }) : t('admin2.qp_restore_row_aria', { name: getQueueProfileDisplayName(profile) })}
                                            title={profile.is_active !== false ? t('admin2.qp_archive_profile_btn') : t('admin2.qp_restore_profile_btn')}
                                            disabled={saving}
                                        >
                                            {profile.is_active !== false ? <Archive size={16} /> : <ArchiveRestore size={16} />}
                                        </button>
                                        <button
                                            className="admin-qp-icon-button"
                                            onClick={() => setEditingProfile(profile)}
                                            aria-label={profile.show_on_qr_page === true
                                                ? t('admin2.qp_edit_row_aria', { name: getQueueProfileDisplayName(profile) })
                                                : t('admin2.qp_edit_publish_row_aria', { name: getQueueProfileDisplayName(profile) })}
                                            title={profile.show_on_qr_page === true
                                                ? t('admin2.qp_edit_btn')
                                                : t('admin2.qp_edit_publish_btn')}
                                            disabled={saving}
                                        >
                                            <Edit2 size={16} />
                                        </button>
                                        {profile.effective_availability?.reason_codes?.includes('parent_conflict') && (
                                            <button
                                                type="button"
                                                className="admin-qp-button"
                                                onClick={() => openParentRepair(profile.key)}
                                                disabled={saving || parentRepairApplying}
                                            >
                                                {t('admin2.qp_parent_repair_open')}
                                            </button>
                                        )}
                                        <button
                                            className="admin-p-6-bd-none-radius-6-bgc-transparent-cur-pointer-secondary-d-inline-flex-ai-center-jc-center-EF4444"
                                            onClick={() => handleDelete(profile.key)}
                                            aria-label={t('admin2.qp_delete_row_aria', { name: getQueueProfileDisplayName(profile) })}
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
                        onSubmit={(data: Record<string, unknown>) => handleUpdate(editingProfile.key, data)}
                        onCancel={() => setEditingProfile(null)}
                        saving={saving}
                        isDark={isDark}
                        isEdit
                        departments={departments}
                    />
                )}
                {parentRepairProfileKey && (
                    <QueueProfileParentRepairDialog
                        profileKey={parentRepairProfileKey}
                        preview={parentRepairPreview}
                        loading={parentRepairLoading}
                        applying={parentRepairApplying}
                        error={parentRepairError}
                        confirmTarget={confirmParentRepairTarget}
                        confirmServices={confirmParentRepairServices}
                        confirmPublicAccess={confirmParentRepairPublicAccess}
                        onConfirmTarget={setConfirmParentRepairTarget}
                        onConfirmServices={setConfirmParentRepairServices}
                        onConfirmPublicAccess={setConfirmParentRepairPublicAccess}
                        onRefresh={() => { void loadParentRepairPreview(parentRepairProfileKey); }}
                        onApply={() => { void applyParentRepair(); }}
                        onClose={closeParentRepair}
                    />
                )}
                {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
                {confirmDialog}
            </div>
        </div>
    );
};
interface QueueProfileParentRepairDialogProps {
    profileKey: string;
    preview: QueueProfileParentRepairPreview | null;
    loading: boolean;
    applying: boolean;
    error: string | null;
    confirmTarget: boolean;
    confirmServices: boolean;
    confirmPublicAccess: boolean;
    onConfirmTarget: (checked: boolean) => void;
    onConfirmServices: (checked: boolean) => void;
    onConfirmPublicAccess: (checked: boolean) => void;
    onRefresh: () => void;
    onApply: () => void;
    onClose: () => void;
}

const QueueProfileParentRepairDialog = ({
    profileKey,
    preview,
    loading,
    applying,
    error,
    confirmTarget,
    confirmServices,
    confirmPublicAccess,
    onConfirmTarget,
    onConfirmServices,
    onConfirmPublicAccess,
    onRefresh,
    onApply,
    onClose,
}: QueueProfileParentRepairDialogProps) => {
    const { t: rawT } = useTranslation();
    const t = rawT;
    const dialogContentRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const previouslyFocused = document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null;
        const dialogContent = dialogContentRef.current;
        if (!dialogContent) return;
        const firstFocusable = dialogContent.querySelector<HTMLElement>(
            'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        (firstFocusable || dialogContent).focus();
        return () => {
            if (previouslyFocused?.isConnected) previouslyFocused.focus();
        };
    }, []);

    const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
        if (event.key === 'Escape') {
            event.preventDefault();
            if (!applying) onClose();
            return;
        }
        if (event.key !== 'Tab') return;
        const content = dialogContentRef.current;
        if (!content) return;
        const focusable = Array.from(content.querySelectorAll<HTMLElement>(
            'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ));
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (!first || !last) {
            event.preventDefault();
            content.focus();
        } else if (event.shiftKey && (document.activeElement === first || !content.contains(document.activeElement))) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !content.contains(document.activeElement))) {
            event.preventDefault();
            first.focus();
        }
    };

    const requiredConfirmationsPresent = Boolean(
        preview
        && confirmTarget
        && (!preview.service_scope_confirmation_required || confirmServices)
        && (!preview.public_access_confirmation_required || confirmPublicAccess),
    );
    const proposedReasonLabels = (preview?.proposed_reason_codes || []).map((reason) => {
        if (reason === 'parent_inactive') return t('admin2.qp_parent_repair_reason_parent_inactive');
        if (reason === 'manual_archived') return t('admin2.qp_parent_repair_reason_manual_archived');
        return reason;
    });

    return (
        <Dialog
            open
            onClose={() => { if (!applying) onClose(); }}
            onKeyDown={handleKeyDown}
            aria-labelledby="queue-profile-parent-repair-title"
            className="admin-modal-body-catalog"
            maxWidth="md"
        >
            <div ref={dialogContentRef} className="admin-qp-modal" tabIndex={-1}>
                <div className="admin-qp-modal-header">
                    <h3 className="admin-qp-modal-title" id="queue-profile-parent-repair-title">
                        {t('admin2.qp_parent_repair_title')}
                    </h3>
                    <button
                        type="button"
                        className="admin-qp-close-button"
                        onClick={onClose}
                        aria-label={t('admin2.qp_close_form_aria')}
                        disabled={applying}
                    >
                        <X size={20} />
                    </button>
                </div>
                <div className="admin-p-20">
                    <p>{t('admin2.qp_parent_repair_intro', { key: profileKey })}</p>
                    {loading && <p role="status" aria-live="polite">{t('admin2.qp_parent_repair_loading')}</p>}
                    {error && <div className="admin-qp-error" role="alert">{error}</div>}
                    {!loading && !preview && !error && (
                        <p role="status">{t('admin2.qp_parent_repair_no_preview')}</p>
                    )}
                    {preview && (
                        <>
                            <section aria-label={t('admin2.qp_parent_repair_current_binding')}>
                                <h4>{t('admin2.qp_parent_repair_current_binding')}</h4>
                                <ul>
                                    {preview.parent_references.map((parent) => (
                                        <li key={`${parent.source}:${parent.department_key}`}>
                                            <strong>{parent.source === 'profile_key'
                                                ? t('admin2.qp_parent_repair_profile_key_parent')
                                                : t('admin2.qp_parent_repair_explicit_parent')}</strong>{' '}
                                            {parent.department_name_ru || parent.department_key} ({parent.department_key}) —{' '}
                                            {parent.exists
                                                ? parent.active
                                                    ? t('admin2.qp_parent_repair_department_active')
                                                    : t('admin2.qp_parent_repair_department_inactive')
                                                : t('admin2.qp_parent_repair_department_missing')}
                                        </li>
                                    ))}
                                </ul>
                            </section>
                            {preview.target && (
                                <section aria-label={t('admin2.qp_parent_repair_target')}>
                                    <h4>{t('admin2.qp_parent_repair_target')}</h4>
                                    <p>
                                        <strong>{preview.target.department_name_ru}</strong> ({preview.target.department_key}) —{' '}
                                        {preview.target.active
                                            ? t('admin2.qp_parent_repair_department_active')
                                            : t('admin2.qp_parent_repair_department_inactive')}
                                    </p>
                                </section>
                            )}
                            <section aria-label={t('admin2.qp_parent_repair_impact')}>
                                <h4>{t('admin2.qp_parent_repair_impact')}</h4>
                                <p>{t('admin2.qp_parent_repair_proposed_availability', {
                                    availability: preview.proposed_availability_state === 'available'
                                        ? t('admin2.qp_parent_repair_available')
                                        : t('admin2.qp_parent_repair_unavailable'),
                                })}</p>
                                {proposedReasonLabels.length > 0 && (
                                    <p>{t('admin2.qp_parent_repair_unavailable_reasons', {
                                        reasons: proposedReasonLabels.join(', '),
                                    })}</p>
                                )}
                                <ul>
                                    <li>{t('admin2.qp_parent_repair_link_summary', {
                                        services: preview.links.services,
                                        departmentServices: preview.links.department_services,
                                        queues: preview.links.daily_queues,
                                        waiting: preview.links.entries_waiting,
                                        addresses: preview.links.active_public_addresses,
                                    })}</li>
                                    <li>{t('admin2.qp_parent_repair_service_scope_delta', {
                                        removed: preview.services_removed_from_parent_scope,
                                        added: preview.services_added_to_parent_scope,
                                    })}</li>
                                    <li>{t('admin2.qp_parent_repair_qr_bookable', {
                                        value: preview.qr_catalog_would_be_bookable
                                            ? t('admin2.qp_parent_repair_yes')
                                            : t('admin2.qp_parent_repair_no'),
                                    })}</li>
                                    <li>{t('admin2.qp_parent_repair_address_bookable', {
                                        value: preview.permanent_address_would_be_bookable
                                            ? t('admin2.qp_parent_repair_yes')
                                            : t('admin2.qp_parent_repair_no'),
                                    })}</li>
                                </ul>
                            </section>
                            {!preview.can_apply && (
                                <p role="alert" className="admin-qp-error">
                                    {preview.blocker_code === 'own_key_department_missing'
                                        ? t('admin2.qp_parent_repair_missing_target')
                                        : t('admin2.qp_parent_repair_not_applicable')}
                                </p>
                            )}
                            {preview.can_apply && (
                                <div className="admin-d-grid-gap-12">
                                    <label className="admin-d-flex-ai-center-gap-8">
                                        <input
                                            type="checkbox"
                                            aria-label={t('admin2.qp_parent_repair_confirm_target', {
                                                department: preview.target?.department_name_ru || preview.profile_key,
                                                key: preview.target?.department_key || preview.profile_key,
                                            })}
                                            checked={confirmTarget}
                                            onChange={(event) => onConfirmTarget(event.target.checked)}
                                        />
                                        {t('admin2.qp_parent_repair_confirm_target', {
                                            department: preview.target?.department_name_ru || preview.profile_key,
                                            key: preview.target?.department_key || preview.profile_key,
                                        })}
                                    </label>
                                    {preview.service_scope_confirmation_required && (
                                        <label className="admin-d-flex-ai-center-gap-8">
                                            <input
                                                type="checkbox"
                                                aria-label={t('admin2.qp_parent_repair_confirm_services', {
                                                    removed: preview.services_removed_from_parent_scope,
                                                    added: preview.services_added_to_parent_scope,
                                                })}
                                                checked={confirmServices}
                                                onChange={(event) => onConfirmServices(event.target.checked)}
                                            />
                                            {t('admin2.qp_parent_repair_confirm_services', {
                                                removed: preview.services_removed_from_parent_scope,
                                                added: preview.services_added_to_parent_scope,
                                            })}
                                        </label>
                                    )}
                                    {preview.public_access_confirmation_required && (
                                        <label className="admin-d-flex-ai-center-gap-8">
                                            <input
                                                type="checkbox"
                                                aria-label={t('admin2.qp_parent_repair_confirm_public')}
                                                checked={confirmPublicAccess}
                                                onChange={(event) => onConfirmPublicAccess(event.target.checked)}
                                            />
                                            {t('admin2.qp_parent_repair_confirm_public')}
                                        </label>
                                    )}
                                </div>
                            )}
                        </>
                    )}
                </div>
                <div className="admin-d-flex-gap-8-jc-flex-end-p-12-20-bd-top-1px-solid-var-mac-bo">
                    <button type="button" className="admin-qp-button" onClick={onRefresh} disabled={loading || applying}>
                        {t('admin2.qp_parent_repair_refresh')}
                    </button>
                    <button type="button" className="admin-qp-button" onClick={onClose} disabled={applying}>
                        {t('admin2.cancel')}
                    </button>
                    <button
                        type="button"
                        className="admin-qp-primary-button"
                        onClick={onApply}
                        disabled={loading || applying || !preview?.can_apply || !preview.preview_token || !requiredConfirmationsPresent}
                    >
                        {applying ? t('admin2.qp_parent_repair_applying') : t('admin2.qp_parent_repair_apply')}
                    </button>
                </div>
            </div>
        </Dialog>
    );
};

// Profile form component with show_on_qr_page support
const ProfileForm = ({ profile, onSubmit, onCancel, saving, isDark, isEdit = false, departments = [] }: { profile?: Record<string, unknown>; onSubmit?: (data: Record<string, unknown>) => void | Promise<void>; onCancel?: () => void; saving?: boolean; isDark?: boolean; isEdit?: boolean; departments?: DepartmentDto[] }) => {
    const { t: rawT } = useTranslation();
  const t = rawT;
    const availableIcons = getAvailableIcons(t);
    const [formData, setFormData] = useState<Record<string, unknown>>({
        key: profile?.key || '',
        title: profile?.title || '',
        title_ru: profile?.title_ru || '',
        queue_tags: ((profile?.queue_tags as unknown[]) || []).join(', '),
        department_key: profile?.department_key || '',
        display_order: profile?.order || 0,
        is_active: profile?.is_active !== false,
        show_on_qr_page: isEdit ? profile?.show_on_qr_page !== false : false, // New profiles remain hidden until a later explicit edit
        icon: profile?.icon || 'Package',
        color: profile?.color || '#718096',
    });
    const dialogContentRef = useRef<HTMLDivElement>(null);
    const wasSavingRef = useRef(Boolean(saving));

    useEffect(() => {
        const wasSaving = wasSavingRef.current;
        wasSavingRef.current = Boolean(saving);
        if (!wasSaving || saving) return;

        const dialogContent = dialogContentRef.current;
        if (!dialogContent || dialogContent.contains(document.activeElement)) return;

        const firstFormControl = dialogContent.querySelector<HTMLElement>(
            'form input:not([type="hidden"]):not([disabled]), form select:not([disabled]), form textarea:not([disabled])',
        );
        const firstFocusable = dialogContent.querySelector<HTMLElement>(
            'button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        (firstFormControl || firstFocusable || dialogContent).focus();
    }, [saving]);

    useEffect(() => {
        const previouslyFocused = document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null;
        const dialogContent = dialogContentRef.current;
        if (!dialogContent) return;

        const firstFormControl = dialogContent.querySelector<HTMLElement>(
            'form input:not([type="hidden"]):not([disabled]), form select:not([disabled]), form textarea:not([disabled])',
        );
        const firstFocusable = dialogContent.querySelector<HTMLElement>(
            'button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        (firstFormControl || firstFocusable || dialogContent).focus();

        return () => {
            if (previouslyFocused?.isConnected) previouslyFocused.focus();
        };
    }, []);

    const handleDialogKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
        if (event.key === 'Escape') {
            event.preventDefault();
            onCancel?.();
            return;
        }

        if (event.key !== 'Tab') return;

        const dialogContent = dialogContentRef.current;
        if (!dialogContent) return;

        const focusable = Array.from(dialogContent.querySelectorAll<HTMLElement>(
            'button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ));
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = document.activeElement;

        if (!first || !last) {
            event.preventDefault();
            dialogContent.focus();
        } else if (event.shiftKey && (active === first || !dialogContent.contains(active))) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && (active === last || !dialogContent.contains(active))) {
            event.preventDefault();
            first.focus();
        }
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (onSubmit) {
            onSubmit({
                ...formData,
                queue_tags: String(formData.queue_tags || '').split(',').map((t: string) => t.trim()).filter(Boolean),
                display_order: parseInt(String(formData.display_order), 10) || 0,
            });
        }
    };
    return (
        <Dialog
            open
            onClose={() => onCancel?.()}
            onKeyDown={handleDialogKeyDown}
            aria-labelledby="queue-profile-dialog-title"
            maxWidth="sm"
            style={{
                maxWidth: '500px',
                maxHeight: '90vh',
                overflowY: 'auto',
                padding: 0,
            }}
        >
            <div
                ref={dialogContentRef}
                className="admin-qp-modal"
                tabIndex={-1}
            >
                <div className="admin-qp-modal-header">
                    <h3 className="admin-qp-modal-title" id="queue-profile-dialog-title">
                        {isEdit ? t('admin2.qp_edit_title') : t('admin2.qp_create_title')}
                    </h3>
                    <button
                        type="button"
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
                            <label className="admin-qp-label" htmlFor="queue-profile-key">{t('admin2.qp_key_label')}</label>
                            <Input
                                id="queue-profile-key"
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
                            <label className="admin-qp-label" htmlFor="queue-profile-title-en">{t('admin2.qp_title_en_label')}</label>
                            <Input
                                id="queue-profile-title-en"
                                className="admin-qp-input" style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}
                                aria-label={t('admin2.qp_title_en_aria')}
                                value={formData.title as string}
                                onChange={e => setFormData({ ...formData, title: e.target.value })}
                                placeholder="Cardiology"
                                required
                            />
                        </div>
                        <div className="admin-mb-16-flex-1">
                            <label className="admin-qp-label" htmlFor="queue-profile-title-ru">{t('admin2.qp_title_ru_label')}</label>
                            <Input
                                id="queue-profile-title-ru"
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
                        <label className="admin-qp-label" htmlFor="queue-profile-tags">Queue Tags</label>
                        <Input
                            id="queue-profile-tags"
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
                        <label className="admin-qp-label" htmlFor="queue-profile-department">{t('admin2.qp_department_label')}</label>
                        <select
                            id="queue-profile-department"
                            className="admin-w-100pct-p-10px-12px-radius-8-bd-1px-solid-var-mac-bo-primary-fs-14-bsz-border-box-w-100-bgc-dyn"
                            style={{ '--admin-bgc0': isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)' } as CSSProperties}
                            value={formData.department_key as string}
                            onChange={e => setFormData({ ...formData, department_key: e.target.value })}
                        >
                            <option value="">{t('admin2.qp_department_none')}</option>
                            {departments.map((d) => (
                                <option key={d.key} value={d.key}>{d.name_ru || d.key}</option>
                            ))}
                        </select>
                        <div className="admin-qp-hint">{t('admin2.qp_department_hint')}</div>
                    </div>

                    {/* Order */}
                    <div className="admin-qp-field">
                        <label className="admin-qp-label" htmlFor="queue-profile-order">{t('admin2.qp_order_label')}</label>
                        <Input
                            id="queue-profile-order"
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
                        <div className="admin-qp-label" id="queue-profile-icon-label">{t('admin2.qp_icon_label')}</div>
                        <div className="admin-qp-icon-grid" role="group" aria-labelledby="queue-profile-icon-label">
                            {availableIcons.map(icon => {
                                const IconComponent = icon.component;
                                const isSelected = formData.icon === icon.name;
                                return (
                                    <button
                                        key={icon.name}
                                        type="button"
                                        aria-pressed={isSelected}
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
                        <div className="admin-qp-label" id="queue-profile-color-label">{t('admin2.qp_color_label')}</div>
                        <div className="admin-qp-color-grid" role="group" aria-labelledby="queue-profile-color-label">
                            {QUEUE_PROFILE_COLOR_PRESETS.map(color => (
                                <button
                                    key={color}
                                    type="button"
                                    aria-pressed={formData.color === color}
                                    className="admin-w-32-h-32-radius-50pct-bd-3px-solid-transparen-cur-pointer-tr-all-0-2s-bgc-dyn-bd-c-dyn-bsh-dyn" style={{ '--admin-bgc0': color, '--admin-bd-c1': formData.color === color ? 'white' : 'transparent', '--admin-bsh2': formData.color === color ? `0 0 0 2px ${color}` : 'none' } as CSSProperties}
                                    onClick={() => setFormData({ ...formData, color })}
                                    aria-label={t('admin2.qp_color_pick_aria', { color })}
                                    title={color}
                                />
                            ))}
                            <Input
                                id="queue-profile-custom-color"
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
                            <Checkbox aria-label={t('admin2.qp_qr_checkbox_aria')} checked={Boolean(formData.show_on_qr_page as boolean)} disabled={!isEdit} onChange={(checked: boolean) => setFormData({ ...formData, show_on_qr_page: checked })}
                            />
                            <span className="admin-qp-label">{t('admin2.qp_qr_label')}</span>
                        </label>
                        <div className="admin-fs-12-secondary-mt-4-ml-24">
                            {t(isEdit ? 'admin2.qp_qr_hint' : 'admin2.qp_qr_create_hint')}
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
        </Dialog>
    );
};




export default QueueProfilesManager;
