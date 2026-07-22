import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import type { CSSProperties } from 'react';
import ReactDOM from 'react-dom';
import { Sun as LSun, Moon as LMoon, Monitor as LMonitor, Rainbow as LRainbow, Layers as LLayers, Sparkles as LSparkles, Bell as BellIcon } from 'lucide-react';
import { useNotificationCenter } from '../../contexts/NotificationCenterContext';
import { useNavigate, useLocation } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth';
import { useTheme } from '../../contexts/ThemeContext';
import CompactConnectionStatus from '../pwa/CompactConnectionStatus';
import {
  Button, Icon,
} from '../ui/macos';
import GlobalSearchBar from '../search/GlobalSearchBar';
import ChatButton from '../chat/ChatButton';
import { COLOR_SCHEMES } from '../../theme/colorScheme';
import { getCanonicalRouteById, getEffectiveRouteByPath, getRoleHomeRoute } from '../../routing/routeSelectors';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const landingRoute = getCanonicalRouteById('landing')?.path || '/';
const loginRoute = getCanonicalRouteById('login')?.path || '/login';
const profileRoute = getCanonicalRouteById('clinical-profile')?.path || '/clinical/profile';
const registrarHomeRoute = getRoleHomeRoute('registrar');

export function isThemeMenuInteraction(event, themeMenuRoot) {
  const path = event.composedPath ? event.composedPath() : [];
  const inRef = Boolean(
    themeMenuRoot &&
    (path.includes(themeMenuRoot) || themeMenuRoot.contains?.(event.target))
  );
  const inMenu = path.some((node) => node?.dataset?.themeMenu === 'true');
  return inRef || inMenu;
}
/**
 * Новый компактный и предсказуемый хедер.
 * Цели:
 * - Абсолютно исключить растяжение кнопок (inline-flex + flex:0 0 auto + nowrap)
 * - Чёткая сетка: brand | nav (scroll) | controls
 * - Повторить функционал текущего Header.jsx, сохранив роли и роутинг
 */
export default function HeaderNew() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t: rawT, language, setLanguage } = useTranslation();  // PR-50: i18n wired
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

  const [state, setState] = useState(auth.getState());
  const { inboxOpen, setInboxOpen, getUnreadCount } = useNotificationCenter();
  const [lang, setLang] = useState(language || 'ru');
  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);  // PR-50: profile dropdown
  const themeMenuRef = useRef(null);
  const themeButtonRef = useRef(null);
  const [menuPos, setMenuPos] = useState({ left: 0, top: 0 });

  useEffect(() => auth.subscribe(setState), []);

  // PR-50: sync lang with useTranslation
  useEffect(() => { setLang(language); }, [language]);

  const { theme, colorScheme, setColorScheme } = useTheme();

  const colorSchemes = useMemo(() => COLOR_SCHEMES.map((scheme) => ({
    ...scheme,
    icon: scheme.id === 'vibrant' ? 'rainbow' :
    scheme.id === 'glass' ? 'layers' :
    scheme.id === 'gradient' ? 'sparkles' :
    scheme.id === 'auto' ? 'monitor' :
    scheme.id === 'dark' ? 'moon' :
    'sun',
  })), []);

  // Close theme menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!isThemeMenuInteraction(event, themeMenuRef.current)) {
        setShowThemeMenu(false);
      }
    };
    document.addEventListener('click', handleClickOutside, true);
    return () => document.removeEventListener('click', handleClickOutside, true);
  }, []);

  const handleThemeClick = (schemeId) => {
    logger.info('[FIX:THEME] Header theme change requested', {
      currentColorScheme: colorScheme,
      nextColorScheme: schemeId,
    });
    setColorScheme(schemeId);
    setShowThemeMenu(false);
  };

  const renderSchemeIcon = (schemeId) => {
    switch (schemeId) {
      case 'vibrant':
        return <LRainbow size={16} />;
      case 'glass':
        return <LLayers size={16} />;
      case 'gradient':
        return <LSparkles size={16} />;
      case 'auto':
        return <LMonitor size={16} />;
      case 'dark':
        return <LMoon size={16} />;
      case 'light':
      default:
        return <LSun size={16} />;
    }
  };

  const stateTyped = state as { profile?: Record<string, unknown>; user?: Record<string, unknown> };
  const user = stateTyped.profile || stateTyped.user || null;
  const role = user?.role || user?.role_name || 'Guest';
  const roleLower = String(role).toLowerCase();
  // Normalize receptionist to registrar for UI consistency
  const roleNormalized = roleLower === 'receptionist' ? 'registrar' : roleLower;
  const currentRoute = getEffectiveRouteByPath(location.pathname);

  const isRegistrarPanel = currentRoute?.id === 'registrar-home';

  // Определяем активную кастомную схему
  const isGlassTheme = colorScheme === 'glass';
  const isGradientTheme = colorScheme === 'gradient';
  const isVibrantTheme = colorScheme === 'vibrant';
  const isCustomTheme = isGlassTheme || isGradientTheme || isVibrantTheme;

  const headerStyle = {
    backgroundColor: isGlassTheme ?
    'rgba(50, 55, 65, 0.85)' :
    isGradientTheme || isVibrantTheme ?
    'var(--mac-bg-toolbar)' :
    theme === 'dark' ? 'rgba(21,23,28,0.78)' : 'var(--mac-bg-toolbar)',
    borderBottom: isGlassTheme ?
    '1px solid rgba(255,255,255,0.25)' :
    isGradientTheme || isVibrantTheme ?
    '1px solid var(--mac-separator)' :
    theme === 'dark' ? '1px solid rgba(255,255,255,0.12)' : '1px solid var(--mac-separator)',
    backdropFilter: 'var(--mac-blur-light)',
    WebkitBackdropFilter: 'var(--mac-blur-light)',
    boxShadow: isGlassTheme ?
    '0 2px 10px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.1)' :
    isGradientTheme || isVibrantTheme ?
    'var(--mac-shadow-sm)' :
    theme === 'dark' ?
    '0 2px 10px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.06)' :
    'var(--mac-shadow-sm)',
    display: 'grid',
    gridTemplateColumns: 'auto 1fr auto',
    alignItems: 'center',
    columnGap: '12px',
    overflow: 'visible',
    borderRadius: 'var(--mac-radius-md)',
    padding: '0 16px',
    height: '54px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    backgroundImage: isGlassTheme ?
    'none' :
    isGradientTheme || isVibrantTheme ?
    'none' :
    theme === 'dark' ? 'linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0))' : 'none'
  };

  // Навигация по ролям (как в исходном хедере)
  const navItems = useMemo(() => {
    const items = [];
    if (roleNormalized !== 'admin') {
      if (roleNormalized === 'registrar') items.push({ to: getRoleHomeRoute('cashier'), label: t('legacy.hn_nav_cashier_role'), icon: 'creditcard' });
      if (roleNormalized === 'cashier') items.push({ to: getRoleHomeRoute('cashier'), label: t('legacy.hn_nav_cashier_home'), icon: 'creditcard' });
    }
    return items;
  }, [roleNormalized]);

  // PR-50: changeLang now uses useTranslation's setLanguage (which updates
  // React context + triggers re-render). Previously only wrote to localStorage
  // — the toggle was decorative.
  const changeLang = (v) => {
    setLang(v);
    setLanguage(v);  // updates useTranslation context → re-renders all consumers
  };

  // QW-05 fix: global Back button. Previously navigate(-1) was used only in 2 of ~50
  // pages, leaving users on detail screens (PatientPickupView, etc.)
  // to rely on the browser back button. The header now renders an ArrowLeft button
  // whenever the user is not on a top-level surface (landing, login, role home).
  // Heuristic: hide on the root path and on each role's home route, where "back"
  // has no meaningful destination.
  const roleHomePath = useMemo(() => {
    try {
      return getRoleHomeRoute(roleNormalized) || '/';
    } catch {
      return '/';
    }
  }, [roleNormalized]);

  const canGoBack = useMemo(() => {
    const p = location.pathname;
    if (p === '/' || p === landingRoute || p === loginRoute) return false;
    if (p === roleHomePath) return false;
    // No history beyond the current entry (new tab / deep link)
    if (!window.history || window.history.length <= 1) return false;
    return true;
    // landingRoute/loginRoute are module-level constants, not React state.
  }, [location.pathname, roleHomePath]);

  const handleBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate(roleHomePath || landingRoute);
    }
    // landingRoute is a module-level constant.
  }, [navigate, roleHomePath]);

  const backButton = canGoBack ? (
    <Button
      variant="ghost"
      size="small"
      onClick={handleBack}
      title={t('legacy.hn_back_title')}
      aria-label={t('legacy.hn_back_title')}
      style={{
        color: 'var(--mac-text-primary)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-1)',
        padding: '8px 10px',
        flexShrink: 0
      }}>
      <Icon name="chevron.left" size="small" style={{ color: 'var(--mac-text-primary)' }} />
    </Button>
  ) : null;

  const brand =
  <Button
    variant="ghost"
    size="small"
    onClick={() => navigate(landingRoute)}
    title={t('legacy.hn_brand_title')}
    style={{
      color: 'var(--mac-text-primary)',
      fontWeight: 'var(--mac-font-weight-bold)',
      fontSize: 'var(--mac-font-size-lg)',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--mac-spacing-2)',
      padding: 'var(--mac-spacing-2) var(--mac-spacing-3)'
    }}>

      <Icon name="stethoscope" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
      <span className="hdr-hide-xs">{t('legacy.hn_brand_text')}</span>
    </Button>;


  const roleNav =
  <div className="hdr-nav-scroll" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'nowrap', whiteSpace: 'nowrap', overflowX: 'auto' }}>
      {navItems.map((item) => {
      const active = location.pathname === item.to;
      return (
        <Button
          key={item.to}
          variant={active ? 'primary' : 'outline'}
          size="small"
          onClick={() => navigate(item.to)}
          title={item.label}
          className="hdr-hide-xs"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            flexShrink: 0,
            color: active ?
            'white' :
            theme === 'dark' ? 'color-mix(in srgb, white, transparent 10%)' : 'var(--mac-text-primary)'
          }}>

            <Icon name={item.icon} size="small" style={{ color: active ? 'white' : theme === 'dark' ? 'rgba(255,255,255,0.85)' : 'var(--mac-text-primary)' }} />
            <span className="hdr-hide-sm">{item.label}</span>
          </Button>);

    })}

      {roleNormalized === 'registrar' && isRegistrarPanel &&
    <>
          <Button
        variant="outline"
        size="small"
        title={t('legacy.hn_registrar_home_title')}
        onClick={() => navigate('/registrar/welcome')}
        className="hdr-hide-md"
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', flexShrink: 0, color: theme === 'dark' ? 'color-mix(in srgb, white, transparent 10%)' : undefined }}>

            <Icon name="house" size="small" style={{ color: theme === 'dark' ? 'rgba(255,255,255,0.85)' : undefined }} />
            <span className="hdr-hide-md">{t('legacy.hn_registrar_home_title')}</span>
          </Button>
          <Button
        variant="outline"
        size="small"
        title={t('legacy.hn_online_queue_title')}
        onClick={() => navigate('/registrar/queue')}
        className="hdr-hide-xs"
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', flexShrink: 0, color: theme === 'dark' ? 'color-mix(in srgb, white, transparent 10%)' : undefined }}>

            <Icon name="bell" size="small" style={{ color: theme === 'dark' ? 'rgba(255,255,255,0.85)' : 'var(--mac-text-primary)' }} />
            <span className="hdr-hide-sm">{t('legacy.hn_online_queue_title')}</span>
          </Button>
          <Button
        variant="primary"
        size="small"
        title={t('legacy.hn_new_appointment_title')}
        onClick={() => {
          // P-008 fix: previously dispatched a CustomEvent('openAppointmentWizard')
          // that only RegistrarPanel listens to — making the button a silent no-op on
          // any other page. Now the button always navigates to the registrar route
          // with ?action=new, and RegistrarPanel reads that query param on mount to
          // auto-open the wizard. Falls back to the CustomEvent when already on the
          // registrar route (preserves the existing in-page UX).
          if (isRegistrarPanel) {
            window.dispatchEvent(new CustomEvent('openAppointmentWizard'));
          } else {
            navigate(`${registrarHomeRoute}?action=new`);
          }
        }}
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', flexShrink: 0 }}>

            <Icon name="plus" size="small" style={{ color: 'white' }} />
            <span className="hdr-hide-md">{t('legacy.hn_new_appointment_title')}</span>
          </Button>
        </>
    }
    </div>;


  const controls =
  <div className="hdr-controls" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'nowrap', whiteSpace: 'nowrap' }}>
      {/* divider for clearer separation in dark mode */}
      <div
      aria-hidden
      style={{
        width: 1,
        alignSelf: 'stretch',
        background: theme === 'dark' ? 'color-mix(in srgb, white, transparent 92%)' : 'var(--mac-separator)'
      }} />

      {/* 1) Язык — PR-50: replaced cycling button with <select> (H-1, H-2 fix) */}
      <select
        value={lang}
        onChange={(e) => changeLang(e.target.value)}
        aria-label={t('legacy.hn_select_language')}
        title={t('legacy.hn_select_language')}
        style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          padding: '6px 10px',
          flex: '0 0 auto',
          border: theme === 'dark' ? '1px solid rgba(255,255,255,0.14)' : '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          backgroundColor: 'var(--mac-bg-secondary)',
          color: 'var(--mac-text-primary)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-1)'
        }}>
        <option value="ru">RU</option>
        <option value="uz">UZ</option>
        <option value="en">EN</option>
      </select>

      {/* 2) Сеть */}
      <div style={{ flex: '0 0 auto' }}>
        <CompactConnectionStatus className="mr-2" />
      </div>

      {/* 2.5) Чат */}
      {user &&
    <div style={{ flex: '0 0 auto' }}>
          <ChatButton />
        </div>
    }

      {/* 2.6) Уведомления — global notification bell, opens inbox via context */}
      {user &&
        <div style={{ flex: '0 0 auto' }}>
          <Button
            variant="ghost"
            size="small"
            onClick={() => setInboxOpen(!inboxOpen)}
            title={t('legacy.hn_notifications_title') || 'Уведомления'}
            aria-label={t('legacy.hn_notifications_title') || 'Уведомления'}
            aria-expanded={inboxOpen}
            style={{
              width: '36px',
              height: '36px',
              padding: 0,
              borderRadius: 'var(--mac-radius-sm)',
              border: '1px solid var(--mac-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
            }}>
            <BellIcon size={16} style={{ color: 'var(--mac-text-primary)' }} />
            {(() => {
              const role = String(user?.role || user?.role_name || '').toLowerCase();
              const normalizedRole = role === 'receptionist' ? 'registrar' : role;
              const count = getUnreadCount(normalizedRole);
              return count > 0 ? (
                <span style={{
                  position: 'absolute',
                  top: -3,
                  right: -3,
                  minWidth: 16,
                  height: 16,
                  padding: '0 4px',
                  borderRadius: 8,
                  background: 'var(--mac-error)',
                  color: 'white',
                  fontSize: 10,
                  lineHeight: '16px',
                  fontWeight: 'var(--mac-font-weight-bold)',
                  textAlign: 'center',
                }}>
                  {count > 99 ? '99+' : count}
                </span>
              ) : null;
            })()}
          </Button>
        </div>
      }

      {/* 3) Тема */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', flex: '0 0 auto' }}>
        <div ref={themeMenuRef} style={{ position: 'relative', display: 'flex', alignItems: 'center', width: '100%', height: '100%' }}>
          <Button
          ref={themeButtonRef}
          variant="ghost"
          size="small"
          onClick={() => {
            logger.log('Theme button clicked, current state:', showThemeMenu);
            // Вычисляем позицию для фиксированного меню
            try {
              const btn = themeButtonRef.current;
              if (btn) {
                const rect = btn.getBoundingClientRect();
                const MENU_WIDTH = 220;
                const left = Math.min(
                  Math.max(8, rect.left),
                  Math.max(8, window.innerWidth - MENU_WIDTH - 8)
                );
                const top = Math.min(rect.bottom + 8, window.innerHeight - 8);
                setMenuPos({ left, top });
              }
            } catch (error) {
              logger.debug('Failed to position theme menu', error);
            }
            setShowThemeMenu((v) => !v);
          }}
          title={t('legacy.hn_select_theme')}
          aria-label={t('legacy.hn_select_theme')}
            style={{
              width: '36px',
            height: '36px',
            padding: 0,
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--mac-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flex: '0 0 auto'
          }}>

            <span style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--mac-text-primary)' }}>
              {renderSchemeIcon(colorScheme)}
            </span>
          </Button>

          {/* Theme Menu Dropdown */}
          {showThemeMenu ?
        ReactDOM.createPortal(
          <div
            data-theme-menu="true"
            style={{
              position: 'fixed',
              left: `${menuPos.left}px`,
              top: `${menuPos.top}px`,
              backgroundColor: isCustomTheme ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-md)',
              padding: 'var(--mac-spacing-2)',
              minWidth: '220px',
              boxShadow: 'var(--mac-shadow-md, 0 8px 24px rgba(0,0,0,0.2))',
              zIndex: 2147483647,
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--mac-spacing-1)',
              pointerEvents: 'auto',
              color: 'var(--mac-text-primary)'
            }}>

                {colorSchemes.map((scheme) =>
            <button
              type="button"
              key={scheme.id}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleThemeClick(scheme.id);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-2)',
                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                border: 'none',
                width: '100%',
                textAlign: 'left',
                borderRadius: 'var(--mac-radius-sm)',
                background: 'transparent',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';}}
              onMouseLeave={(e) => {e.currentTarget.style.backgroundColor = 'transparent';}}>

                    <span style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--mac-accent-blue)' }}>
                      {renderSchemeIcon(scheme.id)}
                    </span>
                    <span style={{ color: 'var(--mac-text-primary)', fontWeight: colorScheme === scheme.id ? 600 : 400 }}>
                      {scheme.name}
                    </span>
                  </button>
            )}
              </div>,
          document.body
        ) :
        null}
        </div>
      </div>

      {/* 4) Профиль / Войти — PR-50: consolidated profile + logout into dropdown (H-6, H-7 fix) */}
      {user ? (
        <div style={{ position: 'relative', flex: '0 0 auto' }}>
          <Button
            variant="outline"
            size="small"
            onClick={() => setShowProfileMenu((v) => !v)}
            title={t('legacy.hn_profile_title')}
            aria-label={t('legacy.hn_profile_title')}
            aria-haspopup="menu"
            aria-expanded={showProfileMenu}
            className="hdr-hide-sm"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)',
              flex: '0 0 auto'
            }}>
            <Icon name="person" size="small" style={{ color: 'var(--mac-text-primary)' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>
              {String(user?.full_name ?? '') || String(user?.username ?? '') || t('legacy.hn_profile_fallback')}
            </span>
          </Button>
          {showProfileMenu && (
            <>
              {/* click-outside overlay — PR-50: added role + keyboard handler */}
              <div
                onClick={() => setShowProfileMenu(false)}
                onKeyDown={(e) => { if (e.key === 'Escape') setShowProfileMenu(false); }}
                role="button"
                tabIndex={-1}
                aria-label={t('legacy.hn_close_profile_menu')}
                style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 99 }}
              />
              <div
                role="menu"
                aria-label={t('legacy.hn_profile_menu')}
                style={{
                  position: 'absolute',
                  top: '100%',
                  right: 0,
                  marginTop: '4px',
                  backgroundColor: 'var(--mac-bg-primary)',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  boxShadow: 'var(--mac-shadow-md)',
                  zIndex: 100,
                  minWidth: '180px',
                  overflow: 'hidden',
                }}>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => { setShowProfileMenu(false); navigate(profileRoute); }}
                  style={{
                    width: '100%',
                    padding: '10px 16px',
                    textAlign: 'left',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-sm)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}>
                  <Icon name="person" size="small" />
                  {t('legacy.hn_profile_menu_item')}
                </button>
                <button
                  type="button"
                  role="menuitem"
                  id="logout-header-btn"
                  onClick={() => { setShowProfileMenu(false); auth.clearToken(); setProfile(null); navigate(loginRoute); }}
                  style={{
                    width: '100%',
                    padding: '10px 16px',
                    textAlign: 'left',
                    background: 'none',
                    border: 'none',
                    borderTop: '1px solid var(--mac-border)',
                    cursor: 'pointer',
                    color: 'var(--mac-danger, #dc2626)',
                    fontSize: 'var(--mac-font-size-sm)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}>
                  <Icon name="arrow.right.square" size="small" />
                  {t('legacy.hn_logout')}
                </button>
              </div>
            </>
          )}
        </div>
      ) : (
        <Button
          variant="primary"
          size="small"
          onClick={() => navigate(loginRoute)}
          className="hdr-hide-sm"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            flex: '0 0 auto'
          }}>
          <Icon name="person" size="small" style={{ color: 'white' }} />
          <span>{t('legacy.hn_login')}</span>
        </Button>
      )}
    </div>;


  return (
    <div className="app-header" style={headerStyle}>
      <div className="hdr-left" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {backButton}
        {brand}
      </div>
      <div className="hdr-center" style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-4)' }}>
        <GlobalSearchBar />
        {/* PR-50: ⌘K chip — replaced synthetic KeyboardEvent hack with a real
            <button> that dispatches a custom event the CommandPalette listens
            for. Previously dispatched a synthetic keydown event which was
            brittle and conflicted with GlobalSearchBar's own ⌘K handler. */}
        <button
          type="button"
          title={t('legacy.hn_command_palette_title')}
          aria-label={t('legacy.hn_command_palette_aria')}
          onClick={() => {
            // PR-50: dispatch a custom event instead of a synthetic KeyboardEvent
            document.dispatchEvent(new CustomEvent('open-command-palette'));
          }}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '4px 8px',
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-secondary, #6b7280)',
            background: 'var(--mac-surface-secondary, #f3f4f6)',
            border: '1px solid var(--mac-border, #d1d5db)',
            borderRadius: 'var(--mac-radius-sm)',
            cursor: 'pointer',
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
            lineHeight: '1.4',
            userSelect: 'none',
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--mac-surface-hover, #e5e7eb)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--mac-surface-secondary, #f3f4f6)';
          }}
        >
          ⌘K
        </button>
        {roleNav}
      </div>
      <div className="hdr-right" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{controls}</div>
    </div>);

}
