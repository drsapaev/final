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
 * P2-4b canonical (review follow-up on #3490/#3491): the dermatology
 * clinical history is a server-side union — GET /derma/examinations and
 * GET /derma/procedures merge dermatology EMR rows (specialty_data) with
 * the closed legacy tables and return the canonical page/size/total/pages
 * envelope (FileList contract). The hook only pages through that union:
 * no client-side EMR fetching, no per-source limits, and `total` is the
 * exact history size, so the UI always knows whether the listing is
 * complete («Показать ещё»).
 */

const HISTORY_PAGE_SIZE = 20;

interface PatientHistorySnapshot {
  patientId: string | null;
  appointments: DermatologyAppointmentHistoryItem[];
  skinExaminations: DermatologySkinExamination[];
  skinExaminationsTotal: number;
  skinExaminationsNextPage: number;
  cosmeticProcedures: DermatologyCosmeticProcedure[];
  cosmeticProceduresTotal: number;
  cosmeticProceduresNextPage: number;
  loading: boolean;
  loadingMoreExaminations: boolean;
  loadingMoreProcedures: boolean;
  error: boolean;
}

const emptySnapshot: PatientHistorySnapshot = {
  patientId: null,
  appointments: [],
  skinExaminations: [],
  skinExaminationsTotal: 0,
  skinExaminationsNextPage: 1,
  cosmeticProcedures: [],
  cosmeticProceduresTotal: 0,
  cosmeticProceduresNextPage: 1,
  loading: false,
  loadingMoreExaminations: false,
  loadingMoreProcedures: false,
  error: false,
};

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

/** Parse the canonical history envelope; an unexpected bare array is
 * treated as a single page with total = items.length (defensive only —
 * the server contract is the page envelope). */
function parseHistoryPage<T>(payload: unknown): { items: T[]; total: number } {
  if (Array.isArray(payload)) {
    return { items: payload as T[], total: payload.length };
  }
  if (payload && typeof payload === 'object') {
    const envelope = payload as { items?: unknown; total?: unknown };
    const items = Array.isArray(envelope.items) ? envelope.items as T[] : [];
    const total = typeof envelope.total === 'number' ? envelope.total : items.length;
    return { items, total };
  }
  return { items: [], total: 0 };
}

async function fetchHistoryPage<T>(
  endpoint: string,
  patientId: string,
  page: number,
): Promise<{ items: T[]; total: number }> {
  const response = await api.get(endpoint, {
    params: { patient_id: patientId, page, size: HISTORY_PAGE_SIZE },
  });
  return parseHistoryPage<T>(response.data);
}

/** Append a page without duplicates (id is int for legacy rows and the
 * synthetic "emr-<record>[-<index>]" string for EMR rows). */
function mergeById<T extends { id: string | number }>(existing: T[], incoming: T[]): T[] {
  const seen = new Set(existing.map((row) => String(row.id)));
  const appended = incoming.filter((row) => !seen.has(String(row.id)));
  return appended.length ? [...existing, ...appended] : existing;
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
    setSnapshot({ ...emptySnapshot, patientId: normalizedPatientId, loading: true });

    void Promise.allSettled([
      api.get(`/patients/${encodeURIComponent(normalizedPatientId)}/appointments`),
      fetchHistoryPage<DermatologySkinExamination>(
        '/derma/examinations', normalizedPatientId, 1,
      ),
      fetchHistoryPage<DermatologyCosmeticProcedure>(
        '/derma/procedures', normalizedPatientId, 1,
      ),
    ]).then(([appointmentsResult, examinationsResult, proceduresResult]) => {
      if (!active) return;

      if (examinationsResult.status === 'rejected' || proceduresResult.status === 'rejected') {
        logger.warn(
          '[DermaHistory] history page unavailable for patient',
          { patientId: normalizedPatientId },
        );
      }

      const appointments = appointmentsResult.status === 'fulfilled'
        ? asArray<DermatologyAppointmentHistoryItem>(appointmentsResult.value.data)
        : [];
      const examinationsPage = examinationsResult.status === 'fulfilled'
        ? examinationsResult.value
        : { items: [] as DermatologySkinExamination[], total: 0 };
      const proceduresPage = proceduresResult.status === 'fulfilled'
        ? proceduresResult.value
        : { items: [] as DermatologyCosmeticProcedure[], total: 0 };

      setSnapshot({
        ...emptySnapshot,
        patientId: normalizedPatientId,
        appointments,
        skinExaminations: examinationsPage.items,
        skinExaminationsTotal: examinationsPage.total,
        skinExaminationsNextPage: 2,
        cosmeticProcedures: proceduresPage.items,
        cosmeticProceduresTotal: proceduresPage.total,
        cosmeticProceduresNextPage: 2,
        loading: false,
        error: [appointmentsResult, examinationsResult, proceduresResult]
          .some((result) => result.status === 'rejected'),
      });
    });

    return () => {
      active = false;
    };
  }, [normalizedPatientId, reloadVersion]);

  const loadMoreExaminations = useCallback(() => {
    if (
      snapshot.loading || snapshot.loadingMoreExaminations
      || snapshot.patientId !== normalizedPatientId
      || snapshot.skinExaminations.length >= snapshot.skinExaminationsTotal
    ) return;

    const patientId = snapshot.patientId as string;
    const nextPage = snapshot.skinExaminationsNextPage;
    setSnapshot((prev) => ({ ...prev, loadingMoreExaminations: true }));
    void fetchHistoryPage<DermatologySkinExamination>('/derma/examinations', patientId, nextPage)
      .then((page) => {
        setSnapshot((current) => (
          current.patientId === patientId
            ? {
              ...current,
              skinExaminations: mergeById(current.skinExaminations, page.items),
              skinExaminationsTotal: page.total,
              skinExaminationsNextPage: nextPage + 1,
              loadingMoreExaminations: false,
            }
            : current
        ));
      })
      .catch(() => {
        logger.warn('[DermaHistory] failed to load more examinations', { patientId });
        setSnapshot((current) => (
          current.patientId === patientId
            ? { ...current, loadingMoreExaminations: false }
            : current
        ));
      });
  }, [snapshot, normalizedPatientId]);

  const loadMoreProcedures = useCallback(() => {
    if (
      snapshot.loading || snapshot.loadingMoreProcedures
      || snapshot.patientId !== normalizedPatientId
      || snapshot.cosmeticProcedures.length >= snapshot.cosmeticProceduresTotal
    ) return;

    const patientId = snapshot.patientId as string;
    const nextPage = snapshot.cosmeticProceduresNextPage;
    setSnapshot((prev) => ({ ...prev, loadingMoreProcedures: true }));
    void fetchHistoryPage<DermatologyCosmeticProcedure>('/derma/procedures', patientId, nextPage)
      .then((page) => {
        setSnapshot((current) => (
          current.patientId === patientId
            ? {
              ...current,
              cosmeticProcedures: mergeById(current.cosmeticProcedures, page.items),
              cosmeticProceduresTotal: page.total,
              cosmeticProceduresNextPage: nextPage + 1,
              loadingMoreProcedures: false,
            }
            : current
        ));
      })
      .catch(() => {
        logger.warn('[DermaHistory] failed to load more procedures', { patientId });
        setSnapshot((current) => (
          current.patientId === patientId
            ? { ...current, loadingMoreProcedures: false }
            : current
        ));
      });
  }, [snapshot, normalizedPatientId]);

  const reload = useCallback(() => setReloadVersion((version) => version + 1), []);
  const isCurrentPatient = Boolean(normalizedPatientId && snapshot.patientId === normalizedPatientId);

  return {
    appointments: isCurrentPatient ? snapshot.appointments : [],
    skinExaminations: isCurrentPatient ? snapshot.skinExaminations : [],
    cosmeticProcedures: isCurrentPatient ? snapshot.cosmeticProcedures : [],
    skinExaminationsTotal: isCurrentPatient ? snapshot.skinExaminationsTotal : 0,
    cosmeticProceduresTotal: isCurrentPatient ? snapshot.cosmeticProceduresTotal : 0,
    hasMoreExaminations: isCurrentPatient
      && snapshot.skinExaminations.length < snapshot.skinExaminationsTotal,
    hasMoreProcedures: isCurrentPatient
      && snapshot.cosmeticProcedures.length < snapshot.cosmeticProceduresTotal,
    loadingMoreExaminations: isCurrentPatient && snapshot.loadingMoreExaminations,
    loadingMoreProcedures: isCurrentPatient && snapshot.loadingMoreProcedures,
    loadMoreExaminations,
    loadMoreProcedures,
    loading: Boolean(normalizedPatientId) && (!isCurrentPatient || snapshot.loading),
    ready: isCurrentPatient && !snapshot.loading,
    error: isCurrentPatient && snapshot.error,
    reload,
  };
}

export default useDermatologyPatientHistory;
