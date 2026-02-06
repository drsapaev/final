/**
 * AISuggestionPopover - Inline popup for field-level AI suggestions
 * 
 * IDE-like "Quick Fix" behavior:
 * - Shows near the field (not inline ghost text)
 * - Click to apply
 * - Shows confidence and explanation
 * 
 * RULES:
 * - NO auto-insert
 * - Click only
 * - Shows source (AI vs History)
 * 
 * Uses Portal to render outside EMR section DOM hierarchy to avoid z-index issues.
 */

import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import './AISuggestionPopover.css';

/**
 * Format confidence as percentage with color
 */
function getConfidenceInfo(confidence) {
    if (typeof confidence !== 'number') return { text: '', className: '' };

    const percent = Math.round(confidence * 100);
    let className = 'ai-popover__confidence--low';
    if (confidence >= 0.8) className = 'ai-popover__confidence--high';
    else if (confidence >= 0.5) className = 'ai-popover__confidence--medium';

    return { text: `${percent}%`, className };
}

/**
 * AISuggestionPopover Component
 * 
 * @param {Object} props
 * @param {Array} props.suggestions - Suggestions for this field
 * @param {Function} props.onApply - Apply callback (suggestion) => void
 * @param {Function} props.onDismiss - Dismiss callback (suggestionId) => void
 * @param {boolean} props.disabled - Disable apply
 * @param {string} props.position - Position: 'top' | 'bottom' | 'right'
 * @param {boolean} props.isOpen - Show popover
 * @param {Function} props.onClose - Close callback
 * @param {React.RefObject} props.anchorRef - Reference to the anchor element for positioning
 */
export function AISuggestionPopover({
    suggestions = [],
    onApply,
    onDismiss,
    disabled = false,
    position = 'bottom',
    isOpen = false,
    onClose,
    anchorRef,
}) {
    const popoverRef = useRef(null);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [popoverStyle, setPopoverStyle] = useState({});

    // Calculate position based on anchor element
    useEffect(() => {
        if (!isOpen || !anchorRef?.current) return;

        const updatePosition = () => {
            const anchorRect = anchorRef.current.getBoundingClientRect();
            const viewportHeight = window.innerHeight;
            const viewportWidth = window.innerWidth;

            let style = {
                position: 'fixed',
                zIndex: 10000,
            };

            // Calculate based on position prop
            if (position === 'bottom') {
                style.top = anchorRect.bottom + 4;
                style.left = anchorRect.left;

                // Check if it would go off-screen bottom
                if (style.top + 300 > viewportHeight) {
                    // Position above instead
                    style.top = anchorRect.top - 4;
                    style.transform = 'translateY(-100%)';
                }
            } else if (position === 'top') {
                style.top = anchorRect.top - 4;
                style.left = anchorRect.left;
                style.transform = 'translateY(-100%)';
            } else if (position === 'right') {
                style.top = anchorRect.top;
                style.left = anchorRect.right + 8;
            }

            // Prevent going off right edge
            if (style.left + 400 > viewportWidth) {
                style.left = viewportWidth - 420;
            }

            // Prevent going off left edge
            if (style.left < 10) {
                style.left = 10;
            }

            setPopoverStyle(style);
        };

        updatePosition();

        // Update on scroll/resize
        window.addEventListener('scroll', updatePosition, true);
        window.addEventListener('resize', updatePosition);

        return () => {
            window.removeEventListener('scroll', updatePosition, true);
            window.removeEventListener('resize', updatePosition);
        };
    }, [isOpen, anchorRef, position]);

    // Keyboard navigation
    useEffect(() => {
        if (!isOpen || suggestions.length === 0) return;

        const handleKeyDown = (e) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex(prev => (prev + 1) % suggestions.length);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (!disabled && onApply) {
                    onApply(suggestions[selectedIndex]);
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                onClose?.();
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, suggestions, selectedIndex, disabled, onApply, onClose]);

    // Click outside to close
    useEffect(() => {
        if (!isOpen) return;

        const handleClickOutside = (e) => {
            if (popoverRef.current && !popoverRef.current.contains(e.target)) {
                // Also check if click was on the anchor
                if (anchorRef?.current && !anchorRef.current.contains(e.target)) {
                    onClose?.();
                }
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen, onClose, anchorRef]);

    if (!isOpen || suggestions.length === 0) return null;

    const popoverContent = (
        <div
            ref={popoverRef}
            className="ai-popover ai-popover--portal"
            style={popoverStyle}
        >
            {/* Header */}
            <div className="ai-popover__header">
                <span className="ai-popover__icon">✨</span>
                <span className="ai-popover__label">AI предлагает</span>
                <span className="ai-popover__count">{suggestions.length} вариант{suggestions.length > 1 ? 'а' : ''}</span>
                <button className="ai-popover__close" onClick={onClose}>×</button>
            </div>

            {/* Suggestions */}
            <div className="ai-popover__list">
                {suggestions.map((suggestion, index) => {
                    const conf = getConfidenceInfo(suggestion.confidence);
                    const isSelected = index === selectedIndex;

                    return (
                        <div
                            key={suggestion.id}
                            className={`ai-popover__item ${isSelected ? 'ai-popover__item--selected' : ''}`}
                            onClick={() => !disabled && onApply?.(suggestion)}
                            onMouseEnter={() => setSelectedIndex(index)}
                        >
                            <div className="ai-popover__item-content">
                                <span className="ai-popover__item-text">{suggestion.content}</span>
                                {suggestion.explanation && (
                                    <span className="ai-popover__item-explanation">
                                        💡 {suggestion.explanation}
                                    </span>
                                )}
                            </div>
                            <div className="ai-popover__item-meta">
                                {conf.text && (
                                    <span className={`ai-popover__confidence ${conf.className}`}>
                                        {conf.text}
                                    </span>
                                )}
                                {suggestion.source && (
                                    <span className={`ai-popover__source ai-popover__source--${suggestion.source}`}>
                                        {suggestion.source === 'history' ? '📜 История' : '🤖 AI'}
                                    </span>
                                )}
                                <button
                                    className="ai-popover__apply"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (!disabled && onApply) onApply(suggestion);
                                    }}
                                    disabled={disabled}
                                >
                                    ✓
                                </button>
                                <button
                                    className="ai-popover__dismiss"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDismiss?.(suggestion.id);
                                    }}
                                >
                                    ×
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Footer */}
            <div className="ai-popover__footer">
                <span>↑↓ выбрать • Enter применить • Esc закрыть</span>
            </div>
        </div>
    );

    // Use portal to render at document.body level
    return createPortal(popoverContent, document.body);
}

export default AISuggestionPopover;
