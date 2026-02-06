/**
 * ICD10Autocomplete - UI-only компонент для выбора кодов МКБ-10
 * 
 * ⚠️ ВАЖНО: Этот компонент НЕ делает AI вызовы напрямую!
 * AI вызывается через useEMRAI / mcpClient в родительском компоненте.
 * 
 * Особенности:
 * - Отображает переданные suggestions
 * - Клавиатурная навигация (↑↓, Enter, Escape)
 * - Локальный поиск по переданным suggestions
 * - Никаких знаний о провайдерах
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import './ICD10Autocomplete.css';

// Debounce hook
const useDebounce = (value, delay) => {
    const [debouncedValue, setDebouncedValue] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedValue(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);
    return debouncedValue;
};

const ICD10Autocomplete = ({
    // Data
    value = '',
    onChange,                      // (code, name) => void

    // Suggestions from parent (via useEMRAI)
    suggestions = [],              // [{ code, name, confidence, isRecent }]
    loading = false,               // AI loading state
    onSearch,                      // (query) => void - callback to trigger search in parent

    // Config
    disabled = false,
    placeholder = 'Начните ввод кода или названия...',
    debounceMs = 300,

    // Recent
    recentCodes = [],
}) => {
    const inputRef = useRef(null);
    const listRef = useRef(null);
    const lastExternalValueRef = useRef(value);

    // State
    const [query, setQuery] = useState(value || '');
    const [isOpen, setIsOpen] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [filteredResults, setFilteredResults] = useState([]);

    const debouncedQuery = useDebounce(query, debounceMs);

    // Стабилизация recentCodes
    const recentCodesStr = useMemo(() => JSON.stringify(recentCodes), [recentCodes]);

    // Стабилизация suggestions (prevent infinite loop from default [] creating new ref)
    const suggestionsStr = useMemo(() => JSON.stringify(suggestions), [suggestions]);

    // Trigger search callback when debounced query changes
    useEffect(() => {
        if (debouncedQuery && debouncedQuery.length >= 2 && onSearch) {
            onSearch(debouncedQuery);
        }
    }, [debouncedQuery, onSearch]);

    // Filter and sort suggestions locally
    useEffect(() => {
        const currentRecentCodes = JSON.parse(recentCodesStr || '[]');
        const currentSuggestions = JSON.parse(suggestionsStr || '[]');

        if (!currentSuggestions || currentSuggestions.length === 0) {
            setFilteredResults(prev => prev.length === 0 ? prev : []);
            return;
        }

        // Локальная фильтрация по query если есть
        let results = currentSuggestions;

        if (query && query.length > 0) {
            const lowerQuery = query.toLowerCase();
            results = currentSuggestions.filter(s =>
                s.code?.toLowerCase().includes(lowerQuery) ||
                s.name?.toLowerCase().includes(lowerQuery)
            );
        }

        // Пометить недавние
        const withRecent = results.map(s => ({
            ...s,
            isRecent: currentRecentCodes.includes(s.code)
        }));

        // Сортировка: недавние → по confidence → по коду
        withRecent.sort((a, b) => {
            if (a.isRecent !== b.isRecent) return a.isRecent ? -1 : 1;
            if ((a.confidence || 0) !== (b.confidence || 0)) return (b.confidence || 0) - (a.confidence || 0);
            return a.code.localeCompare(b.code);
        });

        setFilteredResults(withRecent.slice(0, 10));
        setSelectedIndex(0);
    }, [suggestionsStr, query, recentCodesStr]);

    // Scroll selected into view
    useEffect(() => {
        if (listRef.current && filteredResults.length > 0) {
            const selectedItem = listRef.current.children[selectedIndex];
            if (selectedItem) {
                selectedItem.scrollIntoView({ block: 'nearest' });
            }
        }
    }, [selectedIndex, filteredResults.length]);

    // Handlers
    const handleInputChange = useCallback((e) => {
        setQuery(e.target.value);
        setIsOpen(true);
    }, []);

    const handleFocus = useCallback(() => {
        setIsOpen(true);
        // Trigger initial search if empty
        if (onSearch && !query) {
            onSearch('');
        }
    }, [onSearch, query]);

    const handleBlur = useCallback(() => {
        setTimeout(() => setIsOpen(false), 200);
    }, []);

    const selectItem = useCallback((item) => {
        setQuery(item.code);
        onChange?.(item.code, item.name);
        setIsOpen(false);
    }, [onChange]);

    const handleKeyDown = useCallback((e) => {
        if (!isOpen || filteredResults.length === 0) {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                setIsOpen(true);
            }
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(prev => Math.min(prev + 1, filteredResults.length - 1));
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(prev => Math.max(prev - 1, 0));
                break;
            case 'Enter':
                e.preventDefault();
                if (filteredResults[selectedIndex]) {
                    selectItem(filteredResults[selectedIndex]);
                }
                break;
            case 'Escape':
                e.preventDefault();
                setIsOpen(false);
                break;
            case 'Tab':
                if (filteredResults[selectedIndex]) {
                    selectItem(filteredResults[selectedIndex]);
                }
                break;
            default:
                break;
        }
    }, [isOpen, filteredResults, selectedIndex, selectItem]);

    // Sync external value
    useEffect(() => {
        if (value !== lastExternalValueRef.current) {
            lastExternalValueRef.current = value;
            setQuery(value || '');
        }
    }, [value]);

    return (
        <div className="icd10-autocomplete">
            <div className="icd10-input-wrapper">
                <input
                    ref={inputRef}
                    type="text"
                    className={`icd10-input ${isOpen && filteredResults.length > 0 ? 'icd10-input--open' : ''}`}
                    value={query}
                    onChange={handleInputChange}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    disabled={disabled}
                    autoComplete="off"
                />

                {/* Loading indicator */}
                {loading && (
                    <span className="icd10-loading">🔍</span>
                )}

                {/* Clear button */}
                {query && !disabled && !loading && (
                    <button
                        className="icd10-clear"
                        onClick={() => {
                            setQuery('');
                            onChange?.('', '');
                            inputRef.current?.focus();
                        }}
                        tabIndex={-1}
                    >
                        ✕
                    </button>
                )}
            </div>

            {/* Dropdown */}
            {isOpen && filteredResults.length > 0 && (
                <div className="icd10-dropdown">
                    <div className="icd10-dropdown__list" ref={listRef}>
                        {filteredResults.map((item, idx) => (
                            <button
                                key={item.code}
                                className={`icd10-dropdown__item ${idx === selectedIndex ? 'icd10-dropdown__item--selected' : ''}`}
                                onClick={() => selectItem(item)}
                                onMouseEnter={() => setSelectedIndex(idx)}
                                tabIndex={-1}
                            >
                                <span className="icd10-dropdown__code">{item.code}</span>
                                <span className="icd10-dropdown__name">{item.name}</span>
                                <span className="icd10-dropdown__meta">
                                    {item.isRecent && <span className="icd10-dropdown__recent">⭐</span>}
                                    {item.confidence && (
                                        <span className="icd10-dropdown__confidence">
                                            {Math.round(item.confidence * 100)}%
                                        </span>
                                    )}
                                </span>
                            </button>
                        ))}
                    </div>

                    <div className="icd10-dropdown__footer">
                        <span>↑↓ навигация</span>
                        <span>Enter выбрать</span>
                        <span>Esc закрыть</span>
                    </div>
                </div>
            )}

            {/* No results message */}
            {isOpen && query.length >= 2 && filteredResults.length === 0 && !loading && (
                <div className="icd10-no-results">
                    Коды не найдены
                </div>
            )}
        </div>
    );
};

ICD10Autocomplete.propTypes = {
    value: PropTypes.string,
    onChange: PropTypes.func,
    suggestions: PropTypes.arrayOf(PropTypes.shape({
        code: PropTypes.string,
        name: PropTypes.string,
        confidence: PropTypes.number,
        isRecent: PropTypes.bool,
    })),
    loading: PropTypes.bool,
    onSearch: PropTypes.func,
    disabled: PropTypes.bool,
    placeholder: PropTypes.string,
    debounceMs: PropTypes.number,
    recentCodes: PropTypes.arrayOf(PropTypes.string),
};

ICD10Autocomplete.defaultProps = {
    value: '',
    onChange: null,
    suggestions: [],
    loading: false,
    onSearch: null,
    disabled: false,
    placeholder: 'Начните ввод кода или названия...',
    debounceMs: 300,
    recentCodes: [],
};

export default ICD10Autocomplete;
