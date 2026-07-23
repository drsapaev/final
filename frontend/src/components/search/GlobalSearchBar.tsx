
/**
 * GlobalSearchBar - macOS-style global search component
 * Aggregated search across patients, visits, and lab results
 */
import { useState, useEffect, useRef, useCallback, type CSSProperties } from 'react';
import ReactDOM from 'react-dom';
import { generatePath, useNavigate } from 'react-router-dom';
import { api } from '../../api';
import auth from '../../stores/auth';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { getCanonicalRouteById, getRoleHomeRoute } from '../../routing/routeSelectors';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

const patientSearchRouteByRole = {
  registrar: getRoleHomeRoute('registrar'),
  receptionist: getRoleHomeRoute('registrar'),
  cardio: getRoleHomeRoute('cardio'),
  derma: getRoleHomeRoute('derma'),
  dentist: getRoleHomeRoute('dentist'),
  doctor: getRoleHomeRoute('doctor'),
  lab: getRoleHomeRoute('lab'),
  cashier: getRoleHomeRoute('cashier'),
  admin: getRoleHomeRoute('admin'),
};
const clinicalPickupPath = getCanonicalRouteById('clinical-pickup')?.path || '/clinical/pickup/:patientId';

function routeWithQuery(path, params) {
  const searchParams = new URLSearchParams(params);
  return `${path}?${searchParams.toString()}`;
}

function patientPickupRoute(patientId) {
  return generatePath(clinicalPickupPath, { patientId });
}

// Debounce hook
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

export default function GlobalSearchBar({ className = '' }) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const dropdownRef = useRef(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });

  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState({ patients: [], visits: [], labResults: [] });
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const debouncedQuery = useDebounce(query, 300);

  // Get user role for navigation
  const getUserRole = () => {
    const st = auth.getState();
    const profile = (st as Record<string, any>).profile || (st as Record<string, any>).user || {};
    return String(profile?.role || profile?.role_name || '').toLowerCase();
  };

  // Search API call
  const performSearch = useCallback(async (searchQuery) => {
    if (searchQuery.length < 2) {
      setResults({ patients: [], visits: [], labResults: [] });
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.get('/global-search', { params: { q: searchQuery, limit: 5 } });
      setResults(response.data);
    } catch (error) {
      logger.error('Search error:', error);
      setResults({ patients: [], visits: [], labResults: [] });
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Trigger search on debounced query change
  useEffect(() => {
    if (debouncedQuery) {
      performSearch(debouncedQuery);
      setIsOpen(true);
    } else {
      setResults({ patients: [], visits: [], labResults: [] });
      setIsOpen(false);
    }
  }, [debouncedQuery, performSearch]);

  // Global keyboard shortcut (Ctrl+K / Cmd+K)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        setIsOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target) &&
      dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Update dropdown position when open
  useEffect(() => {
    if (isOpen && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + 4,
        left: rect.left,
        width: Math.max(rect.width, 380)
      });
    }
  }, [isOpen]);

  // Get all items as flat list for keyboard navigation
  const getAllItems = () => {
    const items = [];
    results.patients.forEach((p) => items.push({ type: 'patient', data: p }));
    results.visits.forEach((v) => items.push({ type: 'visit', data: v }));
    results.labResults.forEach((l) => items.push({ type: 'lab', data: l }));
    return items;
  };

  // Handle keyboard navigation
  const handleKeyDown = (e) => {
    const items = getAllItems();

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, items.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && items[selectedIndex]) {
          handleItemClick(items[selectedIndex].type, items[selectedIndex].data);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        // Don't clear text, just close dropdown
        inputRef.current?.blur();
        break;
    }
  };

  // Highlight matching text









  // Handle item click with role-based navigation
  const handleItemClick = (type, item) => {
    const role = getUserRole();

    // Audit logging - log click event
    try {
      api.post('/global-search/log-click', {
        opened_type: type,
        opened_id: item.id,
        query: query
      });
    } catch (e) {
      // Don't block navigation if logging fails
      logger.error('Audit log error:', e);
    }

    setIsOpen(false);
    setQuery('');

    switch (type) {
      case 'patient':
        // Role-based navigation for patients
        // All panels now support ?patientId parameter
        if (patientSearchRouteByRole[role]) {
          navigate(routeWithQuery(patientSearchRouteByRole[role], { patientId: item.id }));
        } else {
          // Fallback for any other role
          navigate(patientPickupRoute(item.id));
        }
        break;
      case 'visit':
        if (role === 'doctor') {
          navigate(routeWithQuery(patientSearchRouteByRole.doctor, { visitId: item.id }));
        } else {
          navigate(routeWithQuery(patientSearchRouteByRole.registrar, { visitId: item.id, patientId: item.patient_id }));
        }
        break;
      case 'lab':
        navigate(routeWithQuery(patientPickupRoute(item.patient_id), { tab: 'lab', orderId: item.id }));
        break;
    }
  };

  const hasResults = results.patients.length > 0 || results.visits.length > 0 || results.labResults.length > 0;
  const listboxId = 'global-search-results';
  const activeOptionId = selectedIndex >= 0 ? `global-search-option-${selectedIndex}` : undefined;
  const searchStatus = isLoading
    ? t('misc.gsb_poisk')
    : query.length < 2
      ? t('misc.gsb_nachnite_vvod_minimum_2_simv')
      : hasResults
        ? t('misc.gsb_rezultaty_poiska_dostupny')
        : t('misc.gsb_nichego_ne_naydeno');

  const handleResultItemKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };

  // Styles
  const styles = {
    container: {
      position: 'relative',
      width: '100%',
      maxWidth: '400px'
    },
    inputWrapper: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center'
    },
    input: {
      width: '100%',
      padding: '8px 12px 8px 36px',
      fontSize: 'var(--mac-font-size-base)',
      border: '1px solid var(--mac-border, #d1d5db)',
      borderRadius: 'var(--mac-radius-md)',
      background: 'var(--mac-bg-secondary, #f8fafc)',
      color: 'var(--mac-text-primary, #1e293b)',
      outline: 'none',
      transition: 'all 0.2s ease'
    },
    searchIcon: {
      position: 'absolute',
      left: '12px',
      top: '50%',
      transform: 'translateY(-50%)',
      color: 'var(--mac-text-tertiary, #94a3b8)',
      pointerEvents: 'none'
    },
    shortcut: {
      position: 'absolute',
      right: '12px',
      top: '50%',
      transform: 'translateY(-50%)',
      fontSize: 'var(--mac-font-size-xs)',
      color: 'var(--mac-text-tertiary, #94a3b8)',
      background: 'var(--mac-bg-tertiary, #e2e8f0)',
      padding: '2px 6px',
      borderRadius: 'var(--mac-radius-sm)',
      pointerEvents: 'none'
    },
    dropdown: {
      position: 'fixed',
      top: `${dropdownPos.top}px`,
      left: `${dropdownPos.left}px`,
      width: `${dropdownPos.width}px`,
      background: 'var(--mac-bg-primary, white)',
      border: '1px solid var(--mac-border, #e2e8f0)',
      borderRadius: 'var(--mac-radius-lg)',
      boxShadow: '0 10px 40px rgba(0,0,0,0.25)',
      zIndex: 2147483647,
      maxHeight: '400px',
      overflowY: 'auto'
    },
    section: {
      padding: 'var(--mac-spacing-2) 0',
      borderBottom: '1px solid var(--mac-separator, #e2e8f0)'
    },
    sectionTitle: {
      padding: '4px 12px',
      fontSize: 'var(--mac-font-size-xs)',
      fontWeight: 'var(--mac-font-weight-semibold)',
      color: 'var(--mac-text-tertiary, #64748b)',
      textTransform: 'uppercase',
      letterSpacing: '0.5px'
    },
    item: {
      padding: '10px 12px',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      transition: 'background 0.15s ease'
    },
    itemSelected: {
      background: 'var(--mac-accent-blue, #3b82f6)',
      color: 'white'
    },
    itemIcon: {
      fontSize: 'var(--mac-font-size-lg)',
      width: '24px',
      textAlign: 'center'
    },
    itemContent: {
      flex: 1,
      minWidth: 0
    },
    itemTitle: {
      fontSize: 'var(--mac-font-size-base)',
      fontWeight: 'var(--mac-font-weight-medium)',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    },
    itemSubtitle: {
      fontSize: 'var(--mac-font-size-xs)',
      opacity: 0.7,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    },
    loading: {
      padding: 'var(--mac-spacing-5)',
      textAlign: 'center',
      color: 'var(--mac-text-tertiary, #64748b)'
    },
    noResults: {
      padding: 'var(--mac-spacing-5)',
      textAlign: 'center',
      color: 'var(--mac-text-tertiary, #64748b)'
    },
    srOnly: {
      position: 'absolute',
      width: '1px',
      height: '1px',
      padding: 0,
      margin: '-1px',
      overflow: 'hidden',
      clip: 'rect(0, 0, 0, 0)',
      whiteSpace: 'nowrap',
      border: 0
    }
  };

  let flatIndex = -1;

  return (
    <div style={styles.container as CSSProperties} className={className} ref={containerRef}>
            <div style={styles.inputWrapper as CSSProperties}>
                <span style={styles.searchIcon as CSSProperties}>🔍</span>
                <Input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setQuery(e.target.value)}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={t('misc.gsb_poisk_patsientov_vizitov')}
          aria-label={t('misc.gsb_globalnyy_poisk_patsientov_v')}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-activedescendant={activeOptionId}
          style={styles.input as CSSProperties} />

                <span style={styles.shortcut as CSSProperties}>⌘K</span>
                <span style={styles.srOnly as CSSProperties} role="status" aria-live="polite">{searchStatus}</span>
            </div>

            {isOpen && ReactDOM.createPortal(
        <div
          id={listboxId}
          role="listbox"
          aria-label={t('misc.gsb_rezultaty_globalnogo_poiska')}
          style={styles.dropdown as CSSProperties}
          ref={dropdownRef}>
                    {isLoading &&
          <div style={styles.loading as CSSProperties}>{t('misc.gsb_poisk_2')}</div>
          }

                    {!isLoading && query.length < 2 &&
          <div style={styles.noResults as CSSProperties}>{t('misc.gsb_nachnite_vvod_minimum_2_simv_2')}</div>
          }

                    {!isLoading && !hasResults && query.length >= 2 &&
          <div style={styles.noResults as CSSProperties}>{t('misc.gsb_nichego_ne_naydeno_2')}</div>
          }

                    {!isLoading && hasResults &&
          <>
                            {/* Patients */}
                            {results.patients.length > 0 &&
            <div style={styles.section as CSSProperties}>
                                    <div style={styles.sectionTitle as CSSProperties}>{t('misc.gsb_patsienty')}</div>
                                    {results.patients.map((p) => {
                flatIndex++;
                const itemIndex = flatIndex;
                const isSelected = itemIndex === selectedIndex;
                return (
                  <div
                    key={`patient-${p.id}`}
                    id={`global-search-option-${itemIndex}`}
                    role="option"
                    aria-selected={isSelected}
                    tabIndex={0}
                    style={{ ...styles.item, ...(isSelected ? styles.itemSelected : {}) } as CSSProperties}
                    onClick={() => handleItemClick('patient', p)}
                    onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleResultItemKeyDown(event, () => handleItemClick('patient', p))}
                    onMouseEnter={() => setSelectedIndex(itemIndex)}>
                    
                                                <span style={styles.itemIcon as CSSProperties}>👤</span>
                                                <div style={styles.itemContent as CSSProperties}>
                                                    <div style={styles.itemTitle as CSSProperties}>
                                                        {p.last_name} {p.first_name} {p.middle_name || ''}
                                                    </div>
                                                    <div style={styles.itemSubtitle as CSSProperties}>
                                                        #{p.id} {p.phone && `• ${p.phone}`}
                                                    </div>
                                                </div>
                                            </div>);

              })}
                                </div>
            }

                            {/* Visits */}
                            {results.visits.length > 0 &&
            <div style={styles.section as CSSProperties}>
                                    <div style={styles.sectionTitle as CSSProperties}>{t('misc.gsb_vizity')}</div>
                                    {results.visits.map((v) => {
                flatIndex++;
                const itemIndex = flatIndex;
                const isSelected = itemIndex === selectedIndex;
                return (
                  <div
                    key={`visit-${v.id}`}
                    id={`global-search-option-${itemIndex}`}
                    role="option"
                    aria-selected={isSelected}
                    tabIndex={0}
                    style={{ ...styles.item, ...(isSelected ? styles.itemSelected : {}) } as CSSProperties}
                    onClick={() => handleItemClick('visit', v)}
                    onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleResultItemKeyDown(event, () => handleItemClick('visit', v))}
                    onMouseEnter={() => setSelectedIndex(itemIndex)}>
                    
                                                <span style={styles.itemIcon as CSSProperties}>📋</span>
                                                <div style={styles.itemContent as CSSProperties}>
                                                    <div style={styles.itemTitle as CSSProperties}>
                                                        {v.patient_name || t('misc.gsb_vizit_v_id', { id: v.id })}
                                                    </div>
                                                    <div style={styles.itemSubtitle as CSSProperties}>
                                                        {v.planned_date} • {v.status || t('misc.gsb_net_statusa')}
                                                    </div>
                                                </div>
                                            </div>);

              })}
                                </div>
            }

                            {/* Lab Results */}
                            {results.labResults.length > 0 &&
            <div style={{ ...styles.section, borderBottom: 'none' } as CSSProperties}>
                                    <div style={styles.sectionTitle as CSSProperties}>{t('misc.gsb_analizy')}</div>
                                    {results.labResults.map((l) => {
                flatIndex++;
                const itemIndex = flatIndex;
                const isSelected = itemIndex === selectedIndex;
                const statusIcon = l.status === 'done' ? '🟢' : l.status === 'in_progress' ? '🟡' : '⚪';
                return (
                  <div
                    key={`lab-${l.id}`}
                    id={`global-search-option-${itemIndex}`}
                    role="option"
                    aria-selected={isSelected}
                    tabIndex={0}
                    style={{ ...styles.item, ...(isSelected ? styles.itemSelected : {}) } as CSSProperties}
                    onClick={() => handleItemClick('lab', l)}
                    onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleResultItemKeyDown(event, () => handleItemClick('lab', l))}
                    onMouseEnter={() => setSelectedIndex(itemIndex)}>
                    
                                                <span style={styles.itemIcon as CSSProperties}>{statusIcon}</span>
                                                <div style={styles.itemContent as CSSProperties}>
                                                    <div style={styles.itemTitle as CSSProperties}>
                                                        {l.patient_name || t('misc.gsb_zakaz_l_id', { id: l.id })}
                                                    </div>
                                                    <div style={styles.itemSubtitle as CSSProperties}>
                                                        {l.test_type || t('misc.gsb_laboratornyy_analiz')} • {l.status}
                                                    </div>
                                                </div>
                                            </div>);

              })}
                                </div>
            }
                        </>
          }
                </div>,
        document.body
      )}
        </div>);

}


GlobalSearchBar.propTypes = {
  ...(GlobalSearchBar.propTypes || {}),
  className: PropTypes.any,
};
