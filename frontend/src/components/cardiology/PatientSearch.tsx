/**
 * PatientSearch — cardioplan slice 4 ("Пациенты и AI").
 *
 * Search patients available to the current doctor by name/phone (backend owns
 * the rules: GET /patients/?q= is doctor-authorized and server-scoped). The
 * panel query guard is client-side only: no request fires below 2 characters.
 *
 * Shows three distinct states (loading / empty / error) so a failed request
 * can never look like a verified "no patients found" answer.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Search } from 'lucide-react';

import { apiClient } from '../../api/client';
import { useTranslation } from '../../i18n/useTranslation';
import { AppEmpty, AppError, AppLoading, Button, Card, Input } from '../ui/macos';
import './PatientSearch.css';

export interface PatientSearchResult {
  id: number | string;
  full_name: string;
  phone: string;
  birth_year: string | null;
}

export const PATIENT_SEARCH_MIN_CHARS = 2;
const PATIENT_SEARCH_LIMIT = 20;
const PATIENT_SEARCH_DEBOUNCE_MS = 300;

interface PatientSearchProps {
  onPick: (patient: PatientSearchResult) => void;
  selectedPatientId?: string | number | null;
}

function toSearchResult(raw: Record<string, unknown>): PatientSearchResult | null {
  const id = raw.id;
  if (id === null || id === undefined || id === '') return null;
  const fullName = String(raw.full_name ?? '').trim();
  const composedName = `${String(raw.last_name ?? '').trim()} ${String(raw.first_name ?? '').trim()}`.trim();
  const birthDate = String(raw.birth_date ?? '').trim();
  return {
    id: id as number | string,
    full_name: fullName || composedName || `#${String(id)}`,
    phone: String(raw.phone ?? '').trim(),
    birth_year: birthDate ? birthDate.slice(0, 4) : null,
  };
}

export function PatientSearch({ onPick, selectedPatientId = null }: PatientSearchProps): React.JSX.Element {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PatientSearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const requestSeq = useRef(0);

  const runSearch = useCallback(async (trimmed: string) => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(false);
    try {
      const { data } = await apiClient.get('/patients/', { params: { q: trimmed, limit: PATIENT_SEARCH_LIMIT } });
      if (seq !== requestSeq.current) return;
      const list = Array.isArray(data) ? data : [];
      setResults(
        list
          .map((item) => toSearchResult(item as Record<string, unknown>))
          .filter((item): item is PatientSearchResult => item !== null),
      );
    } catch {
      if (seq !== requestSeq.current) return;
      setError(true);
      setResults(null);
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < PATIENT_SEARCH_MIN_CHARS) {
      requestSeq.current += 1; // invalidate any in-flight request
      setResults(null);
      setError(false);
      setLoading(false);
      return;
    }
    const timer = window.setTimeout(() => { void runSearch(trimmed); }, PATIENT_SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query, runSearch]);

  const tooShort = query.trim().length < PATIENT_SEARCH_MIN_CHARS;

  return (
    <Card className="cardio-card-fullwidth">
      <h2 className="cardio-queue__title">{t('cardio.patient_search_title')}</h2>
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={t('cardio.patient_search_placeholder')}
        aria-label={t('cardio.patient_search_placeholder')}
        icon={Search}
      />
      {!tooShort && (
        <p className="cardio-queue__doctor" aria-live="polite">
          {t('cardio.patient_search_results_for', { query: query.trim() })}
        </p>
      )}

      {tooShort && <AppEmpty title={t('cardio.patient_search_hint_title')} description={t('cardio.patient_search_hint_desc')} />}

      {!tooShort && loading && <AppLoading />}

      {!tooShort && !loading && error && (
        <AppError
          title={t('cardio.patient_search_error_title')}
          description={t('cardio.patient_search_error_desc')}
          action={(
            <Button variant="outline" onClick={() => { void runSearch(query.trim()); }}>
              {t('cardio.patient_search_retry')}
            </Button>
          )}
        />
      )}

      {!tooShort && !loading && !error && results && results.length === 0 && (
        <AppEmpty title={t('cardio.patient_search_empty_title')} description={t('cardio.patient_search_empty_desc')} />
      )}

      {!tooShort && !loading && !error && results && results.length > 0 && (
        <ul className="cardio-patient-search__list" role="list">
          {results.map((patient) => (
            <li key={String(patient.id)}>
              <button
                type="button"
                className="cardio-patient-search__row"
                onClick={() => onPick(patient)}
                aria-pressed={selectedPatientId !== null && String(selectedPatientId) === String(patient.id)}
              >
                <span className="cardio-patient-search__name">{patient.full_name}</span>
                <span className="cardio-patient-search__meta">
                  {[patient.phone, patient.birth_year].filter(Boolean).join(' • ')}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default PatientSearch;
