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
      api.get('/derma/examinations', { params: { patient_id: normalizedPatientId, limit: 10 } }),
      api.get('/derma/procedures', { params: { patient_id: normalizedPatientId, limit: 10 } }),
    ]).then(([appointmentsResult, examinationsResult, proceduresResult]) => {
      if (!active) return;

      const appointments = appointmentsResult.status === 'fulfilled'
        ? asArray<DermatologyAppointmentHistoryItem>(appointmentsResult.value.data)
        : [];
      const skinExaminations = examinationsResult.status === 'fulfilled'
        ? asArray<DermatologySkinExamination>(examinationsResult.value.data)
        : [];
      const cosmeticProcedures = proceduresResult.status === 'fulfilled'
        ? asArray<DermatologyCosmeticProcedure>(proceduresResult.value.data)
        : [];

      setSnapshot({
        patientId: normalizedPatientId,
        appointments,
        skinExaminations,
        cosmeticProcedures,
        loading: false,
        error: [appointmentsResult, examinationsResult, proceduresResult]
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
