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
import PropTypes from 'prop-types';
import './PhraseSuggestions.css';
import { Checkbox } from '../../ui/macos';
import { useTranslation } from '../../../i18n/useTranslation';

/**
 * Common clinical phrases by field.
 * Keys are translation keys (misc.ph_*) — the actual phrase text is
 * resolved at render time via t().
 * The outer key (e.g. 'pain') is a Russian keyword used to match
 * user input; it's matched against the user-typed text (which is also
 * in Russian for the medical workflow), so it stays as a literal.
 */
const PHRASE_DATABASE = {
    complaints: {
        'боль': [
            'ph_complaint_pain_pressing',
            'ph_complaint_pain_radiation_left_arm',
            'ph_complaint_pain_exertion',
            'ph_complaint_pain_rest',
            'ph_complaint_pain_food',
        ],
        'головн': [
            'ph_complaint_headache_pulsating',
            'ph_complaint_headache_temporal',
            'ph_complaint_headache_nausea',
            'ph_complaint_headache_stress',
        ],
        'давлен': [
            'ph_complaint_bp_high',
            'ph_complaint_bp_episodic',
            'ph_complaint_bp_headache',
        ],
        'одышк': [
            'ph_complaint_dyspnea_exertion',
            'ph_complaint_dyspnea_rest',
            'ph_complaint_dyspnea_walking',
            'ph_complaint_dyspnea_paroxysmal',
        ],
    },
    examination: {
        'ад': [
            'ph_exam_bp_120_80',
            'ph_exam_bp_130_85',
            'ph_exam_bp_140_90',
            'ph_exam_bp_150_95',
            'ph_exam_bp_160_100',
        ],
        'пульс': [
            'ph_exam_pulse_72',
            'ph_exam_pulse_80',
            'ph_exam_pulse_90',
            'ph_exam_pulse_irregular',
        ],
        'кожн': [
            'ph_exam_skin_normal',
            'ph_exam_skin_pale',
            'ph_exam_skin_moist',
        ],
    },
    diagnosis: {
        'гипертен': [
            'ph_dx_ht_stage1_risk2',
            'ph_dx_ht_stage2_risk3',
            'ph_dx_ht_stage3_risk4',
        ],
        'ибс': [
            'ph_dx_ihd_angina_fc2',
            'ph_dx_ihd_angina_fc3',
            'ph_dx_ihd_post_infarct',
        ],
    },
};

/**
 * Find matching phrases based on input
 */
function findMatchingPhrases(text, fieldName, t, maxResults = 5) {
    if (!text || text.length < 3) return [];

    const fieldPhrases = PHRASE_DATABASE[fieldName] || {};
    const words = text.toLowerCase().split(/\s+/);
    const matches = [];

    for (const [keyword, phraseKeys] of Object.entries(fieldPhrases)) {
        const keywordLower = keyword.toLowerCase();
        if (words.some(word => keywordLower.includes(word) || word.includes(keywordLower))) {
            for (const key of phraseKeys) {
                const phraseText = t(`misc.${key}`);
                // Don't suggest what's already in the text
                if (!text.includes(phraseText)) {
                    matches.push({ key, text: phraseText });
                }
            }
        }
    }

    return [...new Map(matches.map(m => [m.key, m])).values()].slice(0, maxResults);
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
    const { t } = useTranslation();
    const [selectedPhrases, setSelectedPhrases] = useState(new Set());

    // Find matching phrases
    const phrases = useMemo(() => {
        return findMatchingPhrases(currentText, fieldName, t);
    }, [currentText, fieldName, t]);

    // Toggle phrase selection
    const togglePhrase = useCallback((key) => {
        setSelectedPhrases(prev => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    }, []);

    // Insert selected phrases
    const handleInsert = useCallback(() => {
        if (selectedPhrases.size === 0) return;

        const phrasesToInsert = phrases
            .filter(p => selectedPhrases.has(p.key))
            .map(p => p.text)
            .join('\n');
        onInsert?.(phrasesToInsert);
        setSelectedPhrases(new Set());
    }, [selectedPhrases, onInsert, phrases]);

    if (!isOpen || phrases.length === 0) return null;

    return (
        <div className="phrase-suggestions">
            <div className="phrase-suggestions__header">
                <span className="phrase-suggestions__icon">📝</span>
                <span>{t('misc.ph_clinical_phrases')}</span>
            </div>

            <div className="phrase-suggestions__list">
                {phrases.map((phrase) => {
                    const isSelected = selectedPhrases.has(phrase.key);
                    return (
                        <label
                            key={phrase.key}
                            className={`phrase-suggestions__item ${isSelected ? 'phrase-suggestions__item--selected' : ''}`}
                        >
                            <Checkbox aria-label={t('misc.ph_select_phrase', { phrase: phrase.text })} checked={isSelected} onChange={() => togglePhrase(phrase.key)}
                                disabled={disabled}
                            />
                            <span className="phrase-suggestions__text">{phrase.text}</span>
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
                    ➕ {t('misc.ph_insert', { count: selectedPhrases.size })}
                </button>
            )}

            <div className="phrase-suggestions__footer">
                {t('misc.ph_footer')}
            </div>
        </div>
    );
}

export default PhraseSuggestions;

PhraseSuggestions.propTypes = {
    currentText: PropTypes.string,
    fieldName: PropTypes.string,
    onInsert: PropTypes.func,
    disabled: PropTypes.bool,
    isOpen: PropTypes.bool,
};
