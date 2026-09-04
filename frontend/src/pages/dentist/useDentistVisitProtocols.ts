import { useCallback, useEffect, useState } from 'react';

import { apiClient } from '../../api/client';
import logger from '../../utils/logger';
import {
  DENTIST_DOCUMENTS_STORAGE_KEY,
  upsertDentistVisitProtocol,
} from '../../utils/dentistryDocuments';
import {
  buildDentistVisitProtocolCard,
  buildDentistVisitProtocolSaveRequest,
  mapDentistVisitProtocolFromEmr,
  mergeDentistVisitProtocolCards,
} from '../../utils/dentistVisitProtocolBridge';
import { getErrorMessage } from '../../utils/type-guards';
import notify from '../../services/notify';
import { dentistCache, loadStoredDentistDocuments, type SelectedPatient } from './dentistContracts';

/**
 * PR-UI-15-4: the dentist visit-protocol lifecycle extracted verbatim from
 * pages/DentistPanelUnified.tsx (registrar/cashier decomposition precedent).
 *
 * Owns:
 *  - savedVisitProtocols state + the localStorage documents sync effect
 *  - loadDentistVisitProtocolsForPatient — GET /v2/emr/patient/{id} + per-visit
 *    GET /v2/emr/{visitId} hydration (module-cached, BS-42 invalidated)
 *  - loadDentistVisitProtocolByVisitId — GET /v2/emr/{visitId} (404-tolerant)
 *  - persistVisitProtocol — POST /v2/emr/{visitId} with local-cache fallback
 *  - reopenVisitProtocol — rehydrate a saved protocol into the visit screen
 *  - the hydrate-from-EMR effect on selectedPatient change
 *
 * This is the AC #4 (единый EMR) surface: every protocol read/write goes
 * through the EMR v2 API — pinned by DentistPanel.contract guards.
 */
export function useDentistVisitProtocols({
  tI18n,
  selectedPatient,
  setSelectedPatient,
  setShowVisitProtocol,
}: {
  tI18n: (key: string, params?: Record<string, unknown>) => string;
  selectedPatient: SelectedPatient | null;
  setSelectedPatient: React.Dispatch<React.SetStateAction<SelectedPatient | null>>;
  setShowVisitProtocol: (open: boolean) => void;
}) {
  const [savedVisitProtocols, setSavedVisitProtocols] = useState<Record<string, unknown>[]>(
    () => loadStoredDentistDocuments().visitProtocols
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(
        DENTIST_DOCUMENTS_STORAGE_KEY,
        JSON.stringify({ visitProtocols: savedVisitProtocols })
      );
    } catch (error: unknown) {
      logger.warn('[Dentist] Не удалось сохранить локальные протоколы визита:', error);
    }
  }, [savedVisitProtocols]);

  const loadDentistVisitProtocolsForPatient = useCallback(async (patient: SelectedPatient | Record<string, unknown> | null) => {
    const patientRecord = (patient ?? {}) as Record<string, unknown>;
    const nestedPatient = patientRecord.patient as { id?: string | number; [k: string]: unknown } | undefined;
    const patientId = nestedPatient?.id || patientRecord.patient_id || patientRecord.id || null;
    if (!patientId) {
      return [];
    }

    const cacheKey = String(patientId);
    const cachedProtocols = dentistCache.visitProtocolsCache.get(cacheKey);
    if (cachedProtocols) {
      return cachedProtocols;
    }

    const inFlightProtocols = dentistCache.visitProtocolsLoadPromises.get(cacheKey);
    if (inFlightProtocols) {
      return inFlightProtocols;
    }

    logger.info('[Dentist] Загружаю протоколы визитов из EMR v2', {
      patientId,
      patientName: patientRecord.patient_name as string || patientRecord.patient_fio as string || patientRecord.name as string || 'Пациент',
    });

    const loadPromise = (async () => {
      try {
        const response = await apiClient.get(`/v2/emr/patient/${patientId}`, {
          params: { limit: 20 },
          silent: true,
        } as Record<string, unknown>);

        const summaries: Record<string, unknown>[] = Array.isArray(response.data) ? response.data : [];
        const records = await Promise.all(
          summaries.map(async (summary) => {
            try {
              const emrResponse = await apiClient.get(`/v2/emr/${summary.visit_id}`, {
                silent: true,
                validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
              } as Record<string, unknown>);

              if (emrResponse.status === 404) {
                return null;
              }

              const protocolRecord = mapDentistVisitProtocolFromEmr(
                emrResponse.data,
                patient as Record<string, unknown> | null,
              );

              if (!protocolRecord) {
                return null;
              }

              return protocolRecord;
            } catch (error: unknown) {
              logger.warn('[Dentist] Не удалось загрузить EMR визита для протокола', {
                patientId,
                visitId: summary.visit_id,
                error: getErrorMessage(error) || error,
              });
              return null;
            }
          })
        );

        const filteredRecords = records.filter((r): r is Record<string, unknown> => Boolean(r));
        dentistCache.visitProtocolsCache.set(cacheKey, filteredRecords);
        return filteredRecords;
      } catch (error: unknown) {
        dentistCache.visitProtocolsCache.delete(cacheKey);
        throw error;
      } finally {
        dentistCache.visitProtocolsLoadPromises.delete(cacheKey);
      }
    })();

    dentistCache.visitProtocolsLoadPromises.set(cacheKey, loadPromise);
    return loadPromise;
  }, []);

  const loadDentistVisitProtocolByVisitId = useCallback(async (visitId: string | number | null | undefined, patient: SelectedPatient | Record<string, unknown> | null = null) => {
    if (!visitId) {
      return null;
    }

    try {
      const response = await apiClient.get(`/v2/emr/${visitId}`, {
        silent: true,
        validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
      } as Record<string, unknown>);

      if (response.status === 404) {
        return null;
      }

      const protocolRecord = mapDentistVisitProtocolFromEmr(response.data, patient as Record<string, unknown> | null);
      if (!protocolRecord) {
        return null;
      }

      logger.info('[Dentist] Протокол визита загружен из EMR v2', {
        visitId,
        emrId: response.data?.id,
        status: response.data?.status,
      });

      return protocolRecord;
    } catch (error: unknown) {
      logger.warn('[Dentist] Не удалось загрузить протокол визита из EMR v2', {
        visitId,
        error: getErrorMessage(error) || error,
      });
      return null;
    }
  }, []);

  const persistVisitProtocol = useCallback(async (patient: SelectedPatient | Record<string, unknown> | null, visitData: Record<string, unknown>) => {
    const patientRecord = (patient ?? {}) as Record<string, unknown>;
    if (!patientRecord.visit_id) {
      return;
    }

    const nestedPatient = patientRecord.patient as { id?: string | number; [k: string]: unknown } | undefined;
    const patientId = nestedPatient?.id || patientRecord.patient_id || patientRecord.id || null;
    const patientName = (patientRecord.patient_name as string) || (patientRecord.patient_fio as string) || (patientRecord.name as string) || tI18n('dental.dental_panel_patient_default');
    const localRecord = buildDentistVisitProtocolCard(patient, visitData, {
      source: 'local_cache',
    });

    try {
      const payload = buildDentistVisitProtocolSaveRequest(patient, visitData, {
        isDraft: true,
        rowVersion: 0,
      });
      logger.info('[Dentist] Сохраняю протокол визита в EMR v2', {
        visitId: patientRecord.visit_id,
        patientId,
      });

      const response = await apiClient.post(`/v2/emr/${patientRecord.visit_id}`, payload);
      const backendRecord = mapDentistVisitProtocolFromEmr(response.data, patient as Record<string, unknown> | null) || localRecord;

      setSavedVisitProtocols((prev) => upsertDentistVisitProtocol(prev, backendRecord));
      return backendRecord;
    } catch (error: unknown) {
      logger.warn('[Dentist] Не удалось сохранить протокол визита в EMR v2, сохраняю локальный кеш', {
        visitId: patientRecord.visit_id,
        patientName,
        error: getErrorMessage(error) || error,
      });

      setSavedVisitProtocols((prev) => upsertDentistVisitProtocol(prev, localRecord));
      return localRecord;
    }
  }, [tI18n]);

  const reopenVisitProtocol = useCallback(async (protocolRecord: Record<string, unknown> | null) => {
    const backendProtocol = await loadDentistVisitProtocolByVisitId(protocolRecord?.visit_id as string | number | null | undefined, protocolRecord);

    if (!backendProtocol && !protocolRecord?.visitData) {
      notify.error(tI18n('dental.protocol_not_found'));
      return;
    }

    const selectedProtocol = (backendProtocol || protocolRecord) as Record<string, unknown>;
    setSelectedPatient({
      id: (selectedProtocol.patient_id as string | number | null) || (protocolRecord?.patient_id as string | number | null) || null,
      patient_id: (selectedProtocol.patient_id as string | number | null) || (protocolRecord?.patient_id as string | number | null) || null,
      patient_name: (selectedProtocol.patient_name as string) || (protocolRecord?.patient_name as string) || tI18n('dental.dental_panel_patient_default'),
      patient_fio: (selectedProtocol.patient_name as string) || (protocolRecord?.patient_name as string) || tI18n('dental.dental_panel_patient_default'),
      visit_id: (selectedProtocol.visit_id as string | number | null) || (protocolRecord?.visit_id as string | number | null) || null,
      visitData: (selectedProtocol.visitData as Record<string, unknown> | null) || (protocolRecord?.visitData as Record<string, unknown> | null) || null,
      source: (selectedProtocol.source as string) || (protocolRecord?.source as string) || 'reports',
    } as SelectedPatient);
    setShowVisitProtocol(true);
  }, [loadDentistVisitProtocolByVisitId, setSelectedPatient, setShowVisitProtocol, tI18n]);

  // Hydrate the local protocol history from EMR v2 when a patient is selected.
  useEffect(() => {
    const selectedPatientIdForProtocols =
      selectedPatient?.patient?.id || selectedPatient?.patient_id || selectedPatient?.id || null;

    if (!selectedPatientIdForProtocols) {
      return;
    }

    let cancelled = false;

    const hydrateDentistVisitProtocols = async () => {
      try {
        const backendProtocols = await loadDentistVisitProtocolsForPatient(selectedPatient);
        if (cancelled || backendProtocols.length === 0) {
          return;
        }

        setSavedVisitProtocols((prev) => mergeDentistVisitProtocolCards(prev, backendProtocols));
      } catch (error: unknown) {
        logger.warn('[Dentist] Не удалось синхронизировать историю протоколов из EMR v2', {
          patientId: selectedPatientIdForProtocols,
          error: getErrorMessage(error) || error,
        });
      }
    };

    hydrateDentistVisitProtocols();

    return () => {
      cancelled = true;
    };
  }, [loadDentistVisitProtocolsForPatient, selectedPatient]);

  return {
    savedVisitProtocols,
    setSavedVisitProtocols,
    loadDentistVisitProtocolsForPatient,
    loadDentistVisitProtocolByVisitId,
    persistVisitProtocol,
    reopenVisitProtocol,
  };
}
