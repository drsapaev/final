/**
 * TreatmentTemplatesPanel v2
 * 
 * EMR v2 Compatible Treatment Templates
 * 
 * CRITICAL RULES:
 * - NO auto-insert
 * - Click only → through setField → reducer
 * - 1 insert = 1 undo
 * - Audit: template_applied (no PHI)
 */

import React, { useState, useMemo, useCallback } from 'react';
import treatmentTemplatesData from '../../../data/treatmentTemplates.json';
import './TreatmentTemplatesPanel.css';

/**
 * Category metadata
 */
const CATEGORY_META = {
    medications: { icon: '💊', label: 'Медикаменты' },
    examinations: { icon: '🔬', label: 'Обследования' },
    labs: { icon: '🧪', label: 'Анализы' },
    followup: { icon: '📅', label: 'Контроль' },
};

/**
 * Merge strategy: APPEND_WITH_SEPARATOR
 */
const mergeWithSeparator = (existing, templateBody) => {
    if (!existing || !existing.trim()) {
        return templateBody;
    }
    return `${existing.trim()}\n\n---\n${templateBody}`;
};

/**
 * TreatmentTemplatesButton - Simple trigger button
 */
export function TreatmentTemplatesButton({ onClick, disabled = false }) {
    if (disabled) return null;

    return (
        <button
            type="button"
            className="treatment-templates-btn"
            onClick={onClick}
            title="Открыть шаблоны"
        >
            📋 Шаблоны
        </button>
    );
}

/**
 * TreatmentTemplatesPanel - Modal with template list
 * 
 * @param {Object} props
 * @param {string} props.specialty - Current specialty
 * @param {string} props.currentValue - Current treatment field value
 * @param {Function} props.onApply - Callback (newValue, templateId) => void
 * @param {Function} props.onClose - Close panel
 * @param {boolean} props.isOpen - Panel visibility
 */
export function TreatmentTemplatesPanel({
    specialty = 'general',
    currentValue = '',
    onApply,
    onClose,
    isOpen = false,
}) {
    const [activeCategory, setActiveCategory] = useState('medications');
    const [searchQuery, setSearchQuery] = useState('');
    const [previewTemplate, setPreviewTemplate] = useState(null);

    // Get templates for specialty
    const templates = useMemo(() => {
        return treatmentTemplatesData[specialty] || treatmentTemplatesData.general;
    }, [specialty]);

    // Filter by search
    const filteredTemplates = useMemo(() => {
        const categoryTemplates = templates[activeCategory] || [];

        if (!searchQuery.trim()) return categoryTemplates;

        const query = searchQuery.toLowerCase();
        return categoryTemplates.filter(t =>
            t.title.toLowerCase().includes(query) ||
            t.body.toLowerCase().includes(query) ||
            (t.tags || []).some(tag => tag.toLowerCase().includes(query))
        );
    }, [templates, activeCategory, searchQuery]);

    // Handle insert
    const handleInsert = useCallback((template) => {
        const mergedValue = mergeWithSeparator(currentValue, template.body);
        onApply?.(mergedValue, template.id);
        setPreviewTemplate(null);
        setSearchQuery('');
        onClose?.();
    }, [currentValue, onApply, onClose]);

    // Handle preview
    const handlePreview = useCallback((template) => {
        setPreviewTemplate(template);
    }, []);

    // Handle close
    const handleClose = useCallback(() => {
        setPreviewTemplate(null);
        setSearchQuery('');
        onClose?.();
    }, [onClose]);

    if (!isOpen) return null;

    return (
        <div className="treatment-templates-overlay">
            {/* Backdrop */}
            <div className="treatment-templates-backdrop" onClick={handleClose} />

            {/* Panel */}
            <div className="treatment-templates-panel">
                {/* Header */}
                <div className="treatment-templates-header">
                    <h3>📋 Шаблоны лечения</h3>
                    <button className="treatment-templates-close" onClick={handleClose}>
                        ×
                    </button>
                </div>

                {/* Search */}
                <div className="treatment-templates-search">
                    <input
                        type="text"
                        placeholder="Поиск шаблона..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        autoFocus
                    />
                </div>

                {/* Categories */}
                <div className="treatment-templates-categories">
                    {Object.entries(CATEGORY_META).map(([key, meta]) => (
                        <button
                            key={key}
                            className={`treatment-templates-category ${activeCategory === key ? 'treatment-templates-category--active' : ''}`}
                            onClick={() => setActiveCategory(key)}
                        >
                            <span>{meta.icon}</span>
                            <span>{meta.label}</span>
                        </button>
                    ))}
                </div>

                {/* Template list */}
                <div className="treatment-templates-list">
                    {filteredTemplates.length > 0 ? (
                        filteredTemplates.map(template => (
                            <div
                                key={template.id}
                                className={`treatment-templates-item ${previewTemplate?.id === template.id ? 'treatment-templates-item--selected' : ''}`}
                            >
                                <div
                                    className="treatment-templates-item-content"
                                    onClick={() => handlePreview(template)}
                                >
                                    <span className="treatment-templates-item-title">{template.title}</span>
                                    <span className="treatment-templates-item-body">{template.body}</span>
                                    {template.tags && (
                                        <div className="treatment-templates-item-tags">
                                            {template.tags.map(tag => (
                                                <span key={tag} className="treatment-templates-tag">{tag}</span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <button
                                    className="treatment-templates-insert-btn"
                                    onClick={() => handleInsert(template)}
                                    title="Вставить в поле"
                                >
                                    ➕ Вставить
                                </button>
                            </div>
                        ))
                    ) : (
                        <div className="treatment-templates-empty">
                            Шаблоны не найдены
                        </div>
                    )}
                </div>

                {/* Preview */}
                {previewTemplate && (
                    <div className="treatment-templates-preview">
                        <div className="treatment-templates-preview-header">
                            👁️ Предпросмотр
                        </div>
                        <div className="treatment-templates-preview-content">
                            {previewTemplate.body}
                        </div>
                        <button
                            className="treatment-templates-preview-insert"
                            onClick={() => handleInsert(previewTemplate)}
                        >
                            ➕ Вставить в лечение
                        </button>
                    </div>
                )}

                {/* Footer disclaimer */}
                <div className="treatment-templates-footer">
                    ⚠️ Шаблон вставляется только по клику. Проверьте дозировки.
                </div>
            </div>
        </div>
    );
}

export default TreatmentTemplatesPanel;
