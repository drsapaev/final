// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * AISuggestionPanel - Sidebar panel for AI suggestions
 * 
 * Shows all suggestions grouped by field
 */
import PropTypes from 'prop-types';
import AISuggestionCard from './AISuggestionCard';
import './AISuggestionPanel.css';
import { useTranslation } from '../../../i18n/useTranslation';

/**
 * Field labels for grouping
 */
const getFieldLabels = (t) => ({
    complaints: t('misc.asp_field_complaints'),
    anamnesis_morbi: t('misc.asp_field_anamnesis_morbi'),
    anamnesis_vitae: t('misc.asp_field_anamnesis_vitae'),
    examination: t('misc.asp_field_examination'),
    diagnosis: t('misc.asp_field_diagnosis'),
    icd10_code: t('misc.asp_field_icd10_code'),
    treatment: t('misc.asp_field_treatment'),
    recommendations: t('misc.asp_field_recommendations'),
    notes: t('misc.asp_field_notes'),
});

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
    const { t } = useTranslation();
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
                            title={t('misc.asp_obnovit')}
                        >
                            🔄
                        </button>
                    )}
                    {onClose && (
                        <button
                            className="ai-suggestion-panel__close"
                            onClick={onClose}
                            title={t('misc.asp_zakryt')}
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
                        <p>{t('misc.asp_net_podskazok')}</p>
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
                                    {getFieldLabels(t)[field] || field}
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

AISuggestionPanel.propTypes = {
    suggestions: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        targetField: PropTypes.string,
        content: PropTypes.string,
        explanation: PropTypes.string,
        source: PropTypes.string,
        confidence: PropTypes.number,
    })),
    onApply: PropTypes.func,
    onDismiss: PropTypes.func,
    onRefresh: PropTypes.func,
    isLoading: PropTypes.bool,
    error: PropTypes.oneOfType([PropTypes.string, PropTypes.node]),
    disabled: PropTypes.bool,
    isOpen: PropTypes.bool,
    onClose: PropTypes.func,
};
