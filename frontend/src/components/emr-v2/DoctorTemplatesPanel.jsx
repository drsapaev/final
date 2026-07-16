import { useTranslation } from '../../i18n/useTranslation';
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
import PropTypes from 'prop-types';
import { History, Pin, Edit2, Trash2, X, Save, Plus } from 'lucide-react';
import { useDoctorSectionTemplates, SECTION_LABELS } from '../../hooks/useDoctorSectionTemplates';
import './DoctorTemplatesPanel.css';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

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
}) {
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
    const [editingTemplate, setEditingTemplate] = useState(null);
    const [editText, setEditText] = useState('');
    // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
    const [confirm, confirmDialog] = useConfirm();

    // Handle template click (apply)
    const handleApply = useCallback((template) => {
        onApply?.(template.template_text);
        onClose?.();
    }, [onApply, onClose]);

    // Handle pin toggle
    const handlePinToggle = useCallback(async (template, e) => {
        e.stopPropagation();
        if (template.is_pinned) {
            await unpinTemplate(template.id);
        } else {
            await pinTemplate(template.id);
        }
    }, [pinTemplate, unpinTemplate]);

    // Handle edit start
    const handleEditStart = useCallback((template, e) => {
        e.stopPropagation();
        setEditingTemplate(template);
        setEditText(template.template_text);
    }, []);

    // Handle edit save
    const handleEditSave = useCallback(async (mode) => {
        if (!editingTemplate || !editText.trim()) return;
        await updateTemplate(editingTemplate.id, editText, mode);
        setEditingTemplate(null);
        setEditText('');
    }, [editingTemplate, editText, updateTemplate]);

    // Handle delete
    const handleDelete = useCallback(async (template, e) => {
        e.stopPropagation();
        // P-013 fix: replaced window.confirm() with shared useConfirm hook.
        const ok = await confirm({
            title: t('misc.dtp_udalenie_shablona'),
            message: t('misc.dtp_udalit_etot_shablon'),
            description: t('misc.dtp_eto_deystvie_neobratimo'),
            confirmLabel: t('misc.delete'),
            cancelLabel: t('misc.cancel'),
            intent: 'danger',
        });
        if (ok) {
            await deleteTemplate(template.id);
        }
    }, [deleteTemplate, confirm]);

    // Handle close
    const handleClose = useCallback(() => {
        setEditingTemplate(null);
        setEditText('');
        onClose?.();
    }, [onClose]);

    if (!isOpen) return null;

    const sectionLabel = SECTION_LABELS[section] || section;
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
                aria-label={t('misc.dtp_zakryt_panel_shablonov')}
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
                        aria-label={t('misc.dtp_zakryt_panel_shablonov_secti', { sectionLabel: sectionLabel })}
                        title={t('misc.dtp_zakryt')}
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
                            <p>{t('misc.dtp_net_sohranyonnyh_shablonov')}</p>
                            <small>
                                {icd10Code
                                    ? t('misc.dtp_dlya_diagnoza_icd10code', { icd10Code: icd10Code })
                                    : t('misc.dtp_dlya_etoy_sektsii')}
                            </small>
                            <small style={{ marginTop: 'var(--mac-spacing-2)', opacity: 0.7 }}>
                                Шаблоны создаются автоматически при подписании EMR
                            </small>
                        </div>
                    ) : (
                        <div className="doctor-templates-list">
                            {templates.map(template => (
                                <div
                                    key={template.id}
                                    className={`doctor-templates-item ${template.is_pinned ? 'doctor-templates-item--pinned' : ''}`}
                                >
                                    {/* Actions */}
                                    <div className="doctor-templates-item-actions">
                                        <button
                                            type="button"
                                            onClick={(e) => handlePinToggle(template, e)}
                                            className={`doctor-templates-action-btn ${template.is_pinned ? 'active' : ''}`}
                                            aria-label={t('misc.dtp_template_is_pinned_otkrepit_', { is_pinned: template.is_pinned ? 'Открепить' : 'Закрепить' })}
                                            title={template.is_pinned ? t('misc.dtp_otkrepit') : t('misc.dtp_zakrepit')}
                                        >
                                            <Pin size={14} />
                                        </button>
                                        <button
                                            type="button"
                                            onClick={(e) => handleEditStart(template, e)}
                                            className="doctor-templates-action-btn"
                                            aria-label={t('misc.dtp_redaktirovat_shablon_vracha')}
                                            title={t('misc.dtp_redaktirovat')}
                                        >
                                            <Edit2 size={14} />
                                        </button>
                                        <button
                                            type="button"
                                            onClick={(e) => handleDelete(template, e)}
                                            className="doctor-templates-action-btn doctor-templates-action-btn--danger"
                                            aria-label={t('misc.dtp_udalit_shablon_vracha')}
                                            title={t('misc.dtp_udalit')}
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>

                                    {/* Content - clickable to apply */}
                                    <button
                                        type="button"
                                        className="doctor-templates-item-content"
                                        onClick={() => handleApply(template)}
                                    >
                                        <div className="doctor-templates-item-text">
                                            {template.template_text.substring(0, 200)}
                                            {template.template_text.length > 200 && '...'}
                                        </div>

                                        {/* Badges */}
                                        <div className="doctor-templates-item-badges">
                                            {template.is_stale && (
                                                <span className="doctor-templates-badge doctor-templates-badge--stale">
                                                    Давно не использовал
                                                </span>
                                            )}
                                            {template.frequency_label && !template.is_stale && (
                                                <span className={t('misc.dtp_doctor_templates_badge_docto', { rare: template.frequency_label === 'часто' ? 'frequent' : 'rare' })}>
                                                    {template.frequency_label}
                                                </span>
                                            )}
                                            {template.icd10_code && (
                                                <span className="doctor-templates-badge doctor-templates-badge--icd">
                                                    {template.icd10_code}
                                                </span>
                                            )}
                                        </div>
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Edit Modal */}
                {editingTemplate && (
                    <div className="doctor-templates-edit-overlay">
                        <div className="doctor-templates-edit-panel">
                            <div className="doctor-templates-edit-header">
                                <Edit2 size={16} />
                                <span>{t('misc.dtp_redaktirovat_shablon')}</span>
                            </div>
                            <textarea
                                className="doctor-templates-edit-textarea"
                                aria-label={t('misc.dtp_tekst_shablona_vracha')}
                                value={editText}
                                onChange={(e) => setEditText(e.target.value)}
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
                                    title={t('misc.dtp_obnovit_suschestvuyuschiy_sh')}
                                >
                                    <Save size={14} />
                                    Заменить старый
                                </button>
                                <button
                                    type="button"
                                    className="doctor-templates-edit-btn doctor-templates-edit-btn--success"
                                    onClick={() => handleEditSave('save_as_new')}
                                    title={t('misc.dtp_sozdat_novyy_shablon_s_izmen')}
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
}) {
    return (
        <button
            type="button"
            className={`doctor-templates-btn ${hasTemplates ? 'doctor-templates-btn--active' : ''}`}
            onClick={onClick}
            disabled={disabled}
            title={hasTemplates ? t('misc.dtp_moy_opyt_count_shablonov', { count: count }) : t('misc.dtp_moy_opyt')}
        >
            <History size={14} />
            <span>{t('misc.dtp_moy_opyt_2')}</span>
            {hasTemplates && count > 0 && (
                <span className="doctor-templates-btn-count">{count}</span>
            )}
        </button>
    );
}

export default DoctorTemplatesPanel;

DoctorTemplatesPanel.propTypes = {
    section: PropTypes.string,
    icd10Code: PropTypes.string,
    onApply: PropTypes.func,
    onClose: PropTypes.func,
    isOpen: PropTypes.bool,
};

DoctorTemplatesButton.propTypes = {
    onClick: PropTypes.func,
    disabled: PropTypes.bool,
    hasTemplates: PropTypes.bool,
    count: PropTypes.number,
};
