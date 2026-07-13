import { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import Icon from '../Icon';
import { useTheme } from '../../contexts/ThemeContext';
import auth from '../../stores/auth.js';
import '../../styles/sidebar-buttons.css';
import '../../styles/cursor-effects.css';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';

/**
 * Унифицированный сайдбар в стиле MediLab
 * Используется во всех панелях для единообразия
 */
const UnifiedSidebar = ({ isCollapsed = false, onToggle }) => {
  const asideRef = useRef(null);
  const location = useLocation();
  const { isDark, toggleTheme } = useTheme();
  const [language, setLanguage] = useState('en');

  // Локально дублируем активную схему на контейнер сайдбара, чтобы исключить зависимость от <html>
  useEffect(() => {
    const applyLocalScheme = () => {
      try {
        const customScheme = localStorage.getItem('customColorScheme');
        const schemeId = localStorage.getItem('activeColorSchemeId');
        const el = asideRef.current;
        if (!el) return;
        if (customScheme === 'true' && schemeId) {
          el.setAttribute('data-color-scheme', schemeId);
        } else {
          el.removeAttribute('data-color-scheme');
        }
      } catch (error) {
        logger.debug('Failed to apply local color scheme for sidebar', error);
      }
    };
    applyLocalScheme();
    const handler = () => applyLocalScheme();
    window.addEventListener('colorSchemeChanged', handler);
    window.addEventListener('storage', handler);
    document.addEventListener('visibilitychange', handler);
    window.addEventListener('focus', handler);
    window.addEventListener('pageshow', handler);
    return () => {
      window.removeEventListener('colorSchemeChanged', handler);
      window.removeEventListener('storage', handler);
      document.removeEventListener('visibilitychange', handler);
      window.removeEventListener('focus', handler);
      window.removeEventListener('pageshow', handler);
    };
  }, []);

  // Функции переключения
  const handleThemeToggle = () => {
    if (toggleTheme) {
      toggleTheme();
    }
  };

  const handleLanguageToggle = () => {
    setLanguage((prev) => prev === 'en' ? 'ru' : 'en');
  };

  const st = auth.getState();
  const profile = st.profile || st.user || {};

  // Для демо-страницы используем роль admin по умолчанию
  const isDemoPage = location.pathname.startsWith('/medilab-demo');
  const role = isDemoPage ? 'admin' : String(profile?.role || profile?.role_name || '').toLowerCase();

  // Основные навигационные элементы
  const mainNavItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      iconName: 'LayoutDashboard',
      path: 'dashboard',
      roles: ['admin', 'doctor', 'registrar', 'cashier', 'lab']
    },
    {
      id: 'patients',
      label: 'Patients',
      iconName: 'Users',
      path: 'patients',
      roles: ['admin', 'doctor', 'registrar', 'cashier', 'lab']
    },
    {
      id: 'appointments',
      label: 'Appointments',
      iconName: 'Calendar',
      path: 'appointments',
      roles: ['admin', 'doctor', 'registrar', 'cashier', 'lab']
    },
    {
      id: 'staff-schedule',
      label: 'Staff Schedule',
      iconName: 'Clock',
      path: 'staff-schedule',
      roles: ['admin', 'doctor', 'registrar', 'cashier', 'lab']
    }
  ];


  // Дополнительные элементы: в demo-режиме они не нужны
  const additionalItems = [];


  // Фильтруем элементы по роли пользователя
  const getVisibleItems = (items) => {
    // Для демо-страницы показываем все элементы
    if (isDemoPage) {
      return items;
    }

    const filtered = items.filter((item) =>
    item.roles.includes(role) || item.roles.includes('all')
    );

    return filtered;
  };

  const visibleMainItems = getVisibleItems(mainNavItems);
  const visibleAdditionalItems = getVisibleItems(additionalItems);

  // Проверяем активность элемента
  const isActive = (path) => {
    if (location.pathname.startsWith('/medilab-demo')) {
      const slug = String(path || '').replace(/^\/+/, '');
      const demoPath = slug === 'dashboard'
        ? '/medilab-demo/dashboard'
        : `/medilab-demo/${slug}`;
      if (location.pathname === '/medilab-demo' && slug === 'dashboard') {
        return true;
      }
      return location.pathname === demoPath;
    }

    const normalizedPath = String(path || '').startsWith('/') ? String(path || '') : `/${String(path || '')}`;
    return location.pathname === normalizedPath || location.pathname.startsWith(normalizedPath);
  };

  // Стили для навигационных элементов
  const navItemStyle = (isActive) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: isCollapsed ? 'center' : 'flex-start',
    gap: isCollapsed ? '0' : '12px',
    padding: isCollapsed ? '0' : '12px 16px',
    borderRadius: isCollapsed ? '8px' : '12px',
    color: isActive ? 'var(--mac-bg-primary)' : 'var(--mac-text-secondary)',
    background: isActive ? 'var(--accent)' : 'transparent',
    textShadow: isActive ? '0 1px 2px rgba(0, 0, 0, 0.35)' : 'none',
    backgroundColor: isActive ? 'transparent' : 'transparent',
    boxShadow: isActive ? '0 6px 18px rgba(0,0,0,0.18)' : 'none',
    textDecoration: 'none',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    fontSize: 'var(--mac-font-size-base)',
    fontWeight: isActive ? '500' : '400',
    marginBottom: isCollapsed ? '4px' : '4px',
    width: isCollapsed ? '40px' : 'auto',
    minWidth: isCollapsed ? '40px' : 'auto',
    maxWidth: isCollapsed ? '40px' : 'auto',
    height: isCollapsed ? '40px' : 'auto',
    minHeight: isCollapsed ? '40px' : 'auto',
    maxHeight: isCollapsed ? '40px' : 'auto',
    flexShrink: 0,
    cursor: 'pointer',
    position: 'relative',
    overflow: 'hidden'
  });

  const hoverStyle = {
    background: 'var(--surface)',
    backgroundColor: 'transparent',
    color: 'var(--mac-text-primary)',
    boxShadow: 'var(--shadow)',
    transform: 'translateY(-2px) scale(1.02)',
    backdropFilter: 'var(--mac-blur-light)'
  };


  return (
    <aside
      ref={asideRef}
      style={{
        width: isCollapsed ? '80px' : '280px',
        height: '100vh',
        background: 'var(--mac-gradient-sidebar, var(--mac-bg-toolbar))',
        backdropFilter: 'var(--mac-blur-light)',
        WebkitBackdropFilter: 'var(--mac-blur-light)',
        borderRight: '1px solid var(--mac-separator)',
        borderRadius: isCollapsed ? '0' : 'var(--mac-radius-md)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.3s ease',
        position: 'fixed',
        left: 0,
        top: 0,
        zIndex: 1000,
        boxShadow: 'var(--shadow)'
      }}>

      {/* Имя пользователя и кнопка сворачивания */}
      <div
        style={{
          padding: isCollapsed ? '12px 8px' : '20px 16px',
          borderBottom: '1px solid var(--mac-separator)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>

        <div style={{ display: 'flex', alignItems: 'center' }}>
          {!isCollapsed &&
          <h1
            style={{
              fontSize: 'var(--mac-font-size-3xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-text-primary)',
              margin: 0
            }}>

              {profile.name || 'Dr. User'}
            </h1>
          }
          {isCollapsed &&
          <div
            style={{
              width: '28px',
              height: '28px',
              backgroundColor: 'var(--mac-accent-blue)',
              borderRadius: 'var(--mac-radius-sm)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-bold)'
            }}>

              {profile.name ? profile.name.charAt(0).toUpperCase() : 'U'}
            </div>
          }
        </div>

        {/* Кнопка сворачивания */}
        <button
          className="sidebar-toggle-button"
          onClick={onToggle}
          style={{
            color: isDark ? 'var(--mac-text-tertiary)' : 'var(--mac-text-secondary)',
            padding: 'var(--mac-spacing-2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minWidth: '28px',
            minHeight: '28px'
          }}
          onMouseEnter={(e) => {
            e.target.style.color = isDark ? 'var(--mac-warning)' : 'var(--mac-accent-blue-active)';
            e.target.style.filter = 'brightness(1.2)';
          }}
          onMouseLeave={(e) => {
            e.target.style.color = isDark ? 'var(--mac-text-tertiary)' : 'var(--mac-text-secondary)';
            e.target.style.filter = 'brightness(1)';
          }}
          title={isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'}
          aria-label={isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'}>

          <Icon name={isCollapsed ? 'ChevronRight' : 'ChevronLeft'} size={16} />
        </button>
      </div>

      {/* Основная навигация */}
      <nav
        style={{
          flex: 1,
          padding: isCollapsed ? '8px 0' : '16px 12px',
          overflowY: isCollapsed ? 'hidden' : 'auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: isCollapsed ? 'center' : 'stretch',
          gap: isCollapsed ? '4px' : '0'
        }}>

        {visibleMainItems.map((item) => {
          const active = isActive(item.path);

          const inlineStyle = isCollapsed ? {
            width: '40px',
            height: '40px',
            minWidth: '40px',
            minHeight: '40px',
            maxWidth: '40px',
            maxHeight: '40px',
            padding: '0',
            margin: '0 auto'
          } : {};

          return (
            <NavLink
              key={item.id}
              to={item.path}
              className="interactive-element hover-lift ripple-effect nav-item-hover focus-ring"
              style={({ isHovered }) => ({
                ...navItemStyle(active),
                ...(isHovered && !active ? hoverStyle : {}),
                ...inlineStyle
              })}
              title={isCollapsed ? item.label : ''}>

              <Icon name={item.iconName} size={isCollapsed ? 24 : 16} />
              {!isCollapsed && <span>{item.label}</span>}
            </NavLink>);

        })}

        {visibleAdditionalItems.length > 0 &&
        <>
          {/* Разделитель */}
          <div
            style={{
              height: '1px',
              backgroundColor: 'var(--mac-separator)',
              margin: '16px 0'
            }} />

          {/* Дополнительные элементы */}
          {visibleAdditionalItems.map((item) => {
            const active = isActive(item.path);

            const inlineStyle = isCollapsed ? {
              width: '40px',
              height: '40px',
              minWidth: '40px',
              minHeight: '40px',
              maxWidth: '40px',
              maxHeight: '40px',
              padding: '0',
              margin: '0 auto'
            } : {};

            return (
              <NavLink
                key={item.id}
                to={item.path}
                className="interactive-element hover-lift ripple-effect nav-item-hover focus-ring"
                style={({ isHovered }) => ({
                  ...navItemStyle(active),
                  ...(isHovered && !active ? hoverStyle : {}),
                  ...inlineStyle
                })}
                title={isCollapsed ? item.label : ''}>

                <Icon name={item.iconName} size={isCollapsed ? 24 : 16} />
                {!isCollapsed && <span>{item.label}</span>}
              </NavLink>);

          })}
        </>}
      </nav>

      {/* Кнопки переключения темы и языка */}
      <div
        style={{
          padding: isCollapsed ? '4px' : '12px 16px',
          borderTop: '1px solid var(--mac-separator)',
          display: 'flex',
          flexDirection: isCollapsed ? 'column' : 'row',
          gap: isCollapsed ? '2px' : '8px',
          alignItems: isCollapsed ? 'center' : 'stretch'
        }}>

        {/* Кнопка переключения темы */}
        <button
          className="sidebar-theme-button"
          onClick={handleThemeToggle}
          style={{
            flex: 1,
            padding: isCollapsed ? '8px' : '8px',
            color: isDark ? '#f8fafb' : 'var(--mac-text-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: isCollapsed ? '0' : '4px',
            fontSize: isCollapsed ? '10px' : '12px',
            fontWeight: 'var(--mac-font-weight-medium)',
            minHeight: isCollapsed ? '32px' : 'auto',
            width: isCollapsed ? '32px' : 'auto'
          }}
          onMouseEnter={(e) => {
            e.target.style.color = isDark ? 'var(--mac-warning)' : 'var(--mac-accent-blue-active)';
            e.target.style.filter = 'brightness(1.2)';
          }}
          onMouseLeave={(e) => {
            e.target.style.color = isDark ? '#f8fafb' : 'var(--mac-text-primary)';
            e.target.style.filter = 'brightness(1)';
          }}
          title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          aria-label={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}>

          <Icon name={isDark ? 'Sun' : 'Moon'} size={isCollapsed ? 16 : 16} />
          {!isCollapsed && (isDark ? 'Light' : 'Dark')}
        </button>

        {/* Кнопка переключения языка */}
        <button
          className="sidebar-language-button"
          onClick={handleLanguageToggle}
          style={{
            flex: 1,
            padding: isCollapsed ? '8px' : '8px',
            color: isDark ? '#f8fafb' : 'var(--mac-text-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: isCollapsed ? '0' : '4px',
            fontSize: isCollapsed ? '10px' : '12px',
            fontWeight: 'var(--mac-font-weight-medium)',
            minHeight: isCollapsed ? '32px' : 'auto',
            width: isCollapsed ? '32px' : 'auto'
          }}
          onMouseEnter={(e) => {
            e.target.style.color = isDark ? 'var(--mac-success)' : 'var(--mac-success)';
            e.target.style.filter = 'brightness(1.2)';
          }}
          onMouseLeave={(e) => {
            e.target.style.color = isDark ? '#f8fafb' : 'var(--mac-text-primary)';
            e.target.style.filter = 'brightness(1)';
          }}
          title={`Switch to ${language === 'en' ? 'Russian' : 'English'}`}
          aria-label={`Switch to ${language === 'en' ? 'Russian' : 'English'}`}>

          <Icon name="Globe" size={isCollapsed ? 16 : 16} />
          {!isCollapsed && (language === 'en' ? 'EN' : 'RU')}
        </button>
      </div>

      {/* Кнопка Log out */}
      <div
        style={{
          padding: isCollapsed ? '8px' : '16px',
          borderTop: '1px solid var(--mac-separator)',
          display: 'flex',
          justifyContent: isCollapsed ? 'center' : 'flex-start'
        }}>

        <button
          className="logout-button"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: isCollapsed ? '0' : '12px',
            padding: isCollapsed ? '8px' : '12px 16px',
            color: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-base)',
            fontWeight: 'var(--mac-font-weight-medium)',
            minWidth: isCollapsed ? '40px' : 'auto',
            minHeight: isCollapsed ? '40px' : 'auto',
            justifyContent: 'center'
          }}
          onMouseEnter={(e) => {
            e.target.style.color = 'var(--mac-error)';
            e.target.style.filter = 'brightness(1.2)';
          }}
          onMouseLeave={(e) => {
            e.target.style.color = isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-text-primary)';
            e.target.style.filter = 'brightness(1)';
          }}
          onClick={() => {
            auth.logout();
          }}
          aria-label="Log out of account"
          title={isCollapsed ? 'Log out' : ''}>

          <Icon name="LogOut" size={isCollapsed ? 16 : 16} />
          {!isCollapsed && <span>Log out</span>}
        </button>
      </div>
    </aside>);

};


UnifiedSidebar.propTypes = {
  ...(UnifiedSidebar.propTypes || {}),
  isCollapsed: PropTypes.any,
  onToggle: PropTypes.any,
};

export default UnifiedSidebar;
