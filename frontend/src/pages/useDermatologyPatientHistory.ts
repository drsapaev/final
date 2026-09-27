import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

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

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
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
      // Triage P2 (owner review of #3491): both derma history sections are
      // served by one combined read-model endpoint — a single EMR scan and
      // a single Visit load on the server instead of two independent scans
      // in GET /derma/examinations and GET /derma/procedures.
      api.get('/derma/history', { params: { patient_id: normalizedPatientId, limit: 10 } }),
    ]).then(([appointmentsResult, historyResult]) => {
      if (!active) return;

      const appointments = appointmentsResult.status === 'fulfilled'
        ? asArray<DermatologyAppointmentHistoryItem>(appointmentsResult.value.data)
        : [];
      const historyData = historyResult.status === 'fulfilled'
        ? (historyResult.value.data as {
            examinations?: unknown;
            procedures?: unknown;
          } | null)
        : null;
      const skinExaminations = asArray<DermatologySkinExamination>(historyData?.examinations);
      const cosmeticProcedures = asArray<DermatologyCosmeticProcedure>(historyData?.procedures);

      setSnapshot({
        patientId: normalizedPatientId,
        appointments,
        skinExaminations,
        cosmeticProcedures,
        loading: false,
        error: [appointmentsResult, historyResult]
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
