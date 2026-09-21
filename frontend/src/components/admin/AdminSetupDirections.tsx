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
 *     resource-flow можно начать БЕЗ существующего тега (round-3
 *     owner-ревью P1): у совершенно новой specialty тега ещё нет —
 *     он появится после создания профиля/услуги на шагах мастера,
 *     после возврата его можно выбрать в селекторе этого же шага;
 *  3. не требует технических ключей: queue_tag/profile_key не вводятся
 *     руками — выбор из существующих значений;
 *  4. QR-колонка — точка расширения зашита, но не реализуется (RQ-18).
 *
 * Экран НЕ редактирует данные сам (только ссылки/статусы; QueueResource
 * CRUD живёт своей поверхностью QueueResourceManager, экран-вход
 * ссылается на него). Статусы всегда пересчитываются из API.
 * Стили — в admin.css (секция RQ-17), без inline-styles (UI ratchet).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import PermanentDirectionQr from './PermanentDirectionQr';
import {
    type Checklist,
    type ChecklistDoctorDto,
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
    const [doctors, setDoctors] = useState<ChecklistDoctorDto[]>([]);
    const [entryMethodsByProfileKey, setEntryMethodsByProfileKey] = useState<
        Record<string, EntryMethodsDto | null>
    >({});
    // RQ-18 follow-up round-3 (P2): post-provision recheck answers as a
    // SEPARATE tri-state override (undefined = no recheck answer yet;
    // boolean = proven; null = recheck failed → honest unknown). Writing
    // null INTO entryMethodsByProfileKey destroyed the last-known
    // EntryMethodsDto — a later `true` then hit `!current` and the
    // checklist row was stuck at unknown forever (only a full page
    // reload resynced it).
    const [postProvisionSupportByProfileKey, setPostProvisionSupportByProfileKey] =
        useState<Record<string, boolean | null | undefined>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [wizard, setWizard] = useState<WizardState>(emptyWizard);

    // RQ-18: react-i18next's `t` gets a new identity on every render, so
    // using it directly in loadCore's deps made the mount effect re-run
    // FOREVER (measured: 360 GETs in 400ms on main — the checklist
    // unmounted/remounted in a loop and any in-block state was wiped).
    // The ref keeps loadCore's identity stable; language switches still
    // take effect on the next render.
    const tRef = useRef(t);
    useEffect(() => {
        tRef.current = t;
    });

    const loadCore = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const [servicesRes, profilesRes, resourcesRows, doctorsRes] = await Promise.all([
                api.get('/services?limit=1000') as Promise<{ data: unknown }>,
                api.get('/queues/profiles?active_only=false') as Promise<{
                    data: { profiles?: ChecklistProfileDto[] };
                }>,
                listQueueResources(),
                // (а) doctor-owned leg: read-side активных Doctor-записей
                // (brief §3(а)); endpoint отдаёт только active=true
                api.get('/services/admin/doctors?limit=500') as Promise<{
                    data: ChecklistDoctorDto[];
                }>,
            ]);
            const serviceRows = (Array.isArray(servicesRes.data)
                ? servicesRes.data
                : []) as ChecklistServiceDto[];
            const profileRows = (profilesRes.data?.profiles || []) as ChecklistProfileDto[];
            const doctorRows = (
                Array.isArray(doctorsRes.data) ? doctorsRes.data : []
            ) as ChecklistDoctorDto[];
            setServices(serviceRows);
            setProfiles(profileRows);
            setResources(resourcesRows);
            setDoctors(doctorRows);

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
            // A fresh FULL read is the new source of truth — any
            // post-provision override from a previous lifecycle is stale.
            setPostProvisionSupportByProfileKey({});
        } catch (err) {
            logger.error('Error loading setup directions data:', err);
            setError(tRef.current('admin2.sdx_load_failed'));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadCore();
    }, [loadCore]);

    const checklist: Checklist = useMemo(
        () =>
            buildChecklist(
                services,
                profiles,
                resources,
                entryMethodsByProfileKey,
                doctors,
                postProvisionSupportByProfileKey,
            ),
        [services, profiles, resources, entryMethodsByProfileKey, doctors, postProvisionSupportByProfileKey],
    );

    // RQ-18 follow-up (P2-4): the permanent address is provisioned PER
    // PROFILE, while checklist rows are per-tag — a profile carrying
    // several queue_tags must render its QR block ONCE (the first visible
    // tag row owns it), not once per tag with independent React states.
    // Pure derivation — no render-order mutations (StrictMode-safe).
    const qrRowByProfileKey = useMemo(() => {
        const first: Record<string, string> = {};
        for (const row of Object.values(checklist)) {
            const key = row.owningProfile?.key;
            if (key && row.owningProfileVisible && !(String(key) in first)) {
                first[String(key)] = row.tag;
            }
        }
        return first;
    }, [checklist]);

    // RQ-18 follow-up (P2-3): the QR block re-reads entry-methods after a
    // provision and reports the fresh permanent_address.supported — the
    // checklist row status must follow (a freshly provisioned healthy
    // direction drops the stale «не готово» state; a failed recheck is an
    // honest unknown, never a confident «недоступно»).
    const handleQrSupportedChange = useCallback(
        (profileKey: string, supported: boolean | null) => {
            // RQ-18 follow-up round-3 (P2): record the recheck answer as a
            // tri-state OVERRIDE — the last-known EntryMethodsDto is never
            // destroyed, so the row can move unknown → true (or → false)
            // when the recheck answers after the pending unknown.
            setPostProvisionSupportByProfileKey((prev) => ({
                ...prev,
                [profileKey]: supported,
            }));
        },
        [],
    );

    const wizardTagOptions = useMemo(
        () => candidateTags(services, profiles).map((tag) => ({ value: tag, label: tag })),
        [services, profiles],
    );

    const openResources = useCallback(() => setView('resources'), []);
    const openChecklist = useCallback(() => setView('checklist'), []);

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
                        onClick={() => void loadCore()}
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
                        <Card className="admin-sdx-header" data-testid="setup-wizard-teaser">
                            <CardContent>
                                <div className="admin-sdx-teaser">
                                    <div className="admin-sdx-teaser-title">
                                        <strong>{t('admin2.sdx_wizard_teaser_title')}</strong>
                                        <div className="admin-sdx-teaser-desc">
                                            {t('admin2.sdx_wizard_teaser_desc')}
                                        </div>
                                    </div>
                                    <Button
                                        variant="primary"
                                        size="sm"
                                        onClick={() => setWizard({ ...emptyWizard(), open: true })}
                                        data-testid="setup-wizard-open"
                                    >
                                        <Plus className="admin-sdx-icon-l" size={14} />
                                        {t('admin2.sdx_wizard_open')}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <Card className="admin-sdx-card-gap" data-testid="setup-wizard">
                            <CardHeader>
                                <CardTitle>{t('admin2.sdx_wizard_title')}</CardTitle>
                                <CardDescription>{t('admin2.sdx_wizard_subtitle')}</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="admin-sdx-steps">
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
                                        <p className="admin-sdx-step-hint">
                                            {t('admin2.sdx_wizard_executor_hint')}
                                        </p>
                                        <div className="admin-sdx-axis-grid">
                                            <div className="admin-sdx-axis-card">
                                                <strong className="admin-sdx-axis-title">{t('admin2.sdx_axis_doctor_title')}</strong>
                                                <p className="admin-sdx-axis-desc">
                                                    {t('admin2.sdx_axis_doctor_desc')}
                                                </p>
                                                <Link className="admin-sdx-link" to="/admin/users">
                                                    {t('admin2.sdx_axis_doctor_link')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                                                </Link>
                                                <div className="admin-sdx-step-nav">
                                                    <Button
                                                        variant="secondary"
                                                        size="sm"
                                                        onClick={() => setWizard((w) => ({ ...w, axis: 'doctor', step: 1 }))}
                                                        data-testid="setup-wizard-axis-doctor"
                                                    >
                                                        {t('admin2.sdx_choose')} <ArrowRight className="admin-sdx-icon-r" size={12} />
                                                    </Button>
                                                </div>
                                            </div>
                                            <div className="admin-sdx-axis-card">
                                                <strong className="admin-sdx-axis-title">{t('admin2.sdx_axis_resource_title')}</strong>
                                                <p className="admin-sdx-axis-desc">
                                                    {t('admin2.sdx_axis_resource_desc')}
                                                </p>
                                                <div className="admin-sdx-axis-select">
                                                    <Select
                                                        placeholder={t('admin2.sdx_wizard_tag_placeholder')}
                                                        options={wizardTagOptions}
                                                        value={wizard.tag}
                                                        onValueChange={(value) => setWizard((w) => ({ ...w, tag: String(value) }))}
                                                        data-testid="setup-wizard-tag-select"
                                                    />
                                                </div>
                                                <p className="admin-sdx-step-hint admin-sdx-muted">
                                                    {t('admin2.sdx_wizard_tag_optional_hint')}
                                                </p>
                                                {/* Round-3 (P1): кнопка НЕ заблокирована пустым тегом —
                                                    новое направление начинается «с пустой формы»: тег
                                                    появится после создания профиля/услуги (шаги ниже)
                                                    и выбирается в селекторе после возврата. */}
                                                <Button
                                                    variant="secondary"
                                                    size="sm"
                                                    onClick={() => setWizard((w) => ({ ...w, axis: 'resource', step: 1 }))}
                                                    data-testid="setup-wizard-axis-resource"
                                                >
                                                    {t('admin2.sdx_choose')} <ArrowRight className="admin-sdx-icon-r" size={12} />
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {wizard.step === 1 && (
                                    <div data-testid="setup-wizard-step-services">
                                        <p className="admin-sdx-step-hint">
                                            {t('admin2.sdx_wizard_services_hint')}
                                        </p>
                                        <Link className="admin-sdx-link" to="/admin/services?servicesTab=catalog">
                                            {t('admin2.sdx_wizard_services_link')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                                        </Link>
                                        <div className="admin-sdx-step-nav">
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => setWizard((w) => ({ ...w, step: 2 }))}
                                                data-testid="setup-wizard-services-next"
                                            >
                                                {t('admin2.sdx_next')} <ArrowRight className="admin-sdx-icon-r" size={12} />
                                            </Button>
                                            <Button variant="ghost" size="sm" onClick={() => setWizard((w) => ({ ...w, step: 0 }))}>
                                                {t('admin2.sdx_back')}
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {wizard.step === 2 && (
                                    <div data-testid="setup-wizard-step-display">
                                        <p className="admin-sdx-step-hint">
                                            {t('admin2.sdx_wizard_display_hint')}
                                        </p>
                                        {wizard.axis === 'resource' && (
                                            <p className="admin-sdx-step-hint admin-sdx-muted">
                                                {t('admin2.sdx_wizard_display_resource_note')}
                                            </p>
                                        )}
                                        <Link className="admin-sdx-link" to="/admin/services?servicesTab=queue-profiles">
                                            {t('admin2.sdx_wizard_display_link')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                                        </Link>
                                        <div className="admin-sdx-step-nav">
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => setWizard((w) => ({ ...w, step: 3 }))}
                                                data-testid="setup-wizard-display-next"
                                            >
                                                {t('admin2.sdx_next')} <ArrowRight className="admin-sdx-icon-r" size={12} />
                                            </Button>
                                            <Button variant="ghost" size="sm" onClick={() => setWizard((w) => ({ ...w, step: 1 }))}>
                                                {t('admin2.sdx_back')}
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {wizard.step === 3 && (
                                    <div data-testid="setup-wizard-step-verify">
                                        <p className="admin-sdx-step-hint">
                                            {t('admin2.sdx_wizard_verify_hint')}
                                        </p>
                                        {wizard.axis === 'resource' && (
                                            <p className="admin-sdx-step-hint">
                                                {t('admin2.sdx_wizard_verify_resource_note')}
                                            </p>
                                        )}
                                        <div className="admin-sdx-step-nav">
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
                                                {t('admin2.sdx_wizard_verify_open')} <ArrowRight className="admin-sdx-icon-r" size={12} />
                                            </Button>
                                            <Button variant="ghost" size="sm" onClick={() => setWizard((w) => ({ ...w, step: 2 }))}>
                                                {t('admin2.sdx_back')}
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {wizard.step === 4 && (
                                    <div data-testid="setup-wizard-step-qr">
                                        <p className="admin-sdx-step-hint">
                                            {t('admin2.sdx_wizard_qr_hint')}
                                        </p>
                                        <div className="admin-sdx-step-nav">
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

                                <div className="admin-sdx-step-nav">
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
                                <div className="admin-sdx-note">{t('admin2.sdx_loading')}</div>
                            ) : Object.keys(checklist).length === 0 ? (
                                <div className="admin-sdx-note" data-testid="setup-checklist-empty">
                                    {t('admin2.sdx_checklist_empty')}
                                </div>
                            ) : (
                                <div className="admin-sdx-rows">
                                    {Object.values(checklist).map((row) => (
                                        <div key={row.tag} className="admin-sdx-card" data-testid={`setup-checklist-row-${row.tag}`}>
                                            <div className="admin-sdx-row-head">
                                                <code className="admin-sdx-code">{row.tag}</code>
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
                                                    <span className="admin-sdx-row-sub">
                                                        {String(row.owningProfile.title_ru)}
                                                    </span>
                                                )}
                                            </div>
                                            <table className="admin-sdx-table">
                                                <tbody>
                                                    <tr data-testid="setup-row-executor">
                                                        <td className="admin-sdx-cell-icon">{statusIcon(row.executorReady)}</td>
                                                        <td className="admin-sdx-cell">{t('admin2.sdx_step_executor')}</td>
                                                        <td className="admin-sdx-cell-right">
                                                            {!row.executorReady && (
                                                                <Link className="admin-sdx-link" to="/admin/users">
                                                                    {t('admin2.sdx_fix_executor')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                                                                </Link>
                                                            )}
                                                        </td>
                                                    </tr>
                                                    <tr data-testid="setup-row-services">
                                                        <td className="admin-sdx-cell-icon">{statusIcon(row.activeServices.length > 0)}</td>
                                                        <td className="admin-sdx-cell">
                                                            {t('admin2.sdx_step_services', { n: row.activeServices.length })}
                                                        </td>
                                                        <td className="admin-sdx-cell-right">
                                                            {row.activeServices.length === 0 && (
                                                                <Link className="admin-sdx-link" to="/admin/services?servicesTab=catalog">
                                                                    {t('admin2.sdx_fix_services')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                                                                </Link>
                                                            )}
                                                        </td>
                                                    </tr>
                                                    {row.axis === 'resource' && (
                                                        <tr data-testid="setup-row-doctorless">
                                                            <td className="admin-sdx-cell-icon">
                                                                {statusIcon(row.activeDoctorlessServices.length > 0)}
                                                            </td>
                                                            <td className="admin-sdx-cell">
                                                                {t('admin2.sdx_step_doctorless', { n: row.activeDoctorlessServices.length })}
                                                            </td>
                                                            <td className="admin-sdx-cell-right">
                                                                {row.activeDoctorlessServices.length === 0 && (
                                                                    <Link className="admin-sdx-link" to="/admin/services?servicesTab=catalog">
                                                                        {t('admin2.sdx_fix_services')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                                                                    </Link>
                                                                )}
                                                            </td>
                                                        </tr>
                                                    )}
                                                    <tr data-testid="setup-row-profile">
                                                        <td className="admin-sdx-cell-icon">{statusIcon(row.owningProfile != null)}</td>
                                                        <td className="admin-sdx-cell">{t('admin2.sdx_step_profile')}</td>
                                                        <td className="admin-sdx-cell-right">
                                                            {!row.owningProfile && (
                                                                <Link className="admin-sdx-link" to="/admin/services?servicesTab=queue-profiles">
                                                                    {t('admin2.sdx_fix_profile')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                                                                </Link>
                                                            )}
                                                        </td>
                                                    </tr>
                                                    <tr data-testid="setup-row-visible">
                                                        <td className="admin-sdx-cell-icon">{statusIcon(row.owningProfileVisible)}</td>
                                                        <td className="admin-sdx-cell">{t('admin2.sdx_step_visible')}</td>
                                                        <td className="admin-sdx-cell-right">
                                                            {row.owningProfile && !row.owningProfileVisible && (
                                                                <Link className="admin-sdx-link" to="/admin/services?servicesTab=queue-profiles">
                                                                    {t('admin2.sdx_fix_visible')} <ExternalLink className="admin-sdx-icon-m" size={11} />
                                                                </Link>
                                                            )}
                                                        </td>
                                                    </tr>
                                                    <tr data-testid="setup-row-permanent-address">
                                                        <td className="admin-sdx-cell-icon">{statusIcon(row.permanentAddress)}</td>
                                                        <td className="admin-sdx-cell">
                                                            {row.permanentAddress === null
                                                                ? t('admin2.sdx_step_address_unknown')
                                                                : t('admin2.sdx_step_address')}
                                                        </td>
                                                        <td className={`admin-sdx-cell-right admin-sdx-muted`}>
                                                            {row.permanentAddress !== true && t('admin2.sdx_step_address_hint')}
                                                        </td>
                                                    </tr>
                                                </tbody>
                                            </table>
                                            {row.owningProfile?.key && row.owningProfileVisible && (
                                                qrRowByProfileKey[String(row.owningProfile.key)] === row.tag ? (
                                                    <PermanentDirectionQr
                                                        profileKey={String(row.owningProfile.key)}
                                                        tag={row.tag}
                                                        supported={row.permanentAddress}
                                                        onSupportedChange={handleQrSupportedChange}
                                                    />
                                                ) : (
                                                    /* RQ-18 follow-up (P2-4): sibling tag rows of the
                                                       SAME profile show a pointer instead of a second,
                                                       independent QR block — the address belongs to the
                                                       profile as a whole, not to an individual tag. */
                                                    <div
                                                        className="admin-sdx-qr-dedupe-note"
                                                        data-testid={`setup-qr-dedupe-${row.tag}`}
                                                    >
                                                        {t('admin2.qrdx_dedupe_note', {
                                                            tag: qrRowByProfileKey[String(row.owningProfile.key)],
                                                        })}
                                                    </div>
                                                )
                                            )}
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
