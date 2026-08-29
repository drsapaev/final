/**
 * Registrar Panel — URL/routing state (view + deep-link params).
 *
 * PR-UI-13-5: extracts the routing slice from RegistrarPanel.tsx (plan
 * §PR-UI-13 "separation of responsibilities without behavior change").
 *
 * Owns:
 * - activeTab + URL sync (?dept=..., R-02 shareable links / back button)
 * - currentView — canonical path-derived view (Phase 3: legacy ?view=/?tab=
 *   params are redirected to canonical paths below and never parsed here)
 * - legacy ?view=welcome|queue → /registrar/{view} replace-redirect (Phase 2)
 * - searchQuery (?q=) + statusFilter (?status=) memos
 * - patientIdFromUrl deep-link auto-search effect (UX Audit Registrar #1:
 *   getPatient() through the axios client — no raw fetch / manual headers)
 *
 * Verbatim port of the original panel code (effects keep their original
 * declaration order relative to the worklist data lifecycle, which is
 * wired after this hook in the panel).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useLocation, useNavigate } from 'react-router-dom';
import logger from '../../utils/logger';
import { getPatient } from '../../api/patients';
import type { HttpApiError } from '../../types/errors';
import { getViewFromPath } from './registrarNavigation';

export function useRegistrarRouting() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();

  // R-02 fix: activeTab синхронизирован с URL (?dept=...).
  // Раньше был useState(null) — F5 сбрасывал выбранное отделение.
  const [activeTab, setActiveTabRaw] = useState(() => searchParams.get('dept') || null);
  const setActiveTab = useCallback((tab: string | null) => {
    setActiveTabRaw(tab);
    // R-02: пишем в URL для shareable links + back button
    const params = new URLSearchParams(window.location.search);
    if (tab) {
      params.set('dept', tab);
    } else {
      params.delete('dept');
    }
    setSearchParams(params, { replace: true });
  }, [setSearchParams]);

  const currentView = useMemo(() => {
    // Phase 3: rely solely on canonical path-derived view.
    // Legacy ?view= and ?tab= params are auto-redirected to canonical paths
    // by the Phase 2 redirect useEffect below, so they never need to be
    // parsed here. The redirect preserves all other query params.
    return getViewFromPath(location.pathname);
  }, [location.pathname]);

  // ✅ Phase 2: redirect legacy ?view=welcome|queue to canonical paths
  // /registrar?view=welcome → /registrar/welcome
  // /registrar?view=queue   → /registrar/queue
  // Preserves all other query params (q, status, date, patientId, dept).
  // The redirect is replace-only (no history pollution) and runs once per
  // legacy-view occurrence.
  useEffect(() => {
    const legacyView = searchParams.get('view');
    if (legacyView !== 'welcome' && legacyView !== 'queue') return;
    // Only redirect when on the bare /registrar path (not already on a sub-path)
    if (location.pathname !== '/registrar') return;

    const params = new URLSearchParams(searchParams);
    params.delete('view');
    params.delete('tab');
    const qs = params.toString();
    const target = qs ? `/registrar/${legacyView}?${qs}` : `/registrar/${legacyView}`;
    navigate(target, { replace: true });
  }, [searchParams, location.pathname, navigate]);

  const searchQuery = useMemo(() => (searchParams.get('q') || '').toLowerCase(), [searchParams]);
  const statusFilter = useMemo(() => searchParams.get('status'), [searchParams]);

  // ✅ Получаем patientId из URL для автоматического поиска
  const patientIdFromUrl = useMemo(() => {
    const id = searchParams.get('patientId');
    return id ? parseInt(id, 10) : null;
  }, [searchParams]);

  // ✅ Эффект для автоматической загрузки пациента из URL
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      if (!patientIdFromUrl) return;

      try {
        // UX Audit Registrar #1: raw fetch() с ручным Authorization-хедером
        // заменён на getPatient() из api/patients.
        // Auth-token добавляется автоматически axios-interceptor'ом в api/client.js.
        // 401/403 обрабатываются интерсептором (redirect to login или refresh).
        const patientData = await getPatient(patientIdFromUrl);
        const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim();

        // Устанавливаем поисковый запрос с именем пациента
        setSearchParams((prev) => {
          const newParams = new URLSearchParams(prev);
          newParams.set('q', patientName);
          return newParams;
        });

        // UX Audit R-3.6: убрано логирование patientName (PII leak).
        logger.info('[Registrar] Загружен пациент из URL (patientId matched)');
      } catch (error: unknown) {
        // 404 — пациент не найден, не логируем как error.
        const status = (error as HttpApiError)?.response?.status;
        if (status !== 404) {
          logger.error('[Registrar] Не удалось загрузить пациента:', error);
        }
      }
    };

    loadPatientFromUrl();
  }, [patientIdFromUrl, setSearchParams]);

  return {
    searchParams,
    setSearchParams,
    location,
    navigate,
    activeTab,
    setActiveTab,
    currentView,
    searchQuery,
    statusFilter,
  };
}

export default useRegistrarRouting;
