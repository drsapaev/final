
/**
 * CompletenessChecker - AI "check missing fields" component
 * 
 * IDE-like "missing imports" behavior:
 * - Button to trigger check
 * - Shows list of missing/incomplete fields
 * - Click to scroll to field
 * 
 * RULES:
 * - AI does NOT fill fields
 * - Only SUGGESTS what to add
 * - Doctor decides
 */

import { useState, useCallback } from 'react';

import './CompletenessChecker.css';
import { useTranslation } from '@/i18n/useTranslation';

interface EmrData {
  complaints?: string;
  anamnesis_morbi?: string;
  anamnesis_vitae?: string;
  examination?: string;
  diagnosis?: string;
  icd10_code?: string;
  treatment?: string;
  recommendations?: string;
  [key: string]: unknown;
}

interface MissingField {
  field: string;
  reason: string;
}

interface CompletenessSuggestion {
  field: string;
  message: string;
}

interface CompletenessResults {
  missingFields: MissingField[];
  suggestions: CompletenessSuggestion[];
  isComplete: boolean;
}

interface CompletenessCheckerProps {
  emrData?: EmrData | null;
  specialty?: string;
  onFieldClick?: (fieldName: string) => void;
}

/**
 * Field labels
 */
const getFieldLabels = (t: (key: string) => string): Record<string, string> => ({
  complaints: t('misc.cc_field_complaints'),
  anamnesis_morbi: t('misc.cc_field_anamnesis_morbi'),
  anamnesis_vitae: t('misc.cc_field_anamnesis_vitae'),
  examination: t('misc.cc_field_examination'),
  diagnosis: t('misc.cc_field_diagnosis'),
  icd10_code: t('misc.cc_field_icd10_code'),
  treatment: t('misc.cc_field_treatment'),
  recommendations: t('misc.cc_field_recommendations')
});

/**
 * CompletenessChecker Component
 * 
 * @param {Object} props
 * @param {Object} props.emrData - Current EMR data
 * @param {string} props.specialty - Doctor specialty
 * @param {Function} props.onFieldClick - Callback when clicking field (fieldName) => void
 */
export function CompletenessChecker({
  emrData,
  specialty = 'general',
  onFieldClick
}: CompletenessCheckerProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<CompletenessResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Check completeness
  const checkCompleteness = useCallback(async () => {
    if (!emrData) return;

    setIsLoading(true);
    setError(null);

    try {
      // Local check for now (can be replaced with AI call)
      const missingFields: MissingField[] = [];
      const suggestions: CompletenessSuggestion[] = [];

      // Check required fields
      if (!emrData.complaints?.trim()) {
        missingFields.push({ field: 'complaints', reason: t('misc.cc_reason_empty') });
      }
      if (!emrData.diagnosis?.trim()) {
        missingFields.push({ field: 'diagnosis', reason: t('misc.cc_reason_no_diagnosis') });
      }
      if (emrData.diagnosis && !emrData.icd10_code?.trim()) {
        missingFields.push({ field: 'icd10_code', reason: t('misc.cc_reason_no_icd10') });
      }
      if (!emrData.treatment?.trim()) {
        missingFields.push({ field: 'treatment', reason: t('misc.cc_reason_no_treatment') });
      }

      // Content suggestions
      if (emrData.complaints?.trim() && !emrData.examination?.trim()) {
        suggestions.push({
          field: 'examination',
          message: t('misc.cc_rekomenduetsya_dobavit_danny')
        });
      }

      // Specialty-specific
      if (specialty === 'cardiology') {
        const exam = emrData.examination?.toLowerCase() || '';
        if (emrData.complaints && !exam.includes(t('misc.cc_ad')) && !exam.includes(t('misc.cc_davlen'))) {
          suggestions.push({
            field: 'examination',
            message: t('misc.cc_dlya_kardiologii_dobavte_ad')
          });
        }
      }

      setResults({
        missingFields,
        suggestions,
        isComplete: missingFields.length === 0
      });
    } catch (err) {
      setError((err instanceof Error ? err.message : String(err)) || t('misc.cc_oshibka_proverki'));
    } finally {
      setIsLoading(false);
    }
  }, [emrData, specialty]);

  // Handle check
  const handleCheck = useCallback(() => {
    if (!isOpen) {
      setIsOpen(true);
      checkCompleteness();
    } else {
      setIsOpen(false);
    }
  }, [isOpen, checkCompleteness]);

  // Handle field click
  const handleFieldClick = useCallback((fieldName: string) => {
    onFieldClick?.(fieldName);
    // Scroll to field
    const element = document.getElementById(`emr-${fieldName}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      element.focus();
    }
  }, [onFieldClick]);

  return (
    <div className="completeness-checker">
            {/* Trigger button */}
            <button
        type="button"
        className={`completeness-checker__btn ${results?.isComplete ? 'completeness-checker__btn--complete' : ''}`}
        onClick={handleCheck}
        disabled={isLoading}>
        
                {isLoading ? '⏳' : results?.isComplete ? '✅' : '🔍'}
                <span>{t('misc.cc_proverit_polnotu')}</span>
            </button>

            {/* Results panel */}
            {isOpen &&
      <div className="completeness-checker__panel">
                    {/* Header */}
                    <div className="completeness-checker__header">
                        <span>🧠 Проверка полноты ЭМК</span>
                        <button onClick={() => setIsOpen(false)}>×</button>
                    </div>

                    {/* Content */}
                    <div className="completeness-checker__content">
                        {isLoading &&
          <div className="completeness-checker__loading">
                                Анализирую...
                            </div>
          }

                        {error &&
          <div className="completeness-checker__error">
                                ❌ {error}
                            </div>
          }

                        {results && !isLoading &&
          <>
                                {results.isComplete ?
            <div className="completeness-checker__success">
                                        ✅ ЭМК заполнена полностью
                                    </div> :

            <>
                                        {/* Missing fields */}
                                        {results.missingFields.length > 0 &&
              <div className="completeness-checker__section">
                                                <div className="completeness-checker__section-title">
                                                    ⚠️ Обязательные поля
                                                </div>
                                                {results.missingFields.map(({ field, reason }) =>
                <button
                  key={field}
                  className="completeness-checker__item completeness-checker__item--error"
                  onClick={() => handleFieldClick(field)}>
                  
                                                        <span className="completeness-checker__item-label">
                                                            {getFieldLabels(t)[field] || field}
                                                        </span>
                                                        <span className="completeness-checker__item-reason">
                                                            {reason}
                                                        </span>
                                                    </button>
                )}
                                            </div>
              }

                                        {/* Suggestions */}
                                        {results.suggestions.length > 0 &&
              <div className="completeness-checker__section">
                                                <div className="completeness-checker__section-title">
                                                    💡 Рекомендации
                                                </div>
                                                {results.suggestions.map(({ field, message }, idx) =>
                <button
                  key={`${field}-${idx}`}
                  className="completeness-checker__item completeness-checker__item--suggestion"
                  onClick={() => handleFieldClick(field)}>
                  
                                                        <span className="completeness-checker__item-label">
                                                            {getFieldLabels(t)[field] || field}
                                                        </span>
                                                        <span className="completeness-checker__item-reason">
                                                            {message}
                                                        </span>
                                                    </button>
                )}
                                            </div>
              }
                                    </>
            }
                            </>
          }
                    </div>

                    {/* Footer */}
                    <div className="completeness-checker__footer">
                        AI не заполняет поля. Решение принимает врач.
                    </div>
                </div>
      }
        </div>);

}

export default CompletenessChecker;

