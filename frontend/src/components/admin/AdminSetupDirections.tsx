import { useTranslation } from '../../i18n/useTranslation';
/**
 * AdminSetupDirections — экран-вход «собранный путь настройки направления»
 * (RQ-17 runtime-PR; brief `RQ17_SETUP_PATH_BRIEF.md` §4, §5-S-14).
 *
 * Один новый admin-route `/admin/setup-directions` (одна запись в реестре
 * маршрутов), который:
 *  1. показывает checklist готовности направлений по тег-строкам — шаги
 *     §3 (а)–(д) со статусами «готово / не хватает X / где исправить»;
 *     каждая «не хватает» ведёт прямой ссылкой в соответствующий экран;
 *  2. начинает мастер нового направления S-14 с пустой формы:
 *     последовательность §3 (исполнитель → услуги → отображение →
 *     проверка → QR), каждый шаг = переход в существующий экран с
 *     возвратом на checklist; для resource-owned — минимальная
 *     поверхность менеджера QueueResource (единственное новое UI);
 *  3. не требует технических ключей: queue_tag/profile_key не вводятся
 *     руками — выбор из существующих значений;
 *  4. QR-колонка — точка расширения зашита, но не реализуется (RQ-18).
 *
 * Экран НЕ редактирует данные сам (только ссылки/статусы; QueueResource
 * CRUD живёт своей поверхностью QueueResourceManager, экран-вход
 * ссылается на него). Статусы всегда пересчитываются из API.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    ArrowRight,
    CheckCircle2,
    CircleAlert,
    ExternalLink,
    ListChecks,
    Plus,
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
    Select,
} from '../ui/macos';
import { type QueueResourceDto, listQueueResources } from '../../api/queueResources';
import QueueResourceManager from './QueueResourceManager';
import {
    type Checklist,
    type ChecklistProfileDto,
    type ChecklistServiceDto,
    type EntryMethodsDto,
    buildChecklist,
    candidateTags,
} from './setupDirectionsReadiness';

type ScreenView = 'checklist' | 'resources';

interface WizardState {
    open: boolean;
    step: number; // 0..4: исполнитель → услуги → отображение → проверка → QR
    axis: 'doctor' | 'resource' | null;
    tag: string;
}

const emptyWizard = (): WizardState => ({
    open: false,
    step: 0,
    axis: null,
    tag: '',
});

const WIZARD_STEP_KEYS = [
    'admin2.sdx_wizard_step_executor',
    'admin2.sdx_wizard_step_services',
    'admin2.sdx_wizard_step_display',
    'admin2.sdx_wizard_step_verify',
    'admin2.sdx_wizard_step_qr',
] as const;

const AdminSetupDirections = () => {
    const { t } = useTranslation();
    const [view, setView] = useState<ScreenView>('checklist');
    const [services, setServices] = useState<ChecklistServiceDto[]>([]);
    const [profiles, setProfiles] = useState<ChecklistProfileDto[]>([]);
    const [resources, setResources] = useState<QueueResourceDto[]>([]);
    const [entryMethodsByProfileKey, setEntryMethodsByProfileKey] = useState<
        Record<string, EntryMethodsDto | null>
    >({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [wizard, setWizard] = useState<WizardState>(emptyWizard);

    const loadCore = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const [servicesRes, profilesRes, resourcesRows] = await Promise.all([
                api.get('/services?limit=1000') as Promise<{ data: unknown }>,
                api.get('/queues/profiles?active_only=false') as Promise<{
                    data: { profiles?: ChecklistProfileDto[] };
                }>,
                listQueueResources(),
            ]);
            const serviceRows = (Array.isArray(servicesRes.data)
                ? servicesRes.data
                : []) as ChecklistServiceDto[];
            const profileRows = (profilesRes.data?.profiles || []) as ChecklistProfileDto[];
            setServices(serviceRows);
            setProfiles(profileRows);
            setResources(resourcesRows);

            // (д) provision-статус — только для QR-visible профилей (иначе
            // read-side честно отказывает); ошибка чтения → статус неизвестен.
            const qrVisible = profileRows.filter(
                (p) => p.is_active !== false && p.show_on_qr_page === true && p.key,
            );
            const methods = await Promise.all(
                qrVisible.map(async (profile) => {
                    try {
                        const res = (await api.get(
                            `/queue/directions/${encodeURIComponent(String(profile.key))}/entry-methods`,
                        )) as { data: EntryMethodsDto };
                        return [String(profile.key), res.data] as const;
                    } catch (err) {
                        logger.warn(
                            `entry-methods unavailable for profile ${String(profile.key)}`,
                            err,
                        );
                        return [String(profile.key), null] as const;
                    }
                }),
            );
            setEntryMethodsByProfileKey(Object.fromEntries(methods));
        } catch (err) {
            logger.error('Error loading setup directions data:', err);
            setError(t('admin2.sdx_load_failed'));
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        void loadCore();
    }, [loadCore]);

    const checklist: Checklist = useMemo(
        () => buildChecklist(services, profiles, resources, entryMethodsByProfileKey),
        [services, profiles, resources, entryMethodsByProfileKey],
    );

    const wizardTagOptions = useMemo(
        () => candidateTags(services, profiles).map((tag) => ({ value: tag, label: tag })),
        [services, profiles],
    );

    const openResources = useCallback(() => setView('resources'), []);
    const openChecklist = useCallback(() => setView('checklist'), []);

    const statusIcon = (ready: boolean | null) => {
        if (ready === true) {
            return <CheckCircle2 size={15} color="var(--mac-green, #34c759)" aria-hidden />;
        }
        if (ready === false) {
            return <XCircle size={15} color="var(--mac-error, #ff3b30)" aria-hidden />;
        }
        return <CircleAlert size={15} color="var(--mac-text-secondary)" aria-hidden />;
    };

    return (
        <div style={{ padding: 16, maxWidth: 980, margin: '0 auto' }} data-testid="setup-directions-screen">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                <h1 style={{ fontSize: 20, margin: 0 }} data-testid="setup-directions-heading">
                    {t('admin2.sdx_title')}
                </h1>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <Button
                        variant={view === 'checklist' ? 'primary' : 'secondary'}
                        size="sm"
                        onClick={openChecklist}
                        data-testid="setup-view-checklist"
                    >
                        <ListChecks size={14} style={{ marginRight: 4 }} />
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
                        onClick={() => void loadCore()}
                        disabled={loading}
                        data-testid="setup-refresh"
                    >
                        <RefreshCw size={14} style={{ marginRight: 4 }} />
                        {t('admin2.sdx_refresh')}
                    </Button>
                </div>
            </div>

            <p style={{ fontSize: 12, color: 'var(--mac-text-secondary)', margin: '0 0 14px' }}>
                {t('admin2.sdx_subtitle')}
            </p>

            {error && (
                <div
                    role="alert"
                    data-testid="setup-directions-error"
                    style={{
                        padding: '8px 10px',
                        marginBottom: 12,
                        borderRadius: 8,
                        background: 'var(--mac-error-bg, rgba(255,59,48,0.08))',
                        color: 'var(--mac-error, #ff3b30)',
                        fontSize: 12,
                    }}
                >
                    {error}
                </div>
            )}

            {view === 'resources' ? (
                <>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={openChecklist}
                        style={{ marginBottom: 10 }}
                        data-testid="setup-back-to-checklist"
                    >
                        <RotateCcw size={14} style={{ marginRight: 4 }} />
                        {t('admin2.sdx_back_to_checklist')}
                    </Button>
                    <QueueResourceManager
                        services={services}
                        profiles={profiles}
                        onRegistryChanged={() => void loadCore()}
                    />
                </>
            ) : (
                <>
                    {/* —— Мастер нового направления S-14 (пустая форма) —— */}
                    {!wizard.open ? (
                        <Card style={{ marginBottom: 14 }} data-testid="setup-wizard-teaser">
                            <CardContent>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                                    <div style={{ fontSize: 13 }}>
                                        <strong>{t('admin2.sdx_wizard_teaser_title')}</strong>
                                        <div style={{ color: 'var(--mac-text-secondary)', fontSize: 12 }}>
                                            {t('admin2.sdx_wizard_teaser_desc')}
                                        </div>
                                    </div>
                                    <Button
                                        variant="primary"
                                        size="sm"
                                        onClick={() => setWizard({ ...emptyWizard(), open: true })}
                                        data-testid="setup-wizard-open"
                                    >
                                        <Plus size={14} style={{ marginRight: 4 }} />
                                        {t('admin2.sdx_wizard_open')}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <Card style={{ marginBottom: 14 }} data-testid="setup-wizard">
                            <CardHeader>
                                <CardTitle>{t('admin2.sdx_wizard_title')}</CardTitle>
                                <CardDescription>{t('admin2.sdx_wizard_subtitle')}</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
                                    {WIZARD_STEP_KEYS.map((key, index) => (
                                        <Badge
                                            key={key}
                                            variant={index === wizard.step ? 'info' : 'secondary'}
                                            data-testid={`setup-wizard-step-${index}`}
                                        >
                                            {index + 1}. {t(key)}
                                        </Badge>
                                    ))}
                                </div>

                                {wizard.step === 0 && (
                                    <div data-testid="setup-wizard-step-executor">
                                        <p style={{ fontSize: 12, margin: '0 0 8px' }}>
                                            {t('admin2.sdx_wizard_executor_hint')}
                                        </p>
                                        <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
                                            <div style={{ border: '1px solid var(--mac-border, rgba(0,0,0,0.1))', borderRadius: 10, padding: 10 }}>
                                                <strong style={{ fontSize: 13 }}>{t('admin2.sdx_axis_doctor_title')}</strong>
                                                <p style={{ fontSize: 12, color: 'var(--mac-text-secondary)', margin: '6px 0' }}>
                                                    {t('admin2.sdx_axis_doctor_desc')}
                                                </p>
                                                <Link to="/admin/users" style={{ fontSize: 12 }}>
                                                    {t('admin2.sdx_axis_doctor_link')} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                                                </Link>
                                                <div style={{ marginTop: 8 }}>
                                                    <Button
                                                        variant="secondary"
                                                        size="sm"
                                                        onClick={() => setWizard((w) => ({ ...w, axis: 'doctor', step: 1 }))}
                                                        data-testid="setup-wizard-axis-doctor"
                                                    >
                                                        {t('admin2.sdx_choose')} <ArrowRight size={12} style={{ marginLeft: 4 }} />
                                                    </Button>
                                                </div>
                                            </div>
                                            <div style={{ border: '1px solid var(--mac-border, rgba(0,0,0,0.1))', borderRadius: 10, padding: 10 }}>
                                                <strong style={{ fontSize: 13 }}>{t('admin2.sdx_axis_resource_title')}</strong>
                                                <p style={{ fontSize: 12, color: 'var(--mac-text-secondary)', margin: '6px 0' }}>
                                                    {t('admin2.sdx_axis_resource_desc')}
                                                </p>
                                                <div style={{ marginBottom: 8 }}>
                                                    <Select
                                                        placeholder={t('admin2.sdx_wizard_tag_placeholder')}
                                                        options={wizardTagOptions}
                                                        value={wizard.tag}
                                                        onValueChange={(value) => setWizard((w) => ({ ...w, tag: String(value) }))}
                                                        data-testid="setup-wizard-tag-select"
                                                    />
                                                </div>
                                                <Button
                                                    variant="secondary"
                                                    size="sm"
                                                    disabled={!wizard.tag}
                                                    onClick={() => setWizard((w) => ({ ...w, axis: 'resource', step: 1 }))}
                                                    data-testid="setup-wizard-axis-resource"
                                                >
                                                    {t('admin2.sdx_choose')} <ArrowRight size={12} style={{ marginLeft: 4 }} />
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {wizard.step === 1 && (
                                    <div data-testid="setup-wizard-step-services">
                                        <p style={{ fontSize: 12, margin: '0 0 8px' }}>
                                            {t('admin2.sdx_wizard_services_hint')}
                                        </p>
                                        <Link to="/admin/services?servicesTab=catalog" style={{ fontSize: 12 }}>
                                            {t('admin2.sdx_wizard_services_link')} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                                        </Link>
                                        <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => setWizard((w) => ({ ...w, step: 2 }))}
                                                data-testid="setup-wizard-services-next"
                                            >
                                                {t('admin2.sdx_next')} <ArrowRight size={12} style={{ marginLeft: 4 }} />
                                            </Button>
                                            <Button variant="ghost" size="sm" onClick={() => setWizard((w) => ({ ...w, step: 0 }))}>
                                                {t('admin2.sdx_back')}
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {wizard.step === 2 && (
                                    <div data-testid="setup-wizard-step-display">
                                        <p style={{ fontSize: 12, margin: '0 0 8px' }}>
                                            {t('admin2.sdx_wizard_display_hint')}
                                        </p>
                                        {wizard.axis === 'resource' && (
                                            <p style={{ fontSize: 12, margin: '0 0 8px', color: 'var(--mac-text-secondary)' }}>
                                                {t('admin2.sdx_wizard_display_resource_note')}
                                            </p>
                                        )}
                                        <Link to="/admin/services?servicesTab=queue-profiles" style={{ fontSize: 12 }}>
                                            {t('admin2.sdx_wizard_display_link')} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                                        </Link>
                                        <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => setWizard((w) => ({ ...w, step: 3 }))}
                                                data-testid="setup-wizard-display-next"
                                            >
                                                {t('admin2.sdx_next')} <ArrowRight size={12} style={{ marginLeft: 4 }} />
                                            </Button>
                                            <Button variant="ghost" size="sm" onClick={() => setWizard((w) => ({ ...w, step: 1 }))}>
                                                {t('admin2.sdx_back')}
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {wizard.step === 3 && (
                                    <div data-testid="setup-wizard-step-verify">
                                        <p style={{ fontSize: 12, margin: '0 0 8px' }}>
                                            {t('admin2.sdx_wizard_verify_hint')}
                                        </p>
                                        {wizard.axis === 'resource' && (
                                            <p style={{ fontSize: 12, margin: '0 0 8px' }}>
                                                {t('admin2.sdx_wizard_verify_resource_note')}
                                            </p>
                                        )}
                                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => {
                                                    void loadCore();
                                                    setView('checklist');
                                                    setWizard((w) => ({ ...w, step: 4 }));
                                                }}
                                                data-testid="setup-wizard-verify-open"
                                            >
                                                {t('admin2.sdx_wizard_verify_open')} <ArrowRight size={12} style={{ marginLeft: 4 }} />
                                            </Button>
                                            <Button variant="ghost" size="sm" onClick={() => setWizard((w) => ({ ...w, step: 2 }))}>
                                                {t('admin2.sdx_back')}
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {wizard.step === 4 && (
                                    <div data-testid="setup-wizard-step-qr">
                                        <p style={{ fontSize: 12, margin: '0 0 8px' }}>
                                            {t('admin2.sdx_wizard_qr_hint')}
                                        </p>
                                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                            <Button
                                                variant="primary"
                                                size="sm"
                                                onClick={() => setWizard(emptyWizard())}
                                                data-testid="setup-wizard-finish"
                                            >
                                                {t('admin2.sdx_wizard_finish')}
                                            </Button>
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => setWizard((w) => ({ ...w, step: 3 }))}
                                            >
                                                {t('admin2.sdx_back')}
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                <div style={{ marginTop: 10 }}>
                                    <Button variant="ghost" size="sm" onClick={() => setWizard(emptyWizard())} data-testid="setup-wizard-close">
                                        {t('admin2.sdx_wizard_close')}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* —— Checklist готовности по тег-строкам —— */}
                    <Card data-testid="setup-checklist">
                        <CardHeader>
                            <CardTitle>{t('admin2.sdx_checklist_title')}</CardTitle>
                            <CardDescription>{t('admin2.sdx_checklist_subtitle')}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {loading ? (
                                <div style={{ padding: 12, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                                    {t('admin2.sdx_loading')}
                                </div>
                            ) : Object.keys(checklist).length === 0 ? (
                                <div style={{ padding: 12, fontSize: 12, color: 'var(--mac-text-secondary)' }} data-testid="setup-checklist-empty">
                                    {t('admin2.sdx_checklist_empty')}
                                </div>
                            ) : (
                                <div style={{ display: 'grid', gap: 10 }}>
                                    {Object.values(checklist).map((row) => (
                                        <div
                                            key={row.tag}
                                            data-testid={`setup-checklist-row-${row.tag}`}
                                            style={{
                                                border: '1px solid var(--mac-border, rgba(0,0,0,0.1))',
                                                borderRadius: 10,
                                                padding: 10,
                                            }}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                                                <code style={{ fontSize: 12 }}>{row.tag}</code>
                                                {row.axis === 'resource' && (
                                                    <Badge variant="info" data-testid="setup-row-axis-resource">
                                                        {t('admin2.sdx_axis_resource_badge')}
                                                    </Badge>
                                                )}
                                                {row.axis === 'doctor' && (
                                                    <Badge data-testid="setup-row-axis-doctor">
                                                        {t('admin2.sdx_axis_doctor_badge')}
                                                    </Badge>
                                                )}
                                                {row.owningProfile?.title_ru && (
                                                    <span style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                                                        {String(row.owningProfile.title_ru)}
                                                    </span>
                                                )}
                                            </div>
                                            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                                                <tbody>
                                                    <tr data-testid="setup-row-executor">
                                                        <td style={{ padding: '3px 6px', width: 20 }}>{statusIcon(row.executorReady)}</td>
                                                        <td style={{ padding: '3px 6px' }}>{t('admin2.sdx_step_executor')}</td>
                                                        <td style={{ padding: '3px 6px', textAlign: 'right' }}>
                                                            {!row.executorReady && (
                                                                <Link to="/admin/users" style={{ fontSize: 12 }}>
                                                                    {t('admin2.sdx_fix_executor')} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                                                                </Link>
                                                            )}
                                                        </td>
                                                    </tr>
                                                    <tr data-testid="setup-row-services">
                                                        <td style={{ padding: '3px 6px' }}>{statusIcon(row.activeServices.length > 0)}</td>
                                                        <td style={{ padding: '3px 6px' }}>
                                                            {t('admin2.sdx_step_services', { n: row.activeServices.length })}
                                                        </td>
                                                        <td style={{ padding: '3px 6px', textAlign: 'right' }}>
                                                            {row.activeServices.length === 0 && (
                                                                <Link to="/admin/services?servicesTab=catalog" style={{ fontSize: 12 }}>
                                                                    {t('admin2.sdx_fix_services')} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                                                                </Link>
                                                            )}
                                                        </td>
                                                    </tr>
                                                    {row.axis === 'resource' && (
                                                        <tr data-testid="setup-row-doctorless">
                                                            <td style={{ padding: '3px 6px' }}>
                                                                {statusIcon(row.activeDoctorlessServices.length > 0)}
                                                            </td>
                                                            <td style={{ padding: '3px 6px' }}>
                                                                {t('admin2.sdx_step_doctorless', { n: row.activeDoctorlessServices.length })}
                                                            </td>
                                                            <td style={{ padding: '3px 6px', textAlign: 'right' }}>
                                                                {row.activeDoctorlessServices.length === 0 && (
                                                                    <Link to="/admin/services?servicesTab=catalog" style={{ fontSize: 12 }}>
                                                                        {t('admin2.sdx_fix_services')} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                                                                    </Link>
                                                                )}
                                                            </td>
                                                        </tr>
                                                    )}
                                                    <tr data-testid="setup-row-profile">
                                                        <td style={{ padding: '3px 6px' }}>{statusIcon(row.owningProfile != null)}</td>
                                                        <td style={{ padding: '3px 6px' }}>{t('admin2.sdx_step_profile')}</td>
                                                        <td style={{ padding: '3px 6px', textAlign: 'right' }}>
                                                            {!row.owningProfile && (
                                                                <Link to="/admin/services?servicesTab=queue-profiles" style={{ fontSize: 12 }}>
                                                                    {t('admin2.sdx_fix_profile')} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                                                                </Link>
                                                            )}
                                                        </td>
                                                    </tr>
                                                    <tr data-testid="setup-row-visible">
                                                        <td style={{ padding: '3px 6px' }}>{statusIcon(row.owningProfileVisible)}</td>
                                                        <td style={{ padding: '3px 6px' }}>{t('admin2.sdx_step_visible')}</td>
                                                        <td style={{ padding: '3px 6px', textAlign: 'right' }}>
                                                            {row.owningProfile && !row.owningProfileVisible && (
                                                                <Link to="/admin/services?servicesTab=queue-profiles" style={{ fontSize: 12 }}>
                                                                    {t('admin2.sdx_fix_visible')} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                                                                </Link>
                                                            )}
                                                        </td>
                                                    </tr>
                                                    <tr data-testid="setup-row-permanent-address">
                                                        <td style={{ padding: '3px 6px' }}>{statusIcon(row.permanentAddress)}</td>
                                                        <td style={{ padding: '3px 6px' }}>
                                                            {row.permanentAddress === null
                                                                ? t('admin2.sdx_step_address_unknown')
                                                                : t('admin2.sdx_step_address')}
                                                        </td>
                                                        <td style={{ padding: '3px 6px', textAlign: 'right', color: 'var(--mac-text-secondary)' }}>
                                                            {row.permanentAddress !== true && t('admin2.sdx_step_address_hint')}
                                                        </td>
                                                    </tr>
                                                </tbody>
                                            </table>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
};

export default AdminSetupDirections;
