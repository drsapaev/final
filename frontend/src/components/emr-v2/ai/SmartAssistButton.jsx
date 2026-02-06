/**
 * SmartAssistButton - AI help button for fields
 * 
 * IDE-like "lightbulb" behavior:
 * - Shows when field has content
 * - Click to get AI suggestions
 * - Positioned near the field
 */

import React from 'react';
import './SmartAssistButton.css';

/**
 * SmartAssistButton Component
 * 
 * @param {Object} props
 * @param {Function} props.onClick - Click handler
 * @param {boolean} props.isLoading - Loading state
 * @param {boolean} props.hasSuggestions - Has pending suggestions
 * @param {boolean} props.disabled - Button disabled
 * @param {string} props.size - 'small' | 'medium'
 */
export function SmartAssistButton({
    onClick,
    isLoading = false,
    hasSuggestions = false,
    disabled = false,
    size = 'small',
}) {
    return (
        <button
            type="button"
            className={`smart-assist-btn smart-assist-btn--${size} ${hasSuggestions ? 'smart-assist-btn--has-suggestions' : ''}`}
            onClick={onClick}
            disabled={disabled || isLoading}
            title={hasSuggestions ? 'Есть AI подсказки' : 'Получить AI подсказки'}
        >
            {isLoading ? (
                <span className="smart-assist-btn__spinner">⏳</span>
            ) : (
                <span className="smart-assist-btn__icon">
                    {hasSuggestions ? '✨' : '🧠'}
                </span>
            )}
            {hasSuggestions && (
                <span className="smart-assist-btn__badge"></span>
            )}
        </button>
    );
}

export default SmartAssistButton;
