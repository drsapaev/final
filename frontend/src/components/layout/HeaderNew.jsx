import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { Sun as LSun, Moon as LMoon, Monitor as LMonitor, Rainbow as LRainbow, Layers as LLayers, Sparkles as LSparkles } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth.js';
import { useTheme } from '../../contexts/ThemeContext.jsx';
import CompactConnectionStatus from '../pwa/CompactConnectionStatus';
import {
  Button, Icon,
} from '../ui/macos';
import GlobalSearchBar from '../search/GlobalSearchBar';
import ChatButton from '../chat/ChatButton';
import { COLOR_SCHEMES } from '../../theme/colorScheme.js';
import { getCanonicalRouteById, getEffectiveRouteByPath, getRoleHomeRoute } from '../../routing/routeSelectors.js';

import logger from '../../utils/logger';

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

  const [state, setState] = useState(auth.getState());
  const [lang, setLang] = useState(localStorage.getItem('lang') || 'ru');
  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const themeMenuRef = useRef(null);
  const themeButtonRef = useRef(null);
  const [menuPos, setMenuPos] = useState({ left: 0, top: 0 });

  useEffect(() => auth.subscribe(setState), []);

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

  const user = state.profile || state.user || null;
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
      if (roleNormalized === 'registrar') items.push({ to: getRoleHomeRoute('cashier'), label: 'Кассир', icon: 'creditcard' });
      if (roleNormalized === 'cashier') items.push({ to: getRoleHomeRoute('cashier'), label: 'Касса', icon: 'creditcard' });
    }
    return items;
  }, [roleNormalized]);

  const changeLang = (v) => {
    setLang(v);
    localStorage.setItem('lang', v);
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
      size="sm"
      onClick={handleBack}
      title="Назад"
      aria-label="Назад"
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
    size="sm"
    onClick={() => navigate(landingRoute)}
    title="На главную"
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
      <span className="hdr-hide-xs">Управление клиникой</span>
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
        title="Главная"
        onClick={() => navigate('/registrar/welcome')}
        className="hdr-hide-md"
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', flexShrink: 0, color: theme === 'dark' ? 'color-mix(in srgb, white, transparent 10%)' : undefined }}>

            <Icon name="house" size="small" style={{ color: theme === 'dark' ? 'rgba(255,255,255,0.85)' : undefined }} />
            <span className="hdr-hide-md">Главная</span>
          </Button>
          <Button
        variant="outline"
        size="small"
        title="Онлайн‑записи"
        onClick={() => navigate('/registrar/queue')}
        className="hdr-hide-xs"
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', flexShrink: 0, color: theme === 'dark' ? 'color-mix(in srgb, white, transparent 10%)' : undefined }}>

            <Icon name="bell" size="small" style={{ color: theme === 'dark' ? 'rgba(255,255,255,0.85)' : 'var(--mac-text-primary)' }} />
            <span className="hdr-hide-sm">Онлайн‑записи</span>
          </Button>
          <Button
        variant="primary"
        size="small"
        title="Новая запись"
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
            <span className="hdr-hide-md">Новая запись</span>
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

      {/* 1) Язык */}
      <Button
      variant="ghost"
      size="small"
      onClick={() => changeLang(lang === 'ru' ? 'uz' : lang === 'uz' ? 'en' : 'ru')}
      title={`Switch to ${lang === 'ru' ? 'UZ' : lang === 'uz' ? 'EN' : 'RU'}`}
      style={{
        fontSize: 'var(--mac-font-size-sm)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        padding: '6px 10px',
        flex: '0 0 auto',
        border: theme === 'dark' ? '1px solid rgba(255,255,255,0.14)' : '1px solid var(--mac-border)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-1)'
      }}>

        <Icon name="globe" size="small" />
        {lang.toUpperCase()}
      </Button>

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
          title="Выбрать тему"
          aria-label="Выбрать тему"
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

      {/* 4) Профиль / Войти */}
      {user ?
    <>
          <Button
        variant="outline"
        size="small"
        onClick={() => navigate(profileRoute)}
        title="Профиль пользователя"
        className="hdr-hide-sm"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)',
          flex: '0 0 auto'
        }}>

            <Icon name="person" size="small" style={{ color: 'var(--mac-text-primary)' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>
              {user.full_name || user.username || 'Профиль'}
            </span>
          </Button>

          {/* 5) Выход */}
          <Button
        id="logout-header-btn"
        variant="danger"
        size="small"
        onClick={() => {auth.clearToken();setProfile(null);navigate(loginRoute);}}
        title="Выйти"
        className="hdr-hide-sm"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)',
          flex: '0 0 auto'
        }}>

            <Icon name="person" size="small" style={{ color: 'white' }} />
            <span>Выйти</span>
          </Button>
        </> :

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
          <span>Войти</span>
        </Button>
    }
    </div>;


  return (
    <div className="app-header" style={headerStyle}>
      <div className="hdr-left" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {backButton}
        {brand}
      </div>
      <div className="hdr-center" style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-4)' }}>
        <GlobalSearchBar />
        {/* P-027 (UX audit): surface the Cmd+K shortcut so power-users
            discover the CommandPalette without reading docs. */}
        <kbd
          role="button"
          tabIndex={0}
          title="Открыть командную палитру (Cmd+K / Ctrl+K)"
          aria-label="Открыть командную палитру (Cmd+K или Ctrl+K)"
          onClick={() => {
            // Dispatch a keyboard event to trigger the CommandPalette's
            // global listener. This is simpler than importing the component.
            const isMac = navigator.platform.toUpperCase().includes('MAC');
            const event = new KeyboardEvent('keydown', {
              key: 'k',
              metaKey: isMac,
              ctrlKey: !isMac,
              bubbles: true,
            });
            document.dispatchEvent(event);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              const isMac = navigator.platform.toUpperCase().includes('MAC');
              const event = new KeyboardEvent('keydown', {
                key: 'k',
                metaKey: isMac,
                ctrlKey: !isMac,
                bubbles: true,
              });
              document.dispatchEvent(event);
            }
          }}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '2px 8px',
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
        </kbd>
        {roleNav}
      </div>
      <div className="hdr-right" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{controls}</div>
    </div>);

}
