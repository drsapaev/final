/**
 * PR-UI-14-6: cashier search state (verbatim move from CashierPanel).
 *
 * Owns the search input state (initialized from a ?patientId= deep link),
 * the focus flag for the syntax-hint (UX Audit #2.4), the 500ms debounce,
 * and the URL patient-load effect (patient name replaces the raw
 * patient:ID query once fetched).
 */

import { useCallback, useEffect, useState } from 'react';

import { useLocation } from 'react-router-dom';
import { getPatient as fetchPatientById } from '../../api/patients';
import type { Patient } from '../../types/domain/clinic';
import tokenManager from '../../utils/tokenManager';
import logger from '../../utils/logger';
import { useDebouncedValue } from '../../hooks/useDebouncedCallback';

export const useCashierSearch = () => {
  const location = useLocation();

// ✅ Получаем patientId из URL для автоматического поиска
  const getPatientIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    const patientIdParam = params.get('patientId');
    return patientIdParam ? parseInt(patientIdParam, 10) : null;
  }, [location.search]);

  // Search state - инициализируем с patientId если есть
  const [query, setQuery] = useState(() => {
    const patientId = new URLSearchParams(window.location.search).get('patientId');
    return patientId ? `patient:${patientId}` : '';
  });
  // UX Audit #2.4: показывать подсказку с примерами синтаксиса поиска,
  // пока input в фокусе и запрос пустой.
  const [searchFocused, setSearchFocused] = useState(false);
  const debouncedQuery = useDebouncedValue(query, 500); // 500ms debounce

  // ✅ Эффект для загрузки пациента из URL
  useEffect(() => {
    const patientIdFromUrl = getPatientIdFromUrl();
    if (patientIdFromUrl && !query.includes(`patient:${patientIdFromUrl}`)) {
      // Загружаем данные пациента для поиска
      const loadPatientForSearch = async () => {
        try {
          // PR-53: migrated from raw fetch() to axios client
          // Wave G5: use api/patients.ts which returns domain Patient via mapper
          const token = tokenManager.getAccessToken();
          if (!token) return;

          const patientData: Patient = await fetchPatientById(patientIdFromUrl);
          const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim();
          setQuery(patientName);
          logger.info('[Cashier] Patient loaded from URL', { patientId: patientData?.id });
        } catch (error: unknown) {
          logger.error('[Cashier] Не удалось загрузить пациента:', error);
        }
      };
      loadPatientForSearch();
    }
  }, [location.search, getPatientIdFromUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    query,
    setQuery,
    searchFocused,
    setSearchFocused,
    debouncedQuery,
  };
};
