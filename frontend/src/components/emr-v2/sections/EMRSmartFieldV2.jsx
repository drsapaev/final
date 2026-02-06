/**
 * EMRSmartFieldV2 - Text field with AI-powered suggestions
 * 
 * REPLACES old Ghost/MVP/Word modes with SAFE alternative:
 * - NO inline ghost text
 * - NO auto-insertion
 * - Suggestions shown NEXT TO the field (popover)
 * - Click to apply (through setField → reducer)
 * 
 * IDE-like behavior:
 * - Shows AI button when field has content
 * - Click AI button → show suggestion popover
 * - Keyboard: Tab to accept first suggestion
 * 
 * ⚠️ EXPERIMENTAL: Advanced Ghost Mode (Opt-in)
 * - Enables inline ghost text for rapid entry
 * - "AI draft – not yet committed" visual marker
 * - Explicit commit required (Tab/Enter)
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { SmartAssistButton } from '../ai/SmartAssistButton';
import { AISuggestionPopover } from '../ai/AISuggestionPopover';
import './EMRSmartFieldV2.css';

/**
 * EMRSmartFieldV2 Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler (value, metadata?)
 * @param {string} props.placeholder - Placeholder text
 * @param {boolean} props.multiline - Textarea or input
 * @param {number} props.rows - Rows for textarea
 * @param {boolean} props.disabled - Read-only
 * @param {string} props.id - Field ID (for scroll navigation)
 * @param {string} props.fieldName - Field name for AI
 * @param {Array} props.suggestions - AI suggestions for this field
 * @param {boolean} props.aiLoading - AI is loading
 * @param {Function} props.onApplySuggestion - Apply suggestion callback
 * @param {Function} props.onDismissSuggestion - Dismiss suggestion callback
 * @param {Function} props.onRequestAI - Request AI suggestions
 * @param {boolean} props.showAIButton - Show AI button
 * @param {boolean} props.experimentalGhostMode - Enable experimental ghost mode
 * @param {Function} props.onTelemetry - Telemetry callback (type, payload)
 */
export function EMRSmartFieldV2({
    value = '',
    onChange,
    placeholder = 'Начните ввод...',
    multiline = true,
    rows = 3,
    disabled = false,
    id,
    fieldName,
    suggestions = [],
    aiLoading = false,
    onApplySuggestion,
    onDismissSuggestion,
    onRequestAI,
    showAIButton = true,
    experimentalGhostMode = false,
    onTelemetry,
}) {
    const [isFocused, setIsFocused] = useState(false);
    const [showPopover, setShowPopover] = useState(false);
    const [ghostText, setGhostText] = useState('');
    const fieldRef = useRef(null);
    const containerRef = useRef(null);

    // Has pending suggestions
    const hasSuggestions = suggestions.length > 0;

    // Handle value change
    const handleChange = useCallback((e) => {
        onChange?.(e.target.value);
    }, [onChange]);

    // Handle focus
    const handleFocus = useCallback(() => {
        setIsFocused(true);
    }, []);

    // Handle blur
    const handleBlur = useCallback(() => {
        setIsFocused(false);
        // Delay closing popover to allow click
        setTimeout(() => {
            if (!containerRef.current?.contains(document.activeElement)) {
                setShowPopover(false);
            }
        }, 200);
    }, []);

    // Handle AI button click
    const handleAIButtonClick = useCallback(() => {
        if (hasSuggestions) {
            setShowPopover(!showPopover);
        } else if (onRequestAI) {
            onRequestAI(fieldName);
        }
    }, [hasSuggestions, showPopover, onRequestAI, fieldName]);

    // Handle apply suggestion
    const handleApply = useCallback((suggestion) => {
        // Merge strategy: append or replace based on current value
        let newValue;
        if (value.trim()) {
            if (experimentalGhostMode && suggestion.content.startsWith(value)) {
                // If suggestion extends current value (completion), replace it
                newValue = suggestion.content;
                onTelemetry?.({ type: 'ghost.accepted', payload: { suggestionId: suggestion.id, source: suggestion.source } });
            } else {
                // Append with newline
                newValue = `${value.trim()}\n${suggestion.content}`;
            }
        } else {
            newValue = suggestion.content;
        }

        onChange?.(newValue, {
            source: 'ai',
            suggestionId: suggestion.id,
            confidence: suggestion.confidence,
        });

        onApplySuggestion?.(suggestion);
        if (!experimentalGhostMode) {
            onTelemetry?.({ type: 'ai_popover.accepted', payload: { suggestionId: suggestion.id, source: suggestion.source } });
        }
        setShowPopover(false);
    }, [value, onChange, onApplySuggestion]);

    // Handle dismiss
    const handleDismiss = useCallback((suggestionId) => {
        onTelemetry?.({ type: 'ai.dismissed', payload: { suggestionId } });
        onDismissSuggestion?.(suggestionId);
        if (suggestions.length <= 1) {
            setShowPopover(false);
        }
    }, [onDismissSuggestion, suggestions.length]);

    // Show popover when suggestions arrive and field is focused
    useEffect(() => {
        if (hasSuggestions && isFocused) {
            if (!showPopover && !experimentalGhostMode) {
                // Auto-show popover when new suggestions arrive (standard mode)
                setShowPopover(true);
            }

            // Ghost Text Logic
            if (experimentalGhostMode && suggestions[0]?.content && value) {
                const topSuggestion = suggestions[0].content;
                if (topSuggestion.startsWith(value) && topSuggestion.length > value.length) {
                    setGhostText(topSuggestion.substring(value.length));
                } else {
                    setGhostText('');
                }
            } else {
                setGhostText('');
            }
        } else {
            setGhostText('');
        }
    }, [hasSuggestions, isFocused, showPopover, experimentalGhostMode, suggestions, value]);

    // Keyboard: Tab to accept first suggestion
    useEffect(() => {
        if (!showPopover || suggestions.length === 0) return;

        const handleKeyDown = (e) => {
            if (e.key === 'Tab' && !e.shiftKey && document.activeElement === fieldRef.current) {
                e.preventDefault();
                handleApply(suggestions[0]);
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [showPopover, suggestions, handleApply]);

    const InputComponent = multiline ? 'textarea' : 'input';

    return (
        <div
            ref={containerRef}
            className={`emr-smart-field-v2 ${isFocused ? 'emr-smart-field-v2--focused' : ''} ${disabled ? 'emr-smart-field-v2--disabled' : ''}`}
        >
            {/* Field */}
            <div className="emr-smart-field-v2__input-wrapper">
                <InputComponent
                    ref={fieldRef}
                    id={id}
                    className="emr-smart-field-v2__input"
                    value={value}
                    onChange={handleChange}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    placeholder={placeholder}
                    disabled={disabled}
                    rows={multiline ? rows : undefined}
                />

                {/* Ghost Text Overlay */}
                {experimentalGhostMode && ghostText && isFocused && (
                    <div className="emr-smart-field-v2__ghost-overlay">
                        <span className="emr-smart-field-v2__ghost-invisible">{value}</span>
                        <span className="emr-smart-field-v2__ghost-text">{ghostText}</span>
                        <span className="emr-smart-field-v2__ghost-marker">AI draft – not yet committed</span>
                    </div>
                )}

                {/* AI Button */}
                {showAIButton && !disabled && (
                    <div className="emr-smart-field-v2__ai-btn">
                        <SmartAssistButton
                            onClick={handleAIButtonClick}
                            isLoading={aiLoading}
                            hasSuggestions={hasSuggestions}
                            disabled={disabled}
                            size="small"
                        />
                    </div>
                )}
            </div>

            {/* Suggestion Popover */}
            {showPopover && (
                <AISuggestionPopover
                    suggestions={suggestions}
                    onApply={handleApply}
                    onDismiss={handleDismiss}
                    disabled={disabled}
                    isOpen={showPopover}
                    onClose={() => setShowPopover(false)}
                    position="bottom"
                    anchorRef={containerRef}
                />
            )}

            {/* Hint when focused with suggestions */}
            {hasSuggestions && isFocused && !showPopover && (
                <div className="emr-smart-field-v2__hint">
                    ✨ Есть AI подсказки — нажмите 🧠
                </div>
            )}
        </div>
    );
}

export default EMRSmartFieldV2;
