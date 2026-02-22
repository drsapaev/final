/**
 * EMRSmartField v3.0 - Полный набор улучшений
 * 
 * Новое:
 * ✅ Переключатель режимов (ghost/mvp/word) прямо в поле
 * ✅ Telemetry (подсчёт показов, принятий, время)
 * ✅ Сортировка по частоте + популярные в специальности
 * ✅ Inline corrections (Ctrl+Alt+Enter)
 * ✅ Унифицированные hotkeys
 * ✅ Гибридный режим (Ghost + Word-by-Word)
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import './EMRSmartField.css';
import { useDoctorPhrases } from '../../hooks/useDoctorPhrases';

// Режимы автозаполнения
const MODES = {
    GHOST: 'ghost',
    MVP: 'mvp',
    WORD: 'word',
    HYBRID: 'hybrid'  // Ghost по умолчанию, Word при длинных фразах
};

const MODE_LABELS = {
    [MODES.GHOST]: { icon: '✨', label: 'Ghost' },
    [MODES.MVP]: { icon: '📋', label: 'MVP' },
    [MODES.WORD]: { icon: '⚡', label: 'Word' },
    [MODES.HYBRID]: { icon: '🔀', label: 'Hybrid' }
};

// Debounce hook
const useDebounce = (value, delay) => {
    const [debouncedValue, setDebouncedValue] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedValue(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);
    return debouncedValue;
};

// Telemetry hook
const useTelemetry = (fieldName) => {
    const telemetryRef = useRef({
        suggestionsShown: 0,
        suggestionsAccepted: 0,
        timeToAccept: [],
        suggestionShownAt: null,
        modeUsage: { ghost: 0, mvp: 0, word: 0 }
    });

    const recordSuggestionShown = useCallback(() => {
        telemetryRef.current.suggestionsShown++;
        telemetryRef.current.suggestionShownAt = Date.now();
    }, []);

    const recordSuggestionAccepted = useCallback((mode) => {
        telemetryRef.current.suggestionsAccepted++;
        if (telemetryRef.current.suggestionShownAt) {
            const timeToAccept = Date.now() - telemetryRef.current.suggestionShownAt;
            telemetryRef.current.timeToAccept.push(timeToAccept);
        }
        if (mode) {
            telemetryRef.current.modeUsage[mode] = (telemetryRef.current.modeUsage[mode] || 0) + 1;
        }
    }, []);

    const getTelemetry = useCallback(() => {
        const t = telemetryRef.current;
        const avgTimeToAccept = t.timeToAccept.length > 0
            ? Math.round(t.timeToAccept.reduce((a, b) => a + b, 0) / t.timeToAccept.length)
            : 0;

        return {
            fieldName,
            suggestionsShown: t.suggestionsShown,
            suggestionsAccepted: t.suggestionsAccepted,
            acceptRate: t.suggestionsShown > 0
                ? Math.round((t.suggestionsAccepted / t.suggestionsShown) * 100)
                : 0,
            avgTimeToAcceptMs: avgTimeToAccept,
            modeUsage: t.modeUsage
        };
    }, [fieldName]);

    return { recordSuggestionShown, recordSuggestionAccepted, getTelemetry };
};

const EMRSmartField = ({
    // Data
    value = '',
    onChange,

    // State
    isEditable = true,

    // AI (legacy - for templates)
    aiEnabled = true,
    onRequestAI,

    // Doctor History-Based Autocomplete (NEW)
    useDoctorHistory = true,  // Использовать историю врача
    doctorId = null,          // ID врача для истории
    onModeChange,             // Callback при смене режима

    // Config
    defaultMode = MODES.GHOST,
    showModeSwitcher = true,
    debounceMs = 500,
    specialty = 'general',

    // Validation
    error,

    // UX
    autoFocus = false,
    onFieldTouch,
    onBlur,
    onTelemetry,        // Callback для отправки telemetry

    // Labels
    label = null,
    placeholder = 'Начните ввод...',
    fieldName = 'field',
    multiline = true,
    rows = 3
}) => {
    const textareaRef = useRef(null);
    const lastAcceptedRef = useRef('');
    const cursorPositionRef = useRef(0);

    // State
    const [mode, setMode] = useState(defaultMode);
    const [isFocused, setIsFocused] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const [ghostText, setGhostText] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [isLoading, setIsLoading] = useState(false);
    const [dismissed, setDismissed] = useState(false);
    const [recentTemplates, setRecentTemplates] = useState([]);
    const [showModeMenu, setShowModeMenu] = useState(false);

    // Inline correction state
    const [inlineCorrection, setInlineCorrection] = useState(null);

    // Telemetry
    const { recordSuggestionShown, recordSuggestionAccepted, getTelemetry } = useTelemetry(fieldName);

    // 🔥 Doctor History-Based Suggestions
    // АВТОМАТИЧЕСКАЯ АКТИВАЦИЯ: работает ТОЛЬКО когда ready=true
    // Это НЕ генерация - это поиск в истории врача!
    const {
        suggestions: historySuggestions,
        loading: historyLoading,
        topSuggestion: historyTopSuggestion,
        clearSuggestions: clearHistorySuggestions,
        indexPhrases,
        recordTelemetry: recordHistoryTelemetry,
        // 🔥 READINESS (automatic activation)
        ready: historyReady,
        readinessChecked: historyReadinessChecked,
        readinessMessage: historyReadinessMessage,
        // 🔥 PER-FIELD PAUSE (hybrid control)
        paused: historyPaused,
        togglePause: toggleHistoryPause
    } = useDoctorPhrases({
        doctorId: useDoctorHistory ? doctorId : null,
        field: fieldName,
        specialty,
        currentText: value,
        cursorPosition: cursorPositionRef.current,
        config: { debounceMs, minQueryLength: 3, maxSuggestions: 5 }
    });

    // Debounced value
    const debouncedValue = useDebounce(value, debounceMs);

    // Auto-focus
    useEffect(() => {
        if (autoFocus && isEditable && textareaRef.current) {
            setTimeout(() => textareaRef.current?.focus(), 100);
        }
    }, [autoFocus, isEditable]);

    // Track cursor position
    const updateCursorPosition = useCallback(() => {
        if (textareaRef.current) {
            cursorPositionRef.current = textareaRef.current.selectionStart;
        }
    }, []);

    // Сортировка с учётом частоты и недавних
    const sortSuggestions = useCallback((items) => {
        return items.sort((a, b) => {
            // Недавние первые
            const aRecent = recentTemplates.some(r => r.id === a.id) ? 1 : 0;
            const bRecent = recentTemplates.some(r => r.id === b.id) ? 1 : 0;
            if (aRecent !== bRecent) return bRecent - aRecent;

            // По частоте использования
            const aCount = a.usageCount || 0;
            const bCount = b.usageCount || 0;
            if (aCount !== bCount) return bCount - aCount;

            // По специальности
            const aSpecialty = a.specialty === specialty ? 1 : 0;
            const bSpecialty = b.specialty === specialty ? 1 : 0;
            return bSpecialty - aSpecialty;
        });
    }, [recentTemplates, specialty]);

    // 🔥 USE DOCTOR HISTORY FIRST (primary source)
    // Это поиск в истории врача, НЕ генерация!
    useEffect(() => {
        if (!useDoctorHistory || !doctorId || !isEditable || !isFocused || dismissed || historyPaused) {
            if (historyPaused) setSuggestions([]); // Clear if paused
            return;
        }

        // Если есть history suggestions - используем их
        if (historySuggestions.length > 0) {
            const withMeta = historySuggestions.map((s, idx) => ({
                id: `history-${idx}`,
                originalId: s.id, // ID из базы для телеметрии
                text: s.text,
                source: 'history',
                usageCount: s.usageCount,
                isRecent: false
            }));

            setSuggestions(withMeta);
            setSelectedIndex(0);

            // Записываем телеметрию для истории
            recordHistoryTelemetry('shown', historySuggestions[0]?.id);
            recordSuggestionShown(); // Общий логгер

            // Ghost text = хвост (continuation), не полный текст!
            if ((mode === MODES.GHOST || mode === MODES.HYBRID) && historyTopSuggestion) {
                setGhostText(historyTopSuggestion.text);
            }
        } else {
            // Нет history - пробуем AI templates (fallback)
            if (!aiEnabled || !onRequestAI) return;
        }
    }, [historySuggestions, historyTopSuggestion, useDoctorHistory, doctorId, isEditable, isFocused, dismissed, mode, recordSuggestionShown, aiEnabled, onRequestAI, historyPaused, recordHistoryTelemetry]);

    // FALLBACK: AI suggestions (templates) - когда нет history
    useEffect(() => {
        // Пропускаем если history уже дал результаты
        if (useDoctorHistory && doctorId && historySuggestions.length > 0) return;
        if (!aiEnabled || !isEditable || !isFocused || dismissed) return;

        const textBeforeCursor = debouncedValue.substring(0, cursorPositionRef.current || debouncedValue.length);

        if (!textBeforeCursor || textBeforeCursor.length < 3) {
            if (!historySuggestions.length) {
                setSuggestions([]);
                setGhostText('');
            }
            return;
        }

        if (debouncedValue === lastAcceptedRef.current) return;

        const fetchSuggestions = async () => {
            if (!onRequestAI) return;

            setIsLoading(true);
            try {
                const result = await onRequestAI(textBeforeCursor, fieldName, mode);

                if (Array.isArray(result) && result.length > 0) {
                    const sorted = sortSuggestions(result);

                    // Помечаем недавние
                    const withRecent = sorted.map(s => ({
                        ...s,
                        isRecent: recentTemplates.some(r => r.id === s.id)
                    }));

                    setSuggestions(withRecent);
                    setSelectedIndex(0);
                    recordSuggestionShown();

                    // Ghost text
                    if ((mode === MODES.GHOST || mode === MODES.HYBRID) && withRecent[0]) {
                        setGhostText(withRecent[0].text);
                    }

                    // Inline correction - если текст похож но немного отличается
                    const current = textBeforeCursor.toLowerCase();
                    const suggested = withRecent[0]?.text?.toLowerCase();
                    if (suggested && current.length > 10 && suggested.includes(current.substring(0, 5))) {
                        setInlineCorrection({
                            original: textBeforeCursor,
                            suggested: withRecent[0].text,
                            diff: findDiff(textBeforeCursor, withRecent[0].text)
                        });
                    } else {
                        setInlineCorrection(null);
                    }
                }
            } catch (e) {
                console.error('AI suggestion error:', e);
            } finally {
                setIsLoading(false);
            }
        };

        fetchSuggestions();
    }, [debouncedValue, aiEnabled, isEditable, isFocused, mode, fieldName, dismissed, onRequestAI, sortSuggestions, recordSuggestionShown, recentTemplates, useDoctorHistory, doctorId, historySuggestions]);

    // Простой поиск различий
    const findDiff = (original, suggested) => {
        const words1 = original.split(' ');
        const words2 = suggested.split(' ');
        const diffs = [];

        for (let i = 0; i < Math.max(words1.length, words2.length); i++) {
            if (words1[i] !== words2[i]) {
                diffs.push({ index: i, original: words1[i], suggested: words2[i] });
            }
        }
        return diffs;
    };

    // Clear on value change
    useEffect(() => {
        if (value !== lastAcceptedRef.current) {
            setDismissed(false);
            setSuggestions([]);
            setGhostText('');
            setInlineCorrection(null);
        }
    }, [value]);

    // Handlers
    const handleChange = useCallback((e) => {
        onChange?.(e.target.value);
        onFieldTouch?.(fieldName);
        updateCursorPosition();
    }, [onChange, onFieldTouch, fieldName, updateCursorPosition]);

    const handleFocus = useCallback(() => {
        setIsFocused(true);
        setDismissed(false);
        updateCursorPosition();
    }, [updateCursorPosition]);

    const handleBlur = useCallback(() => {
        setIsFocused(false);
        setShowModeMenu(false);
        onBlur?.();

        // Отправляем telemetry при потере фокуса
        if (onTelemetry) {
            onTelemetry(getTelemetry());
        }
    }, [onBlur, onTelemetry, getTelemetry]);

    // Insert at cursor
    const insertAtCursor = useCallback((textToInsert) => {
        const textarea = textareaRef.current;
        if (!textarea) return;

        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const before = value.substring(0, start);
        const after = value.substring(end);

        const needsSeparator = before.length > 0 && !before.endsWith(' ') && !before.endsWith('\n') && !before.endsWith(',');
        const separator = needsSeparator ? ', ' : '';

        const newValue = before + separator + textToInsert + after;
        const newCursorPos = start + separator.length + textToInsert.length;

        lastAcceptedRef.current = newValue;
        onChange?.(newValue);
        setSuggestions([]);
        setGhostText('');
        setDismissed(true);
        setInlineCorrection(null);

        setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(newCursorPos, newCursorPos);
            cursorPositionRef.current = newCursorPos;
        }, 0);
    }, [value, onChange]);

    // Accept suggestion
    const acceptSuggestion = useCallback((suggestion) => {
        if (!suggestion) return;

        // 🔥 Telemetry for history
        if (suggestion.source === 'history') {
            recordHistoryTelemetry('accepted', suggestion.originalId);
        }

        // Add to recent
        setRecentTemplates(prev => {
            const filtered = prev.filter(t => t.id !== suggestion.id);
            return [suggestion, ...filtered].slice(0, 10);
        });

        recordSuggestionAccepted(mode);
        insertAtCursor(suggestion.text);
    }, [insertAtCursor, mode, recordSuggestionAccepted, recordHistoryTelemetry]);

    // Accept ghost text
    const acceptGhostText = useCallback(() => {
        if (!ghostText) return;
        const suggestion = suggestions[selectedIndex];
        if (suggestion) {
            acceptSuggestion(suggestion);
        }
    }, [ghostText, suggestions, selectedIndex, acceptSuggestion]);

    // Apply inline correction
    const applyInlineCorrection = useCallback(() => {
        if (!inlineCorrection) return;

        // Заменяем текст на исправленный
        lastAcceptedRef.current = inlineCorrection.suggested;
        onChange?.(inlineCorrection.suggested);
        setInlineCorrection(null);
        recordSuggestionAccepted(mode);

        if (textareaRef.current) {
            textareaRef.current.focus();
        }
    }, [inlineCorrection, onChange, mode, recordSuggestionAccepted]);

    // Dismiss
    const dismissSuggestions = useCallback(() => {
        setSuggestions([]);
        setGhostText('');
        setDismissed(true);
        setInlineCorrection(null);
    }, []);

    // Mode switch
    const switchMode = useCallback((newMode) => {
        setMode(newMode);
        setShowModeMenu(false);
        setSuggestions([]);
        setGhostText('');
        setDismissed(false);
        // Notify parent about mode change (for preferences)
        onModeChange?.(newMode);
    }, [onModeChange]);

    // Keyboard handling (унифицированные hotkeys)
    const handleKeyDown = useCallback((e) => {
        // Ctrl+Alt+Enter - apply inline correction
        if (e.ctrlKey && e.altKey && e.key === 'Enter' && inlineCorrection) {
            e.preventDefault();
            applyInlineCorrection();
            return;
        }

        // Tab - accept ghost text (only in ghost/hybrid mode)
        if (e.key === 'Tab' && !e.shiftKey && ghostText && (mode === MODES.GHOST || mode === MODES.HYBRID)) {
            e.preventDefault();
            acceptGhostText();
            return;
        }

        if (suggestions.length > 0) {
            // Arrow navigation
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                const newIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
                setSelectedIndex(newIndex);
                if (mode === MODES.GHOST || mode === MODES.HYBRID) {
                    setGhostText(suggestions[newIndex]?.text || '');
                }
                return;
            }

            if (e.key === 'ArrowUp') {
                e.preventDefault();
                const newIndex = Math.max(selectedIndex - 1, 0);
                setSelectedIndex(newIndex);
                if (mode === MODES.GHOST || mode === MODES.HYBRID) {
                    setGhostText(suggestions[newIndex]?.text || '');
                }
                return;
            }

            // Alt+Enter - accept (все режимы)
            if (e.key === 'Enter' && e.altKey) {
                e.preventDefault();
                acceptSuggestion(suggestions[selectedIndex]);
                return;
            }

            // Alt+1/2/3 - quick select (все режимы)
            if (e.altKey && ['1', '2', '3'].includes(e.key)) {
                e.preventDefault();
                const idx = parseInt(e.key) - 1;
                if (suggestions[idx]) {
                    acceptSuggestion(suggestions[idx]);
                }
                return;
            }

            // Enter in Word mode - accept current word
            if (e.key === 'Enter' && !e.altKey && !e.ctrlKey && mode === MODES.WORD) {
                e.preventDefault();
                acceptSuggestion(suggestions[selectedIndex]);
                return;
            }

            // Escape - dismiss (все режимы)
            if (e.key === 'Escape') {
                e.preventDefault();
                dismissSuggestions();
                return;
            }
        }
    }, [mode, ghostText, suggestions, selectedIndex, inlineCorrection,
        acceptGhostText, acceptSuggestion, dismissSuggestions, applyInlineCorrection]);

    // CSS classes
    const fieldClasses = [
        'emr-smart-field',
        isFocused && 'emr-smart-field--focused',
        !isEditable && 'emr-smart-field--readonly',
        error && 'emr-smart-field--error'
    ].filter(Boolean).join(' ');

    // Ghost text display
    const displayGhostText = useMemo(() => {
        if (!ghostText || !isFocused || !(mode === MODES.GHOST || mode === MODES.HYBRID)) return null;
        return ghostText;
    }, [ghostText, isFocused, mode]);

    const InputComponent = multiline ? 'textarea' : 'input';

    return (
        <div className="emr-smart-wrapper">
            {/* Header with label and mode switcher */}
            <div className="emr-smart-header">
                <label className="emr-smart-label">{label}</label>

                {showModeSwitcher && isEditable && (
                    <div className="emr-smart-mode-switcher">
                        <button
                            className="emr-smart-mode-current"
                            onClick={() => setShowModeMenu(!showModeMenu)}
                            tabIndex={-1}
                        >
                            {MODE_LABELS[mode].icon} {MODE_LABELS[mode].label}
                            <span className="emr-smart-mode-arrow">▾</span>
                        </button>

                        {showModeMenu && (
                            <div className="emr-smart-mode-menu">
                                {Object.entries(MODE_LABELS).map(([key, val]) => (
                                    <button
                                        key={key}
                                        className={`emr-smart-mode-option ${mode === key ? 'emr-smart-mode-option--active' : ''}`}
                                        onClick={() => switchMode(key)}
                                        tabIndex={-1}
                                    >
                                        {val.icon} {val.label}
                                        {mode === key && ' ✓'}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* 🔥 PASSIVE INDICATOR: показать когда history autocomplete активен */}
                {useDoctorHistory && doctorId && historyReady && (
                    <div className="emr-smart-history-controls">
                        <div
                            className="emr-smart-history-indicator"
                            title={historyPaused ? 'Подсказки приостановлены' : 'Подсказки из ваших записей'}
                        >
                            {historyPaused ? '⏸️' : '📝'}
                        </div>
                        <button
                            className={`emr-smart-pause-btn ${historyPaused ? 'emr-smart-pause-btn--active' : ''}`}
                            onClick={toggleHistoryPause}
                            tabIndex={-1}
                            title={historyPaused ? 'Возобновить подсказки' : 'Приостановить подсказки'}
                        >
                            {historyPaused ? '▶️' : '⏸️'}
                        </button>
                    </div>
                )}
            </div>

            <div className="emr-smart-container">
                {/* Input with ghost overlay */}
                <div className="emr-smart-input-wrapper">
                    <InputComponent
                        ref={textareaRef}
                        className={fieldClasses}
                        value={value}
                        onChange={handleChange}
                        onFocus={handleFocus}
                        onBlur={handleBlur}
                        onKeyDown={handleKeyDown}
                        onSelect={updateCursorPosition}
                        onClick={updateCursorPosition}
                        placeholder={placeholder}
                        disabled={!isEditable}
                        rows={multiline ? rows : undefined}
                    />

                    {/* Ghost text overlay */}
                    {displayGhostText && (
                        <div className="emr-smart-ghost">
                            <span className="emr-smart-ghost__existing">{value}</span>
                            <span className="emr-smart-ghost__suggestion">
                                {value && !value.endsWith(' ') && !value.endsWith(',') ? ', ' : ''}
                                {displayGhostText}
                            </span>
                            <span className="emr-smart-ghost__hint">Tab ↹</span>
                        </div>
                    )}
                </div>

                {/* Inline correction indicator */}
                {inlineCorrection && (
                    <div className="emr-smart-correction">
                        <span className="emr-smart-correction__icon">✏️</span>
                        <span className="emr-smart-correction__text">
                            Исправление: <strong>{inlineCorrection.suggested.substring(0, 50)}...</strong>
                        </span>
                        <span className="emr-smart-correction__hint">Ctrl+Alt+Enter</span>
                    </div>
                )}

                {/* Error */}
                {error && (
                    <div className="emr-smart-error">⚠️ {error}</div>
                )}

                {/* Dropdown (MVP mode) */}
                {mode === MODES.MVP && suggestions.length > 0 && isEditable && (
                    <div className="emr-smart-dropdown">
                        <div className="emr-smart-dropdown__header">
                            <span>{useDoctorHistory && doctorId ? '📝 Из вашей истории:' : '📋 Варианты из шаблонов:'}</span>
                            <button onClick={dismissSuggestions} tabIndex={-1}>✕</button>
                        </div>

                        <div className="emr-smart-dropdown__list">
                            {suggestions.map((s, idx) => (
                                <button
                                    key={s.id || idx}
                                    className={`emr-smart-dropdown__item ${idx === selectedIndex ? 'emr-smart-dropdown__item--selected' : ''}`}
                                    onClick={() => acceptSuggestion(s)}
                                    tabIndex={-1}
                                >
                                    <span className="emr-smart-dropdown__number">{idx + 1}</span>
                                    <span className="emr-smart-dropdown__text">{s.text}</span>
                                    <span className="emr-smart-dropdown__meta">
                                        {s.isRecent && <span className="emr-smart-dropdown__recent">⭐</span>}
                                        {s.usageCount && <span className="emr-smart-dropdown__count">×{s.usageCount}</span>}
                                        {s.source && <span className="emr-smart-dropdown__source">{s.source}</span>}
                                    </span>
                                </button>
                            ))}
                        </div>

                        <div className="emr-smart-dropdown__footer">
                            <span>↑↓</span>
                            <span>Alt+Enter</span>
                            <span>Alt+1/2/3</span>
                        </div>
                    </div>
                )}

                {/* Mini suggestions (Ghost/Hybrid mode) */}
                {(mode === MODES.GHOST || mode === MODES.HYBRID) && suggestions.length > 1 && isEditable && (
                    <div className="emr-smart-mini-list">
                        {suggestions.slice(0, 3).map((s, idx) => (
                            <button
                                key={s.id || idx}
                                className={`emr-smart-mini-item ${idx === selectedIndex ? 'emr-smart-mini-item--selected' : ''}`}
                                onClick={() => acceptSuggestion(s)}
                                tabIndex={-1}
                            >
                                <span className="emr-smart-mini-number">Alt+{idx + 1}</span>
                                <span className="emr-smart-mini-text">{s.text.substring(0, 40)}...</span>
                                {s.isRecent && <span className="emr-smart-mini-recent">⭐</span>}
                            </button>
                        ))}
                    </div>
                )}

                {/* Word mode tooltip */}
                {mode === MODES.WORD && suggestions.length > 0 && (
                    <div className="emr-smart-word-hint">
                        Enter = принять слово
                    </div>
                )}

                {/* Loading */}
                {(isLoading || historyLoading) && (
                    <div className="emr-smart-loading">🔍</div>
                )}

                {/* Read-only */}
                {!isEditable && (
                    <div className="emr-smart-readonly">🔒 Подписано</div>
                )}
            </div>
        </div>
    );
};

EMRSmartField.MODES = MODES;

export default EMRSmartField;
