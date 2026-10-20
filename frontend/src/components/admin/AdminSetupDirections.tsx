import { useTranslation } from '../../i18n/useTranslation';
/**
 * AdminSetupDirections consumes the T13 read model. It does not reconstruct
 * queue eligibility, profile ownership, or publication readiness in React.
 * QueueResource CRUD and permanent-address writes remain in their existing
 * surfaces; this page presents their backend facts and safe entry points.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
    CheckCircle2,
    CircleAlert,
    ExternalLink,
    ListChecks,
    RefreshCw,
    RotateCcw,
    XCircle,
} from 'lucide-react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
    Badge,
    Button,
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '../ui/macos';
import QueueResourceManager from './QueueResourceManager';
import PermanentDirectionQr from './PermanentDirectionQr';
import type {
    QueueAdminDirections,
    QueueDirectionNextAction,
    QueueAdminDirection,
} from '../../types/domain/adminQueueDirections';
import { fetchAdminQueueDirections, fetchDirectionEntryMethods } from '../../api/queueDirections';
import {
    type ChecklistProfileDto,
    type ChecklistServiceDto,
    readPermanentAddressSupported,
} from './setupDirectionsReadiness';

type ScreenView = QueueSetupSection;

export type QueueSetupSection = 'checklist' | 'resources';
export type QueueSetupEditorDestination = 'service-catalog' | 'queue-profiles' | 'user-management';
export type QueueSetupEntityRef =
    | { kind: 'queue_profile' | 'queue_tag'; key: string }
    | { kind: 'service' | 'doctor' | 'queue_resource'; id: number };

/** Typed, allowlisted context carried from setup into an existing editor. */
export interface QueueSetupReturnContext {
    version: 1;
    destination: QueueSetupEditorDestination;
    profileKey: string | null;
    section: QueueSetupSection;
    day: string | null;
    entity: QueueSetupEntityRef | null;
}

const QUEUE_SETUP_RETURN_MARKER = 'queue-directions-v1';
const validQueueSetupSections = new Set<QueueSetupSection>(['checklist', 'resources']);

const isIsoCalendarDay = (value: string): boolean => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000-')) return false;
    const parsed = new Date(`${value}T00:00:00.000Z`);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
};

const isSafeProfileKey = (value: string): boolean =>
    value.length > 0 && value.length <= 128 && value.trim() === value &&
    !Array.from(value).some((character) => {
        const code = character.charCodeAt(0);
        return code <= 0x1f || code === 0x7f;
    });

const readSetupPageContext = (search: string) => {
    const params = new URLSearchParams(search);
    const rawSection = params.getAll('section').length === 1 ? params.get('section') : null;
    const rawDay = params.getAll('day').length === 1 ? params.get('day') : null;
    const rawProfileKey = params.getAll('profile').length === 1 ? params.get('profile') : null;
    return {
        section: validQueueSetupSections.has(rawSection as QueueSetupSection)
            ? rawSection as QueueSetupSection
            : 'checklist' as const,
        day: rawDay && isIsoCalendarDay(rawDay) ? rawDay : '',
        profileKey: rawProfileKey && isSafeProfileKey(rawProfileKey) ? rawProfileKey : null,
    };
};

const serializeQueueSetupEditorLink = (context: QueueSetupReturnContext): string => {
    const params = new URLSearchParams();
    params.set('setupReturn', QUEUE_SETUP_RETURN_MARKER);
    params.set('setupSection', context.section);
    if (context.profileKey) params.set('setupProfile', context.profileKey);
    if (context.day) params.set('setupDay', context.day);
    if (context.entity) {
        params.set('setupEntityKind', context.entity.kind);
        if ('key' in context.entity) params.set('setupEntityKey', context.entity.key);
        else params.set('setupEntityId', String(context.entity.id));
    }

    const query = params.toString();
    switch (context.destination) {
        case 'service-catalog':
            return `/admin/services?servicesTab=catalog&${query}`;
        case 'queue-profiles':
            return `/admin/services?servicesTab=queue-profiles&${query}`;
        case 'user-management':
            return `/admin/users?${query}`;
    }
};

type QrReadState = {
    generation: number;
    status: 'loading' | 'loaded' | 'error';
    supported: boolean | null;
};

const configurationStateKeys: Record<QueueAdminDirection['configuration_state'], string> = {
    ready: 'admin2.sdx_state_ready',
    incomplete: 'admin2.sdx_state_incomplete',
    conflict: 'admin2.sdx_state_conflict',
    unavailable: 'admin2.sdx_state_unavailable',
};

const modeKeys: Record<QueueAdminDirection['resolved_mode'], string> = {
    booking: 'admin2.sdx_mode_booking',
    overview: 'admin2.sdx_mode_overview',
    unresolved: 'admin2.sdx_mode_unresolved',
};

const reasonKeys: Record<string, string> = {
    manual_archived: 'admin2.sdx_reason_manual_archived',
    parent_missing: 'admin2.sdx_reason_parent_missing',
    parent_conflict: 'admin2.sdx_reason_parent_conflict',
    parent_inactive: 'admin2.sdx_reason_parent_inactive',
    no_bookable_owner: 'admin2.sdx_reason_no_bookable_owner',
    mixed_direction_targets: 'admin2.sdx_reason_mixed_targets',
    overview_must_remain_internal: 'admin2.sdx_reason_overview_internal',
    not_published: 'admin2.sdx_reason_not_published',
    public_target_not_selectable: 'admin2.sdx_reason_public_target',
    publish_target_not_selectable: 'admin2.sdx_reason_publish_target',
};

const precreateReasonKeys: Record<string, string> = {
    no_active_service: 'admin2.sdx_precreate_no_service',
    active_resource_owner: 'admin2.sdx_precreate_resource_owner',
    no_explicit_service_owner: 'admin2.sdx_precreate_no_explicit_owner',
    multiple_active_service_owners: 'admin2.sdx_precreate_multiple_owners',
    ineligible_service_owner: 'admin2.sdx_precreate_ineligible_owner',
    single_active_service_owner: 'admin2.sdx_precreate_single_owner',
    active_queue_exists: 'admin2.sdx_precreate_queue_exists',
};

const actionLabelKeys: Record<QueueDirectionNextAction['kind'], string> = {
    restore_profile: 'admin2.sdx_action_restore_profile',
    configure_ownership: 'admin2.sdx_action_configure_ownership',
    review_configuration: 'admin2.sdx_action_review_configuration',
    publish_profile: 'admin2.sdx_action_publish_profile',
    provision_permanent_address: 'admin2.sdx_action_provision_address',
};

const AdminSetupDirections = () => {
    const { t, language } = useTranslation();
    const location = useLocation();
    const navigate = useNavigate();
    const setupPageContext = readSetupPageContext(location.search);
    const view = setupPageContext.section;
    const selectedDay = setupPageContext.day;
    const selectedProfileKey = setupPageContext.profileKey;
    const [services, setServices] = useState<ChecklistServiceDto[]>([]);
    const [profiles, setProfiles] = useState<ChecklistProfileDto[]>([]);
    const [directions, setDirections] = useState<QueueAdminDirections | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [resourceLoading, setResourceLoading] = useState(false);
    const [resourceError, setResourceError] = useState<string | null>(null);
    const [resourceDataLoaded, setResourceDataLoaded] = useState(false);
    const [expandedQrProfileKey, setExpandedQrProfileKey] = useState<string | null>(null);
    const [qrReadStates, setQrReadStates] = useState<Record<string, QrReadState>>({});
    const qrReadStatesRef = useRef<Record<string, QrReadState>>({});
    const qrInFlightRef = useRef(new Map<string, { generation: number; promise: Promise<void> }>());
    const qrQueueRef = useRef<Promise<void>>(Promise.resolve());
    const coreRequestRef = useRef(0);
    const resourceRequestRef = useRef(0);
    const supportGenerationRef = useRef(0);
    const [supportGeneration, setSupportGeneration] = useState(0);

    const updateSetupPageContext = useCallback((patch: Partial<{
        profileKey: string | null;
        section: ScreenView;
        day: string | null;
    }>, replace = false) => {
        const current = readSetupPageContext(location.search);
        const hasProfilePatch = Object.prototype.hasOwnProperty.call(patch, 'profileKey');
        const hasDayPatch = Object.prototype.hasOwnProperty.call(patch, 'day');
        const nextProfileKey = hasProfilePatch ? patch.profileKey || null : current.profileKey;
        const nextSection = patch.section || current.section;
        const nextDay = hasDayPatch ? patch.day || '' : current.day;
        const params = new URLSearchParams();
        if (nextProfileKey) params.set('profile', nextProfileKey);
        params.set('section', nextSection);
        if (nextDay) params.set('day', nextDay);
        const search = params.toString();
        navigate({ pathname: location.pathname, search: search ? `?${search}` : '' }, { replace });
    }, [location.pathname, location.search, navigate]);

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        let changed = false;
        const rawSection = params.get('section');
        const rawDay = params.get('day');
        const rawProfile = params.get('profile');
        if (params.getAll('section').length > 1 ||
            (rawSection !== null && !validQueueSetupSections.has(rawSection as QueueSetupSection))) {
            params.set('section', 'checklist');
            changed = true;
        }
        if (params.getAll('day').length > 1 || (rawDay !== null && !isIsoCalendarDay(rawDay))) {
            params.delete('day');
            changed = true;
        }
        if (params.getAll('profile').length > 1 || (rawProfile !== null && !isSafeProfileKey(rawProfile))) {
            params.delete('profile');
            changed = true;
        }
        if (changed) {
            const search = params.toString();
            navigate({ pathname: location.pathname, search: search ? `?${search}` : '' }, { replace: true });
        }
    }, [location.pathname, location.search, navigate]);

    const tRef = useRef(t);
    useEffect(() => {
        tRef.current = t;
    });

    const writeQrReadState = useCallback((profileKey: string, state: QrReadState) => {
        qrReadStatesRef.current = { ...qrReadStatesRef.current, [profileKey]: state };
        setQrReadStates((previous) => ({ ...previous, [profileKey]: state }));
    }, []);

    const loadCore = useCallback(async (day?: string) => {
        const requestId = ++coreRequestRef.current;
        const nextGeneration = supportGenerationRef.current + 1;
        supportGenerationRef.current = nextGeneration;
        setSupportGeneration(nextGeneration);
        qrReadStatesRef.current = {};
        setQrReadStates({});
        setExpandedQrProfileKey(null);
        setLoading(true);
        setError(null);
        try {
            const response = await fetchAdminQueueDirections(day);
            if (requestId !== coreRequestRef.current) return;
            setDirections(response);
        } catch (err) {
            if (requestId !== coreRequestRef.current) return;
            logger.error('Error loading setup directions data:', err);
            setError(tRef.current('admin2.sdx_load_failed'));
        } finally {
            if (requestId === coreRequestRef.current) setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadCore(selectedDay || undefined);
        return () => {
            coreRequestRef.current += 1;
        };
    }, [loadCore, selectedDay]);

    const loadResourceData = useCallback(async (force = false) => {
        if (resourceDataLoaded && !force) return;
        const requestId = ++resourceRequestRef.current;
        setResourceLoading(true);
        setResourceError(null);
        try {
            const [serviceResponse, profileResponse] = await Promise.all([
                api.get('/services?limit=1000') as Promise<{ data: unknown }>,
                api.get('/queues/profiles?active_only=false') as Promise<{
                    data: { profiles?: ChecklistProfileDto[] };
                }>,
            ]);
            if (requestId !== resourceRequestRef.current) return;
            setServices(
                Array.isArray(serviceResponse.data)
                    ? serviceResponse.data as ChecklistServiceDto[]
                    : [],
            );
            setProfiles(profileResponse.data?.profiles || []);
            setResourceDataLoaded(true);
        } catch (err) {
            if (requestId !== resourceRequestRef.current) return;
            logger.error('Error loading queue resource editor data:', err);
            setResourceError(tRef.current('admin2.sdx_resource_load_failed'));
        } finally {
            if (requestId === resourceRequestRef.current) setResourceLoading(false);
        }
    }, [resourceDataLoaded]);

    useEffect(() => {
        if (view === 'resources') void loadResourceData();
    }, [loadResourceData, view]);

    const ensureQrRead = useCallback((profileKey: string, retry = false) => {
        const generation = supportGenerationRef.current;
        const current = qrReadStatesRef.current[profileKey];
        if (!retry && current?.generation === generation && current.status !== 'error') return;
        const inFlight = qrInFlightRef.current.get(profileKey);
        if (!retry && inFlight?.generation === generation) return;

        writeQrReadState(profileKey, { generation, status: 'loading', supported: null });
        const queued = qrQueueRef.current.then(async () => {
            if (generation !== supportGenerationRef.current) return null;
            return fetchDirectionEntryMethods(profileKey);
        });
        qrQueueRef.current = queued.then(() => undefined, () => undefined);
        const request = queued.then(
            (methods) => {
                if (!methods || generation !== supportGenerationRef.current) return;
                writeQrReadState(profileKey, {
                    generation,
                    status: 'loaded',
                    supported: readPermanentAddressSupported(methods),
                });
            },
            (err) => {
                if (generation !== supportGenerationRef.current) return;
                logger.warn('entry-methods unavailable for profile ' + profileKey, err);
                writeQrReadState(profileKey, { generation, status: 'error', supported: null });
            },
        );
        qrInFlightRef.current.set(profileKey, { generation, promise: request });
        void request.finally(() => {
            if (qrInFlightRef.current.get(profileKey)?.promise === request) {
                qrInFlightRef.current.delete(profileKey);
            }
        });
    }, [writeQrReadState]);

    const handleQrSupportedChange = useCallback(
        (profileKey: string, supported: boolean | null, generation?: number) => {
            const issuedGeneration = generation ?? supportGenerationRef.current;
            if (issuedGeneration !== supportGenerationRef.current) return;
            writeQrReadState(profileKey, { generation: issuedGeneration, status: 'loaded', supported });
        },
        [writeQrReadState],
    );

    const handleAddressProvisioned = useCallback((profileKey: string, generation?: number) => {
        if ((generation ?? supportGenerationRef.current) !== supportGenerationRef.current) return;
        setDirections((previous) => previous ? {
            ...previous,
            directions: (previous.directions || []).map((direction) =>
                direction.profile.key === profileKey
                    ? {
                        ...direction,
                        permanent_address_exists: true,
                        allowed_next_actions: (direction.allowed_next_actions || []).filter(
                            (action) => action.kind !== 'provision_permanent_address',
                        ),
                    }
                    : direction,
            ),
        } : previous);
    }, []);

    const openResources = useCallback(() => updateSetupPageContext({ section: 'resources' }), [updateSetupPageContext]);
    const openChecklist = useCallback(() => updateSetupPageContext({ section: 'checklist' }), [updateSetupPageContext]);

    const statusIcon = (ready: boolean | null) => {
        const cls =
            ready === true
                ? 'admin-sdx-status-ok'
                : ready === false
                  ? 'admin-sdx-status-err'
                  : 'admin-sdx-status-unknown';
        const Icon = ready === true ? CheckCircle2 : ready === false ? XCircle : CircleAlert;
        return (
            <span className={cls}>
                <Icon size={15} aria-hidden />
            </span>
        );
    };

    const directionTitle = (direction: QueueAdminDirection) =>
        (language === 'ru' ? direction.profile.title_ru : null) ||
        direction.profile.title ||
        (direction.profile.queue_tags || []).join(', ');

    const reasonLabel = (code: string) =>
        t(reasonKeys[code] || 'admin2.sdx_reason_unknown');

    const toggleQr = (direction: QueueAdminDirection) => {
        const profileKey = direction.profile.key;
        if (expandedQrProfileKey === profileKey) {
            setExpandedQrProfileKey(null);
            return;
        }
        setExpandedQrProfileKey(profileKey);
        if (direction.permanent_address_exists && !direction.public_availability) {
            handleQrSupportedChange(profileKey, false);
            return;
        }
        ensureQrRead(profileKey);
    };

    const queueTagEntity = (action: QueueDirectionNextAction): QueueSetupEntityRef | null => {
        const key = action.entity_key || '';
        return key ? { kind: 'queue_tag', key } : null;
    };

    const editorLink = (
        destination: QueueSetupEditorDestination,
        direction: QueueAdminDirection,
        entity: QueueSetupEntityRef | null,
    ) => serializeQueueSetupEditorLink({
        version: 1,
        destination,
        profileKey: direction.profile.key,
        section: view,
        day: selectedDay || null,
        entity,
    });
    const setupEditorLink = (destination: QueueSetupEditorDestination) => serializeQueueSetupEditorLink({
        version: 1,
        destination,
        profileKey: null,
        section: view,
        day: selectedDay || null,
        entity: null,
    });

    const profileSelectionLink = (profileKey: string) => {
        const params = new URLSearchParams();
        params.set('section', view);
        params.set('profile', profileKey);
        if (selectedDay) params.set('day', selectedDay);
        return { pathname: location.pathname, search: '?' + params.toString() };
    };

    const renderActionControl = (action: QueueDirectionNextAction, direction: QueueAdminDirection) => {
        const label = t(actionLabelKeys[action.kind]);
        if (action.kind === 'provision_permanent_address') {
            return (
                <Button key={`${action.kind}:${action.entity_key || ''}`} variant="secondary" size="sm" onClick={() => toggleQr(direction)}>
                    {label}
                </Button>
            );
        }
        if (action.kind === 'configure_ownership' || (action.kind === 'review_configuration' && action.entity_type === 'queue_tag')) {
            const entity = queueTagEntity(action);
            return (
                <div key={`${action.kind}:${action.entity_key || ''}`} className="admin-sdx-action-list" data-testid="setup-action-editors">
                    <span className="admin-sdx-muted">{label}</span>
                    <Link className="admin-sdx-link" to={editorLink('service-catalog', direction, entity)}>
                        {t('admin2.sdx_wizard_services_link')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                    </Link>
                    <Link className="admin-sdx-link" to={editorLink('user-management', direction, entity)}>
                        {t('admin2.sdx_axis_doctor_link')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                    </Link>
                    <Button variant="ghost" size="sm" onClick={openResources}>
                        {t('admin2.sdx_view_resources')}
                    </Button>
                </div>
            );
        }
        if (action.kind === 'restore_profile' || action.kind === 'publish_profile' || (action.kind === 'review_configuration' && action.entity_type === 'queue_profile')) {
            const profileKey = action.entity_key || direction.profile.key;
            return (
                <Link
                    key={`${action.kind}:${action.entity_key || ''}`}
                    className="admin-sdx-link"
                    to={editorLink('queue-profiles', direction, { kind: 'queue_profile', key: profileKey })}
                >
                    {label} <ExternalLink className="admin-sdx-icon-m" size={11} />
                </Link>
            );
        }
        return (
            <span key={`${action.kind}:${action.entity_type}:${action.entity_key || ''}`} className="admin-sdx-muted" data-testid="setup-action-without-editor">
                {label} — {t('admin2.sdx_action_no_direct_editor')}
            </span>
        );
    };

    return (
        <div className="admin-sdx-wrap" data-testid="setup-directions-screen">
            <div className="admin-sdx-header">
                <h1 className="admin-page-title" data-testid="setup-directions-heading">
                    {t('admin2.sdx_title')}
                </h1>
                <div className="admin-sdx-header-actions">
                    <Button
                        variant={view === 'checklist' ? 'primary' : 'secondary'}
                        size="sm"
                        onClick={openChecklist}
                        data-testid="setup-view-checklist"
                    >
                        <ListChecks className="admin-sdx-icon-l" size={14} />
                        {t('admin2.sdx_view_checklist')}
                    </Button>
                    <Button
                        variant={view === 'resources' ? 'primary' : 'secondary'}
                        size="sm"
                        onClick={openResources}
                        data-testid="setup-view-resources"
                    >
                        {t('admin2.sdx_view_resources')}
                    </Button>
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void loadCore(selectedDay || undefined)}
                        disabled={loading}
                        data-testid="setup-refresh"
                    >
                        <RefreshCw className="admin-sdx-icon-l" size={14} />
                        {t('admin2.sdx_refresh')}
                    </Button>
                </div>
            </div>

            <p className="admin-sdx-subtitle">{t('admin2.sdx_subtitle')}</p>

            {error && (
                <div role="alert" className="admin-sdx-alert" data-testid="setup-directions-error">
                    {error}
                    <Button variant="secondary" size="sm" onClick={() => void loadCore(selectedDay || undefined)}>
                        {t('admin2.sdx_retry')}
                    </Button>
                </div>
            )}

            {view === 'resources' ? (
                <>
                    <div className="admin-sdx-step-nav">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={openChecklist}
                            data-testid="setup-back-to-checklist"
                        >
                            <RotateCcw className="admin-sdx-icon-l" size={14} />
                            {t('admin2.sdx_back_to_checklist')}
                        </Button>
                    </div>
                    {resourceError && (
                        <div role="alert" className="admin-sdx-alert" data-testid="setup-resource-error">
                            {resourceError}
                            <Button variant="secondary" size="sm" onClick={() => void loadResourceData(true)}>
                                {t('admin2.sdx_retry')}
                            </Button>
                        </div>
                    )}
                    {resourceLoading ? (
                        <div className="admin-sdx-note" role="status">{t('admin2.sdx_loading')}</div>
                    ) : resourceDataLoaded && !resourceError ? (
                        <QueueResourceManager
                            services={services}
                            profiles={profiles}
                            onRegistryChanged={() => {
                                void loadResourceData(true);
                                void loadCore(selectedDay || undefined);
                            }}
                        />
                    ) : null}
                </>
            ) : (
                <>
                    <div className="admin-sdx-day-bar">
                        <label htmlFor="setup-directions-day">{t('admin2.sdx_day_label')}</label>
                        <input
                            id="setup-directions-day"
                            type="date"
                            aria-label={t('admin2.sdx_day_label')}
                            value={selectedDay || (!loading ? directions?.as_of_day || '' : '')}
                            onChange={(event) => updateSetupPageContext({ day: event.currentTarget.value || null })}
                            data-testid="setup-day-select"
                        />
                        <Button variant="ghost" size="sm" onClick={() => updateSetupPageContext({ day: null })} data-testid="setup-day-today">
                            {t('admin2.sdx_day_today')}
                        </Button>
                        {directions?.as_of_day && (
                            <span className="admin-sdx-muted" data-testid="setup-day-context">
                                {t('admin2.sdx_day_context', { day: directions.as_of_day })}
                            </span>
                        )}
                        {loading && directions && <span role="status">{t('admin2.sdx_refreshing')}</span>}
                    </div>

                    <Card data-testid="setup-directions-facts">
                        <CardHeader>
                            <CardTitle>{t('admin2.sdx_checklist_title')}</CardTitle>
                            <CardDescription>{t('admin2.sdx_checklist_subtitle')}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {!directions && loading ? (
                                <div className="admin-sdx-note" role="status">{t('admin2.sdx_loading')}</div>
                            ) : !directions ? (
                                <div className="admin-sdx-note" data-testid="setup-checklist-empty">
                                    {t('admin2.sdx_checklist_empty')}
                                </div>
                            ) : (directions.directions || []).length === 0 ? (
                                <div className="admin-sdx-note" data-testid="setup-checklist-empty">
                                    {t('admin2.sdx_no_profiles')}
                                </div>
                            ) : (
                                <div className="admin-sdx-rows">
                                    {(directions.directions || []).map((direction) => {
                                        const profile = direction.profile;
                                        const qrKey = profile.key;
                                        const qrState = qrReadStates[qrKey]?.generation === supportGeneration
                                            ? qrReadStates[qrKey]
                                            : undefined;
                                        const provisionAction = (direction.allowed_next_actions || []).some(
                                            (action) => action.kind === 'provision_permanent_address',
                                        );
                                        const canProvisionQr = direction.public_availability &&
                                            !direction.permanent_address_exists && provisionAction;
                                        const canOpenQr = direction.permanent_address_exists || canProvisionQr;
                                        const firstTag = profile.queue_tags?.[0] || String(profile.id);
                                        const reasons = direction.configuration_reasons || [];
                                        const targets = direction.booking_targets || [];
                                        const queues = direction.current_day_queues || [];
                                        const precreate = direction.precreate_by_tag || [];

                                        return (
                                            <section
                                                key={profile.id}
                                                className="admin-sdx-card admin-sdx-direction-card"
                                                aria-current={selectedProfileKey === profile.key ? 'true' : undefined}
                                                data-selected={selectedProfileKey === profile.key ? 'true' : undefined}
                                                data-testid={'setup-checklist-row-' + firstTag}
                                            >
                                                <div className="admin-sdx-row-head">
                                                    <h3 className="admin-sdx-direction-title">
                                                        <Link
                                                            className="admin-sdx-link"
                                                            to={profileSelectionLink(profile.key)}
                                                            aria-current={selectedProfileKey === profile.key ? 'page' : undefined}
                                                            data-testid={'setup-select-profile-' + profile.key}
                                                        >
                                                            {directionTitle(direction)}
                                                        </Link>
                                                    </h3>
                                                    <Badge variant={direction.configuration_state === 'ready' ? 'info' : 'secondary'}>
                                                        {t(configurationStateKeys[direction.configuration_state])}
                                                    </Badge>
                                                    {(profile.queue_tags || []).map((tag) => (
                                                        <code className="admin-sdx-code" key={tag}>{tag}</code>
                                                    ))}
                                                </div>

                                                <section className="admin-sdx-fact-group" aria-label={t('admin2.sdx_group_configuration')}>
                                                    <h4>{t('admin2.sdx_group_configuration')}</h4>
                                                    <div className="admin-sdx-fact-row">
                                                        {statusIcon(
                                                            direction.configuration_state === 'ready'
                                                                ? true
                                                                : direction.configuration_state === 'incomplete'
                                                                  ? null
                                                                  : false,
                                                        )}
                                                        <span>{t(configurationStateKeys[direction.configuration_state])}</span>
                                                        <span className="admin-sdx-muted">{t(modeKeys[direction.resolved_mode])}</span>
                                                    </div>
                                                    <div className="admin-sdx-fact-row">
                                                        {statusIcon(
                                                            direction.effective_availability === 'available'
                                                                ? true
                                                                : direction.effective_availability === 'conflict'
                                                                  ? false
                                                                  : null,
                                                        )}
                                                        <span>{t('admin2.sdx_effective_availability')}</span>
                                                        <span>{t('admin2.sdx_availability_' + direction.effective_availability)}</span>
                                                    </div>
                                                    {reasons.length > 0 && (
                                                        <ul className="admin-sdx-reason-list" data-testid="setup-direction-reasons">
                                                            {reasons.map((reason, index) => (
                                                                <li key={reason.code + ':' + index} data-severity={reason.severity}>
                                                                    {reasonLabel(reason.code)}
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    )}
                                                    {(direction.effective_availability_reasons || []).length > 0 && (
                                                        <ul className="admin-sdx-reason-list">
                                                            {(direction.effective_availability_reasons || []).map((code, index) => (
                                                                <li key={code + ':' + index}>{reasonLabel(code)}</li>
                                                            ))}
                                                        </ul>
                                                    )}
                                                </section>

                                                <section className="admin-sdx-fact-group" aria-label={t('admin2.sdx_group_public')}>
                                                    <h4>{t('admin2.sdx_group_public')}</h4>
                                                    <div className="admin-sdx-fact-row" data-testid="setup-row-profile-active">
                                                        <span>{t('admin2.sdx_profile_activity')}</span>
                                                        <span>{t(profile.is_active ? 'admin2.sdx_profile_active' : 'admin2.sdx_profile_inactive')}</span>
                                                    </div>
                                                    <div className="admin-sdx-fact-row" data-testid="setup-row-public-setting">
                                                        <span>{t('admin2.sdx_saved_qr_setting')}</span>
                                                        <span>{t(profile.show_on_qr_page ? 'admin2.sdx_qr_setting_on' : 'admin2.sdx_qr_setting_off')}</span>
                                                    </div>
                                                    <div className="admin-sdx-fact-row" data-testid="setup-row-public-availability">
                                                        <span>{t('admin2.sdx_public_entry')}</span>
                                                        <span>{t(direction.public_availability ? 'admin2.sdx_public_available' : 'admin2.sdx_public_unavailable')}</span>
                                                    </div>
                                                    <div className="admin-sdx-fact-row" data-testid="setup-row-permanent-address">
                                                        <span>{t('admin2.sdx_address_exists')}</span>
                                                        <span>{t(direction.permanent_address_exists ? 'admin2.sdx_yes' : 'admin2.sdx_no')}</span>
                                                    </div>
                                                    {canOpenQr && (
                                                        <div className="admin-sdx-qr-disclosure">
                                                            <Button
                                                                variant="secondary"
                                                                size="sm"
                                                                aria-expanded={expandedQrProfileKey === qrKey}
                                                                onClick={() => toggleQr(direction)}
                                                                data-testid={'setup-qr-expand-' + firstTag}
                                                            >
                                                                {t(canProvisionQr ? actionLabelKeys.provision_permanent_address : 'admin2.sdx_qr_open')}
                                                            </Button>
                                                            {expandedQrProfileKey === qrKey && (
                                                                <div className="admin-sdx-qr-load-state">
                                                                    {qrState?.status === 'loading' && (
                                                                        <div role="status">{t('admin2.sdx_qr_loading')}</div>
                                                                    )}
                                                                    {qrState?.status === 'error' && (
                                                                        <div role="alert" className="admin-sdx-qr-error">
                                                                            {t('admin2.sdx_qr_read_failed')}
                                                                            <Button
                                                                                variant="secondary"
                                                                                size="sm"
                                                                                onClick={() => ensureQrRead(qrKey, true)}
                                                                                data-testid={'setup-qr-read-retry-' + firstTag}
                                                                            >
                                                                                {t('admin2.sdx_retry')}
                                                                            </Button>
                                                                        </div>
                                                                    )}
                                                                    {qrState?.status === 'loaded' && (
                                                                        <>
                                                                            {qrState.supported === null && (
                                                                                <Button
                                                                                    variant="ghost"
                                                                                    size="sm"
                                                                                    onClick={() => ensureQrRead(qrKey, true)}
                                                                                    data-testid={'setup-qr-read-retry-' + firstTag}
                                                                                >
                                                                                    {t('admin2.sdx_retry')}
                                                                                </Button>
                                                                            )}
                                                                            <PermanentDirectionQr
                                                                                profileKey={qrKey}
                                                                                tag={firstTag}
                                                                                supported={qrState.supported}
                                                                                savedAddressExists={direction.permanent_address_exists}
                                                                                publicAvailability={direction.public_availability}
                                                                                onSupportedChange={handleQrSupportedChange}
                                                                                onAddressProvisioned={handleAddressProvisioned}
                                                                                supportGeneration={supportGeneration}
                                                                            />
                                                                        </>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </section>

                                                <section className="admin-sdx-fact-group" aria-label={t('admin2.sdx_group_targets')}>
                                                    <h4>{t('admin2.sdx_group_targets')}</h4>
                                                    {targets.length === 0 ? (
                                                        <p className="admin-sdx-muted">{t('admin2.sdx_targets_empty')}</p>
                                                    ) : (
                                                        <ul className="admin-sdx-entity-list" data-testid="setup-direction-targets">
                                                            {targets.map((target) => {
                                                                const existingQueueCount = target.existing_daily_queue_ids?.length ?? 0;
                                                                return (
                                                                    <li key={target.owner_type + ':' + target.owner_id + ':' + target.queue_tag}>
                                                                        <span className="admin-sdx-entity-title">
                                                                            {target.label} — {t('admin2.sdx_owner_' + target.owner_type)}
                                                                        </span>
                                                                        <span>{t(target.eligible_for_new_booking ? 'admin2.sdx_target_bookable' : 'admin2.sdx_target_not_bookable')}</span>
                                                                        {!target.is_active && <span>{t('admin2.sdx_target_inactive')}</span>}
                                                                        {existingQueueCount > 0 && (
                                                                            <span>{t('admin2.sdx_target_existing_queues', { n: existingQueueCount })}</span>
                                                                        )}
                                                                    </li>
                                                                );
                                                            })}
                                                        </ul>
                                                    )}
                                                </section>

                                                <section className="admin-sdx-fact-group" aria-label={t('admin2.sdx_group_queues')}>
                                                    <h4>{t('admin2.sdx_group_queues', { day: directions.as_of_day })}</h4>
                                                    {queues.length === 0 ? (
                                                        <p className="admin-sdx-muted">{t('admin2.sdx_queues_empty')}</p>
                                                    ) : (
                                                        <ul className="admin-sdx-entity-list" data-testid="setup-direction-queues">
                                                            {queues.map((queue) => {
                                                                const target = targets.find((candidate) =>
                                                                    candidate.owner_type === queue.owner_type &&
                                                                    candidate.owner_id === queue.owner_id &&
                                                                    candidate.queue_tag === queue.queue_tag,
                                                                );
                                                                const ownerType = queue.owner_type || 'unresolved';
                                                                const ownerKey = ownerType === 'doctor' || ownerType === 'resource'
                                                                    ? 'admin2.sdx_owner_' + ownerType
                                                                    : 'admin2.sdx_owner_unresolved';
                                                                const ownerLabel = target?.label || t(ownerKey);
                                                                return (
                                                                    <li key={queue.daily_queue_id}>
                                                                        <span>{queue.queue_tag} — {ownerLabel}</span>
                                                                        <span>{t('admin2.sdx_queue_id', { id: queue.daily_queue_id })}</span>
                                                                    </li>
                                                                );
                                                            })}
                                                        </ul>
                                                    )}
                                                </section>

                                                <section className="admin-sdx-fact-group" aria-label={t('admin2.sdx_group_precreate')}>
                                                    <h4>{t('admin2.sdx_group_precreate')}</h4>
                                                    {precreate.length === 0 ? (
                                                        <p className="admin-sdx-muted">{t('admin2.sdx_precreate_empty')}</p>
                                                    ) : (
                                                        <ul className="admin-sdx-entity-list" data-testid="setup-direction-precreate">
                                                            {precreate.map((item) => (
                                                                <li key={item.queue_tag}>
                                                                    <span className="admin-sdx-entity-title">{item.queue_tag}</span>
                                                                    <span>{t('admin2.sdx_precreate_state_' + item.state)}</span>
                                                                    <span>{t('admin2.sdx_precreate_count', { n: item.active_service_count })}</span>
                                                                    {item.owner_type && <span>{t('admin2.sdx_owner_' + item.owner_type)}</span>}
                                                                    {(item.reason_codes || []).map((code, index) => (
                                                                        <span className="admin-sdx-muted" key={code + ':' + index}>
                                                                            {t(precreateReasonKeys[code] || 'admin2.sdx_reason_unknown')}
                                                                        </span>
                                                                    ))}
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    )}
                                                </section>

                                                <section className="admin-sdx-fact-group" aria-label={t('admin2.sdx_group_actions')}>
                                                    <h4>{t('admin2.sdx_group_actions')}</h4>
                                                    {(direction.allowed_next_actions || []).filter((action) => action.kind !== 'provision_permanent_address').length === 0 ? (
                                                        <p className="admin-sdx-muted">{t('admin2.sdx_actions_none')}</p>
                                                    ) : (
                                                        <div className="admin-sdx-action-list" data-testid="setup-direction-actions">
                                                            {(direction.allowed_next_actions || []).filter((action) => action.kind !== 'provision_permanent_address').map((action) =>
                                                                renderActionControl(action, direction),
                                                            )}
                                                        </div>
                                                    )}
                                                </section>
                                            </section>
                                        );
                                    })}
                                </div>
                            )}
                            {directions && (
                                <div className="admin-sdx-action-list" data-testid="setup-editor-links">
                                    <Link className="admin-sdx-link" to={setupEditorLink('service-catalog')}>
                                        {t('admin2.sdx_wizard_services_link')}
                                    </Link>
                                    <Link className="admin-sdx-link" to={setupEditorLink('queue-profiles')}>
                                        {t('admin2.qp_page_title')}
                                    </Link>
                                    <Link className="admin-sdx-link" to={setupEditorLink('user-management')}>
                                        {t('admin2.sdx_axis_doctor_link')}
                                    </Link>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {directions && (
                        <Card data-testid="setup-unattached-catalog">
                            <CardHeader>
                                <CardTitle>{t('admin2.sdx_unattached_title')}</CardTitle>
                                <CardDescription>{t('admin2.sdx_unattached_subtitle')}</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {(directions.unattached?.queue_tags || []).length === 0 &&
                                (directions.unattached?.services || []).length === 0 &&
                                (directions.unattached?.resources || []).length === 0 ? (
                                    <p className="admin-sdx-muted">{t('admin2.sdx_unattached_empty')}</p>
                                ) : (
                                    <div className="admin-sdx-unattached-grid">
                                        <div>
                                            <h4>{t('admin2.sdx_unattached_tags')}</h4>
                                            {(directions.unattached?.queue_tags || []).length === 0 ? (
                                                <p className="admin-sdx-muted">{t('admin2.sdx_unattached_empty_group')}</p>
                                            ) : (
                                                <ul className="admin-sdx-entity-list">
                                                    {(directions.unattached?.queue_tags || []).map((tag) => <li key={tag}><code>{tag}</code></li>)}
                                                </ul>
                                            )}
                                        </div>
                                        <div>
                                            <h4>{t('admin2.sdx_unattached_services')}</h4>
                                            {(directions.unattached?.services || []).length === 0 ? (
                                                <p className="admin-sdx-muted">{t('admin2.sdx_unattached_empty_group')}</p>
                                            ) : (
                                                <ul className="admin-sdx-entity-list">
                                                    {(directions.unattached?.services || []).map((service) => (
                                                        <li key={service.service_id}>
                                                            <span>{service.name}</span>
                                                            {service.queue_tag && <code>{service.queue_tag}</code>}
                                                            {!service.active && <span>{t('admin2.sdx_target_inactive')}</span>}
                                                        </li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>
                                        <div>
                                            <h4>{t('admin2.sdx_unattached_resources')}</h4>
                                            {(directions.unattached?.resources || []).length === 0 ? (
                                                <p className="admin-sdx-muted">{t('admin2.sdx_unattached_empty_group')}</p>
                                            ) : (
                                                <ul className="admin-sdx-entity-list">
                                                    {(directions.unattached?.resources || []).map((resource) => (
                                                        <li key={resource.resource_id}>
                                                            <span>{resource.display_name}</span>
                                                            <code>{resource.queue_tag}</code>
                                                            {!resource.active && <span>{t('admin2.sdx_target_inactive')}</span>}
                                                        </li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </>
            )}
        </div>
    );
};

export default AdminSetupDirections;
