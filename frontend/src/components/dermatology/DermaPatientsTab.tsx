import { useEffect, useMemo, useState } from 'react';
import { Calendar, HeartPulse, Phone, Search, Sparkles, User } from 'lucide-react';
import type { Patient } from '../../types/domain/clinic';
import { searchPatients } from '../../api/patients';
import { useTranslation } from '../../i18n/useTranslation';
import { Badge, Button, Card, Input } from '../ui/macos';
import DermaHistoryTab from './DermaHistoryTab';
import type {
  DermatologyAppointmentHistoryItem,
  DermatologyCosmeticProcedure,
  DermatologySkinExamination,
} from '../../pages/useDermatologyPatientHistory';

export interface DermatologyPatientRecord {
  id?: number | string | null;
  patient_id?: number | string | null;
  patient_name?: string;
  first_name?: string;
  last_name?: string;
  middle_name?: string;
  phone?: string;
  birth_date?: string;
  patient_birth_year?: string | number;
  visit_id?: string | number | null;
  [key: string]: unknown;
}

function toDermatologyPatient(patient: Patient): DermatologyPatientRecord {
  const fullName = patient.full_name || [patient.last_name, patient.first_name, patient.middle_name]
    .filter(Boolean)
    .join(' ');

  return {
    ...patient,
    id: patient.id,
    patient_id: patient.id,
    patient_name: fullName || patient.name || '',
    phone: patient.phone || '',
    birth_date: patient.birth_date || '',
  };
}

function patientId(patient: DermatologyPatientRecord | null): string | null {
  const id = patient?.patient_id ?? patient?.id;
  return id === null || id === undefined || id === '' ? null : String(id);
}

function patientName(patient: DermatologyPatientRecord): string {
  return patient.patient_name || [patient.last_name, patient.first_name, patient.middle_name]
    .filter(Boolean)
    .join(' ') || '';
}

function birthLabel(patient: DermatologyPatientRecord): string {
  return patient.patient_birth_year ? String(patient.patient_birth_year) : patient.birth_date || '';
}

interface DermaPatientsTabProps {
  selectedPatient: DermatologyPatientRecord | null;
  onSelectPatient: (patient: DermatologyPatientRecord | null) => void;
  onOpenExam: (patient: DermatologyPatientRecord) => void;
  onOpenProcedure: (patient: DermatologyPatientRecord) => void;
  appointments: DermatologyAppointmentHistoryItem[];
  skinExaminations: DermatologySkinExamination[];
  cosmeticProcedures: DermatologyCosmeticProcedure[];
  historyLoading: boolean;
  historyReady: boolean;
  historyError: boolean;
}

export function DermaPatientsTab({
  selectedPatient,
  onSelectPatient,
  onOpenExam,
  onOpenProcedure,
  appointments,
  skinExaminations,
  cosmeticProcedures,
  historyLoading,
  historyReady,
  historyError,
}: DermaPatientsTabProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Patient[]>([]);
  const [resultsFor, setResultsFor] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchErrorFor, setSearchErrorFor] = useState('');
  const normalizedQuery = query.trim();
  const selectedId = patientId(selectedPatient);
  const searchError = Boolean(normalizedQuery && searchErrorFor === normalizedQuery);
  const visibleResults = useMemo(
    () => resultsFor === normalizedQuery ? results : [],
    [normalizedQuery, results, resultsFor],
  );

  useEffect(() => {
    let active = true;
    if (normalizedQuery.length < 2) {
      setResults([]);
      setResultsFor(normalizedQuery);
      setSearching(false);
      setSearchErrorFor('');
      return () => { active = false; };
    }

    const timeout = window.setTimeout(() => {
      setSearching(true);
      setSearchErrorFor('');
      void searchPatients(normalizedQuery)
        .then((patients) => {
          if (!active) return;
          setResults(patients);
          setResultsFor(normalizedQuery);
        })
        .catch(() => {
          if (!active) return;
          setResults([]);
          setResultsFor(normalizedQuery);
          setSearchErrorFor(normalizedQuery);
        })
        .finally(() => {
          if (active) setSearching(false);
        });
    }, 300);

    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [normalizedQuery]);

  return (
    <div className="derma-flex-col-24">
      <Card className="derma-p-8">
        <div className="derma-flex-center">
          <h3 className="derma-flex-center">
            <User size={20} className="derma-icon-mr-green" aria-hidden="true" />
            {t('derma.derma_panel_patients_title')}
          </h3>
          <Badge variant="info">{t('derma.derma_panel_patients_count', { count: visibleResults.length })}</Badge>
        </div>

        <label className="derma-p-14-secondary" htmlFor="derma-patient-search">
          {t('derma.derma_panel_patients_search_label')}
        </label>
        <Input
          id="derma-patient-search"
          type="search"
          icon={Search}
          value={query}
          autoComplete="off"
          placeholder={t('derma.derma_panel_patients_search_placeholder')}
          onChange={(event) => setQuery(event.target.value)}
        />

        {normalizedQuery.length < 2 && (
          <p className="derma-p-14-secondary" role="status">
            {t('derma.derma_panel_patients_search_minimum')}
          </p>
        )}
        {searching && (
          <p className="derma-p-14-secondary" role="status">
            {t('derma.derma_panel_patients_loading')}
          </p>
        )}
        {searchError && <p role="alert">{t('derma.derma_panel_patients_search_error')}</p>}
        {!searching && !searchError && resultsFor === normalizedQuery && normalizedQuery.length >= 2 && visibleResults.length === 0 && (
          <p className="derma-p-14-secondary" role="status">
            {t('derma.derma_panel_patients_search_empty')}
          </p>
        )}

        {visibleResults.length > 0 && (
          <ul
            className="derma-flex-col-24"
            aria-label={t('derma.derma_panel_patients_search_results')}
            style={{ listStyle: 'none', margin: 0, padding: 0 }}
          >
            {visibleResults.map((patient) => {
              const mappedPatient = toDermatologyPatient(patient);
              const id = patientId(mappedPatient);
              return (
                <li key={String(id)} className="derma-patient-card">
                  <div className="derma-flex-between-top">
                    <div className="derma-flex-1">
                      <h4 className="derma-h4-16-600">{patientName(mappedPatient)}</h4>
                      <div className="derma-patient-info-list">
                        {mappedPatient.phone && (
                          <span className="derma-flex-center">
                            <Phone size={16} className="derma-icon-mr derma-text-accent" aria-hidden="true" />
                            {mappedPatient.phone}
                          </span>
                        )}
                        {birthLabel(mappedPatient) && (
                          <span className="derma-flex-center">
                            <Calendar size={14} className="derma-icon-mr" aria-hidden="true" />
                            {birthLabel(mappedPatient)}
                          </span>
                        )}
                      </div>
                    </div>
                    <Button
                      variant={selectedId === id ? 'primary' : 'outline'}
                      aria-pressed={selectedId === id}
                      onClick={() => onSelectPatient(mappedPatient)}
                    >
                      {t('derma.derma_panel_patients_select')}
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {selectedPatient && selectedId && (
        <>
          <Card className="derma-p-8">
            <div className="derma-flex-between-top">
              <div>
                <h3>{patientName(selectedPatient)}</h3>
                <div className="derma-patient-info-list">
                  {selectedPatient.phone && <span>{selectedPatient.phone}</span>}
                  {birthLabel(selectedPatient) && <span>{birthLabel(selectedPatient)}</span>}
                  <span>{t('derma.derma_panel_patient_id', { id: selectedId })}</span>
                </div>
              </div>
              <div className="derma-flex-gap-16" style={{ flexWrap: 'wrap' }}>
                <Button variant="outline" onClick={() => onOpenExam(selectedPatient)}>
                  <HeartPulse size={16} aria-hidden="true" />
                  {t('derma.derma_panel_button_exam')}
                </Button>
                <Button variant="outline" onClick={() => onOpenProcedure(selectedPatient)}>
                  <Sparkles size={16} aria-hidden="true" />
                  {t('derma.derma_panel_button_procedure')}
                </Button>
                <Button variant="outline" onClick={() => onSelectPatient(null)}>
                  {t('derma.derma_panel_patients_clear_selection')}
                </Button>
              </div>
            </div>
          </Card>

          {historyLoading && (
            <Card className="derma-p-8">
              <p className="derma-p-14-secondary" role="status">
                {t('derma.derma_panel_patient_history_loading')}
              </p>
            </Card>
          )}
          {historyError && historyReady && (
            <p role="alert">{t('derma.derma_panel_patient_history_error')}</p>
          )}
          {historyReady && (
            <DermaHistoryTab
              appointments={appointments}
              skinExaminations={skinExaminations}
              cosmeticProcedures={cosmeticProcedures}
            />
          )}
        </>
      )}

      {!selectedPatient && (
        <Card className="derma-p-8">
          <p className="derma-p-14-secondary" role="status">
            {t('derma.derma_panel_patient_history_select_prompt')}
          </p>
        </Card>
      )}
    </div>
  );
}

export default DermaPatientsTab;
