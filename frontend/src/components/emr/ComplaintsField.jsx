/**
 * ComplaintsField - Эталонное поле «Жалобы»
 * 
 * v2.0 - Multi-suggestion support:
 * - AI возвращает 2-3 варианта из ранее заполненных шаблонов
 * - Врач выбирает один из вариантов или продолжает вводить
 * - Подсказки основаны на истории EMR, а не на генерации
 * 
 * Состояния:
 * 1. ПУСТО - placeholder, auto-focus
 * 2. В ПРОЦЕССЕ - печать, auto-save hint
 * 3. AI ПОДСКАЗКИ - несколько вариантов после паузы
 * 4. ЗАПОЛНЕНО - blur, готово к подписи
 * 5. ПОДПИСАНО - read-only
 * 6. ОШИБКА - при попытке подписать пустое
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import './ComplaintsField.css';
import logger from '../../utils/logger';

// Debounce hook
const useDebounce = (value, delay) => {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedValue(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);

    return debouncedValue;
};

const ComplaintsField = ({
    // Data
    value = '',
    onChange,

    // State
    isEditable = true,

    // AI - теперь возвращает массив вариантов
    aiEnabled = true,
    onRequestAI,          // (text) => Promise<Array<{id, text, source}>> - 2-3 варианта из шаблонов

    // Validation
    error,

    // UX
    autoFocus = false,
    onFieldTouch,         // для telemetry
    onBlur,

    // Labels
    label = 'Жалобы',
    placeholder = 'Введите жалобы пациента...'
}) => {
    const textareaRef = useRef(null);

    // Local state
    const [isFocused, setIsFocused] = useState(false);
    const [aiSuggestions, setAiSuggestions] = useState([]); // Массив вариантов
    const [selectedIndex, setSelectedIndex] = useState(0);   // Выбранный вариант
    const [isLoadingAI, setIsLoadingAI] = useState(false);
    const [lastSavedAt, setLastSavedAt] = useState(null);

    // Debounced value for AI suggestions (1.5 sec delay)
    const debouncedValue = useDebounce(value, 1500);

    // Auto-focus on mount
    useEffect(() => {
        if (autoFocus && isEditable && textareaRef.current) {
            const timer = setTimeout(() => {
                textareaRef.current?.focus();
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [autoFocus, isEditable]);

    // Request AI suggestions after pause
    useEffect(() => {
        if (!aiEnabled || !isEditable || !isFocused) return;
        if (!debouncedValue || debouncedValue.length < 5) {
            setAiSuggestions([]);
            return;
        }

        // Don't request if already has suggestions for this value
        if (aiSuggestions.length > 0) return;

        const requestSuggestions = async () => {
            if (!onRequestAI) return;

            setIsLoadingAI(true);
            try {
                const suggestions = await onRequestAI(debouncedValue);
                if (Array.isArray(suggestions) && suggestions.length > 0) {
                    setAiSuggestions(suggestions);
                    setSelectedIndex(0);
                }
            } catch (e) {
                logger.error('AI suggestion error:', e);
            } finally {
                setIsLoadingAI(false);
            }
        };

        requestSuggestions();
    }, [debouncedValue, aiEnabled, isEditable, isFocused, onRequestAI, aiSuggestions.length]);

    // Clear AI suggestions when value changes
    useEffect(() => {
        setAiSuggestions([]);
        setSelectedIndex(0);
    }, [value]);

    // Handlers
    const handleChange = useCallback((e) => {
        onChange?.(e.target.value);
        onFieldTouch?.('complaints');
    }, [onChange, onFieldTouch]);

    const handleFocus = useCallback(() => {
        setIsFocused(true);
    }, []);

    const handleBlur = useCallback(() => {
        setIsFocused(false);
        setLastSavedAt(new Date());
        onBlur?.();
    }, [onBlur]);

    const handleAcceptSuggestion = useCallback((suggestion) => {
        if (!suggestion) return;

        // Append suggestion text with proper separator
        const separator = value.trim().endsWith('.') ? ' ' : ', ';
        const newValue = value.trim() + separator + suggestion.text;

        onChange?.(newValue);
        setAiSuggestions([]);

        // Keep focus in field, cursor at end
        if (textareaRef.current) {
            textareaRef.current.focus();
            textareaRef.current.setSelectionRange(newValue.length, newValue.length);
        }
    }, [value, onChange]);

    const handleDismissAI = useCallback(() => {
        setAiSuggestions([]);
    }, []);

    const handleKeyDown = useCallback((e) => {
        if (aiSuggestions.length === 0) return;

        // Arrow Up/Down to navigate suggestions
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIndex(prev => Math.min(prev + 1, aiSuggestions.length - 1));
            return;
        }

        if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIndex(prev => Math.max(prev - 1, 0));
            return;
        }

        // Enter or Tab to accept selected suggestion
        if ((e.key === 'Enter' && e.altKey) || (e.key === 'Tab' && aiSuggestions.length > 0)) {
            e.preventDefault();
            handleAcceptSuggestion(aiSuggestions[selectedIndex]);
            return;
        }

        // 1, 2, 3 keys to select specific suggestion
        if (['1', '2', '3'].includes(e.key) && e.altKey) {
            e.preventDefault();
            const idx = parseInt(e.key) - 1;
            if (idx < aiSuggestions.length) {
                handleAcceptSuggestion(aiSuggestions[idx]);
            }
            return;
        }

        // Escape to dismiss suggestions
        if (e.key === 'Escape') {
            e.preventDefault();
            handleDismissAI();
            return;
        }
    }, [aiSuggestions, selectedIndex, handleAcceptSuggestion, handleDismissAI]);

    // Compute CSS classes
    const fieldClasses = [
        'complaints-field',
        isFocused && 'complaints-field--focused',
        !isEditable && 'complaints-field--readonly',
        error && 'complaints-field--error'
    ].filter(Boolean).join(' ');

    return (
        <div className="complaints-wrapper">
            <label className="complaints-label">{label}</label>

            <div className="complaints-container">
                <textarea
                    ref={textareaRef}
                    className={fieldClasses}
                    value={value}
                    onChange={handleChange}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    disabled={!isEditable}
                    rows={3}
                />

                {/* Auto-save indicator */}
                {isFocused && isEditable && !error && (
                    <div className="complaints-autosave">
                        {lastSavedAt
                            ? `💾 Сохранено ${lastSavedAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`
                            : '💾 Auto-save через 3 сек'
                        }
                    </div>
                )}

                {/* Error message */}
                {error && (
                    <div className="complaints-error">
                        ⚠️ {error}
                    </div>
                )}

                {/* AI Suggestions - Multiple variants */}
                {aiSuggestions.length > 0 && isEditable && (
                    <div className="complaints-ai-suggestions">
                        <div className="complaints-ai-header">
                            <span className="complaints-ai-header__icon">📋</span>
                            <span className="complaints-ai-header__title">Варианты из шаблонов:</span>
                            <button
                                className="complaints-ai-header__close"
                                onClick={handleDismissAI}
                                tabIndex={-1}
                            >
                                ✕
                            </button>
                        </div>

                        <div className="complaints-ai-list">
                            {aiSuggestions.map((suggestion, idx) => (
                                <button
                                    key={suggestion.id || idx}
                                    className={`complaints-ai-item ${idx === selectedIndex ? 'complaints-ai-item--selected' : ''}`}
                                    onClick={() => handleAcceptSuggestion(suggestion)}
                                    tabIndex={-1}
                                >
                                    <span className="complaints-ai-item__number">{idx + 1}</span>
                                    <span className="complaints-ai-item__text">{suggestion.text}</span>
                                    {suggestion.source && (
                                        <span className="complaints-ai-item__source">{suggestion.source}</span>
                                    )}
                                </button>
                            ))}
                        </div>

                        <div className="complaints-ai-footer">
                            <span>↑↓ выбор</span>
                            <span>Alt+Enter принять</span>
                            <span>Esc закрыть</span>
                        </div>
                    </div>
                )}

                {/* AI Loading indicator */}
                {isLoadingAI && (
                    <div className="complaints-ai-loading">
                        🔍 Ищу похожие записи...
                    </div>
                )}

                {/* Read-only indicator */}
                {!isEditable && (
                    <div className="complaints-readonly-badge">
                        🔒 Подписано
                    </div>
                )}
            </div>
        </div>
    );
};

export default ComplaintsField;
