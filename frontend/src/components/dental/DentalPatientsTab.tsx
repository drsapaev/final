import { useEffect, useRef, useState } from 'react';
import { Search } from 'lucide-react';
import { searchPatients } from '../../api/patients';
import type { Patient } from '../../types/domain/clinic';
import { useTranslation } from '../../i18n/useTranslation';
import { Button, Card, Input } from '../ui/macos';

export interface DentalPatientsTabPatient extends Record<string, unknown> {
  id?: string | number;
  patient_id?: string | number;
  name?: string;
  full_name?: string;
  phone?: string;
}

export interface DentalPatientsTabProps {
  onSelectPatient?: (patient: DentalPatientsTabPatient) => void;
  onGoToQueue?: () => void;
}

type SearchState = 'idle' | 'loading' | 'error' | 'ready';

export default function DentalPatientsTab({ onSelectPatient, onGoToQueue }: DentalPatientsTabProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [retryKey, setRetryKey] = useState(0);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [state, setState] = useState<SearchState>('idle');
  const requestId = useRef(0);

  useEffect(() => {
    const currentRequest = ++requestId.current;
    const normalized = query.trim();
    if (normalized.length < 2) {
      setPatients([]);
      setState('idle');
      return;
    }

    setState('loading');
    const timer = window.setTimeout(() => {
      searchPatients(normalized).then((results) => {
        if (requestId.current !== currentRequest) return;
        setPatients(results);
        setState('ready');
      }).catch(() => {
        if (requestId.current !== currentRequest) return;
        setPatients([]);
        setState('error');
      });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      if (requestId.current === currentRequest) requestId.current += 1;
    };
  }, [query, retryKey]);

  const selectPatient = (patient: Patient) => {
    const name = patient.full_name || patient.name || [patient.last_name, patient.first_name, patient.middle_name].filter(Boolean).join(' ');
    onSelectPatient?.({ ...patient, id: patient.id, patient_id: patient.id, name, full_name: name });
  };

  return (
    <div className="dental-flex-col dental-gap-16">
      <Card padding="large">
        <div className="dental-flex-col dental-gap-12">
          <h2 className="dental-text-primary">{t('dental.dental_dpt_title')}</h2>
          <label htmlFor="dental-patient-search" className="dental-text-secondary">
            {t('dental.dental_dpt_search_label')}
          </label>
          <Input
            id="dental-patient-search"
            type="search"
            icon={Search}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('dental.dental_dpt_search_placeholder')}
            autoComplete="off"
          />
          <p className="dental-text-desc dental-text-secondary">{t('dental.dental_dpt_search_hint')}</p>
        </div>
      </Card>

      {state === 'loading' && <p role="status" aria-live="polite" className="dental-text-secondary">{t('dental.dental_dpt_search_loading')}</p>}
      {state === 'idle' && query.trim().length > 0 && query.trim().length < 2 && (
        <p role="status" className="dental-text-secondary">{t('dental.dental_dpt_search_minimum')}</p>
      )}
      {state === 'error' && (
        <Card padding="large" role="alert">
          <div className="dental-flex-col dental-gap-12">
            <p className="dental-text-primary">{t('dental.dental_dpt_search_error')}</p>
            <Button variant="outline" onClick={() => setRetryKey((value) => value + 1)}>{t('dental.dental_dpt_retry')}</Button>
          </div>
        </Card>
      )}
      {state === 'ready' && patients.length === 0 && (
        <Card padding="large">
          <div className="dental-flex-col dental-gap-12">
            <p className="dental-text-primary">{t('dental.dental_dpt_search_empty')}</p>
            <Button variant="outline" onClick={onGoToQueue}>
              {t('dental.dental_dpt_go_queue')}
            </Button>
          </div>
        </Card>
      )}
      {patients.map((patient) => {
        const name = patient.full_name || patient.name || [patient.last_name, patient.first_name, patient.middle_name].filter(Boolean).join(' ') || '—';
        return (
          <Card key={String(patient.id)} padding="default">
            <div className="dental-flex-between-16">
              <div>
                <p className="dental-text-primary dental-font-medium">{name}</p>
                {patient.phone && <p className="dental-text-desc dental-text-secondary">{patient.phone}</p>}
              </div>
              <Button
                variant="outline"
                onClick={() => selectPatient(patient)}
                aria-label={t('dental.dental_dpt_aria_select', { name })}>
                {t('dental.dental_dpt_select')}
              </Button>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
