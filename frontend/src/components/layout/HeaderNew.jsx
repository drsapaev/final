import React, { useEffect, useMemo, useState, useRef } from 'react';
import ReactDOM from 'react-dom';
import { Sun as LSun, Moon as LMoon, Monitor as LMonitor, Rainbow as LRainbow, Layers as LLayers, Sparkles as LSparkles } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth.js';
import { useTheme } from '../../contexts/ThemeContext.jsx';
import CompactConnectionStatus from '../pwa/CompactConnectionStatus';
import { Button, Icon } from '../ui/macos';
import GlobalSearchBar from '../search/GlobalSearchBar';
import ChatButton from '../chat/ChatButton';

import logger from '../../utils/logger';
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

  const { theme, toggleTheme, setTheme } = useTheme();

  // Color schemes list (иконки соответствуют ColorSchemeSelector)
  const colorSchemes = [
    { id: 'light', name: 'Светлая', icon: 'sun' },
    { id: 'dark', name: 'Темная', icon: 'moon' },
    { id: 'auto', name: 'Авто', icon: 'monitor' },
    { id: 'vibrant', name: 'Яркая многоцветная', icon: 'rainbow' }, // Rainbow из ColorSchemeSelector
    { id: 'glass', name: 'Полупрозрачная стеклянная', icon: 'layers' }, // Layers из ColorSchemeSelector
    { id: 'gradient', name: 'Градиентная палитра', icon: 'sparkles' } // Sparkles из ColorSchemeSelector
  ];

  // Close theme menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      const path = event.composedPath ? event.composedPath() : [];
      const inRef = themeMenuRef.current && (path.includes(themeMenuRef.current) || themeMenuRef.current.contains(event.target));
      const inMenu = !!(event.target && event.target.closest && event.target.closest('[data-theme-menu="true"]'));
      const inside = inRef || inMenu;
      if (!inside) {
        setShowThemeMenu(false);
      }
    };
    document.addEventListener('click', handleClickOutside, true);
    return () => document.removeEventListener('click', handleClickOutside, true);
  }, []);

  // Apply color scheme
  const applyColorScheme = (schemeId) => {
    const root = document.documentElement;
    document.body.classList.remove('light-theme', 'dark-theme');
    root.removeAttribute('data-theme');

    if (schemeId === 'vibrant') {
      // Матовые приглушённые цвета
      root.style.setProperty('--mac-bg-primary', '#6b8db3'); /* Приглушённый синий */
      root.style.setProperty('--mac-bg-secondary', '#7fa899'); /* Приглушённый бирюзовый */
      root.style.setProperty('--mac-accent-blue', '#d4a063'); /* Приглушённый оранжевый */
      root.style.setProperty('--mac-text-primary', '#ffffff');
      root.style.setProperty('--mac-text-secondary', 'rgba(255,255,255,0.92)');
      root.style.setProperty('--mac-gradient-window', 'linear-gradient(135deg, rgba(107, 141, 179, 0.75) 0%, rgba(127, 168, 153, 0.7) 40%, rgba(212, 160, 99, 0.65) 80%), linear-gradient(135deg, rgba(120, 130, 145, 0.3) 0%, rgba(130, 140, 150, 0.25) 100%)');
      root.style.setProperty('--mac-gradient-sidebar', 'linear-gradient(135deg, rgba(100, 130, 165, 0.7) 0%, rgba(115, 155, 140, 0.65) 45%, rgba(200, 150, 90, 0.6) 100%), linear-gradient(135deg, rgba(130, 140, 150, 0.25) 0%, rgba(140, 150, 160, 0.2) 100%)');
      root.style.setProperty('--bg', '#6b8db3');
      root.style.setProperty('--mac-bg-toolbar', 'rgba(30, 35, 45, 0.4)');
      root.style.setProperty('--mac-separator', 'rgba(255,255,255,0.22)');
      root.style.setProperty('--mac-border', 'rgba(255,255,255,0.22)');
      root.style.setProperty('--mac-border-secondary', 'rgba(255,255,255,0.18)');
      root.setAttribute('data-color-scheme', 'vibrant');
    } else if (schemeId === 'glass') {
      // Синхронизировано с macos.css [data-color-scheme="glass"]
      // Улучшенные значения для лучшей видимости карточек
      root.style.setProperty('--mac-bg-primary', 'rgba(50, 55, 65, 0.75)');
      root.style.setProperty('--mac-bg-secondary', 'rgba(60, 65, 75, 0.65)');
      root.style.setProperty('--mac-bg-toolbar', 'rgba(50, 55, 65, 0.85)'); /* Увеличенная непрозрачность для хедера */
      root.style.setProperty('--mac-bg-tertiary', 'rgba(70, 75, 85, 0.55)');
      root.style.setProperty('--mac-accent-blue', 'rgba(0,122,255,0.8)');
      root.style.setProperty('--mac-text-primary', '#f0f1f5');
      root.style.setProperty('--mac-text-secondary', 'rgba(240,240,245,0.9)');
      root.style.setProperty('--mac-border', 'rgba(255, 255, 255, 0.2)');
      root.style.setProperty('--mac-border-secondary', 'rgba(255, 255, 255, 0.15)');
      root.style.setProperty('--mac-blur-light', 'saturate(180%) blur(22px)');
      root.style.setProperty('--surface', 'rgba(255,255,255,0.25)');
      root.style.setProperty('--bg', '#f6f7f9');
      // Очищаем градиент из предыдущих тем
      root.style.setProperty('--mac-gradient-window', 'none');
      // Применяем фон и backdrop-filter на html и body
      document.documentElement.style.background = 'rgba(20, 20, 25, 0.3)';
      document.documentElement.style.backdropFilter = 'blur(22px) saturate(160%)';
      document.documentElement.style.webkitBackdropFilter = 'blur(22px) saturate(160%)';
      document.body.style.background = 'rgba(20, 20, 25, 0.3)';
      document.body.style.backdropFilter = 'blur(22px) saturate(160%)';
      document.body.style.webkitBackdropFilter = 'blur(22px) saturate(160%)';
      root.setAttribute('data-color-scheme', 'glass');
    } else if (schemeId === 'gradient') {
      root.style.setProperty('--mac-bg-primary', '#667eea');
      root.style.setProperty('--mac-bg-secondary', '#764ba2');
      root.style.setProperty('--mac-accent-blue', '#f093fb');
      root.style.setProperty('--mac-text-primary', '#ffffff');
      root.style.setProperty('--mac-text-secondary', 'rgba(255,255,255,0.9)');
      root.style.setProperty('--mac-gradient-window', 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)');
      root.style.setProperty('--bg', '#667eea');
      root.style.setProperty('--mac-bg-toolbar', '#667eea');
      // Сброс стеклянных эффектов при переходе из Glass
      document.documentElement.style.background = '';
      document.documentElement.style.backdropFilter = '';
      document.documentElement.style.webkitBackdropFilter = '';
      document.body.style.background = '';
      document.body.style.backdropFilter = '';
      document.body.style.webkitBackdropFilter = '';
      root.setAttribute('data-color-scheme', 'gradient');
    }

    setShowThemeMenu(false);
  };

  const getCurrentScheme = () => {
    const savedScheme = localStorage.getItem('colorScheme') || localStorage.getItem('activeColorSchemeId');
    if (savedScheme && ['vibrant', 'glass', 'gradient'].includes(savedScheme)) {
      return savedScheme;
    }
    return theme;
  };

  const handleThemeClick = (schemeId) => {
    logger.log('🔥 Theme clicked:', schemeId);
    logger.log('Current theme state:', theme);

    if (schemeId === 'vibrant' || schemeId === 'glass' || schemeId === 'gradient') {
      logger.log('Applying custom scheme:', schemeId);
      // Set flags BEFORE applying to prevent ThemeContext override
      localStorage.setItem('customColorScheme', 'true');
      localStorage.setItem('activeColorSchemeId', schemeId);
      localStorage.setItem('colorScheme', schemeId);
      // Apply custom color scheme
      applyColorScheme(schemeId);
      // Broadcast to other tabs/components
      window.dispatchEvent(new CustomEvent('colorSchemeChanged', { detail: schemeId }));
    } else {
      logger.log('Applying standard theme:', schemeId);

      // Clear custom schemes FIRST
      logger.log('Clearing custom scheme flags');
      localStorage.removeItem('customColorScheme');
      localStorage.removeItem('activeColorSchemeId');

      // Apply standard themes
      let targetTheme = schemeId;

      if (schemeId === 'auto') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        targetTheme = prefersDark ? 'dark' : 'light';
        logger.log('Auto theme detected:', targetTheme);
      }

      logger.log('Setting theme to:', targetTheme);
      localStorage.setItem('ui_theme', targetTheme);
      localStorage.setItem('theme', targetTheme);
      localStorage.setItem('colorScheme', schemeId);

      // Force update DOM immediately BEFORE setTheme to prevent race condition
      logger.log('Updating DOM attributes');
      document.body.classList.remove('light-theme', 'dark-theme');
      document.body.classList.add(`${targetTheme}-theme`);
      document.documentElement.setAttribute('data-theme', targetTheme);
      document.documentElement.removeAttribute('data-color-scheme');

      // Call setTheme AFTER DOM updates
      setTheme(targetTheme);
      // Broadcast selected scheme id (light/dark/auto)
      window.dispatchEvent(new CustomEvent('colorSchemeChanged', { detail: schemeId }));
    }

    setShowThemeMenu(false);
    logger.log('Theme change completed');
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

  // Принудительная перерисовка при смене темы
  const [themeKey, setThemeKey] = useState(0);
  useEffect(() => {
    setThemeKey(prev => prev + 1);
  }, [theme]);

  const user = state.profile || state.user || null;
  const role = (user?.role || user?.role_name || 'Guest');
  const roleLower = String(role).toLowerCase();
  // Normalize receptionist to registrar for UI consistency
  const roleNormalized = roleLower === 'receptionist' ? 'registrar' : roleLower;

  const isRegistrarPanel = location.pathname === '/registrar-panel';

  // Определяем активную кастомную схему
  const activeColorScheme = document.documentElement.getAttribute('data-color-scheme');
  const isGlassTheme = activeColorScheme === 'glass';
  const isGradientTheme = activeColorScheme === 'gradient';
  const isVibrantTheme = activeColorScheme === 'vibrant';
  const isCustomTheme = isGlassTheme || isGradientTheme || isVibrantTheme;

  const headerStyle = {
    backgroundColor: isGlassTheme
      ? 'rgba(50, 55, 65, 0.85)'
      : (isGradientTheme || isVibrantTheme
        ? 'var(--mac-bg-toolbar)'
        : (theme === 'dark' ? 'rgba(21,23,28,0.78)' : 'var(--mac-bg-toolbar)')),
    borderBottom: isGlassTheme
      ? '1px solid rgba(255,255,255,0.25)'
      : (isGradientTheme || isVibrantTheme
        ? '1px solid var(--mac-separator)'
        : (theme === 'dark' ? '1px solid rgba(255,255,255,0.12)' : '1px solid var(--mac-separator)')),
    backdropFilter: 'var(--mac-blur-light)',
    WebkitBackdropFilter: 'var(--mac-blur-light)',
    boxShadow: isGlassTheme
      ? '0 2px 10px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.1)'
      : (isGradientTheme || isVibrantTheme
        ? 'var(--mac-shadow-sm)'
        : (theme === 'dark'
          ? '0 2px 10px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.06)'
          : 'var(--mac-shadow-sm)')),
    display: 'grid',
    gridTemplateColumns: 'auto 1fr auto',
    alignItems: 'center',
    columnGap: '12px',
    overflow: 'visible',
    borderRadius: 'var(--mac-radius-md)',
    padding: '0 16px',
    height: '54px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    backgroundImage: isGlassTheme
      ? 'none'
      : (isGradientTheme || isVibrantTheme
        ? 'none'
        : (theme === 'dark' ? 'linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0))' : 'none'))
  };

  // Навигация по ролям (как в исходном хедере)
  const navItems = useMemo(() => {
    const items = [];
    if (roleNormalized !== 'admin') {
      if (roleNormalized === 'registrar') items.push({ to: '/cashier-panel', label: 'Кассир', icon: 'creditcard' });
      if (roleNormalized === 'cashier') items.push({ to: '/cashier-panel', label: 'Касса', icon: 'creditcard' });
    }
    return items;
  }, [roleNormalized]);

  const changeLang = (v) => {
    setLang(v);
    localStorage.setItem('lang', v);
  };

  const brand = (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => navigate('/')}
      title="На главную"
      style={{
        color: 'var(--mac-text-primary)',
        fontWeight: '700',
        fontSize: 'var(--mac-font-size-lg)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px'
      }}
    >
      <Icon name="stethoscope" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
      <span className="hdr-hide-xs">Clinic Management</span>
    </Button>
  );

  const roleNav = (
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
              gap: '6px',
              flexShrink: 0,
              color: active
                ? 'white'
                : (theme === 'dark' ? 'rgba(255,255,255,0.9)' : 'var(--mac-text-primary)')
            }}
          >
            <Icon name={item.icon} size="small" style={{ color: active ? 'white' : (theme === 'dark' ? 'rgba(255,255,255,0.85)' : 'var(--mac-text-primary)') }} />
            <span className="hdr-hide-sm">{item.label}</span>
          </Button>
        );
      })}

      {roleNormalized === 'registrar' && isRegistrarPanel && (
        <>
          <Button
            variant="outline"
            size="small"
            title="Главная"
            onClick={() => navigate('/registrar-panel?view=welcome')}
            className="hdr-hide-md"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0, color: theme === 'dark' ? 'rgba(255,255,255,0.9)' : undefined }}
          >
            <Icon name="house" size="small" style={{ color: theme === 'dark' ? 'rgba(255,255,255,0.85)' : undefined }} />
            <span className="hdr-hide-md">Главная</span>
          </Button>
          <Button
            variant="outline"
            size="small"
            title="Онлайн‑записи"
            onClick={() => navigate('/registrar-panel?view=queue')}
            className="hdr-hide-xs"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0, color: theme === 'dark' ? 'rgba(255,255,255,0.9)' : undefined }}
          >
            <Icon name="bell" size="small" style={{ color: theme === 'dark' ? 'rgba(255,255,255,0.85)' : 'var(--mac-text-primary)' }} />
            <span className="hdr-hide-sm">Онлайн‑записи</span>
          </Button>
          <Button
            variant="primary"
            size="small"
            title="Новая запись"
            onClick={() => {
              // Отправляем событие для открытия мастера записи
              window.dispatchEvent(new CustomEvent('openAppointmentWizard'));
            }}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}
          >
            <Icon name="plus" size="small" style={{ color: 'white' }} />
            <span className="hdr-hide-md">Новая запись</span>
          </Button>
        </>
      )}
    </div>
  );

  const controls = (
    <div className="hdr-controls" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'nowrap', whiteSpace: 'nowrap' }}>
      {/* divider for clearer separation in dark mode */}
      <div
        aria-hidden
        style={{
          width: 1,
          alignSelf: 'stretch',
          background: theme === 'dark' ? 'rgba(255,255,255,0.08)' : 'var(--mac-separator)'
        }}
      />
      {/* 1) Язык */}
      <Button
        variant="ghost"
        size="small"
        onClick={() => changeLang(lang === 'ru' ? 'uz' : lang === 'uz' ? 'en' : 'ru')}
        title={`Switch to ${lang === 'ru' ? 'UZ' : lang === 'uz' ? 'EN' : 'RU'}`}
        style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: '600',
          padding: '6px 10px',
          flex: '0 0 auto',
          border: theme === 'dark' ? '1px solid rgba(255,255,255,0.14)' : '1px solid var(--mac-border)',
          display: 'flex',
          alignItems: 'center',
          gap: '4px'
        }}
      >
        <Icon name="magnifyingglass" size="small" />
        {lang.toUpperCase()}
      </Button>

      {/* 2) Сеть */}
      <div style={{ flex: '0 0 auto' }}>
        <CompactConnectionStatus className="mr-2" />
      </div>

      {/* 2.5) Чат */}
      {user && (
        <div style={{ flex: '0 0 auto' }}>
          <ChatButton />
        </div>
      )}

      {/* 3) Тема */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', flex: '0 0 auto' }} key={themeKey}>
        <div ref={themeMenuRef} style={{ position: 'relative', display: 'flex', alignItems: 'center', width: '100%', height: '100%' }}>
          <Button
            ref={themeButtonRef}
            variant="ghost"
            size="small"
            onClick={(e) => {
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
              } catch { }
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
            }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--mac-text-primary)' }}>
              {renderSchemeIcon(getCurrentScheme())}
            </span>
          </Button>

          {/* Theme Menu Dropdown */}
          {showThemeMenu ? (
            ReactDOM.createPortal(
              <div
                data-theme-menu="true"
                onClick={(e) => {
                  e.stopPropagation();
                }}
                style={{
                  position: 'fixed',
                  left: `${menuPos.left}px`,
                  top: `${menuPos.top}px`,
                  backgroundColor: isCustomTheme ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  padding: '8px',
                  minWidth: '220px',
                  boxShadow: 'var(--mac-shadow-md, 0 8px 24px rgba(0,0,0,0.2))',
                  zIndex: 2147483647,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  pointerEvents: 'auto',
                  color: 'var(--mac-text-primary)'
                }}
              >
                {colorSchemes.map((scheme) => (
                  <div
                    key={scheme.id}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleThemeClick(scheme.id);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 12px',
                      borderRadius: 'var(--mac-radius-sm)',
                      background: 'transparent',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--mac-accent-blue)' }}>
                      {renderSchemeIcon(scheme.id)}
                    </span>
                    <span style={{ color: 'var(--mac-text-primary)' }}>{scheme.name}</span>
                  </div>
                ))}
              </div>,
              document.body
            )
          ) : null}
        </div>
      </div>

      {/* 4) Профиль / Войти */}
      {user ? (
        <>
          <Button
            variant="outline"
            size="small"
            onClick={() => navigate('/profile')}
            title="Профиль пользователя"
            className="hdr-hide-sm"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flex: '0 0 auto'
            }}
          >
            <Icon name="person" size="small" style={{ color: 'var(--mac-text-primary)' }} />
            <span style={{ fontWeight: 600 }}>
              {user.full_name || user.username || 'Профиль'}
            </span>
          </Button>

          {/* 5) Выход */}
          <Button
            id="logout-header-btn"
            variant="danger"
            size="small"
            onClick={() => { auth.clearToken(); setProfile(null); navigate('/login'); }}
            title="Выйти"
            className="hdr-hide-sm"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flex: '0 0 auto'
            }}
          >
            <Icon name="person" size="small" style={{ color: 'white' }} />
            <span>Выйти</span>
          </Button>
        </>
      ) : (
        <Button
          variant="primary"
          size="small"
          onClick={() => navigate('/login')}
          className="hdr-hide-sm"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            flex: '0 0 auto'
          }}
        >
          <Icon name="person" size="small" style={{ color: 'white' }} />
          <span>Войти</span>
        </Button>
      )}
    </div>
  );

  return (
    <div className="app-header" style={headerStyle}>
      <div className="hdr-left" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{brand}</div>
      <div className="hdr-center" style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: '16px' }}>
        <GlobalSearchBar />
        {roleNav}
      </div>
      <div className="hdr-right" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{controls}</div>
    </div>
  );
}




