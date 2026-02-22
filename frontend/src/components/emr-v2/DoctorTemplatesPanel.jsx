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
        if (window.confirm('Удалить этот шаблон?')) {
            await deleteTemplate(template.id);
        }
    }, [deleteTemplate]);

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
                aria-label="Закрыть панель шаблонов"
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
                        title="Закрыть"
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
                            <p>Нет сохранённых шаблонов</p>
                            <small>
                                {icd10Code
                                    ? `для диагноза ${icd10Code}`
                                    : 'для этой секции'}
                            </small>
                            <small style={{ marginTop: '8px', opacity: 0.7 }}>
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
                                            title={template.is_pinned ? 'Открепить' : 'Закрепить'}
                                        >
                                            <Pin size={14} />
                                        </button>
                                        <button
                                            type="button"
                                            onClick={(e) => handleEditStart(template, e)}
                                            className="doctor-templates-action-btn"
                                            title="Редактировать"
                                        >
                                            <Edit2 size={14} />
                                        </button>
                                        <button
                                            type="button"
                                            onClick={(e) => handleDelete(template, e)}
                                            className="doctor-templates-action-btn doctor-templates-action-btn--danger"
                                            title="Удалить"
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
                                                <span className={`doctor-templates-badge doctor-templates-badge--${template.frequency_label === 'часто' ? 'frequent' : 'rare'}`}>
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
                                <span>Редактировать шаблон</span>
                            </div>
                            <textarea
                                className="doctor-templates-edit-textarea"
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
                                    title="Обновить существующий шаблон"
                                >
                                    <Save size={14} />
                                    Заменить старый
                                </button>
                                <button
                                    type="button"
                                    className="doctor-templates-edit-btn doctor-templates-edit-btn--success"
                                    onClick={() => handleEditSave('save_as_new')}
                                    title="Создать новый шаблон с изменениями"
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
            title={hasTemplates ? `Мой опыт (${count} шаблонов)` : 'Мой опыт'}
        >
            <History size={14} />
            <span>Мой опыт</span>
            {hasTemplates && count > 0 && (
                <span className="doctor-templates-btn-count">{count}</span>
            )}
        </button>
    );
}

export default DoctorTemplatesPanel;
