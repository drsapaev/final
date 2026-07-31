
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

import { useState, useCallback } from 'react';
import { History, Pin, Edit2, Trash2, X, Save, Plus } from 'lucide-react';
import { useDoctorSectionTemplates, SECTION_LABELS } from '../../hooks/useDoctorSectionTemplates';
import './DoctorTemplatesPanel.css';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

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
    onApply?: (text: string) => void;
    onClose?: () => void;
    isOpen?: boolean;
}) {
  const { t: rawT } = useTranslation(); const t = rawT;
    const {
        templates,
        loading,
        hasTemplates,
        pinTemplate,
        unpinTemplate,
        updateTemplate,
        deleteTemplate,
    } = useDoctorSectionTemplates({ section, icd10Code });

    // Edit state
    const [editingTemplate, setEditingTemplate] = useState<Record<string, unknown> | null>(null);
    const [editText, setEditText] = useState('');
    // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
    const [confirm, confirmDialog] = useConfirm();

    // Handle template click (apply)
    const handleApply = useCallback((template: Record<string, unknown>) => {
        onApply?.(template.template_text as string);
        onClose?.();
    }, [onApply, onClose]);

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
    }, []);

    // Handle edit save
    const handleEditSave = useCallback(async (mode: string) => {
        if (!editingTemplate || !editText.trim()) return;
        await updateTemplate(String((editingTemplate as { id: string | number }).id), editText, mode as 'replace' | 'save_as_new');
        setEditingTemplate(null);
        setEditText('');
    }, [editingTemplate, editText, updateTemplate]);

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
                    ) : !hasTemplates ? (
                        <div className="doctor-templates-empty">
                            <History size={32} opacity={0.3} />
                            <p>{t18('misc.dtp_net_sohranyonnyh_shablonov')}</p>
                            <small>
                                {icd10Code
                                    ? t18('misc.dtp_dlya_diagnoza_icd10code', { icd10Code: icd10Code })
                                    : t18('misc.dtp_dlya_etoy_sektsii')}
                            </small>
                            <small style={{ marginTop: 'var(--mac-spacing-2)', opacity: 0.7 }}>
                                Шаблоны создаются автоматически при подписании EMR
                            </small>
                        </div>
                    ) : (
                        <div className="doctor-templates-list">
                            {templates.map((template: unknown) => {
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
                                        onClick={() => handleApply(tmpl)}
                                    >
                                        <div className="doctor-templates-item-text">
                                            {(tmpl.template_text as string).substring(0, 200)}
                                            {(tmpl.template_text as string).length > 200 && '...'}
                                        </div>

                                        {/* Badges */}
                                        <div className="doctor-templates-item-badges">
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
                                </div>
                                );
                            })}
                        </div>
                    )}
                </div>

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
                                    onClick={() => handleEditSave('replace')}
                                    title={t18('misc.dtp_obnovit_suschestvuyuschiy_sh')}
                                >
                                    <Save size={14} />
                                    Заменить старый
                                </button>
                                <button
                                    type="button"
                                    className="doctor-templates-edit-btn doctor-templates-edit-btn--success"
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


