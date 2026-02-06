/**
 * EMRTextField - Универсальный компонент поля EMR с шаблонами
 * 
 * Используется для всех текстовых полей:
 * - Жалобы
 * - Анамнез заболевания
 * - Анамнез жизни
 * - Объективный статус
 * - Диагноз
 * - План
 * 
 * Особенности:
 * - AI показывает 2-3 варианта из ранее заполненных шаблонов
 * - После выбора варианта шаблоны закрываются
 * - Повторное появление только после нового ввода
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import './EMRTextField.css';

// Debounce hook
const useDebounce = (value, delay) => {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedValue(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);

    return debouncedValue;
};

const EMRTextField = ({
    // Data
    value = '',
    onChange,

    // State
    isEditable = true,

    // AI - возвращает массив вариантов [{id, text, source}]
    aiEnabled = true,
    onRequestAI,

    // Validation
    error,

    // UX
    autoFocus = false,
    onFieldTouch,
    onBlur,

    // Labels & Config
    label = null,
    placeholder = 'Введите текст...',
    fieldName = 'field',
    multiline = true,
    rows = 3
}) => {
    const textareaRef = useRef(null);
    const lastAcceptedValueRef = useRef(''); // Трекинг принятого значения

    // Local state
    const [isFocused, setIsFocused] = useState(false);
    const [aiSuggestions, setAiSuggestions] = useState([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [isLoadingAI, setIsLoadingAI] = useState(false);
    const [suggestionsDismissed, setSuggestionsDismissed] = useState(false);

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
        if (!aiEnabled || !isEditable || !isFocused || suggestionsDismissed) return;
        if (!debouncedValue || debouncedValue.length < 5) {
            setAiSuggestions([]);
            return;
        }

        // Не запрашивать если значение не изменилось после принятия
        if (debouncedValue === lastAcceptedValueRef.current) {
            return;
        }

        // Не запрашивать если уже есть подсказки
        if (aiSuggestions.length > 0) return;

        const requestSuggestions = async () => {
            if (!onRequestAI) return;

            setIsLoadingAI(true);
            try {
                const suggestions = await onRequestAI(debouncedValue, fieldName);
                if (Array.isArray(suggestions) && suggestions.length > 0) {
                    setAiSuggestions(suggestions);
                    setSelectedIndex(0);
                }
            } catch (e) {
                console.error('AI suggestion error:', e);
            } finally {
                setIsLoadingAI(false);
            }
        };

        requestSuggestions();
    }, [debouncedValue, aiEnabled, isEditable, isFocused, onRequestAI, fieldName, suggestionsDismissed]);

    // Сброс при изменении значения пользователем
    useEffect(() => {
        // Если новое значение отличается от принятого - разрешаем новые подсказки
        if (value !== lastAcceptedValueRef.current) {
            setSuggestionsDismissed(false);
            setAiSuggestions([]);
            setSelectedIndex(0);
        }
    }, [value]);

    // Handlers
    const handleChange = useCallback((e) => {
        onChange?.(e.target.value);
        onFieldTouch?.(fieldName);
    }, [onChange, onFieldTouch, fieldName]);

    const handleFocus = useCallback(() => {
        setIsFocused(true);
        setSuggestionsDismissed(false); // Разрешаем подсказки при фокусе
    }, []);

    const handleBlur = useCallback(() => {
        setIsFocused(false);
        onBlur?.();
    }, [onBlur]);

    const handleAcceptSuggestion = useCallback((suggestion) => {
        if (!suggestion) return;

        // Append suggestion text with proper separator
        const separator = value.trim().endsWith('.') ? ' ' : ', ';
        const newValue = value.trim() + separator + suggestion.text;

        // Запоминаем принятое значение чтобы не показывать подсказки сразу
        lastAcceptedValueRef.current = newValue;

        onChange?.(newValue);
        setAiSuggestions([]);
        setSuggestionsDismissed(true); // Блокируем повторное появление

        // Keep focus in field, cursor at end
        if (textareaRef.current) {
            textareaRef.current.focus();
            setTimeout(() => {
                textareaRef.current?.setSelectionRange(newValue.length, newValue.length);
            }, 0);
        }
    }, [value, onChange]);

    const handleDismissAI = useCallback(() => {
        setAiSuggestions([]);
        setSuggestionsDismissed(true);
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
        if ((e.key === 'Enter' && e.altKey) || (e.key === 'Tab' && aiSuggestions.length > 0 && !e.shiftKey)) {
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
        'emr-text-field',
        isFocused && 'emr-text-field--focused',
        !isEditable && 'emr-text-field--readonly',
        error && 'emr-text-field--error'
    ].filter(Boolean).join(' ');

    const InputComponent = multiline ? 'textarea' : 'input';

    return (
        <div className="emr-text-wrapper">
            <label className="emr-text-label">{label}</label>

            <div className="emr-text-container">
                <InputComponent
                    ref={textareaRef}
                    className={fieldClasses}
                    value={value}
                    onChange={handleChange}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    disabled={!isEditable}
                    rows={multiline ? rows : undefined}
                />

                {/* Error message */}
                {error && (
                    <div className="emr-text-error">
                        ⚠️ {error}
                    </div>
                )}

                {/* AI Suggestions - Multiple variants */}
                {aiSuggestions.length > 0 && isEditable && (
                    <div className="emr-text-suggestions">
                        <div className="emr-text-suggestions__header">
                            <span className="emr-text-suggestions__icon">📋</span>
                            <span className="emr-text-suggestions__title">Варианты из шаблонов:</span>
                            <button
                                className="emr-text-suggestions__close"
                                onClick={handleDismissAI}
                                tabIndex={-1}
                            >
                                ✕
                            </button>
                        </div>

                        <div className="emr-text-suggestions__list">
                            {aiSuggestions.map((suggestion, idx) => (
                                <button
                                    key={suggestion.id || idx}
                                    className={`emr-text-suggestions__item ${idx === selectedIndex ? 'emr-text-suggestions__item--selected' : ''}`}
                                    onClick={() => handleAcceptSuggestion(suggestion)}
                                    tabIndex={-1}
                                >
                                    <span className="emr-text-suggestions__number">{idx + 1}</span>
                                    <span className="emr-text-suggestions__text">{suggestion.text}</span>
                                    {suggestion.source && (
                                        <span className="emr-text-suggestions__source">{suggestion.source}</span>
                                    )}
                                </button>
                            ))}
                        </div>

                        <div className="emr-text-suggestions__footer">
                            <span>↑↓ выбор</span>
                            <span>Alt+Enter принять</span>
                            <span>Esc закрыть</span>
                        </div>
                    </div>
                )}

                {/* AI Loading indicator */}
                {isLoadingAI && (
                    <div className="emr-text-loading">
                        🔍 Ищу похожие записи...
                    </div>
                )}

                {/* Read-only indicator */}
                {!isEditable && (
                    <div className="emr-text-readonly">
                        🔒 Подписано
                    </div>
                )}
            </div>
        </div>
    );
};

export default EMRTextField;
