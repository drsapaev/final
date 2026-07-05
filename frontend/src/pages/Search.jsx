import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { getVisit } from '../api/visits';
import {
  AppEmpty, AppError, Button,
} from '../components/ui/macos';
import { getRoleHomeRoute } from '../routing/routeSelectors.js';

const registrarHomeRoute = getRoleHomeRoute('registrar');

// Modern Search Page with Full Functionality
export default function Search() {
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
        } catch {
          // Visit not found by ID, try by patient_id
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
        } catch {
          // No visits for this patient
        }
      }

      // Strategy 2: Find patients matching query and get their visits
      if (patientsData.length > 0 && visitsData.length < 10) {
        const patientIds = patientsData.slice(0, 5).map(p => p.id);
        for (const patientId of patientIds) {
          try {
            const pvRes = await api.get(`/visits/visits?patient_id=${patientId}&limit=5`);
            if (Array.isArray(pvRes.data)) {
              const existingIds = new Set(visitsData.map(v => v.id));
              pvRes.data.forEach(v => {
                if (!existingIds.has(v.id)) {
                  visitsData.push(v);
                }
              });
            }
          } catch {
            // Skip on error
          }
        }
      }

      setVisits(visitsData);
    } catch {
      setError('Ошибка поиска. Попробуйте снова.');
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
      open: { bg: 'var(--mac-accent-bg)', color: 'var(--mac-accent)', label: 'Открыт' },
      waiting: { bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)', label: 'Ожидание' },
      in_progress: { bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)', label: 'В процессе' },
      in_visit: { bg: 'var(--mac-success-bg)', color: 'var(--mac-success)', label: 'На приёме' },
      completed: { bg: 'var(--mac-success-bg)', color: 'var(--mac-success)', label: 'Завершён' },
      closed: { bg: 'var(--mac-bg-secondary)', color: 'var(--mac-text-secondary)', label: 'Закрыт' },
      canceled: { bg: 'var(--mac-error-bg)', color: 'var(--mac-error)', label: 'Отменён' },
      paid: { bg: 'var(--mac-success-bg)', color: 'var(--mac-success)', label: 'Оплачен' },
    };
    return colors[status] || { bg: 'var(--mac-bg-secondary)', color: 'var(--mac-text-secondary)', label: status || '—' };
  };

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  // Get patient name from visits (we need to fetch it)
  const [patientNames, setPatientNames] = useState({});

  useEffect(() => {
    // Fetch patient names for visits
    const fetchPatientNames = async () => {
      const uniquePatientIds = [...new Set(visits.map(v => v.patient_id).filter(Boolean))];
      const namesMap = { ...patientNames };
      let hasUpdates = false;

      for (const pid of uniquePatientIds) {
        if (!namesMap[pid]) {
          try {
            const res = await api.get(`/patients/${pid}`);
            if (res.data) {
              namesMap[pid] = `${res.data.last_name || ''} ${res.data.first_name || ''} ${res.data.middle_name || ''}`.trim();
              hasUpdates = true;
            }
          } catch {
            namesMap[pid] = `Пациент #${pid}`;
            hasUpdates = true;
          }
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
          Глобальный поиск
        </h1>
        <p style={styles.subtitle}>
          Поиск пациентов, визитов и записей по ФИО, телефону, ID
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} style={styles.searchForm}>
        <div style={styles.searchBox}>
          <label htmlFor={searchInputId} style={styles.visuallyHidden}>
            Поиск пациентов и визитов
          </label>
          <input
            id={searchInputId}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите ФИО, телефон, ID пациента или номер визита..."
            style={styles.searchInput}
            aria-label="Поиск пациентов и визитов"
            aria-describedby={query.length > 0 && query.length < 2 ? searchHintId : undefined}
            autoFocus
          />
          <button
            type="submit"
            disabled={isSearchDisabled}
            aria-label={loading ? 'Поиск выполняется' : 'Искать пациентов и визиты'}
            aria-describedby={query.length > 0 && query.length < 2 ? searchHintId : undefined}
            style={{
              ...styles.searchButton,
              opacity: isSearchDisabled ? 0.6 : 1,
            }}
          >
            {loading ? (
              <span style={styles.spinner}>⏳</span>
            ) : (
              'Искать'
            )}
          </button>
        </div>
        {query.length > 0 && query.length < 2 && (
          <p id={searchHintId} style={styles.hint}>Введите минимум 2 символа для поиска</p>
        )}
      </form>

      {/* Error Message */}
      {error && (
        <AppError
          title="Ошибка поиска"
          description={error}
          action={
            <Button
              type="button"
              onClick={() => performSearch(query)}
              disabled={isSearchDisabled}
              loading={loading}
              size="small"
              variant="outline"
              aria-label="Повторить поиск с текущим запросом">
              Повторить поиск
            </Button>
          }
          style={styles.errorBox}
        />
      )}

      {/* Results Tabs */}
      {searchPerformed && (
        <div style={styles.tabs} role="group" aria-label="Фильтр результатов поиска">
          <button
            type="button"
            onClick={() => setActiveTab('all')}
            aria-pressed={activeTab === 'all'}
            aria-label="Показать все результаты поиска"
            style={{
              ...styles.tab,
              ...(activeTab === 'all' ? styles.tabActive : {}),
            }}
          >
            Все ({patients.length + visits.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('patients')}
            aria-pressed={activeTab === 'patients'}
            aria-label="Показать только пациентов"
            style={{
              ...styles.tab,
              ...(activeTab === 'patients' ? styles.tabActive : {}),
            }}
          >
            Пациенты ({patients.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('visits')}
            aria-pressed={activeTab === 'visits'}
            aria-label="Показать только визиты"
            style={{
              ...styles.tab,
              ...(activeTab === 'visits' ? styles.tabActive : {}),
            }}
          >
            Визиты ({visits.length})
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
              Пациенты
              <span style={styles.count}>{patients.length}</span>
            </h2>
            <div style={styles.grid}>
              {patients.map(patient => (
                <div
                  key={patient.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`Открыть пациента ${[patient.last_name, patient.first_name, patient.middle_name].filter(Boolean).join(' ') || `#${patient.id}`}`}
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
              ))}
            </div>
          </div>
        )}

        {/* Visits Section */}
        {showVisits && visits.length > 0 && (
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <span style={styles.sectionIcon}>📋</span>
              Визиты
              <span style={styles.count}>{visits.length}</span>
            </h2>
            <div style={styles.grid}>
              {visits.map(visit => {
                const statusInfo = getStatusColor(visit.status);
                return (
                  <div
                    key={visit.id}
                    role="button"
                    tabIndex={0}
                    aria-label={`Открыть визит #${visit.id} пациента ${patientNames[visit.patient_id] || `#${visit.patient_id}`}`}
                    onClick={() => goToVisit(visit)}
                    onKeyDown={(event) => handleActivationKeyDown(event, () => goToVisit(visit))}
                    style={styles.card}
                    onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                    onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                  >
                    <div style={styles.cardHeader}>
                      <span style={styles.visitId}>Визит #{visit.id}</span>
                      <span style={styles.cardArrow}>→</span>
                    </div>
                    <div style={styles.visitPatient}>
                      {patientNames[visit.patient_id] || `Пациент #${visit.patient_id}`}
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
            title="Ничего не найдено"
            description="Проверьте написание ФИО, телефон, ID пациента или номер визита и попробуйте снова."
            style={styles.noResults}
          />
        )}

        {/* Initial State */}
        {!searchPerformed && !loading && (
          <AppEmpty
            title="Начните поиск"
            description="Введите ФИО пациента, номер телефона, ID пациента или номер визита."
            action={
              <div style={styles.tips}>
                <div style={styles.tip}>
                  <strong>Примеры запросов:</strong>
                </div>
                <div style={styles.tip}>• «Иванов» — поиск по фамилии</div>
                <div style={styles.tip}>• «+998» — поиск по телефону</div>
                <div style={styles.tip}>• «428» — поиск по ID пациента или визита</div>
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
    padding: '24px',
    minHeight: '100vh',
    background: 'var(--mac-bg-secondary)',
  },
  header: {
    textAlign: 'center',
    marginBottom: 32,
  },
  title: {
    fontSize: 32,
    fontWeight: 700,
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
    fontWeight: 600,
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
    border: '1px solid #fecaca',
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
    fontWeight: 500,
    color: 'var(--mac-text-secondary)',
    backgroundColor: 'var(--mac-bg-primary)',
    border: '1px solid #e2e8f0',
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
    fontWeight: 600,
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
    fontWeight: 500,
    color: 'var(--mac-text-secondary)',
    backgroundColor: '#f1f5f9',
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
    border: '1px solid #e2e8f0',
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
    fontWeight: 600,
    color: 'var(--mac-accent-blue, #3b82f6)',
    backgroundColor: 'var(--mac-accent-bg)',
    padding: '4px 8px',
    borderRadius: 6,
  },
  visitId: {
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--mac-accent-purple)',
    backgroundColor: '#f5f3ff',
    padding: '4px 8px',
    borderRadius: 6,
  },
  cardArrow: {
    fontSize: 16,
    color: 'var(--mac-text-tertiary)',
    transition: 'transform 0.2s',
  },
  patientName: {
    fontSize: 16,
    fontWeight: 600,
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
    fontWeight: 500,
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
    fontWeight: 500,
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
    fontWeight: 600,
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
    fontWeight: 600,
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
    padding: '16px 24px',
    borderRadius: 12,
    border: '1px solid #e2e8f0',
  },
  tip: {
    fontSize: 14,
    color: 'var(--mac-text-secondary)',
    marginBottom: 4,
  },
};
