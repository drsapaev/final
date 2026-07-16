// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { getVisit } from '../api/visits';
import logger from '../utils/logger';  // PR-38 / Medium-23: log instead of silent catch
import {
  AppEmpty, AppError, Button,
  Input } from '../components/ui/macos';
import { getRoleHomeRoute } from '../routing/routeSelectors.js';
import { useTranslation } from '../i18n/useTranslation';

const registrarHomeRoute = getRoleHomeRoute('registrar');

// Modern Search Page with Full Functionality
export default function Search() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [patients, setPatients] = useState([]);
  const [visits, setVisits] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('all'); // all, patients, visits
  const [searchPerformed, setSearchPerformed] = useState(false);

  // Debounced search
  const performSearch = useCallback(async (searchQuery) => {
    if (!searchQuery || searchQuery.trim().length < 2) {
      setPatients([]);
      setVisits([]);
      setSearchPerformed(false);
      return;
    }

    setLoading(true);
    setError(null);
    setSearchPerformed(true);

    try {
      // Search patients
      const patientsRes = await api.get(`/patients/?q=${encodeURIComponent(searchQuery)}&limit=30`);
      const patientsData = Array.isArray(patientsRes.data) ? patientsRes.data : [];
      setPatients(patientsData);

      // Search visits - try multiple strategies
      let visitsData = [];

      // Strategy 1: If query is a number, try to find visit by ID or patient_id
      if (/^\d+$/.test(searchQuery.trim())) {
        const visitId = parseInt(searchQuery.trim(), 10);

        // Try to get visit by ID directly
        try {
          const visitRes = await getVisit(visitId);
          if (visitRes?.visit) {
            visitsData = [visitRes.visit];
          }
        } catch (err) {
          // PR-38 / Medium-23: log the error instead of silently swallowing.
          // Visit not found by ID — we'll try by patient_id next.
          logger.warn('Search: getVisit failed, will try by patient_id', err?.message);
        }

        // Also get visits for patient with this ID
        try {
          const patientVisitsRes = await api.get(`/visits/visits?patient_id=${visitId}&limit=20`);
          if (Array.isArray(patientVisitsRes.data)) {
            // Merge without duplicates
            const existingIds = new Set(visitsData.map(v => v.id));
            patientVisitsRes.data.forEach(v => {
              if (!existingIds.has(v.id)) {
                visitsData.push(v);
              }
            });
          }
        } catch (err) {
          // PR-38 / Medium-23: log instead of silent catch.
          logger.warn('Search: patient visits fetch failed', err?.message);
        }
      }

      // Strategy 2: Find patients matching query and get their visits
      // PR-37 / P0-13: Replaced sequential for-loop with await api.get()
      // (up to 10 sequential HTTP round-trips) with Promise.all batched
      // in parallel. Network latency × 10 → network latency × 1.
      if (patientsData.length > 0 && visitsData.length < 10) {
        const patientIds = patientsData.slice(0, 5).map(p => p.id);
        const visitResults = await Promise.allSettled(
          patientIds.map(pid => api.get(`/visits/visits?patient_id=${pid}&limit=5`))
        );
        const existingIds = new Set(visitsData.map(v => v.id));
        for (const result of visitResults) {
          if (result.status === 'fulfilled' && Array.isArray(result.value.data)) {
            result.value.data.forEach(v => {
              if (!existingIds.has(v.id)) {
                visitsData.push(v);
              }
            });
          }
        }
      }

      setVisits(visitsData);
    } catch (err) {
      // PR-38 / Medium-23: log instead of silent catch.
      logger.error('Search: query failed', err?.message);
      setError(t('misc.srch_error_search_failed'));
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle search submit
  const handleSearch = (e) => {
    e?.preventDefault();
    performSearch(query);
  };

  // Navigate to patient - open registrar panel with wizard for this patient
  const goToPatient = (patient) => {
    // Open registrar panel with the patient pre-selected for new appointment
    const patientName = `${patient.last_name || ''} ${patient.first_name || ''} ${patient.middle_name || ''}`.trim();
    navigate(`${registrarHomeRoute}?action=new&patientId=${patient.id}&patientName=${encodeURIComponent(patientName)}`);
  };

  // Navigate to visit details in registrar panel
  const goToVisit = (visit) => {
    navigate(`${registrarHomeRoute}?visitId=${visit.id}&patientId=${visit.patient_id}`);
  };
  const handleActivationKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };

  // Get status badge color
  const getStatusColor = (status) => {
    const colors = {
      open: { bg: 'var(--mac-accent-bg)', color: 'var(--mac-accent)', label: t('misc.srch_status_open') },
      waiting: { bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)', label: t('misc.srch_status_waiting') },
      in_progress: { bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)', label: t('misc.srch_status_in_progress') },
      in_visit: { bg: 'var(--mac-success-bg)', color: 'var(--mac-success)', label: t('misc.srch_status_in_visit') },
      completed: { bg: 'var(--mac-success-bg)', color: 'var(--mac-success)', label: t('misc.srch_status_completed') },
      closed: { bg: 'var(--mac-bg-secondary)', color: 'var(--mac-text-secondary)', label: t('misc.srch_status_closed') },
      canceled: { bg: 'var(--mac-error-bg)', color: 'var(--mac-error)', label: t('misc.srch_status_canceled') },
      paid: { bg: 'var(--mac-success-bg)', color: 'var(--mac-success)', label: t('misc.srch_status_paid') },
    };
    return colors[status] || { bg: 'var(--mac-bg-secondary)', color: 'var(--mac-text-secondary)', label: status || '—' };
  };

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch (err) {
      // PR-38 / Medium-23: log instead of silent catch.
      logger.warn('Search: formatDate failed', err?.message);
      return dateStr;
    }
  };

  // Get patient name from visits (we need to fetch it)
  const [patientNames, setPatientNames] = useState({});

  useEffect(() => {
    // Fetch patient names for visits
    // PR-37 / P0-13: Replaced sequential for-loop with await api.get()
    // (up to N sequential HTTP round-trips where N = unique patient count)
    // with Promise.allSettled batched in parallel.
    const fetchPatientNames = async () => {
      const uniquePatientIds = [...new Set(visits.map(v => v.patient_id).filter(Boolean))];
      const namesMap = { ...patientNames };
      // Filter to IDs we haven't fetched yet
      const idsToFetch = uniquePatientIds.filter(pid => !namesMap[pid]);
      if (idsToFetch.length === 0) return;

      const results = await Promise.allSettled(
        idsToFetch.map(pid => api.get(`/patients/${pid}`).then(res => ({ pid, data: res.data })))
      );
      let hasUpdates = false;
      for (const result of results) {
        if (result.status === 'fulfilled' && result.value.data) {
          const { pid, data } = result.value;
          namesMap[pid] = `${data.last_name || ''} ${data.first_name || ''} ${data.middle_name || ''}`.trim();
          hasUpdates = true;
        } else if (result.status === 'rejected') {
          // Extract pid from the rejected promise's input — we know it was
          // one of idsToFetch. Use index to find which one failed.
          const idx = results.indexOf(result);
          const failedPid = idsToFetch[idx];
          namesMap[failedPid] = t('misc.srch_patient_fallback', { id: failedPid });
          hasUpdates = true;
        }
      }

      if (hasUpdates) {
        setPatientNames(namesMap);
      }
    };

    if (visits.length > 0) {
      fetchPatientNames();
    }
  }, [visits, patientNames]);

  // Filtered results based on active tab
  const showPatients = activeTab === 'all' || activeTab === 'patients';
  const showVisits = activeTab === 'all' || activeTab === 'visits';
  const searchInputId = 'global-search-query';
  const searchHintId = 'global-search-query-hint';
  const isSearchDisabled = loading || query.trim().length < 2;

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>
          <span style={styles.icon}>🔍</span>
          {t('misc.srch_title')}
        </h1>
        <p style={styles.subtitle}>
          {t('misc.srch_subtitle')}
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} style={styles.searchForm}>
        <div style={styles.searchBox}>
          <label htmlFor={searchInputId} style={styles.visuallyHidden}>
            {t('misc.srch_label_search')}
          </label>
          <Input
            id={searchInputId}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('misc.srch_input_placeholder')}
            style={styles.searchInput}
            aria-label={t('misc.srch_label_search')}
            aria-describedby={query.length > 0 && query.length < 2 ? searchHintId : undefined}
            autoFocus
          />
          <button
            type="submit"
            disabled={isSearchDisabled}
            aria-label={loading ? t('misc.srch_aria_search_in_progress') : t('misc.srch_aria_search_patients_visits')}
            aria-describedby={query.length > 0 && query.length < 2 ? searchHintId : undefined}
            style={{
              ...styles.searchButton,
              opacity: isSearchDisabled ? 0.6 : 1,
            }}
          >
            {loading ? (
              <span style={styles.spinner}>⏳</span>
            ) : (
              t('misc.srch_btn_search')
            )}
          </button>
        </div>
        {query.length > 0 && query.length < 2 && (
          <p id={searchHintId} style={styles.hint}>{t('misc.srch_hint_min_chars')}</p>
        )}
      </form>

      {/* Error Message */}
      {error && (
        <AppError
          title={t('misc.srch_error_title')}
          description={error}
          action={
            <Button
              type="button"
              onClick={() => performSearch(query)}
              disabled={isSearchDisabled}
              loading={loading}
              size="small"
              variant="outline"
              aria-label={t('misc.srch_aria_retry_search')}>
              {t('misc.srch_btn_retry')}
            </Button>
          }
          style={styles.errorBox}
        />
      )}

      {/* Results Tabs */}
      {searchPerformed && (
        <div style={styles.tabs} role="group" aria-label={t('misc.srch_aria_filter_group')}>
          <button
            type="button"
            onClick={() => setActiveTab('all')}
            aria-pressed={activeTab === 'all'}
            aria-label={t('misc.srch_aria_show_all_results')}
            style={{
              ...styles.tab,
              ...(activeTab === 'all' ? styles.tabActive : {}),
            }}
          >
            {t('misc.srch_tab_all', { count: patients.length + visits.length })}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('patients')}
            aria-pressed={activeTab === 'patients'}
            aria-label={t('misc.srch_aria_show_patients_only')}
            style={{
              ...styles.tab,
              ...(activeTab === 'patients' ? styles.tabActive : {}),
            }}
          >
            {t('misc.srch_tab_patients', { count: patients.length })}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('visits')}
            aria-pressed={activeTab === 'visits'}
            aria-label={t('misc.srch_aria_show_visits_only')}
            style={{
              ...styles.tab,
              ...(activeTab === 'visits' ? styles.tabActive : {}),
            }}
          >
            {t('misc.srch_tab_visits', { count: visits.length })}
          </button>
        </div>
      )}

      {/* Results */}
      <div style={styles.results}>
        {/* Patients Section */}
        {showPatients && patients.length > 0 && (
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <span style={styles.sectionIcon}>👤</span>
              {t('misc.srch_section_patients')}
              <span style={styles.count}>{patients.length}</span>
            </h2>
            <div style={styles.grid}>
              {patients.map(patient => {
                const patientDisplay = [patient.last_name, patient.first_name, patient.middle_name].filter(Boolean).join(' ') || `#${patient.id}`;
                return (
                <div
                  key={patient.id}
                  role="button"
                  tabIndex={0}
                  aria-label={t('misc.srch_aria_open_patient', { name: patientDisplay })}
                  onClick={() => goToPatient(patient)}
                  onKeyDown={(event) => handleActivationKeyDown(event, () => goToPatient(patient))}
                  style={styles.card}
                  onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                  onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                >
                  <div style={styles.cardHeader}>
                    <span style={styles.patientId}>#{patient.id}</span>
                    <span style={styles.cardArrow}>→</span>
                  </div>
                  <div style={styles.patientName}>
                    {patient.last_name} {patient.first_name} {patient.middle_name || ''}
                  </div>
                  <div style={styles.patientInfo}>
                    {patient.phone && (
                      <span style={styles.infoItem}>
                        📞 {patient.phone}
                      </span>
                    )}
                    {patient.birth_date && (
                      <span style={styles.infoItem}>
                        🎂 {formatDate(patient.birth_date)}
                      </span>
                    )}
                  </div>
                </div>
              );})}
            </div>
          </div>
        )}

        {/* Visits Section */}
        {showVisits && visits.length > 0 && (
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <span style={styles.sectionIcon}>📋</span>
              {t('misc.srch_section_visits')}
              <span style={styles.count}>{visits.length}</span>
            </h2>
            <div style={styles.grid}>
              {visits.map(visit => {
                const statusInfo = getStatusColor(visit.status);
                const visitPatientName = patientNames[visit.patient_id] || t('misc.srch_visit_patient_fallback', { patientId: visit.patient_id });
                return (
                  <div
                    key={visit.id}
                    role="button"
                    tabIndex={0}
                    aria-label={t('misc.srch_aria_open_visit', { visitId: visit.id, patientName: visitPatientName })}
                    onClick={() => goToVisit(visit)}
                    onKeyDown={(event) => handleActivationKeyDown(event, () => goToVisit(visit))}
                    style={styles.card}
                    onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                    onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                  >
                    <div style={styles.cardHeader}>
                      <span style={styles.visitId}>{t('misc.srch_visit_id', { visitId: visit.id })}</span>
                      <span style={styles.cardArrow}>→</span>
                    </div>
                    <div style={styles.visitPatient}>
                      {visitPatientName}
                    </div>
                    <div style={styles.visitMeta}>
                      <span
                        style={{
                          ...styles.statusBadge,
                          backgroundColor: statusInfo.bg,
                          color: statusInfo.color,
                        }}
                      >
                        {statusInfo.label}
                      </span>
                      <span style={styles.visitDate}>
                        📅 {formatDate(visit.created_at || visit.planned_date)}
                      </span>
                    </div>
                    {visit.notes && (
                      <div style={styles.visitNotes}>
                        💬 {visit.notes.substring(0, 50)}{visit.notes.length > 50 ? '...' : ''}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* No Results */}
        {searchPerformed && !loading && patients.length === 0 && visits.length === 0 && (
          <AppEmpty
            title={t('misc.srch_no_results_title')}
            description={t('misc.srch_no_results_description')}
            style={styles.noResults}
          />
        )}

        {/* Initial State */}
        {!searchPerformed && !loading && (
          <AppEmpty
            title={t('misc.srch_initial_title')}
            description={t('misc.srch_initial_description')}
            action={
              <div style={styles.tips}>
                <div style={styles.tip}>
                  <strong>{t('misc.srch_examples_title')}</strong>
                </div>
                <div style={styles.tip}>{t('misc.srch_example_name')}</div>
                <div style={styles.tip}>{t('misc.srch_example_phone')}</div>
                <div style={styles.tip}>{t('misc.srch_example_id')}</div>
              </div>
            }
            style={styles.initialState}
          />
        )}
      </div>
    </div >
  );
}

// Styles
const styles = {
  container: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: 'var(--mac-spacing-6)',
    minHeight: '100vh',
    background: 'var(--mac-bg-secondary)',
  },
  header: {
    textAlign: 'center',
    marginBottom: 32,
  },
  title: {
    fontSize: 32,
    fontWeight: 'var(--mac-font-weight-bold)',
    color: 'var(--mac-text-primary)',
    margin: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  icon: {
    fontSize: 36,
  },
  subtitle: {
    fontSize: 16,
    color: 'var(--mac-text-secondary)',
    marginTop: 8,
  },
  searchForm: {
    marginBottom: 24,
  },
  searchBox: {
    display: 'flex',
    gap: 12,
    maxWidth: 800,
    margin: '0 auto',
  },
  visuallyHidden: {
    position: 'absolute',
    width: 1,
    height: 1,
    padding: 0,
    margin: -1,
    overflow: 'hidden',
    clip: 'rect(0, 0, 0, 0)',
    whiteSpace: 'nowrap',
    border: 0,
  },
  searchInput: {
    flex: 1,
    padding: '16px 20px',
    fontSize: 16,
    border: '2px solid var(--mac-border)',
    borderRadius: 12,
    outline: 'none',
    transition: 'all 0.2s',
    backgroundColor: 'var(--mac-bg-primary)',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  },
  searchButton: {
    padding: '16px 32px',
    fontSize: 16,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-bg-primary)',
    background: 'var(--mac-accent-blue)',
    border: 'none',
    borderRadius: 12,
    cursor: 'pointer',
    transition: 'all 0.2s',
    boxShadow: '0 4px 6px -1px rgba(59, 130, 246, 0.4)',
  },
  spinner: {
    animation: 'spin 1s linear infinite',
  },
  hint: {
    textAlign: 'center',
    color: 'var(--mac-text-tertiary)',
    fontSize: 14,
    marginTop: 8,
  },
  errorBox: {
    maxWidth: 800,
    margin: '0 auto 24px',
    padding: '16px 20px',
    backgroundColor: 'var(--mac-error-bg)',
    color: 'var(--mac-error)',
    borderRadius: 12,
    border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))',
  },
  tabs: {
    display: 'flex',
    gap: 8,
    justifyContent: 'center',
    marginBottom: 24,
    flexWrap: 'wrap',
  },
  tab: {
    padding: '10px 20px',
    fontSize: 14,
    fontWeight: 'var(--mac-font-weight-medium)',
    color: 'var(--mac-text-secondary)',
    backgroundColor: 'var(--mac-bg-primary)',
    border: '1px solid var(--mac-border)',
    borderRadius: 8,
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  tabActive: {
    color: 'var(--mac-bg-primary)',
    backgroundColor: 'var(--mac-accent-blue, #3b82f6)',
    borderColor: 'var(--mac-accent-blue, #3b82f6)',
  },
  results: {
    maxWidth: 1000,
    margin: '0 auto',
  },
  section: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    marginBottom: 16,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  sectionIcon: {
    fontSize: 24,
  },
  count: {
    fontSize: 14,
    fontWeight: 'var(--mac-font-weight-medium)',
    color: 'var(--mac-text-secondary)',
    backgroundColor: 'var(--mac-bg-tertiary)',
    padding: '4px 10px',
    borderRadius: 12,
    marginLeft: 8,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: 16,
  },
  card: {
    padding: 20,
    backgroundColor: 'var(--mac-bg-primary)',
    borderRadius: 12,
    border: '1px solid var(--mac-border)',
    cursor: 'pointer',
    transition: 'all 0.2s',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  patientId: {
    fontSize: 12,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-accent-blue, #3b82f6)',
    backgroundColor: 'var(--mac-accent-bg)',
    padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
    borderRadius: 6,
  },
  visitId: {
    fontSize: 12,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-accent-purple)',
    backgroundColor: '#f5f3ff',
    padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
    borderRadius: 6,
  },
  cardArrow: {
    fontSize: 16,
    color: 'var(--mac-text-tertiary)',
    transition: 'transform 0.2s',
  },
  patientName: {
    fontSize: 16,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    marginBottom: 8,
  },
  patientInfo: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 12,
  },
  infoItem: {
    fontSize: 13,
    color: 'var(--mac-text-secondary)',
  },
  visitPatient: {
    fontSize: 15,
    fontWeight: 'var(--mac-font-weight-medium)',
    color: 'var(--mac-text-primary)',
    marginBottom: 10,
  },
  visitMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap',
  },
  statusBadge: {
    fontSize: 12,
    fontWeight: 'var(--mac-font-weight-medium)',
    padding: '4px 10px',
    borderRadius: 6,
  },
  visitDate: {
    fontSize: 13,
    color: 'var(--mac-text-secondary)',
  },
  visitNotes: {
    fontSize: 13,
    color: 'var(--mac-text-secondary)',
    marginTop: 8,
    fontStyle: 'italic',
  },
  noResults: {
    textAlign: 'center',
    padding: '60px 20px',
  },
  noResultsIcon: {
    fontSize: 48,
    marginBottom: 16,
    opacity: 0.5,
  },
  noResultsText: {
    fontSize: 20,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-secondary)',
    marginBottom: 8,
  },
  noResultsHint: {
    fontSize: 14,
    color: 'var(--mac-text-tertiary)',
  },
  initialState: {
    textAlign: 'center',
    padding: '60px 20px',
  },
  initialIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  initialText: {
    fontSize: 20,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-secondary)',
    marginBottom: 8,
  },
  initialHint: {
    fontSize: 14,
    color: 'var(--mac-text-tertiary)',
    marginBottom: 24,
  },
  tips: {
    display: 'inline-block',
    textAlign: 'left',
    backgroundColor: 'var(--mac-bg-secondary)',
    padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
    borderRadius: 12,
    border: '1px solid var(--mac-border)',
  },
  tip: {
    fontSize: 14,
    color: 'var(--mac-text-secondary)',
    marginBottom: 4,
  },
};
