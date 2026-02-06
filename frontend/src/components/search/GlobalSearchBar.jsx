/**
 * GlobalSearchBar - macOS-style global search component
 * Aggregated search across patients, visits, and lab results
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import auth from '../../stores/auth';

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
        const profile = st.profile || st.user || {};
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
            console.error('Search error:', error);
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
        results.patients.forEach(p => items.push({ type: 'patient', data: p }));
        results.visits.forEach(v => items.push({ type: 'visit', data: v }));
        results.labResults.forEach(l => items.push({ type: 'lab', data: l }));
        return items;
    };

    // Handle keyboard navigation
    const handleKeyDown = (e) => {
        const items = getAllItems();

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(prev => Math.min(prev + 1, items.length - 1));
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(prev => Math.max(prev - 1, -1));
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
    const highlightMatch = (text, query) => {
        if (!text || !query || query.length < 2) return text;
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        const parts = String(text).split(regex);
        return parts.map((part, i) =>
            regex.test(part) ? <mark key={i} style={{ background: '#fef08a', padding: '0 2px', borderRadius: '2px' }}>{part}</mark> : part
        );
    };

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
            console.error('Audit log error:', e);
        }

        setIsOpen(false);
        setQuery('');

        switch (type) {
            case 'patient':
                // Role-based navigation for patients
                // All panels now support ?patientId parameter
                if (role === 'registrar' || role === 'receptionist') {
                    // Registrar, Receptionist -> Registrar panel with patient search
                    navigate(`/registrar-panel?patientId=${item.id}`);
                } else if (role === 'cardio') {
                    // Cardiologist -> Cardiology panel with patient context
                    navigate(`/cardiologist?patientId=${item.id}`);
                } else if (role === 'derma') {
                    // Dermatologist -> Dermatology panel with patient context
                    navigate(`/dermatologist?patientId=${item.id}`);
                } else if (role === 'dentist') {
                    // Dentist -> Dentist panel with patient context
                    navigate(`/dentist?patientId=${item.id}`);
                } else if (role === 'doctor') {
                    // General doctor -> Doctor panel with patient context
                    navigate(`/doctor-panel?patientId=${item.id}`);
                } else if (role === 'lab') {
                    // Lab -> Lab panel with patient context
                    navigate(`/lab-panel?patientId=${item.id}`);
                } else if (role === 'cashier') {
                    // Cashier -> Cashier panel with patient context
                    navigate(`/cashier-panel?patientId=${item.id}`);
                } else if (role === 'admin') {
                    // Admin -> Admin panel with patient search
                    navigate(`/admin?patientId=${item.id}`);
                } else {
                    // Fallback for any other role
                    navigate(`/pickup/${item.id}`);
                }
                break;
            case 'visit':
                if (role === 'doctor') {
                    navigate(`/doctor-panel?visitId=${item.id}`);
                } else {
                    navigate(`/registrar-panel?visitId=${item.id}&patientId=${item.patient_id}`);
                }
                break;
            case 'lab':
                navigate(`/pickup/${item.patient_id}?tab=lab&orderId=${item.id}`);
                break;
        }
    };

    const hasResults = results.patients.length > 0 || results.visits.length > 0 || results.labResults.length > 0;

    // Styles
    const styles = {
        container: {
            position: 'relative',
            width: '100%',
            maxWidth: '400px',
        },
        inputWrapper: {
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
        },
        input: {
            width: '100%',
            padding: '8px 12px 8px 36px',
            fontSize: '14px',
            border: '1px solid var(--mac-border, #d1d5db)',
            borderRadius: '8px',
            background: 'var(--mac-bg-secondary, #f8fafc)',
            color: 'var(--mac-text-primary, #1e293b)',
            outline: 'none',
            transition: 'all 0.2s ease',
        },
        searchIcon: {
            position: 'absolute',
            left: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            color: 'var(--mac-text-tertiary, #94a3b8)',
            pointerEvents: 'none',
        },
        shortcut: {
            position: 'absolute',
            right: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            fontSize: '11px',
            color: 'var(--mac-text-tertiary, #94a3b8)',
            background: 'var(--mac-bg-tertiary, #e2e8f0)',
            padding: '2px 6px',
            borderRadius: '4px',
            pointerEvents: 'none',
        },
        dropdown: {
            position: 'fixed',
            top: `${dropdownPos.top}px`,
            left: `${dropdownPos.left}px`,
            width: `${dropdownPos.width}px`,
            background: 'var(--mac-bg-primary, white)',
            border: '1px solid var(--mac-border, #e2e8f0)',
            borderRadius: '12px',
            boxShadow: '0 10px 40px rgba(0,0,0,0.25)',
            zIndex: 2147483647,
            maxHeight: '400px',
            overflowY: 'auto',
        },
        section: {
            padding: '8px 0',
            borderBottom: '1px solid var(--mac-separator, #e2e8f0)',
        },
        sectionTitle: {
            padding: '4px 12px',
            fontSize: '11px',
            fontWeight: '600',
            color: 'var(--mac-text-tertiary, #64748b)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
        },
        item: {
            padding: '10px 12px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            transition: 'background 0.15s ease',
        },
        itemSelected: {
            background: 'var(--mac-accent-blue, #3b82f6)',
            color: 'white',
        },
        itemIcon: {
            fontSize: '16px',
            width: '24px',
            textAlign: 'center',
        },
        itemContent: {
            flex: 1,
            minWidth: 0,
        },
        itemTitle: {
            fontSize: '14px',
            fontWeight: '500',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
        },
        itemSubtitle: {
            fontSize: '12px',
            opacity: 0.7,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
        },
        loading: {
            padding: '20px',
            textAlign: 'center',
            color: 'var(--mac-text-tertiary, #64748b)',
        },
        noResults: {
            padding: '20px',
            textAlign: 'center',
            color: 'var(--mac-text-tertiary, #64748b)',
        },
    };

    let flatIndex = -1;

    return (
        <div style={styles.container} className={className} ref={containerRef}>
            <div style={styles.inputWrapper}>
                <span style={styles.searchIcon}>🔍</span>
                <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onFocus={() => setIsOpen(true)}
                    onKeyDown={handleKeyDown}
                    placeholder="Поиск пациентов, визитов..."
                    style={styles.input}
                />
                <span style={styles.shortcut}>⌘K</span>
            </div>

            {isOpen && ReactDOM.createPortal(
                <div style={styles.dropdown} ref={dropdownRef}>
                    {isLoading && (
                        <div style={styles.loading}>Поиск...</div>
                    )}

                    {!isLoading && query.length < 2 && (
                        <div style={styles.noResults}>Начните ввод (минимум 2 символа)</div>
                    )}

                    {!isLoading && !hasResults && query.length >= 2 && (
                        <div style={styles.noResults}>Ничего не найдено</div>
                    )}

                    {!isLoading && hasResults && (
                        <>
                            {/* Patients */}
                            {results.patients.length > 0 && (
                                <div style={styles.section}>
                                    <div style={styles.sectionTitle}>Пациенты</div>
                                    {results.patients.map((p) => {
                                        flatIndex++;
                                        const isSelected = flatIndex === selectedIndex;
                                        return (
                                            <div
                                                key={`patient-${p.id}`}
                                                style={{ ...styles.item, ...(isSelected ? styles.itemSelected : {}) }}
                                                onClick={() => handleItemClick('patient', p)}
                                                onMouseEnter={() => setSelectedIndex(flatIndex)}
                                            >
                                                <span style={styles.itemIcon}>👤</span>
                                                <div style={styles.itemContent}>
                                                    <div style={styles.itemTitle}>
                                                        {p.last_name} {p.first_name} {p.middle_name || ''}
                                                    </div>
                                                    <div style={styles.itemSubtitle}>
                                                        #{p.id} {p.phone && `• ${p.phone}`}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}

                            {/* Visits */}
                            {results.visits.length > 0 && (
                                <div style={styles.section}>
                                    <div style={styles.sectionTitle}>Визиты</div>
                                    {results.visits.map((v) => {
                                        flatIndex++;
                                        const isSelected = flatIndex === selectedIndex;
                                        return (
                                            <div
                                                key={`visit-${v.id}`}
                                                style={{ ...styles.item, ...(isSelected ? styles.itemSelected : {}) }}
                                                onClick={() => handleItemClick('visit', v)}
                                                onMouseEnter={() => setSelectedIndex(flatIndex)}
                                            >
                                                <span style={styles.itemIcon}>📋</span>
                                                <div style={styles.itemContent}>
                                                    <div style={styles.itemTitle}>
                                                        {v.patient_name || `Визит #${v.id}`}
                                                    </div>
                                                    <div style={styles.itemSubtitle}>
                                                        {v.planned_date} • {v.status || 'нет статуса'}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}

                            {/* Lab Results */}
                            {results.labResults.length > 0 && (
                                <div style={{ ...styles.section, borderBottom: 'none' }}>
                                    <div style={styles.sectionTitle}>Анализы</div>
                                    {results.labResults.map((l) => {
                                        flatIndex++;
                                        const isSelected = flatIndex === selectedIndex;
                                        const statusIcon = l.status === 'done' ? '🟢' : l.status === 'in_progress' ? '🟡' : '⚪';
                                        return (
                                            <div
                                                key={`lab-${l.id}`}
                                                style={{ ...styles.item, ...(isSelected ? styles.itemSelected : {}) }}
                                                onClick={() => handleItemClick('lab', l)}
                                                onMouseEnter={() => setSelectedIndex(flatIndex)}
                                            >
                                                <span style={styles.itemIcon}>{statusIcon}</span>
                                                <div style={styles.itemContent}>
                                                    <div style={styles.itemTitle}>
                                                        {l.patient_name || `Заказ #${l.id}`}
                                                    </div>
                                                    <div style={styles.itemSubtitle}>
                                                        {l.test_type || 'Лабораторный анализ'} • {l.status}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </>
                    )}
                </div>,
                document.body
            )}
        </div>
    );
}
