import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import type { CSSProperties } from 'react';
import ReactDOM from 'react-dom';
import { ArrowRight, ChevronLeft, CreditCard, Plus, Stethoscope, User, Sun as LSun, Moon as LMoon, Monitor as LMonitor, Rainbow as LRainbow, Layers as LLayers, Sparkles as LSparkles, Bell as BellIcon, type LucideIcon } from 'lucide-react';
import { useNotificationCenter } from '../../contexts/NotificationCenterContext';
import { useNavigate, useLocation } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth';
import { useTheme } from '../../contexts/ThemeContext';
import CompactConnectionStatus from '../pwa/CompactConnectionStatus';
import { Button } from '../ui/macos';
import LanguageSwitcher from '../LanguageSwitcher';
import GlobalSearchBar from '../search/GlobalSearchBar';
import ChatButton from '../chat/ChatButton';
import { COLOR_SCHEMES } from '../../theme/colorScheme';
import { getCanonicalRouteById, getEffectiveRouteByPath, getRoleHomeRoute } from '../../routing/routeSelectors';
import { HEADER_PORTAL_Z } from '../../theme/zLayers';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const landingRoute = getCanonicalRouteById('landing')?.path || '/';
const loginRoute = getCanonicalRouteById('login')?.path || '/login';
const profileRoute = getCanonicalRouteById('clinical-profile')?.path || '/clinical/profile';
const registrarHomeRoute = getRoleHomeRoute('registrar');

// HDR-FX-1 (P2-3): menus layered INSIDE the sticky header stacking context
// (z-1000 in header-new.css) use small named consts; body portals use
// HEADER_PORTAL_Z from theme/zLayers.ts (single z-strategy for the header).
const PROFILE_OVERLAY_Z = 99;
const PROFILE_MENU_Z = 100;

export function isThemeMenuInteraction(event: { composedPath?: () => EventTarget[]; target: EventTarget | null; }, themeMenuRoot: HTMLElement | null) {
  const path = event.composedPath ? event.composedPath() : [];
  const inRef = Boolean(
    themeMenuRoot &&
    (path.includes(themeMenuRoot) || themeMenuRoot.contains?.(event.target as Node))
  );
  const inMenu = path.some((node) => (node as HTMLElement)?.dataset?.themeMenu === 'true');
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
  const { t: rawT } = useTranslation();  // PR-UI-03b: language handled by LanguageSwitcher
  const t = rawT;

  const [state, setState] = useState(auth.getState());
  const { inboxOpen, setInboxOpen, getUnreadCount } = useNotificationCenter();
  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);  // PR-50: profile dropdown
  const themeMenuRef = useRef<HTMLDivElement | null>(null);
  const themeButtonRef = useRef<HTMLButtonElement | null>(null);
  // HDR-FX-1 (P1-3): the theme menu renders in a body portal, so it needs
  // its own ref for focus management (themeMenuRef only wraps the trigger).
  const themePortalRef = useRef<HTMLDivElement | null>(null);
  // HDR-FX-1 (P1-2): profile menu keyboard/focus management refs.
  const profileButtonRef = useRef<HTMLButtonElement | null>(null);
  const profileMenuRef = useRef<HTMLDivElement | null>(null);
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
    const handleClickOutside = (event: MouseEvent) => {
      if (!isThemeMenuInteraction(event, themeMenuRef.current)) {
        setShowThemeMenu(false);
      }
    };
    document.addEventListener('click', handleClickOutside, true);
    return () => document.removeEventListener('click', handleClickOutside, true);
  }, []);

  // HDR-FX-1 (P1-2): when the profile menu opens, move focus to its first
  // item (WAI-ARIA menu pattern). Previously focus stayed on the trigger and
  // Escape was unreachable: the click-outside overlay was tabIndex={-1}, so
  // its onKeyDown handler could never fire from the keyboard.
  useEffect(() => {
    if (!showProfileMenu) return undefined;
    const raf = requestAnimationFrame(() => {
      profileMenuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    });
    return () => cancelAnimationFrame(raf);
  }, [showProfileMenu]);

  // HDR-FX-1 (P1-3): focus the checked scheme item when the theme menu opens.
  useEffect(() => {
    if (!showThemeMenu) return undefined;
    const raf = requestAnimationFrame(() => {
      const items = Array.from(themePortalRef.current?.querySelectorAll<HTMLElement>('[role="menuitemradio"]') ?? []);
      (items.find((el) => el.getAttribute('aria-checked') === 'true') || items[0])?.focus();
    });
    return () => cancelAnimationFrame(raf);
  }, [showThemeMenu]);

  // HDR-FX-1 (P1-2/P1-3): shared menu keyboard contract — Escape closes and
  // restores trigger focus, ArrowDown/ArrowUp cycle items with wrap-around.
  const handleMenuKeyDown = useCallback(
    (close: () => void, triggerRef: React.RefObject<HTMLElement | null>) =>
      (event: React.KeyboardEvent<HTMLElement>) => {
        if (event.key === 'Escape') {
          event.preventDefault();
          event.stopPropagation();
          close();
          triggerRef.current?.focus();
          return;
        }
        if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
        event.preventDefault();
        const items = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>('[role="menuitem"], [role="menuitemradio"]'),
        );
        if (items.length === 0) return;
        const index = items.indexOf(document.activeElement as HTMLElement);
        const next = event.key === 'ArrowDown'
          ? items[(index + 1) % items.length]
          : items[(index - 1 + items.length) % items.length];
        next.focus();
      },
    [],
  );

  const toggleThemeMenu = useCallback(() => {
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
  }, [showThemeMenu]);

  const handleThemeClick = (schemeId: string) => {
    logger.info('[FIX:THEME] Header theme change requested', {
      currentColorScheme: colorScheme,
      nextColorScheme: schemeId,
    });
    setColorScheme(schemeId);
    // Codex round 4 (P2): the focused menuitemradio is about to unmount —
    // restore the trigger focus BEFORE closing, or keyboard users fall back
    // to <body> and must restart the header tab sequence.
    themeButtonRef.current?.focus();
    setShowThemeMenu(false);
  };

  const renderSchemeIcon = (schemeId: string) => {
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

  const stateTyped = state as unknown as { profile?: Record<string, unknown>; user?: Record<string, unknown> };
  const user = stateTyped.profile || stateTyped.user || null;
  const role = user?.role || user?.role_name || 'Guest';
  const roleLower = String(role).toLowerCase();
  // REC-3: receptionist->registrar normalization removed with the alias —
  // canonical profiles carry 'registrar' directly.
  const roleNormalized = roleLower;
  const currentRoute = getEffectiveRouteByPath(location.pathname);

  // HDR-FX-1 (P2-4, audit P3-5): the CTA belongs to every registrar surface,
  // not only the home route. The old exact-id check hid it on
  // /registrar/welcome|queue, and where it did render off-home the dual-mode
  // navigate branch clobbered the user's current view.
  const isRegistrarSurface = currentRoute?.id === 'registrar-home'
    || currentRoute?.id === 'registrar-welcome'
    || currentRoute?.id === 'registrar-queue';

  // HDR-FX-1 (P2-2 + Codex round 2): unread count for the bell, computed
  // once. The polite live region must be a SIBLING of the bell button —
  // button descendants are flattened as presentational in the accessibility
  // tree, so a role="status" inside it may never be announced.
  const bellRole = user ? String(user?.role || user?.role_name || '').toLowerCase() : '';
  // REC-3: receptionist normalization removed with the alias.
  const bellCount = user ? getUnreadCount(bellRole) : 0;

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
    const items: Array<{ to: string; label: string; icon: LucideIcon }> = [];
    if (roleNormalized !== 'admin') {
      // PR-UI-04b: cashier home button removed from header — now in canonical Sidebar
      // via SIDEBAR_PRESETS.cashier. Cross-role navigation (registrar → cashier)
      // is still available here for roles that don't have their own sidebar.
      if (roleNormalized === 'registrar') items.push({ to: getRoleHomeRoute('cashier'), label: t('legacy.hn_nav_cashier_role'), icon: CreditCard });
    }
    return items;
  }, [roleNormalized]);


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
      <ChevronLeft size={16} aria-hidden="true" style={{ color: 'var(--mac-text-primary)' }} />
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

      <Stethoscope size={20} aria-hidden="true" style={{ color: 'var(--mac-accent-blue)' }} />
      <span className="hdr-hide-xs">{t('legacy.hn_brand_text')}</span>
    </Button>;


  // HDR-FX-1 (P1-1): this cluster never compresses on desktop (flexShrink is
  // owned by .hdr-nav-scroll in header-new.css — a <=900px media query trades
  // it for shrink+pan where the center column is starved).
  const roleNav =
  <div className="hdr-nav-scroll" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'nowrap', whiteSpace: 'nowrap' }}>
      {navItems.map((item) => {
      const active = location.pathname === item.to;
      const ItemIcon = item.icon;
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

            <ItemIcon size={16} aria-hidden="true" style={{ color: active ? 'white' : theme === 'dark' ? 'rgba(255,255,255,0.85)' : 'var(--mac-text-primary)' }} />
            {/* HDR-FX-1 (P1-1): label collapses to icon-only below 1200px. */}
            <span className="hdr-hide-nav-label">{item.label}</span>
          </Button>);

    })}

      {roleNormalized === 'registrar' && isRegistrarSurface &&
    <>
          {/* PR-UI-04: removed hardcoded "Home" and "Queue" nav buttons —
              they're now in canonical Sidebar via SIDEBAR_PRESETS.registrar.
              Kept only the "New appointment" CTA — it's a primary action, not navigation. */}
          <Button
        variant="primary"
        size="small"
        title={t('legacy.hn_new_appointment_title')}
        onClick={() => {
          // HDR-FX-1 (P2-4): uniform behavior on every registrar surface —
          // dispatch the wizard event in place (the useRegistrarNavigation
          // listener is mounted on all three /registrar/* routes), so the
          // user's current view is preserved. Only off-surface falls back to
          // the P-008 deep link (?action=new is consumed on mount).
          if (isRegistrarSurface) {
            window.dispatchEvent(new CustomEvent('openAppointmentWizard'));
          } else {
            navigate(`${registrarHomeRoute}?action=new`);
          }
        }}
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', flexShrink: 0 }}>

            <Plus size={16} aria-hidden="true" style={{ color: 'white' }} />
            {/* HDR-FX-1 (P1-1): label collapses to icon-only below 1200px
                (replaces hdr-hide-md — its 1024px boundary left the
                1025-1310px dead zone where the CTA text clipped). */}
            <span className="hdr-hide-nav-label">{t('legacy.hn_new_appointment_title')}</span>
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

      {/* 1) Язык — PR-UI-03b: replaced inline <select> with canonical LanguageSwitcher
          component (dropdown UI with flags + nativeName). LanguageSwitcher uses
          useTranslation().setLanguage() directly — no local state duplication. */}
      <LanguageSwitcher compact />

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
          {/* HDR-FX-1 (P2-2 + Codex round 3): the live region stays MOUNTED
              for every count including zero — assistive tech announces text
              mutations inside an existing region, not region insertion, so
              conditional mounting would silence both boundary transitions. */}
          <span role="status" className="sr-only">
            {t('legacy.hn_notifications_unread', { count: bellCount })}
          </span>
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
            {bellCount > 0 &&
              <span aria-hidden="true" style={{
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
                {bellCount > 99 ? '99+' : bellCount}
              </span>
            }
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
          onClick={toggleThemeMenu}
          onKeyDown={(e: React.KeyboardEvent<HTMLElement>) => {
            // HDR-FX-1 (P1-3): trigger-level keyboard contract — ArrowDown
            // opens, Escape closes (focus stays on the trigger).
            if (e.key === 'ArrowDown' && !showThemeMenu) {
              e.preventDefault();
              toggleThemeMenu();
            } else if (e.key === 'Escape' && showThemeMenu) {
              e.preventDefault();
              setShowThemeMenu(false);
            }
          }}
          title={t('legacy.hn_select_theme')}
          aria-label={t('legacy.hn_select_theme')}
          aria-haspopup="menu"
          aria-expanded={showThemeMenu}
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
            ref={themePortalRef}
            data-theme-menu="true"
            role="menu"
            aria-label={t('legacy.hn_select_theme')}
            // Focus lives on the items (menuitemradio); tabIndex={-1} keeps the
            // container programmatically focusable without tab stops (a11y lint).
            tabIndex={-1}
            onKeyDown={handleMenuKeyDown(() => setShowThemeMenu(false), themeButtonRef)}
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
              zIndex: HEADER_PORTAL_Z,
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
              role="menuitemradio"
              aria-checked={colorScheme === scheme.id}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
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
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';}}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {e.currentTarget.style.backgroundColor = 'transparent';}}>

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
            ref={profileButtonRef}
            variant="outline"
            size="small"
            onClick={() => setShowProfileMenu((v) => !v)}
            onKeyDown={(e: React.KeyboardEvent<HTMLElement>) => {
            // HDR-FX-1 (P1-2): trigger-level keyboard contract — ArrowDown
            // opens (focus then moves to the first item), Escape closes.
            if (e.key === 'ArrowDown' && !showProfileMenu) {
              e.preventDefault();
              setShowProfileMenu(true);
            } else if (e.key === 'Escape' && showProfileMenu) {
              e.preventDefault();
              setShowProfileMenu(false);
            }
          }}
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
            <User size={16} aria-hidden="true" style={{ color: 'var(--mac-text-primary)' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>
              {String(user?.full_name ?? '') || String(user?.username ?? '') || t('legacy.hn_profile_fallback')}
            </span>
          </Button>
          {showProfileMenu && (
            <>
              {/* click-outside overlay — HDR-FX-1 (P1-2): decorative,
                  non-focusable click-catcher. The old role="button" +
                  tabIndex={-1} + onKeyDown combo was dead weight: the overlay
                  can never receive focus, so its Escape handler was
                  unreachable; Escape now lives on the trigger and the menu. */}
              <div
                onClick={() => setShowProfileMenu(false)}
                aria-hidden="true"
                style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: PROFILE_OVERLAY_Z }}
              />
              <div
                ref={profileMenuRef}
                role="menu"
                aria-label={t('legacy.hn_profile_menu')}
                // Focus lives on the menuitem children; tabIndex={-1} satisfies
                // interactive-supports-focus without adding a tab stop.
                tabIndex={-1}
                onKeyDown={handleMenuKeyDown(() => setShowProfileMenu(false), profileButtonRef)}
                style={{
                  position: 'absolute',
                  top: '100%',
                  right: 0,
                  marginTop: '4px',
                  backgroundColor: 'var(--mac-bg-primary)',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  boxShadow: 'var(--mac-shadow-md)',
                  zIndex: PROFILE_MENU_Z,
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
                  <User size={16} aria-hidden="true" />
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
                  <ArrowRight size={16} aria-hidden="true" />
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
          <User size={16} aria-hidden="true" style={{ color: 'white' }} />
          <span>{t('legacy.hn_login')}</span>
        </Button>
      )}
    </div>;


  return (
    <header className="app-header" style={headerStyle}>
      <div className="hdr-left" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {backButton}
        {brand}
      </div>
      <div className="hdr-center" style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-4)' }}>
        {/* HDR-FX-1 (P1-1): the search bar is the designated shrivable item —
            it absorbs center-column squeeze first (basis = its own 400px
            maxWidth) so the roleNav cluster and the CTA never clip. Styles
            live in .hdr-search-shrink (header-new.css) — the UI ratchet
            counts inline style objects, so none is added here. */}
        <div className="hdr-search-shrink">
          <GlobalSearchBar />
        </div>
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
            // AXE-EXP-2: the previous background var(--mac-surface-secondary,
            // #f3f4f6) resolved to the LIGHT literal in both themes (the
            // token is not defined anywhere) — in dark the ink fell to
            // dark secondary #98989d on the light surface = 2.6:1. Now a
            // themed tertiary surface + the on-tertiary ink (5.71:1 light /
            // 6.74:1 dark).
            color: 'var(--mac-text-on-tertiary, #455568)',
            background: 'var(--mac-bg-tertiary, #d7e1ee)',
            border: '1px solid var(--mac-border, #d1d5db)',
            borderRadius: 'var(--mac-radius-sm)',
            cursor: 'pointer',
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
            lineHeight: '1.4',
            userSelect: 'none',
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary, #e3ebf5)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-tertiary, #d7e1ee)';
          }}
        >
          ⌘K
        </button>
        {roleNav}
      </div>
      <div className="hdr-right" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{controls}</div>
    </header>);

}
