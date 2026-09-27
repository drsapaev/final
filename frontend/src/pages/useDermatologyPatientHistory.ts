import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import logger from '../utils/logger';

export interface DermatologyAppointmentHistoryItem {
  id: number | string;
  appointment_date: string;
  appointment_time?: string | null;
  department?: string | null;
  status?: string | null;
}

export interface DermatologySkinExamination {
  id: string | number;
  examination_date?: string;
  exam_date?: string;
  skin_type?: string;
  skin_condition?: string;
  diagnosis?: string;
}

export interface DermatologyCosmeticProcedure {
  id: string | number;
  procedure_date?: string;
  total_cost?: number | string;
  procedure_type?: string;
  area_treated?: string;
}

/**
 * P2-4b: the dermatology clinical history reads the EMR (emr/v2) as the
 * canonical source — GET /v2/emr/patient/{id} summaries plus per-visit
 * hydration (dentist protocol precedent) — and keeps the legacy
 * /derma/examinations + /derma/procedures tables as a read-only fallback
 * for pre-cutover rows (their write endpoints return 410 since P2-4a).
 * Both sources are merged, most recent first.
 */

interface EmrRecord {
  id: number | string;
  created_at?: string | null;
  diagnosis_main?: string | null;
  data?: {
    specialty?: string | null;
    specialty_data?: Record<string, unknown> | null;
  } | null;
}

interface DermatologyEmrHistory {
  skinExaminations: DermatologySkinExamination[];
  cosmeticProcedures: DermatologyCosmeticProcedure[];
}

interface PatientHistorySnapshot {
  patientId: string | null;
  appointments: DermatologyAppointmentHistoryItem[];
  skinExaminations: DermatologySkinExamination[];
  cosmeticProcedures: DermatologyCosmeticProcedure[];
  loading: boolean;
  error: boolean;
}

const emptySnapshot: PatientHistorySnapshot = {
  patientId: null,
  appointments: [],
  skinExaminations: [],
  cosmeticProcedures: [],
  loading: false,
  error: false,
};

const EMR_HISTORY_SUMMARY_LIMIT = 20;
const LEGACY_HISTORY_LIMIT = 10;

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function textValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function emrDatePart(record: EmrRecord): string {
  return String(record.created_at || '').slice(0, 10);
}

function mapEmrExaminations(records: EmrRecord[]): DermatologySkinExamination[] {
  const examinations: DermatologySkinExamination[] = [];
  for (const record of records) {
    const data = record.data || {};
    if (data.specialty !== 'dermatology') continue;

    const specialtyData = data.specialty_data || {};
    const skinType = textValue(specialtyData.skin_type);
    const skinCondition = textValue(specialtyData.skin_condition);
    const diagnosis = textValue(record.diagnosis_main);
    if (!skinType && !skinCondition && !diagnosis) continue;

    examinations.push({
      id: `emr-${record.id}`,
      examination_date: emrDatePart(record),
      ...(skinType ? { skin_type: skinType } : {}),
      ...(skinCondition ? { skin_condition: skinCondition } : {}),
      ...(diagnosis ? { diagnosis } : {}),
    });
  }
  return examinations;
}

function mapEmrProcedures(records: EmrRecord[]): DermatologyCosmeticProcedure[] {
  const procedures: DermatologyCosmeticProcedure[] = [];
  for (const record of records) {
    const data = record.data || {};
    if (data.specialty !== 'dermatology') continue;

    const rawProcedures = data.specialty_data?.cosmetic_procedures;
    if (!Array.isArray(rawProcedures)) continue;

    rawProcedures.forEach((entry, index) => {
      if (!entry || typeof entry !== 'object') return;
      const item = entry as Record<string, unknown>;
      const procedureDate = textValue(item.procedure_date);
      const procedureType = textValue(item.procedure_type);
      if (!procedureDate && !procedureType) return;

      procedures.push({
        id: `emr-${record.id}-${index}`,
        ...(procedureDate ? { procedure_date: procedureDate } : {}),
        ...(procedureType ? { procedure_type: procedureType } : {}),
        ...(textValue(item.area_treated) ? { area_treated: textValue(item.area_treated) } : {}),
      });
    });
  }
  return procedures;
}

async function loadDermatologyEmrHistory(patientId: string): Promise<DermatologyEmrHistory> {
  const summaryResponse = await api.get(`/v2/emr/patient/${encodeURIComponent(patientId)}`, {
    params: { limit: EMR_HISTORY_SUMMARY_LIMIT },
  });
  const summaries = Array.isArray(summaryResponse.data)
    ? summaryResponse.data as Array<{ visit_id?: unknown }>
    : [];

  const records = await Promise.all(
    summaries.map(async (summary) => {
      const visitId = summary?.visit_id;
      if (visitId === undefined || visitId === null || visitId === '') return null;
      try {
        const emrResponse = await api.get(`/v2/emr/${encodeURIComponent(String(visitId))}`, {
          validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
        });
        if (emrResponse.status === 404) return null;
        return emrResponse.data as EmrRecord;
      } catch {
        return null;
      }
    }),
  );

  const validRecords = records.filter((record): record is EmrRecord => Boolean(record));
  return {
    skinExaminations: mapEmrExaminations(validRecords),
    cosmeticProcedures: mapEmrProcedures(validRecords),
  };
}

function examinationDate(examination: DermatologySkinExamination): string {
  return String(examination.exam_date || examination.examination_date || '').slice(0, 10);
}

function sortExaminationsByDateDesc(
  list: DermatologySkinExamination[],
): DermatologySkinExamination[] {
  return [...list].sort((left, right) => {
    const leftDate = examinationDate(left);
    const rightDate = examinationDate(right);
    if (leftDate === rightDate) return 0;
    if (!leftDate) return 1;
    if (!rightDate) return -1;
    return rightDate.localeCompare(leftDate);
  });
}

function sortProceduresByDateDesc(
  list: DermatologyCosmeticProcedure[],
): DermatologyCosmeticProcedure[] {
  return [...list].sort((left, right) => {
    const leftDate = String(left.procedure_date || '').slice(0, 10);
    const rightDate = String(right.procedure_date || '').slice(0, 10);
    if (leftDate === rightDate) return 0;
    if (!leftDate) return 1;
    if (!rightDate) return -1;
    return rightDate.localeCompare(leftDate);
  });
}

/** Load history only for the selected patient and discard responses from older selections. */
export function useDermatologyPatientHistory(patientId: string | number | null | undefined) {
  const normalizedPatientId = patientId === null || patientId === undefined || patientId === ''
    ? null
    : String(patientId);
  const [snapshot, setSnapshot] = useState<PatientHistorySnapshot>(emptySnapshot);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    if (!normalizedPatientId) {
      setSnapshot(emptySnapshot);
      return;
    }

    let active = true;
    setSnapshot({ ...emptySnapshot, loading: true });

    void Promise.allSettled([
      api.get(`/patients/${encodeURIComponent(normalizedPatientId)}/appointments`),
      loadDermatologyEmrHistory(normalizedPatientId),
      api.get('/derma/examinations', { params: { patient_id: normalizedPatientId, limit: LEGACY_HISTORY_LIMIT } }),
      api.get('/derma/procedures', { params: { patient_id: normalizedPatientId, limit: LEGACY_HISTORY_LIMIT } }),
    ]).then(([appointmentsResult, emrResult, examinationsResult, proceduresResult]) => {
      if (!active) return;

      if (emrResult.status === 'rejected') {
        logger.warn(
          '[DermaHistory] EMR history unavailable, showing legacy rows only',
          { patientId: normalizedPatientId },
        );
      }

      const emrHistory = emrResult.status === 'fulfilled'
        ? emrResult.value
        : { skinExaminations: [], cosmeticProcedures: [] };
      const appointments = appointmentsResult.status === 'fulfilled'
        ? asArray<DermatologyAppointmentHistoryItem>(appointmentsResult.value.data)
        : [];
      const legacyExaminations = examinationsResult.status === 'fulfilled'
        ? asArray<DermatologySkinExamination>(examinationsResult.value.data)
        : [];
      const legacyProcedures = proceduresResult.status === 'fulfilled'
        ? asArray<DermatologyCosmeticProcedure>(proceduresResult.value.data)
        : [];

      setSnapshot({
        patientId: normalizedPatientId,
        appointments,
        skinExaminations: sortExaminationsByDateDesc([
          ...emrHistory.skinExaminations,
          ...legacyExaminations,
        ]),
        cosmeticProcedures: sortProceduresByDateDesc([
          ...emrHistory.cosmeticProcedures,
          ...legacyProcedures,
        ]),
        loading: false,
        error: [appointmentsResult, emrResult, examinationsResult, proceduresResult]
          .some((result) => result.status === 'rejected'),
      });
    });

    return () => {
      active = false;
    };
  }, [normalizedPatientId, reloadVersion]);

  const reload = useCallback(() => setReloadVersion((version) => version + 1), []);
  const isCurrentPatient = Boolean(normalizedPatientId && snapshot.patientId === normalizedPatientId);

  return {
    appointments: isCurrentPatient ? snapshot.appointments : [],
    skinExaminations: isCurrentPatient ? snapshot.skinExaminations : [],
    cosmeticProcedures: isCurrentPatient ? snapshot.cosmeticProcedures : [],
    loading: Boolean(normalizedPatientId) && (!isCurrentPatient || snapshot.loading),
    ready: isCurrentPatient && !snapshot.loading,
    error: isCurrentPatient && snapshot.error,
    reload,
  };
}

export default useDermatologyPatientHistory;
