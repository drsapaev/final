/**
 * PhraseSuggestions - Contextual phrase suggestions
 * 
 * IDE-like "snippets" behavior:
 * - User starts typing
 * - System suggests clinical formulations
 * - Click to insert (checkboxes)
 * 
 * RULES:
 * - NO auto-insert
 * - Click only (checkbox)
 * - Each insert = 1 undo
 */

import { useState, useMemo, useCallback } from 'react';
import './PhraseSuggestions.css';

/**
 * Common clinical phrases by field
 */
const PHRASE_DATABASE = {
    complaints: {
        pain: [
            'Боль давящего характера',
            'Боль с иррадиацией в левую руку',
            'Боль усиливается при физической нагрузке',
            'Боль в покое',
            'Боль связана с приемом пищи',
        ],
        головн: [
            'Головная боль пульсирующего характера',
            'Головная боль в височной области',
            'Головная боль с тошнотой',
            'Головная боль после стресса',
        ],
        давлен: [
            'Повышение АД до 180/100 мм рт.ст.',
            'Эпизодическое повышение АД',
            'Повышение АД с головной болью',
        ],
        одышк: [
            'Одышка при физической нагрузке',
            'Одышка в покое',
            'Одышка при ходьбе на 100 м',
            'Пароксизмальная ночная одышка',
        ],
    },
    examination: {
        'ад': [
            'АД 120/80 мм рт.ст.',
            'АД 130/85 мм рт.ст.',
            'АД 140/90 мм рт.ст.',
            'АД 150/95 мм рт.ст.',
            'АД 160/100 мм рт.ст.',
        ],
        пульс: [
            'Пульс 72 уд/мин, ритмичный',
            'Пульс 80 уд/мин, ритмичный',
            'Пульс 90 уд/мин, ритмичный',
            'Пульс нерегулярный',
        ],
        кожн: [
            'Кожные покровы обычной окраски',
            'Кожные покровы бледные',
            'Кожные покровы влажные',
        ],
    },
    diagnosis: {
        гипертен: [
            'Артериальная гипертензия I стадии, риск ССО 2',
            'Артериальная гипертензия II стадии, риск ССО 3',
            'Артериальная гипертензия III стадии, риск ССО 4',
        ],
        ибс: [
            'ИБС: стенокардия напряжения II ФК',
            'ИБС: стенокардия напряжения III ФК',
            'ИБС: постинфарктный кардиосклероз',
        ],
    },
};

/**
 * Find matching phrases based on input
 */
function findMatchingPhrases(text, fieldName, maxResults = 5) {
    if (!text || text.length < 3) return [];

    const fieldPhrases = PHRASE_DATABASE[fieldName] || {};
    const words = text.toLowerCase().split(/\s+/);
    const matches = [];

    for (const [keyword, phrases] of Object.entries(fieldPhrases)) {
        const keywordLower = keyword.toLowerCase();
        if (words.some(word => keywordLower.includes(word) || word.includes(keywordLower))) {
            for (const phrase of phrases) {
                if (!text.includes(phrase)) {  // Don't suggest what's already there
                    matches.push(phrase);
                }
            }
        }
    }

    return [...new Set(matches)].slice(0, maxResults);
}

/**
 * PhraseSuggestions Component
 * 
 * @param {Object} props
 * @param {string} props.currentText - Current field text
 * @param {string} props.fieldName - Field name ('complaints', 'examination', etc.)
 * @param {Function} props.onInsert - Insert callback (phrase) => void
 * @param {boolean} props.disabled - Disable
 * @param {boolean} props.isOpen - Show panel
 */
export function PhraseSuggestions({
    currentText = '',
    fieldName,
    onInsert,
    disabled = false,
    isOpen = true,
}) {
    const [selectedPhrases, setSelectedPhrases] = useState(new Set());

    // Find matching phrases
    const phrases = useMemo(() => {
        return findMatchingPhrases(currentText, fieldName);
    }, [currentText, fieldName]);

    // Toggle phrase selection
    const togglePhrase = useCallback((phrase) => {
        setSelectedPhrases(prev => {
            const next = new Set(prev);
            if (next.has(phrase)) {
                next.delete(phrase);
            } else {
                next.add(phrase);
            }
            return next;
        });
    }, []);

    // Insert selected phrases
    const handleInsert = useCallback(() => {
        if (selectedPhrases.size === 0) return;

        const phrasesToInsert = Array.from(selectedPhrases).join('\n');
        onInsert?.(phrasesToInsert);
        setSelectedPhrases(new Set());
    }, [selectedPhrases, onInsert]);

    if (!isOpen || phrases.length === 0) return null;

    return (
        <div className="phrase-suggestions">
            <div className="phrase-suggestions__header">
                <span className="phrase-suggestions__icon">📝</span>
                <span>Клинические формулировки</span>
            </div>

            <div className="phrase-suggestions__list">
                {phrases.map((phrase, idx) => {
                    const isSelected = selectedPhrases.has(phrase);
                    return (
                        <label
                            key={idx}
                            className={`phrase-suggestions__item ${isSelected ? 'phrase-suggestions__item--selected' : ''}`}
                        >
                            <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => togglePhrase(phrase)}
                                disabled={disabled}
                            />
                            <span className="phrase-suggestions__text">{phrase}</span>
                        </label>
                    );
                })}
            </div>

            {selectedPhrases.size > 0 && (
                <button
                    className="phrase-suggestions__insert"
                    onClick={handleInsert}
                    disabled={disabled}
                >
                    ➕ Вставить ({selectedPhrases.size})
                </button>
            )}

            <div className="phrase-suggestions__footer">
                Выберите и нажмите «Вставить»
            </div>
        </div>
    );
}

export default PhraseSuggestions;
