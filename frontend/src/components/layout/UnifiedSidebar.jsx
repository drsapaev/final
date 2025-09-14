import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import Icon from '../Icon';
import { useTheme } from '../../contexts/ThemeContext';
import auth from '../../stores/auth.js';
import '../../styles/sidebar-buttons.css';
import '../../styles/cursor-effects.css';

/**
 * Унифицированный сайдбар в стиле MediLab
 * Используется во всех панелях для единообразия
 */
const UnifiedSidebar = ({ isCollapsed = false, onToggle }) => {
  const location = useLocation();
  const { isDark, getColor, toggleTheme } = useTheme();
  const [language, setLanguage] = useState('en');
  
  // Функции переключения
  const handleThemeToggle = () => {
    if (toggleTheme) {
      toggleTheme();
    }
  };
  
  const handleLanguageToggle = () => {
    setLanguage(prev => prev === 'en' ? 'ru' : 'en');
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
      path: '/dashboard',
      roles: ['admin', 'doctor', 'registrar', 'cashier', 'lab']
    },
    {
      id: 'patients',
      label: 'Patients',
      iconName: 'Users',
      path: '/patients',
      roles: ['admin', 'doctor', 'registrar']
    },
    {
      id: 'appointments',
      label: 'Appointments',
      iconName: 'Calendar',
      path: '/appointments',
      roles: ['admin', 'doctor', 'registrar']
    },
    {
      id: 'staff-schedule',
      label: 'Staff Schedule',
      iconName: 'Clock',
      path: '/staff-schedule',
      roles: ['admin', 'registrar']
    },
    {
      id: 'doctors',
      label: 'Doctors',
      iconName: 'Stethoscope',
      path: '/doctors',
      roles: ['admin', 'registrar']
    },
    {
      id: 'departments',
      label: 'Departments',
      iconName: 'Building',
      path: '/departments',
      roles: ['admin']
    },
    {
      id: 'stock',
      label: 'Stock',
      iconName: 'Package',
      path: '/stock',
      roles: ['admin', 'lab', 'cashier']
    }
  ];

  // Дополнительные элементы
  const additionalItems = [
    {
      id: 'settings',
      label: 'Settings',
      iconName: 'Settings',
      path: '/settings',
      roles: ['admin', 'doctor', 'registrar', 'cashier', 'lab']
    },
    {
      id: 'help',
      label: 'Help Center',
      iconName: 'HelpCircle',
      path: '/help',
      roles: ['admin', 'doctor', 'registrar', 'cashier', 'lab']
    }
  ];

  // Фильтруем элементы по роли пользователя
  const getVisibleItems = (items) => {
    // Для демо-страницы показываем все элементы
    if (isDemoPage) {
      return items;
    }
    
    const filtered = items.filter(item => 
      item.roles.includes(role) || item.roles.includes('all')
    );
    
    return filtered;
  };

  const visibleMainItems = getVisibleItems(mainNavItems);
  const visibleAdditionalItems = getVisibleItems(additionalItems);

  // Проверяем активность элемента
  const isActive = (path) => {
    if (path === '/dashboard' || path === '/') {
      return location.pathname === '/' || location.pathname === '/dashboard' || location.pathname === '/medilab-demo' || location.pathname === '/medilab-demo/dashboard';
    }
    
    // Для демо-страницы проверяем специальные маршруты
    if (location.pathname.startsWith('/medilab-demo')) {
      const demoPath = path.replace('/', '/medilab-demo');
      return location.pathname === demoPath;
    }
    
    return location.pathname.startsWith(path);
  };

  // Стили для навигационных элементов
  const navItemStyle = (isActive) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: isCollapsed ? 'center' : 'flex-start',
    gap: isCollapsed ? '0' : '12px',
    padding: isCollapsed ? '8px' : '12px 16px',
    borderRadius: '12px',
    color: isActive ? '#ffffff' : (isDark ? '#cbd5e1' : '#64748b'),
    background: isActive ? 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)' : 'transparent',
    backgroundColor: isActive ? 'transparent' : 'transparent',
    boxShadow: isActive ? '0 8px 25px rgba(102, 126, 234, 0.3), 0 4px 12px rgba(118, 75, 162, 0.2), 0 2px 6px rgba(240, 147, 251, 0.2)' : 'none',
    textDecoration: 'none',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    fontSize: '14px',
    fontWeight: isActive ? '500' : '400',
    marginBottom: isCollapsed ? '2px' : '4px',
    width: isCollapsed ? '48px' : 'auto',
    height: isCollapsed ? '36px' : 'auto',
    cursor: 'pointer',
    position: 'relative',
    overflow: 'hidden'
  });

  const hoverStyle = {
    background: isDark 
      ? 'linear-gradient(135deg, #4a5568 0%, #2d3748 100%)' 
      : 'linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%)',
    backgroundColor: 'transparent',
    color: isDark ? '#f8fafc' : '#1e293b',
    boxShadow: isDark 
      ? '0 8px 25px rgba(74, 85, 104, 0.4), 0 4px 12px rgba(45, 55, 72, 0.3), 0 2px 6px rgba(0, 0, 0, 0.2)' 
      : '0 8px 25px rgba(247, 250, 252, 0.5), 0 4px 12px rgba(237, 242, 247, 0.4), 0 2px 6px rgba(0, 0, 0, 0.1)',
    transform: 'translateY(-2px) scale(1.02)',
    backdropFilter: 'blur(10px)'
  };


  return (
    <aside 
      style={{
        width: isCollapsed ? '80px' : '280px',
        height: '100vh',
        backgroundColor: isDark ? '#1e293b' : '#ffffff',
        borderRight: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.3s ease',
        position: 'fixed',
        left: 0,
        top: 0,
        zIndex: 1000,
        boxShadow: '2px 0 4px rgba(0, 0, 0, 0.1)'
      }}
    >
       {/* Имя пользователя и кнопка сворачивания */}
       <div 
         style={{
           padding: isCollapsed ? '12px 8px' : '20px 16px',
           borderBottom: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
           display: 'flex',
           alignItems: 'center',
           justifyContent: 'space-between'
         }}
       >
         <div style={{ display: 'flex', alignItems: 'center' }}>
           {!isCollapsed && (
             <h1 
               style={{
                 fontSize: '24px',
                 fontWeight: '700',
                 color: isDark ? '#f8fafc' : '#1e293b',
                 margin: 0
               }}
             >
               {profile.name || 'Dr. User'}
             </h1>
           )}
           {isCollapsed && (
             <div 
               style={{
                 width: '28px',
                 height: '28px',
                 backgroundColor: '#3b82f6',
                 borderRadius: '6px',
                 display: 'flex',
                 alignItems: 'center',
                 justifyContent: 'center',
                 color: 'white',
                 fontSize: '14px',
                 fontWeight: 'bold'
               }}
             >
               {profile.name ? profile.name.charAt(0).toUpperCase() : 'U'}
             </div>
           )}
         </div>
         
         {/* Кнопка сворачивания */}
         <button
           className="sidebar-toggle-button"
           onClick={onToggle}
           style={{
             color: isDark ? '#9ca3af' : '#6b7280',
             padding: '6px',
             display: 'flex',
             alignItems: 'center',
             justifyContent: 'center',
             minWidth: '28px',
             minHeight: '28px'
           }}
           onMouseEnter={(e) => {
             e.target.style.color = isDark ? '#fbbf24' : '#1e40af';
             e.target.style.filter = 'brightness(1.2)';
           }}
           onMouseLeave={(e) => {
             e.target.style.color = isDark ? '#9ca3af' : '#6b7280';
             e.target.style.filter = 'brightness(1)';
           }}
           title={isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'}
         >
           <Icon name={isCollapsed ? 'ChevronRight' : 'ChevronLeft'} size={16} />
         </button>
       </div>

      {/* Основная навигация */}
      <nav 
        style={{
          flex: 1,
          padding: isCollapsed ? '8px 4px' : '16px 12px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: isCollapsed ? 'center' : 'stretch'
        }}
      >
        {visibleMainItems.map((item) => {
          const active = isActive(item.path);
          
          // Для демо-страницы используем специальные маршруты
          const demoPath = location.pathname.startsWith('/medilab-demo') 
            ? item.path.replace('/', '/medilab-demo')
            : item.path;
          
          return (
            <NavLink
              key={item.id}
              to={demoPath}
              className="interactive-element hover-lift ripple-effect nav-item-hover focus-ring"
              style={({ isHovered }) => ({
                ...navItemStyle(active),
                ...(isHovered && !active ? hoverStyle : {})
              })}
              title={isCollapsed ? item.label : ''}
            >
              <Icon name={item.iconName} size={16} />
              {!isCollapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}

        {/* Разделитель */}
        <div 
          style={{
            height: '1px',
            backgroundColor: isDark ? '#334155' : '#e2e8f0',
            margin: '16px 0'
          }}
        />

        {/* Дополнительные элементы */}
        {visibleAdditionalItems.map((item) => {
          const active = isActive(item.path);
          
          return (
            <NavLink
              key={item.id}
              to={item.path}
              className="interactive-element hover-lift ripple-effect nav-item-hover focus-ring"
              style={({ isHovered }) => ({
                ...navItemStyle(active),
                ...(isHovered && !active ? hoverStyle : {})
              })}
              title={isCollapsed ? item.label : ''}
            >
              <Icon name={item.iconName} size={16} />
              {!isCollapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Кнопки переключения темы и языка */}
      <div 
        style={{
          padding: isCollapsed ? '4px' : '12px 16px',
          borderTop: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
          display: 'flex',
          flexDirection: isCollapsed ? 'column' : 'row',
          gap: isCollapsed ? '2px' : '8px',
          alignItems: isCollapsed ? 'center' : 'stretch'
        }}
      >
        {/* Кнопка переключения темы */}
        <button
          className="sidebar-theme-button"
          onClick={handleThemeToggle}
          style={{
            flex: 1,
            padding: isCollapsed ? '8px' : '8px',
            color: isDark ? '#f8fafb' : '#374151',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: isCollapsed ? '0' : '4px',
            fontSize: isCollapsed ? '10px' : '12px',
            fontWeight: '500',
            minHeight: isCollapsed ? '32px' : 'auto',
            width: isCollapsed ? '32px' : 'auto'
          }}
          onMouseEnter={(e) => {
            e.target.style.color = isDark ? '#fbbf24' : '#1e40af';
            e.target.style.filter = 'brightness(1.2)';
          }}
          onMouseLeave={(e) => {
            e.target.style.color = isDark ? '#f8fafb' : '#374151';
            e.target.style.filter = 'brightness(1)';
          }}
          title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
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
            color: isDark ? '#f8fafb' : '#374151',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: isCollapsed ? '0' : '4px',
            fontSize: isCollapsed ? '10px' : '12px',
            fontWeight: '500',
            minHeight: isCollapsed ? '32px' : 'auto',
            width: isCollapsed ? '32px' : 'auto'
          }}
          onMouseEnter={(e) => {
            e.target.style.color = isDark ? '#10b981' : '#059669';
            e.target.style.filter = 'brightness(1.2)';
          }}
          onMouseLeave={(e) => {
            e.target.style.color = isDark ? '#f8fafb' : '#374151';
            e.target.style.filter = 'brightness(1)';
          }}
          title={`Switch to ${language === 'en' ? 'Russian' : 'English'}`}
        >
          <Icon name="Globe" size={isCollapsed ? 16 : 16} />
          {!isCollapsed && (language === 'en' ? 'EN' : 'RU')}
        </button>
      </div>

       {/* Кнопка Log out */}
       <div 
         style={{
           padding: isCollapsed ? '8px' : '16px',
           borderTop: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
           display: 'flex',
           justifyContent: isCollapsed ? 'center' : 'flex-start'
         }}
       >
         <button
           className="logout-button"
           style={{
             display: 'flex',
             alignItems: 'center',
             gap: isCollapsed ? '0' : '12px',
             padding: isCollapsed ? '8px' : '12px 16px',
             color: isDark ? '#f8fafc' : '#1e293b',
             fontSize: '14px',
             fontWeight: '500',
             minWidth: isCollapsed ? '40px' : 'auto',
             minHeight: isCollapsed ? '40px' : 'auto',
             justifyContent: 'center'
           }}
           onMouseEnter={(e) => {
             e.target.style.color = '#ef4444';
             e.target.style.filter = 'brightness(1.2)';
           }}
           onMouseLeave={(e) => {
             e.target.style.color = isDark ? '#f8fafc' : '#1e293b';
             e.target.style.filter = 'brightness(1)';
           }}
           onClick={() => {
             auth.logout();
           }}
           aria-label="Log out of account"
           title={isCollapsed ? 'Log out' : ''}
         >
           <Icon name="LogOut" size={isCollapsed ? 16 : 16} />
           {!isCollapsed && <span>Log out</span>}
         </button>
       </div>
    </aside>
  );
};

export default UnifiedSidebar;
