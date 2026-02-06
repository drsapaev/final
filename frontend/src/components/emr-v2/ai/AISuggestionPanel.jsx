/**
 * AISuggestionPanel - Sidebar panel for AI suggestions
 * 
 * Shows all suggestions grouped by field
 */

import React from 'react';
import AISuggestionCard from './AISuggestionCard';
import './AISuggestionPanel.css';

/**
 * Field labels for grouping
 */
const FIELD_LABELS = {
    complaints: 'Жалобы',
    anamnesis_morbi: 'Анамнез заболевания',
    anamnesis_vitae: 'Анамнез жизни',
    examination: 'Осмотр',
    diagnosis: 'Диагноз',
    icd10_code: 'Код МКБ-10',
    treatment: 'Лечение',
    recommendations: 'Рекомендации',
    notes: 'Примечания',
};

/**
 * AISuggestionPanel Component
 * 
 * @param {Object} props
 * @param {Array} props.suggestions - All suggestions
 * @param {Function} props.onApply - Apply callback (receives suggestion)
 * @param {Function} props.onDismiss - Dismiss callback (receives suggestion.id)
 * @param {Function} props.onRefresh - Refresh suggestions
 * @param {boolean} props.isLoading - Loading state
 * @param {string} props.error - Error message
 * @param {boolean} props.disabled - Disable all apply buttons
 * @param {boolean} props.isOpen - Panel is open
 * @param {Function} props.onClose - Close callback
 */
export function AISuggestionPanel({
    suggestions = [],
    onApply,
    onDismiss,
    onRefresh,
    isLoading = false,
    error,
    disabled = false,
    isOpen = true,
    onClose,
}) {
    if (!isOpen) return null;

    // Group suggestions by field
    const groupedSuggestions = suggestions.reduce((acc, suggestion) => {
        const field = suggestion.targetField;
        if (!acc[field]) {
            acc[field] = [];
        }
        acc[field].push(suggestion);
        return acc;
    }, {});

    const hasAnySuggestions = suggestions.length > 0;

    return (
        <div className="ai-suggestion-panel">
            {/* Header */}
            <div className="ai-suggestion-panel__header">
                <div className="ai-suggestion-panel__title">
                    <span className="ai-suggestion-panel__icon">🤖</span>
                    <h3>AI Подсказки</h3>
                </div>
                <div className="ai-suggestion-panel__actions">
                    {onRefresh && (
                        <button
                            className="ai-suggestion-panel__refresh"
                            onClick={onRefresh}
                            disabled={isLoading}
                            title="Обновить"
                        >
                            🔄
                        </button>
                    )}
                    {onClose && (
                        <button
                            className="ai-suggestion-panel__close"
                            onClick={onClose}
                            title="Закрыть"
                        >
                            ×
                        </button>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="ai-suggestion-panel__content">
                {isLoading && (
                    <div className="ai-suggestion-panel__loading">
                        <span className="ai-suggestion-panel__spinner">⏳</span>
                        Анализирую...
                    </div>
                )}

                {error && (
                    <div className="ai-suggestion-panel__error">
                        ❌ {error}
                    </div>
                )}

                {!isLoading && !error && !hasAnySuggestions && (
                    <div className="ai-suggestion-panel__empty">
                        <p>Нет подсказок</p>
                        <span className="ai-suggestion-panel__empty-hint">
                            Продолжайте заполнять ЭМК — AI предложит подсказки по мере ввода
                        </span>
                    </div>
                )}

                {!isLoading && hasAnySuggestions && (
                    <div className="ai-suggestion-panel__groups">
                        {Object.entries(groupedSuggestions).map(([field, fieldSuggestions]) => (
                            <div key={field} className="ai-suggestion-panel__group">
                                <div className="ai-suggestion-panel__group-header">
                                    {FIELD_LABELS[field] || field}
                                </div>
                                {fieldSuggestions.map(suggestion => (
                                    <AISuggestionCard
                                        key={suggestion.id}
                                        suggestion={suggestion}
                                        onApply={onApply}
                                        onDismiss={onDismiss}
                                        disabled={disabled}
                                    />
                                ))}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Footer disclaimer */}
            <div className="ai-suggestion-panel__footer">
                ⚠️ AI не ставит диагнозы. Все решения принимает врач.
            </div>
        </div>
    );
}

export default AISuggestionPanel;
