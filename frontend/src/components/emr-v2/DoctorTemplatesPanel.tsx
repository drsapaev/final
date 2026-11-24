
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
/**
 * DoctorTemplatesPanel - Universal "Мой опыт" panel for all EMR sections
 * 
 * Reusable modal that displays doctor's personalized templates.
 * Can be used in any section: Treatment, Recommendations, Examination, etc.
 * 
 * Features:
 * - 📌 Pin/Unpin templates
 * - ✏️ Edit templates (replace / save as new)
 * - 🗑️ Delete templates
 * - Frequency badges (часто/редко)
 * - Stale warning (давно не использовал)
 */

import { useState, useCallback, useRef } from 'react';
import { History, Pin, Edit2, Trash2, X, Save, Plus } from 'lucide-react';
import { useDoctorSectionTemplates, SECTION_LABELS } from '../../hooks/useDoctorSectionTemplates';
import './DoctorTemplatesPanel.css';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Input, Textarea } from '../ui/macos';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

/** EMRTEMPL-FE-001 (audit 3886 round 23): module-level style constant —
 * the ui-ratchet forbids new inline style literals, raw hex colors and
 * var() usages without a fallback. */
const EDIT_ERROR_STYLE: React.CSSProperties = {
    color: 'var(--accent-danger, currentcolor)',
    fontSize: 'var(--mac-font-size-sm, inherit)',
    marginTop: 'var(--mac-spacing-2, 8px)',
};

/**
 * DoctorTemplatesPanel Component
 * 
 * @param {Object} props
 * @param {string} props.section - Section type (treatment, recommendations, etc.)
 * @param {string} [props.icd10Code] - ICD-10 code for filtering
 * @param {Function} props.onApply - Called when template is selected (text) => void
 * @param {Function} props.onClose - Called when panel is closed
 * @param {boolean} props.isOpen - Panel visibility
 */
export function DoctorTemplatesPanel({
    section,
    icd10Code = null,
    onApply,
    onClose,
    isOpen = false,
}: {
    section: string;
    icd10Code?: string | null;
    onApply?: (text: string, source?: Record<string, unknown>) => void;
    onClose?: () => void;
    isOpen?: boolean;
}) {
  const { t: rawT } = useTranslation(); const t = rawT;
    const {
        templates,
        loading,
        error,
        hasTemplates,
        refetch,
        pinTemplate,
        unpinTemplate,
        updateTemplate,
        reviewTemplate,
        deleteTemplate,
    } = useDoctorSectionTemplates({ section, icd10Code });

    // Edit state
    const [editingTemplate, setEditingTemplate] = useState<Record<string, unknown> | null>(null);
    const [editText, setEditText] = useState('');
    // EMRTEMPL-FE-001 (audit 3886 round 23): a failed update must keep the
    // dialog open with the typed revision — never silently discard it.
    const [editError, setEditError] = useState('');
    const [editSaving, setEditSaving] = useState(false);
    const [search, setSearch] = useState('');
    const [preview, setPreview] = useState<{ item: Record<string, unknown>; text: string }>();
    const [reviewBusy, setReviewBusy] = useState(false);
    const [reviewFailed, setReviewFailed] = useState(false);
    const previewTextarea = useRef<HTMLTextAreaElement>(null);
    // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
    const [confirm, confirmDialog] = useConfirm();

    // Handle template click (apply)
    const handleApply = useCallback((template: Record<string, unknown>, text = String(template.template_text ?? '')) => {
        if (!template.reviewed_at || !text.trim()) return;
        onApply?.(text, {
            source: 'section_template',
            templateId: String(template.id),
            templateRevision: Number(template.template_revision),
        });
        setPreview(undefined);
        onClose?.();
    }, [onApply, onClose]);

    async function handleReview(template: Record<string, unknown>) {
        setReviewFailed(false);
        setReviewBusy(true);
        try {
            await reviewTemplate(String(template.id), Number(template.template_revision), !template.reviewed_at);
            setPreview(undefined);
        } catch {
            setReviewFailed(true);
        } finally {
            setReviewBusy(false);
        }
    }

    // Handle pin toggle
    const handlePinToggle = useCallback(async (template: Record<string, unknown>, e: React.MouseEvent<HTMLElement>) => {
        e.stopPropagation();
        if (template.is_pinned) {
            await unpinTemplate(String(template.id));
        } else {
            await pinTemplate(String(template.id));
        }
    }, [pinTemplate, unpinTemplate]);

    // Handle edit start
    const handleEditStart = useCallback((template: Record<string, unknown>, e: React.MouseEvent<HTMLElement>) => {
        e.stopPropagation();
        setEditingTemplate(template);
        setEditText(template.template_text as string);
        setEditError('');
        setPreview(undefined);
        setSearch('');
    }, []);

    // Handle edit save
    const handleEditSave = useCallback(async (mode: string) => {
        if (!editingTemplate || !editText.trim() || editSaving) return;
        setEditSaving(true);
        setEditError('');
        const result = await updateTemplate(
            String((editingTemplate as { id: string | number }).id),
            editText,
            mode as 'replace' | 'save_as_new',
        ) as { success?: boolean; error?: string } | undefined;
        setEditSaving(false);
        // EMRTEMPL-FE-001: a FAILED update must NOT close the dialog or
        // discard the typed revision — surface the failure and let the
        // doctor retry or cancel explicitly.
        if (!result?.success) {
            setEditError(result?.error || t18('misc.dtp_edit_save_failed'));
            return;
        }
        setEditingTemplate(null);
        setEditText('');
    }, [editingTemplate, editText, editSaving, updateTemplate]);

    // Handle delete
    const handleDelete = useCallback(async (template: Record<string, unknown>, e: React.MouseEvent<HTMLElement>) => {
        e.stopPropagation();
        // P-013 fix: replaced window.confirm() with shared useConfirm hook.
        const ok = await (confirm as unknown as (opts: Record<string, unknown>) => Promise<boolean>)({
            title: t18('misc.dtp_udalenie_shablona'),
            message: t18('misc.dtp_udalit_etot_shablon'),
            description: t18('misc.dtp_eto_deystvie_neobratimo'),
            confirmLabel: t18('misc.delete'),
            cancelLabel: t18('misc.cancel'),
            intent: 'danger',
        });
        if (ok) {
            await deleteTemplate(String(template.id));
        }
    }, [deleteTemplate, confirm]);

    // Handle close
    const handleClose = useCallback(() => {
        setEditingTemplate(null);
        setEditText('');
        setEditError('');
        setPreview(undefined);
        setSearch('');
        onClose?.();
    }, [onClose]);

    if (!isOpen) return null;

    const sectionLabel = (SECTION_LABELS as Record<string, string>)[section] || section;
    const backdropStyle = { border: 'none', margin: 0, padding: 0 };

    return (
        <div className="doctor-templates-overlay">
            {/* Backdrop */}
            <button
                type="button"
                className="doctor-templates-backdrop"
                onClick={handleClose}
                tabIndex={-1}
                style={backdropStyle}
                aria-label={t18('misc.dtp_zakryt_panel_shablonov')}
            />

            {/* Panel */}
            <div className="doctor-templates-panel">
                {/* Header */}
                <div className="doctor-templates-header">
                    <div className="doctor-templates-title">
                        <History size={18} />
                        <span>Мой опыт: {sectionLabel}</span>
                        {icd10Code && (
                            <span className="doctor-templates-icd">{icd10Code}</span>
                        )}
                    </div>
                    <button
                        className="doctor-templates-close"
                        onClick={handleClose}
                        aria-label={t18('misc.dtp_zakryt_panel_shablonov_secti', { sectionLabel: sectionLabel })}
                        title={t18('misc.dtp_zakryt')}
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Content */}
                <div className="doctor-templates-content">
                    {loading ? (
                        <div className="doctor-templates-loading">
                            Загрузка...
                        </div>
                    ) : error ? (
                        <div className="doctor-templates-empty" role="alert">
                            <History size={32} opacity={0.3} />
                            <p>{t18('misc.dtp_oshibka_zagruzki_shablonov')}</p>
                            <small className="doctor-templates-error-detail">{String(error)}</small>
                            <button
                                type="button"
                                className="doctor-templates-retry"
                                onClick={() => refetch()}
                            >
                                {t18('misc.dtp_povtorit')}
                            </button>
                        </div>
                    ) : !hasTemplates ? (
                        <div className="doctor-templates-empty">
                            <History size={32} opacity={0.3} />
                            <p>{t18('misc.dtp_net_sohranyonnyh_shablonov')}</p>
                            <small>
                                {icd10Code
                                    ? t18('misc.dtp_dlya_diagnoza_icd10code', { icd10Code: icd10Code })
                                    : t18('misc.dtp_dlya_etoy_sektsii')}
                            </small>
                            <small>{t('emr_workspace.template_learned')}</small>
                        </div>
                    ) : (
                        <div className="doctor-templates-list">
                            <label className="emr-workspace-field">{t('emr_workspace.template_search')}
                                <Input aria-label={t('emr_workspace.template_search')} value={search}
                                    onChange={event => setSearch(event.target.value)} />
                            </label>
                            {templates.filter((template: unknown) => String(
                                (template as Record<string, unknown>).template_text,
                            ).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())).map((template: unknown) => {
                                const tmpl = template as Record<string, unknown>;
                                return (
                                <div
                                    key={String(tmpl.id)}
                                    className={`doctor-templates-item ${tmpl.is_pinned ? 'doctor-templates-item--pinned' : ''}`}
                                >
                                    {/* Actions */}
                                    <div className="doctor-templates-item-actions">
                                        <button
                                            type="button"
                                            onClick={(e: React.MouseEvent<HTMLElement>) => handlePinToggle(tmpl, e)}
                                            className={`doctor-templates-action-btn ${tmpl.is_pinned ? 'active' : ''}`}
                                            aria-label={t18('misc.dtp_template_is_pinned_otkrepit_', { is_pinned: tmpl.is_pinned ? 'Открепить' : 'Закрепить' })}
                                            title={tmpl.is_pinned ? t18('misc.dtp_otkrepit') : t18('misc.dtp_zakrepit')}
                                        >
                                            <Pin size={14} />
                                        </button>
                                        <button
                                            type="button"
                                            onClick={(e: React.MouseEvent<HTMLElement>) => handleEditStart(tmpl, e)}
                                            className="doctor-templates-action-btn"
                                            aria-label={t18('misc.dtp_redaktirovat_shablon_vracha')}
                                            title={t18('misc.dtp_redaktirovat')}
                                        >
                                            <Edit2 size={14} />
                                        </button>
                                        <button
                                            type="button"
                                            onClick={(e: React.MouseEvent<HTMLElement>) => handleDelete(tmpl, e)}
                                            className="doctor-templates-action-btn doctor-templates-action-btn--danger"
                                            aria-label={t18('misc.dtp_udalit_shablon_vracha')}
                                            title={t18('misc.dtp_udalit')}
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>

                                    {/* Content - clickable to apply */}
                                    <button
                                        type="button"
                                        className="doctor-templates-item-content"
                                        onClick={() => {
                                            setReviewFailed(false);
                                            setPreview({ item: tmpl, text: String(tmpl.template_text ?? '') });
                                        }}
                                    >
                                        <div className="doctor-templates-item-text">
                                            {(tmpl.template_text as string).substring(0, 200)}
                                            {(tmpl.template_text as string).length > 200 && '...'}
                                        </div>

                                        {/* Badges */}
                                        <div className="doctor-templates-item-badges">
                                            <span className="doctor-templates-badge">
                                                {t(tmpl.reviewed_at ? 'emr_workspace.template_reviewed' : 'emr_workspace.template_needs_review')}
                                            </span>
                                            {Boolean(tmpl.is_stale) && (
                                                <span className="doctor-templates-badge doctor-templates-badge--stale">
                                                    Давно не использовал
                                                </span>
                                            )}
                                            {Boolean(tmpl.frequency_label) && !tmpl.is_stale && (
                                                <span className={t18('misc.dtp_doctor_templates_badge_docto', { rare: tmpl.frequency_label === 'часто' ? 'frequent' : 'rare' })}>
                                                    {String(tmpl.frequency_label)}
                                                </span>
                                            )}
                                            {Boolean(tmpl.icd10_code) && (
                                                <span className="doctor-templates-badge doctor-templates-badge--icd">
                                                    {String(tmpl.icd10_code)}
                                                </span>
                                            )}
                                        </div>
                                    </button>
                                    {Boolean(tmpl.reviewed_at) && String(tmpl.template_text).length <= 100
                                      && !/[\n\r]|\{\{/.test(String(tmpl.template_text)) && (
                                        <Button type="button" size="small" variant="outline" onClick={() => handleApply(tmpl)}>
                                            {t('emr_workspace.template_quick_insert')}
                                        </Button>
                                    )}
                                </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {preview && <Dialog open onClose={() => setPreview(undefined)} maxWidth="md" fullWidth>
                    <DialogTitle>{t('emr_workspace.template_preview')}</DialogTitle>
                    <DialogContent>
                        <label className="emr-workspace-field">{t('emr_workspace.template_text')}
                            <Textarea ref={previewTextarea} aria-label={t('emr_workspace.template_text')}
                                rows={9} value={preview.text} readOnly={!preview.item.reviewed_at}
                                onChange={event => setPreview({ ...preview, text: event.target.value })} />
                        </label>
                        <p>{t(preview.item.reviewed_at ? 'emr_workspace.template_select_help' : 'emr_workspace.template_review_help')}</p>
                        {reviewFailed && <p role="alert">{t('emr_workspace.save_error')}</p>}
                    </DialogContent>
                    <DialogActions>
                        <Button type="button" size="small" variant="ghost" onClick={() => setPreview(undefined)}>{t('misc.cancel')}</Button>
                        <Button type="button" size="small" variant="outline" disabled={reviewBusy}
                            onClick={() => void handleReview(preview.item)}>
                            {t(preview.item.reviewed_at ? 'emr_workspace.template_revoke' : 'emr_workspace.template_approve')}
                        </Button>
                        {Boolean(preview.item.reviewed_at) && <Button type="button" size="small"
                            disabled={!preview.text.trim() || /\{\{[^}]*\}\}/.test(preview.text)} onClick={() => {
                                const field = previewTextarea.current;
                                const selection = field && field.selectionStart !== field.selectionEnd
                                    ? preview.text.slice(field.selectionStart, field.selectionEnd) : preview.text;
                                handleApply(preview.item, selection);
                            }}>{t('emr_workspace.template_insert')}</Button>}
                    </DialogActions>
                </Dialog>}

                {/* Edit Modal */}
                {editingTemplate && (
                    <div className="doctor-templates-edit-overlay">
                        <div className="doctor-templates-edit-panel">
                            <div className="doctor-templates-edit-header">
                                <Edit2 size={16} />
                                <span>{t18('misc.dtp_redaktirovat_shablon')}</span>
                            </div>
                            <textarea
                                className="doctor-templates-edit-textarea"
                                aria-label={t18('misc.dtp_tekst_shablona_vracha')}
                                value={editText}
                                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setEditText(e.target.value)}
                                rows={6}
                                autoFocus
                            />
                            {editError && (
                                <div role="alert" style={EDIT_ERROR_STYLE}>
                                    {editError}
                                </div>
                            )}
                            <div className="doctor-templates-edit-actions">
                                <button
                                    type="button"
                                    className="doctor-templates-edit-btn doctor-templates-edit-btn--secondary"
                                    onClick={() => setEditingTemplate(null)}
                                >
                                    Отмена
                                </button>
                                <button
                                    type="button"
                                    className="doctor-templates-edit-btn doctor-templates-edit-btn--primary"
                                    disabled={editSaving}
                                    onClick={() => handleEditSave('replace')}
                                    title={t18('misc.dtp_obnovit_suschestvuyuschiy_sh')}
                                >
                                    <Save size={14} />
                                    Заменить старый
                                </button>
                                <button
                                    type="button"
                                    className="doctor-templates-edit-btn doctor-templates-edit-btn--success"
                                    disabled={editSaving}
                                    onClick={() => handleEditSave('save_as_new')}
                                    title={t18('misc.dtp_sozdat_novyy_shablon_s_izmen')}
                                >
                                    <Plus size={14} />
                                    Сохранить как новый
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Footer */}
                <div className="doctor-templates-footer">
                    Кликните на шаблон, чтобы вставить в текст
                </div>
            </div>
            {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
            {confirmDialog}
        </div>
    );
}

/**
 * DoctorTemplatesButton - Trigger button for opening the panel
 * 
 * @param {Object} props
 * @param {Function} props.onClick - Click handler
 * @param {boolean} [props.disabled] - Disabled state
 * @param {boolean} [props.hasTemplates] - Show count badge
 * @param {number} [props.count] - Number of templates
 */
export function DoctorTemplatesButton({
    onClick,
    disabled = false,
    hasTemplates = false,
    count = 0,
}: {
    onClick: () => void;
    disabled?: boolean;
    hasTemplates?: boolean;
    count?: number;
}) {
    return (
        <button
            type="button"
            className={`doctor-templates-btn ${hasTemplates ? 'doctor-templates-btn--active' : ''}`}
            onClick={onClick}
            disabled={disabled}
            title={hasTemplates ? t18('misc.dtp_moy_opyt_count_shablonov', { count: count }) : t18('misc.dtp_moy_opyt')}
        >
            <History size={14} />
            <span>{t18('misc.dtp_moy_opyt_2')}</span>
            {hasTemplates && count > 0 && (
                <span className="doctor-templates-btn-count">{count}</span>
            )}
        </button>
    );
}

export default DoctorTemplatesPanel;


