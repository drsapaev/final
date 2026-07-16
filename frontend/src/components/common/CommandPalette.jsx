/**
 * CommandPalette — global Cmd+K / Ctrl+K command palette for admin navigation.
 *
 * SW-05 fix: admin sidebar has 38 routes. Finding a function requires scanning
 * the sidebar manually. This palette lets the admin press Cmd+K, type 2-3 letters,
 * and jump to any route instantly. Also supports quick actions (create appointment,
 * new patient, etc.).
 *
 * Features:
 *   - Fuzzy search on route label, id, path, and section
 *   - Keyboard navigation (ArrowUp/Down, Enter, Escape)
 *   - Quick actions (not just navigation)
 *   - Recent items (last 5 visited via palette)
 *   - Role-aware: only shows routes the current user can access
 *
 * Usage in App.jsx:
 *   <CommandPalette profile={authState.profile} navigate={navigate} />
 *   // The palette listens for Cmd+K globally and renders itself via portal.
 */
import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Search, ArrowRight, Clock } from 'lucide-react';
import { getCanonicalRoutes, isRouteAccessibleToProfile } from '../../routing/routeSelectors';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

const MAX_RESULTS = 8;
const MAX_RECENT = 5;
const RECENT_KEY = 'cmd_palette_recent';

// Quick actions available in the palette (not routes, but shortcuts)
const QUICK_ACTIONS = [
  {
    id: 'action-new-appointment',
    label: 'Новая запись',
    description: 'Открыть мастер создания записи',
    icon: 'plus',
    keywords: ['запись', 'новая', 'создать', 'appointment', 'new'],
    action: 'navigate',
    target: '/registrar?action=new',
    section: 'Действия',
  },
  {
    id: 'action-search-patient',
    label: 'Поиск пациента',
    description: 'Открыть форму поиска пациента',
    icon: 'search',
    keywords: ['пациент', 'поиск', 'find', 'patient', 'search'],
    action: 'navigate',
    target: '/clinical/search',
    section: 'Действия',
  },
  {
    id: 'action-back',
    label: 'Назад',
    description: 'Вернуться на предыдущую страницу',
    icon: 'arrow.left',
    keywords: ['назад', 'back', 'previous'],
    action: 'back',
    section: 'Действия',
  },
];

function loadRecent() {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveRecent(items) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(items.slice(0, MAX_RECENT)));
  } catch {
    // ignore
  }
}

function fuzzyMatch(query, text) {
  if (!query) return true;
  const q = query.toLowerCase();
  const t = (text || '').toLowerCase();
  if (t.includes(q)) return true;
  // Simple fuzzy: check if all chars of query appear in order
  let qi = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) qi++;
  }
  return qi === q.length;
}

function scoreResult(query, item) {
  if (!query) return 0;
  const q = query.toLowerCase();
  const label = (item.label || '').toLowerCase();
  const id = (item.id || '').toLowerCase();
  const path = (item.path || '').toLowerCase();
  const keywords = (item.keywords || []).map(k => k.toLowerCase());

  // Exact match = highest score
  if (label === q) return 100;
  if (id === q) return 95;

  // Starts with
  if (label.startsWith(q)) return 80;
  if (id.startsWith(q)) return 75;

  // Contains
  if (label.includes(q)) return 60;
  if (path.includes(q)) return 50;
  if (id.includes(q)) return 45;

  // Keywords
  for (const kw of keywords) {
    if (kw === q) return 70;
    if (kw.startsWith(q)) return 55;
    if (kw.includes(q)) return 40;
  }

  // Fuzzy match
  if (fuzzyMatch(q, label)) return 20;
  if (fuzzyMatch(q, id)) return 15;

  return 0;
}

export function CommandPalette({ profile, navigate }) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recent, setRecent] = useState(loadRecent);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  // Build items from routes + quick actions
  const allItems = useMemo(() => {
    const routes = getCanonicalRoutes();
    const accessibleRoutes = routes.filter(route =>
      route.nav !== false &&
      route.group !== 'internal-demo' &&
      route.group !== 'public' &&
      isRouteAccessibleToProfile(route, profile)
    );

    const routeItems = accessibleRoutes.map(route => ({
      id: route.id,
      label: route.nav?.label || route.title || route.id,
      description: route.nav?.section || route.group || '',
      path: route.path,
      icon: route.nav?.icon,
      section: route.nav?.section || 'Маршруты',
      keywords: [route.id, route.path, route.title],
      action: 'navigate',
      target: route.path,
    }));

    // Filter quick actions by role
    const roleNorm = (profile?.role || '').toLowerCase();
    const actionItems = QUICK_ACTIONS.filter(action => {
      if (action.id === 'action-new-appointment') {
        return roleNorm === 'admin' || roleNorm === 'registrar';
      }
      if (action.id === 'action-search-patient') {
        return true; // all clinical roles can search
      }
      return true;
    });

    return [...actionItems, ...routeItems];
  }, [profile]);

  // Filter + sort
  const results = useMemo(() => {
    if (!query.trim()) {
      // Show recent first, then first N items
      const recentItems = recent
        .map(id => allItems.find(item => item.id === id))
        .filter(Boolean);
      const nonRecent = allItems.filter(item => !recent.includes(item.id));
      return [...recentItems, ...nonRecent].slice(0, MAX_RESULTS);
    }

    return allItems
      .map(item => ({ item, score: scoreResult(query, item) }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, MAX_RESULTS)
      .map(({ item }) => item);
  }, [query, allItems, recent]);

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(prev => !prev);
      }
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    // PR-50: listen for custom 'open-command-palette' event from header ⌘K button.
    // Previously the header dispatched a synthetic KeyboardEvent which was brittle
    // and conflicted with GlobalSearchBar's own ⌘K handler.
    const handleOpenPalette = () => setIsOpen(true);

    window.addEventListener('keydown', handleKeyDown);
    document.addEventListener('open-command-palette', handleOpenPalette);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('open-command-palette', handleOpenPalette);
    };
  }, [isOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = results[selectedIndex];
      if (item) handleSelect(item);
    }
  }, [results, selectedIndex]);

  const handleSelect = useCallback((item) => {
    // Save to recent
    const newRecent = [item.id, ...recent.filter(id => id !== item.id)].slice(0, MAX_RECENT);
    setRecent(newRecent);
    saveRecent(newRecent);

    // Execute action
    if (item.action === 'navigate' && item.target) {
      navigate(item.target);
    } else if (item.action === 'back') {
      window.history.back();
    }

    setIsOpen(false);
  }, [navigate, recent]);

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const selected = listRef.current.children[selectedIndex];
      if (selected) {
        selected.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  if (!isOpen) return null;

  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '15vh',
        backgroundColor: 'rgba(0, 0, 0, 0.4)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={() => setIsOpen(false)}
      role="button"
      tabIndex={-1}
      onKeyDown={(e) => { if (e.key === 'Escape') setIsOpen(false); }}
      aria-label="Закрыть панель команд"
    >
      <div
        role="dialog"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === 'Escape') setIsOpen(false); }}
        style={{
          width: '90%',
          maxWidth: '560px',
          maxHeight: '60vh',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'var(--mac-bg-primary, #ffffff)',
          borderRadius: '14px',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
          border: '1px solid var(--mac-border, rgba(0,0,0,0.1))',
          overflow: 'hidden',
        }}
      >
        {/* Search input */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '14px 16px',
          borderBottom: '1px solid var(--mac-border, rgba(0,0,0,0.08))',
        }}>
          <Search size={18} style={{ color: 'var(--mac-text-secondary, #6b7280)', flexShrink: 0 }} />
          <Input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Поиск маршрута или действия..."
            aria-label="Search commands"
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              backgroundColor: 'transparent',
              color: 'var(--mac-text-primary, #1a1a1a)',
              fontSize: 'var(--mac-font-size-lg)',
              fontFamily: 'inherit',
            }}
          />
          <kbd style={{
            padding: '2px 6px',
            borderRadius: 'var(--mac-radius-sm)',
            backgroundColor: 'var(--mac-bg-secondary, rgba(0,0,0,0.05))',
            color: 'var(--mac-text-secondary, #6b7280)',
            fontSize: 'var(--mac-font-size-xs)',
            fontFamily: 'ui-monospace, monospace',
          }}>ESC</kbd>
        </div>

        {/* Results */}
        <div
          ref={listRef}
          role="listbox"
          style={{
            overflowY: 'auto',
            flex: 1,
            padding: 'var(--mac-spacing-2)',
          }}
        >
          {results.length === 0 && (
            <div style={{
              padding: '24px 16px',
              textAlign: 'center',
              color: 'var(--mac-text-secondary, #6b7280)',
              fontSize: 'var(--mac-font-size-base)',
            }}>
              Ничего не найдено для «{query}»
            </div>
          )}
          {results.map((item, index) => {
            const isSelected = index === selectedIndex;
            const isRecent = !query && recent.includes(item.id);
            return (
              <div
                key={item.id}
                role="option"
                aria-selected={isSelected}
                onClick={() => handleSelect(item)}
                tabIndex={isSelected ? 0 : -1}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSelect(item); }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '10px 12px',
                  borderRadius: 'var(--mac-radius-md)',
                  cursor: 'pointer',
                  backgroundColor: isSelected
                    ? 'var(--mac-accent-blue, #007aff)'
                    : 'transparent',
                  color: isSelected
                    ? 'var(--mac-bg-primary)'
                    : 'var(--mac-text-primary, #1a1a1a)',
                  transition: 'background-color 0.1s ease',
                }}
              >
                {isRecent && (
                  <Clock size={14} style={{
                    color: isSelected ? 'color-mix(in srgb, white, transparent 30%)' : 'var(--mac-text-secondary, #6b7280)',
                    flexShrink: 0,
                  }} />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 'var(--mac-font-size-base)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {item.label}
                  </div>
                  {item.description && (
                    <div style={{
                      fontSize: 'var(--mac-font-size-xs)',
                      color: isSelected ? 'color-mix(in srgb, white, transparent 30%)' : 'var(--mac-text-secondary, #6b7280)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {item.description}
                    </div>
                  )}
                </div>
                {isSelected && (
                  <ArrowRight size={14} style={{ color: 'color-mix(in srgb, white, transparent 30%)', flexShrink: 0 }} />
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-3)',
          padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
          borderTop: '1px solid var(--mac-border, rgba(0,0,0,0.08))',
          fontSize: 'var(--mac-font-size-xs)',
          color: 'var(--mac-text-secondary, #6b7280)',
        }}>
          <span>↑↓ навигация</span>
          <span>↵ выбрать</span>
          <span>esc закрыть</span>
          <span style={{ marginLeft: 'auto' }}>{results.length} результатов</span>
        </div>
      </div>
    </div>,
    document.body
  );
}

export default CommandPalette;
