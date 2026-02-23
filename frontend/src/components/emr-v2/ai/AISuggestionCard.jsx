/**
 * AISuggestionCard - Single AI suggestion UI
 * 
 * CRITICAL: 
 * - Clicking "Apply" MUST go through parent's setField
 * - AI only suggests, doctor confirms
 */
import './AISuggestionCard.css';

/**
 * Format confidence as percentage
 */
function formatConfidence(confidence) {
  if (typeof confidence !== 'number') return '';
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Get confidence color class
 */
function getConfidenceClass(confidence) {
  if (confidence >= 0.8) return 'ai-suggestion-card__confidence--high';
  if (confidence >= 0.5) return 'ai-suggestion-card__confidence--medium';
  return 'ai-suggestion-card__confidence--low';
}

/**
 * AISuggestionCard Component
 * 
 * @param {Object} props
 * @param {Object} props.suggestion - Suggestion object
 * @param {Function} props.onApply - Apply callback (receives suggestion)
 * @param {Function} props.onDismiss - Dismiss callback (receives suggestion.id)
 * @param {boolean} props.disabled - Disable apply button
 */
export function AISuggestionCard({
  suggestion,
  onApply,
  onDismiss,
  disabled = false
}) {
  const { id, content, confidence, explanation } = suggestion;

  const handleApply = () => {
    if (!disabled && onApply) {
      onApply(suggestion);
    }
  };

  const handleDismiss = () => {
    if (onDismiss) {
      onDismiss(id);
    }
  };

  return (
    <div className="ai-suggestion-card">
            {/* Header */}
            <div className="ai-suggestion-card__header">
                <span className="ai-suggestion-card__icon">🤖</span>
                <span className="ai-suggestion-card__label">AI предлагает</span>
                {confidence &&
        <span className={`ai-suggestion-card__confidence ${getConfidenceClass(confidence)}`}>
                        {formatConfidence(confidence)}
                    </span>
        }
                <button
          className="ai-suggestion-card__close"
          onClick={handleDismiss}
          title="Закрыть">
          
                    ×
                </button>
            </div>

            {/* Content preview */}
            <div className="ai-suggestion-card__content">
                {content}
            </div>

            {/* Explanation (if available) */}
            {explanation &&
      <div className="ai-suggestion-card__explanation">
                    💡 {explanation}
                </div>
      }

            {/* Actions */}
            <div className="ai-suggestion-card__actions">
                <button
          className="ai-suggestion-card__apply"
          onClick={handleApply}
          disabled={disabled}>
          
                    ✓ Применить
                </button>
                <button
          className="ai-suggestion-card__dismiss"
          onClick={handleDismiss}>
          
                    Отклонить
                </button>
            </div>

            {/* Disclaimer */}
            <div className="ai-suggestion-card__disclaimer">
                AI не ставит диагнозы. Решение принимает врач.
            </div>
        </div>);

}

export default AISuggestionCard;