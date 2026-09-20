import { useTranslation } from '../../i18n/useTranslation';
/**
 * QueueResourceManager — минимальная admin-поверхность CRUD реестра
 * QueueResource (RQ-17 runtime-PR; brief `RQ17_SETUP_PATH_BRIEF.md` §3(а),
 * §3.2, §4(1); backend `codex/rq17-runtime-setup-path` d4424aca).
 *
 * Границы поверхности (§3.2 mutability contract — зашит в бэкенд-DTO):
 * - create: draft-by-default (`active=false`); `active=true` сразу — только
 *   при уже пройденном gate §3.1 (тег доказанно doctorless);
 * - PATCH: ordinary-поля (`display_name`, `start_number_online`,
 *   `max_online_per_day`, `default_cabinet`); lifecycle-переход `active`;
 *   `code`/`queue_tag` immutable — UI не предлагает их редактирование
 *   (попытка через API отклоняется 422);
 * - отказ gate §3.1 (409) показывается текстом detail от сервера.
 *
 * «Ноль технических ключей» (§4(3)): queue_tag выбирается из существующих
 * значений (теги профилей/услуг), не вводится руками.
 * Стили — в admin.css (секция RQ-17), без inline-styles (UI ratchet).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Plus,
    Edit2,
    X,
    Check,
    RefreshCw,
    AlertCircle,
    ShieldCheck,
    ShieldOff,
} from 'lucide-react';
import logger from '../../utils/logger';
import {
    Badge,
    Button,
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
    Checkbox,
    Input,
    Select,
} from '../ui/macos';
import { notify } from '../../services/notify';
import {
    type QueueResourceCreatePayload,
    type QueueResourceDto,
    type QueueResourceUpdatePayload,
    createQueueResource,
    listQueueResources,
    queueResourceErrorText,
    updateQueueResource,
} from '../../api/queueResources';
import type { ChecklistProfileDto, ChecklistServiceDto } from './setupDirectionsReadiness';
import { candidateTags } from './setupDirectionsReadiness';

interface QueueResourceManagerProps {
    /** Read-side соседей чек-листа: кандидатные теги = существующие значения (§4(3)). */
    services?: ChecklistServiceDto[];
    profiles?: ChecklistProfileDto[];
    /** Колбэк после каждой успешной мутации — checklist пересчитывает статусы из API. */
    onRegistryChanged?: () => void;
}

interface DraftFormState {
    code: string;
    /** true — code ещё не правился админом вручную и автоподставляется из тега (§4(3)). */
    codeAuto: boolean;
    queue_tag: string;
    display_name: string;
    start_number_online: string;
    max_online_per_day: string;
    default_cabinet: string;
    active: boolean;
}

const emptyDraft = (): DraftFormState => ({
    code: '',
    codeAuto: true,
    queue_tag: '',
    display_name: '',
    start_number_online: '1',
    max_online_per_day: '15',
    default_cabinet: '',
    active: false,
});

/** code — машинный идентификатор новой строки; предзаполняется из тега, чтобы не быть «обязательным знанием» (§4(3)). */
const suggestCode = (tag: string): string =>
    `res-${tag.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')}`.slice(0, 50);

const QueueResourceManager = ({
    services = [],
    profiles = [],
    onRegistryChanged,
}: QueueResourceManagerProps) => {
    const { t } = useTranslation();
    const [resources, setResources] = useState<QueueResourceDto[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [draft, setDraft] = useState<DraftFormState>(emptyDraft);
    const [editing, setEditing] = useState<QueueResourceDto | null>(null);
    const [editDraft, setEditDraft] = useState<{
        display_name: string;
        start_number_online: string;
        max_online_per_day: string;
        default_cabinet: string;
    }>({ display_name: '', start_number_online: '1', max_online_per_day: '15', default_cabinet: '' });

    const tagOptions = useMemo(
        () =>
            candidateTags(services, profiles).map((tag) => ({ value: tag, label: tag })),
        [services, profiles],
    );

    const loadResources = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const rows = await listQueueResources();
            setResources(rows);
        } catch (err) {
            logger.error('Error loading queue resources:', err);
            setError(
                queueResourceErrorText(err, t('admin2.qrm_load_failed')),
            );
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        void loadResources();
    }, [loadResources]);

    const afterMutation = useCallback(async () => {
        await loadResources();
        onRegistryChanged?.();
    }, [loadResources, onRegistryChanged]);

    const handleDraftTagChange = (tag: string) => {
        setDraft((prev) => ({
            ...prev,
            queue_tag: tag,
            // code предзаполняется из тега — админ может не знать о нём вовсе
            code: prev.codeAuto ? suggestCode(tag) : prev.code,
            codeAuto: true,
        }));
    };

    const handleCreate = async () => {
        if (!draft.queue_tag || !draft.display_name.trim()) {
            setError(t('admin2.qrm_create_validation'));
            return;
        }
        const payload: QueueResourceCreatePayload = {
            code: draft.code.trim() || suggestCode(draft.queue_tag),
            queue_tag: draft.queue_tag,
            display_name: draft.display_name.trim(),
            start_number_online: Number(draft.start_number_online) || 1,
            max_online_per_day: Number(draft.max_online_per_day) || 15,
            default_cabinet: draft.default_cabinet.trim() || null,
            // draft-by-default (S-14): услуги/профиль → draft-ресурс → активация;
            // active=true сразу — только при уже пройденном gate §3.1.
            active: draft.active,
        };
        try {
            setSaving(true);
            setError(null);
            await createQueueResource(payload);
            notify.success(t('admin2.qrm_created'));
            setDraft(emptyDraft());
            setShowCreateForm(false);
            await afterMutation();
        } catch (err) {
            logger.error('Error creating queue resource:', err);
            setError(queueResourceErrorText(err, t('admin2.qrm_create_error')));
        } finally {
            setSaving(false);
        }
    };

    const handleActivateToggle = async (resource: QueueResourceDto) => {
        const payload: QueueResourceUpdatePayload = { active: !resource.active };
        try {
            setSaving(true);
            setError(null);
            await updateQueueResource(resource.id, payload);
            notify.success(
                payload.active
                    ? t('admin2.qrm_activated')
                    : t('admin2.qrm_deactivated'),
            );
            await afterMutation();
        } catch (err) {
            logger.error('Error toggling queue resource active:', err);
            // 409 — отказ gate §3.1 (инвариант тега), текст detail от сервера
            setError(queueResourceErrorText(err, t('admin2.qrm_toggle_error')));
        } finally {
            setSaving(false);
        }
    };

    const openEdit = (resource: QueueResourceDto) => {
        setEditing(resource);
        setEditDraft({
            display_name: resource.display_name,
            start_number_online: String(resource.start_number_online),
            max_online_per_day: String(resource.max_online_per_day),
            default_cabinet: resource.default_cabinet || '',
        });
    };

    const handleUpdate = async () => {
        if (!editing) {
            return;
        }
        const payload: QueueResourceUpdatePayload = {
            display_name: editDraft.display_name.trim(),
            start_number_online: Number(editDraft.start_number_online) || 1,
            max_online_per_day: Number(editDraft.max_online_per_day) || 15,
            default_cabinet: editDraft.default_cabinet.trim() || null,
        };
        try {
            setSaving(true);
            setError(null);
            await updateQueueResource(editing.id, payload);
            notify.success(t('admin2.qrm_updated'));
            setEditing(null);
            await afterMutation();
        } catch (err) {
            logger.error('Error updating queue resource:', err);
            setError(queueResourceErrorText(err, t('admin2.qrm_update_error')));
        } finally {
            setSaving(false);
        }
    };

    return (
        <Card data-testid="qr-resource-manager">
            <CardHeader>
                <CardTitle>{t('admin2.qrm_title')}</CardTitle>
                <CardDescription>{t('admin2.qrm_subtitle')}</CardDescription>
            </CardHeader>
            <CardContent>
                <div className="admin-qrm-toolbar">
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void loadResources()}
                        disabled={loading}
                        data-testid="qr-resource-refresh"
                    >
                        <RefreshCw className="admin-sdx-icon-l" size={14} />
                        {t('admin2.qrm_refresh')}
                    </Button>
                    <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                            setShowCreateForm((v) => !v);
                            setEditing(null);
                        }}
                        data-testid="qr-resource-create-toggle"
                    >
                        <Plus className="admin-sdx-icon-l" size={14} />
                        {t('admin2.qrm_create')}
                    </Button>
                </div>

                {error && (
                    <div role="alert" className="admin-sdx-alert" data-testid="qr-resource-error">
                        <AlertCircle size={14} />
                        <span>{error}</span>
                    </div>
                )}

                {showCreateForm && (
                    <div className="admin-qrm-form" data-testid="qr-resource-create-form">
                        <Select
                            label={t('admin2.qrm_field_tag')}
                            placeholder={t('admin2.qrm_field_tag_placeholder')}
                            options={tagOptions}
                            value={draft.queue_tag}
                            onValueChange={(value) => handleDraftTagChange(String(value))}
                            data-testid="qr-resource-tag-select"
                        />
                        <Input
                            label={t('admin2.qrm_field_code')}
                            value={draft.code}
                            onChange={(e) => setDraft((p) => ({ ...p, code: e.target.value }))}
                            hint={t('admin2.qrm_field_code_hint')}
                            data-testid="qr-resource-code-input"
                        />
                        <Input
                            label={t('admin2.qrm_field_display_name')}
                            value={draft.display_name}
                            onChange={(e) => setDraft((p) => ({ ...p, display_name: e.target.value }))}
                            data-testid="qr-resource-display-name-input"
                        />
                        <Input
                            label={t('admin2.qrm_field_start_number')}
                            type="number"
                            min={1}
                            value={draft.start_number_online}
                            onChange={(e) => setDraft((p) => ({ ...p, start_number_online: e.target.value }))}
                        />
                        <Input
                            label={t('admin2.qrm_field_max_online')}
                            type="number"
                            min={1}
                            value={draft.max_online_per_day}
                            onChange={(e) => setDraft((p) => ({ ...p, max_online_per_day: e.target.value }))}
                        />
                        <Input
                            label={t('admin2.qrm_field_cabinet')}
                            value={draft.default_cabinet}
                            onChange={(e) => setDraft((p) => ({ ...p, default_cabinet: e.target.value }))}
                        />
                        <Checkbox
                            checked={draft.active}
                            onChange={(checked) => setDraft((p) => ({ ...p, active: checked }))}
                            label={t('admin2.qrm_field_active_hint')}
                            data-testid="qr-resource-active-draft"
                        />
                        <div className="admin-qrm-form-span admin-sdx-step-nav">
                            <Button
                                variant="primary"
                                size="sm"
                                onClick={() => void handleCreate()}
                                disabled={saving}
                                data-testid="qr-resource-submit"
                            >
                                <Check className="admin-sdx-icon-l" size={14} />
                                {t('admin2.qrm_save')}
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    setShowCreateForm(false);
                                    setDraft(emptyDraft());
                                }}
                            >
                                {t('admin2.cancel')}
                            </Button>
                        </div>
                    </div>
                )}

                {editing && (
                    <div className="admin-qrm-form" data-testid="qr-resource-edit-form">
                        <div className="admin-qrm-immutable">
                            <strong>{t('admin2.qrm_edit_immutable')}</strong>{' '}
                            <code className="admin-sdx-code">{editing.code}</code>,{' '}
                            <code className="admin-sdx-code">{editing.queue_tag}</code>{' '}
                            — {t('admin2.qrm_edit_immutable_hint')}
                        </div>
                        <Input
                            label={t('admin2.qrm_field_display_name')}
                            value={editDraft.display_name}
                            onChange={(e) => setEditDraft((p) => ({ ...p, display_name: e.target.value }))}
                        />
                        <Input
                            label={t('admin2.qrm_field_start_number')}
                            type="number"
                            min={1}
                            value={editDraft.start_number_online}
                            onChange={(e) => setEditDraft((p) => ({ ...p, start_number_online: e.target.value }))}
                        />
                        <Input
                            label={t('admin2.qrm_field_max_online')}
                            type="number"
                            min={1}
                            value={editDraft.max_online_per_day}
                            onChange={(e) => setEditDraft((p) => ({ ...p, max_online_per_day: e.target.value }))}
                        />
                        <Input
                            label={t('admin2.qrm_field_cabinet')}
                            value={editDraft.default_cabinet}
                            onChange={(e) => setEditDraft((p) => ({ ...p, default_cabinet: e.target.value }))}
                        />
                        <div className="admin-qrm-form-span admin-sdx-step-nav">
                            <Button
                                variant="primary"
                                size="sm"
                                onClick={() => void handleUpdate()}
                                disabled={saving}
                                data-testid="qr-resource-edit-submit"
                            >
                                <Check className="admin-sdx-icon-l" size={14} />
                                {t('admin2.qrm_save')}
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setEditing(null)}>
                                <X className="admin-sdx-icon-l" size={14} />
                                {t('admin2.cancel')}
                            </Button>
                        </div>
                    </div>
                )}

                {loading ? (
                    <div className="admin-sdx-note">{t('admin2.qrm_loading')}</div>
                ) : resources.length === 0 ? (
                    <div className="admin-sdx-note" data-testid="qr-resource-empty">
                        {t('admin2.qrm_empty')}
                    </div>
                ) : (
                    <div className="admin-qrm-table-wrap">
                        <table className="admin-qrm-table" data-testid="qr-resource-table">
                            <thead>
                                <tr>
                                    <th className="admin-qrm-th">{t('admin2.qrm_col_code')}</th>
                                    <th className="admin-qrm-th">{t('admin2.qrm_col_tag')}</th>
                                    <th className="admin-qrm-th">{t('admin2.qrm_col_display_name')}</th>
                                    <th className="admin-qrm-th">{t('admin2.qrm_col_numbers')}</th>
                                    <th className="admin-qrm-th">{t('admin2.qrm_col_cabinet')}</th>
                                    <th className="admin-qrm-th">{t('admin2.qrm_col_status')}</th>
                                    <th className="admin-qrm-th">{t('admin2.qrm_col_actions')}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {resources.map((resource) => (
                                    <tr key={resource.id} className="admin-qrm-tr" data-testid={`qr-resource-row-${resource.id}`}>
                                        <td className="admin-qrm-td">
                                            <code className="admin-sdx-code">{resource.code}</code>
                                        </td>
                                        <td className="admin-qrm-td">
                                            <code className="admin-sdx-code">{resource.queue_tag}</code>
                                        </td>
                                        <td className="admin-qrm-td">{resource.display_name}</td>
                                        <td className="admin-qrm-td">
                                            {resource.start_number_online} / {resource.max_online_per_day}
                                        </td>
                                        <td className="admin-qrm-td">{resource.default_cabinet || '—'}</td>
                                        <td className="admin-qrm-td">
                                            {resource.active ? (
                                                <Badge data-testid="qr-resource-badge-active">{t('admin2.qrm_status_active')}</Badge>
                                            ) : (
                                                <Badge variant="secondary" data-testid="qr-resource-badge-draft">{t('admin2.qrm_status_draft')}</Badge>
                                            )}
                                        </td>
                                        <td className="admin-qrm-td-right">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => openEdit(resource)}
                                                disabled={saving}
                                                aria-label={t('admin2.qrm_edit')}
                                            >
                                                <Edit2 size={13} />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => void handleActivateToggle(resource)}
                                                disabled={saving}
                                                title={resource.active ? t('admin2.qrm_deactivate') : t('admin2.qrm_activate')}
                                                aria-label={resource.active ? t('admin2.qrm_deactivate') : t('admin2.qrm_activate')}
                                                data-testid={`qr-resource-toggle-${resource.id}`}
                                            >
                                                {resource.active ? (
                                                    <ShieldOff size={13} />
                                                ) : (
                                                    <ShieldCheck size={13} />
                                                )}
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

export default QueueResourceManager;
