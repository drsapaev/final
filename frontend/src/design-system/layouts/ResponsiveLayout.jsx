/**
 * Адаптивная система макетов для всех панелей клиники
 * Обеспечивает единообразный responsive дизайн
 */

import React, { useState, useEffect } from 'react';
import { useBreakpoint, useTouchDevice } from '../hooks';
import { medicalTheme } from '../theme/medical';
import { 
  Menu, 
  X, 
  ChevronLeft, 
  Settings, 
  Bell, 
  User,
  Sun,
  Moon,
  Maximize2,
  Minimize2
} from 'lucide-react';

const ResponsiveLayout = ({
  // Контент
  children,
  sidebar,
  header,
  footer,
  
  // Настройки макета
  sidebarWidth = '280px',
  collapsedWidth = '64px',
  headerHeight = '64px',
  
  // Поведение
  collapsible = true,
  autoCollapse = true, // Автоматически сворачивать на мобильных
  overlay = true, // Показывать sidebar как overlay на мобильных
  
  // Темы
  theme = 'light',
  onThemeChange,
  
  // Заголовок
  title,
  subtitle,
  breadcrumbs,
  
  // Действия в заголовке
  headerActions,
  
  // Стилизация
  className = '',
  style = {},
  
  ...props
}) => {
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const isTouch = useTouchDevice();
  
  // Состояние sidebar
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    autoCollapse && (isMobile || isTablet)
  );
  const [sidebarVisible, setSidebarVisible] = useState(!isMobile);
  
  // Полноэкранный режим
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  // Автоматическое сворачивание на мобильных
  useEffect(() => {
    if (autoCollapse) {
      setSidebarCollapsed(isMobile || isTablet);
      setSidebarVisible(!isMobile);
    }
  }, [isMobile, isTablet, autoCollapse]);
  
  // Обработчики
  const toggleSidebar = () => {
    if (isMobile) {
      setSidebarVisible(!sidebarVisible);
    } else {
      setSidebarCollapsed(!sidebarCollapsed);
    }
  };
  
  const closeSidebar = () => {
    if (isMobile) {
      setSidebarVisible(false);
    }
  };
  
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };
  
  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    if (onThemeChange) {
      onThemeChange(newTheme);
    }
  };
  
  // Стили
  const layoutStyles = {
    light: {
      background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
      text: '#1e293b',
      sidebar: '#ffffff',
      header: '#ffffff',
      border: '#e2e8f0'
    },
    dark: {
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      text: '#f8fafc',
      sidebar: '#1e293b',
      header: '#1e293b',
      border: '#334155'
    },
    medical: {
      background: medicalTheme.gradients.medical,
      text: '#1e293b',
      sidebar: '#ffffff',
      header: '#ffffff',
      border: '#dcfce7'
    }
  };
  
  const currentStyles = layoutStyles[theme] || layoutStyles.light;
  
  const containerStyle = {
    minHeight: '100vh',
    background: currentStyles.background,
    color: currentStyles.text,
    fontFamily: 'system-ui, -apple-system, sans-serif',
    display: 'flex',
    flexDirection: 'column',
    ...style
  };
  
  const headerStyle = {
    height: headerHeight,
    background: currentStyles.header,
    borderBottom: `1px solid ${currentStyles.border}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 20px',
    position: 'sticky',
    top: 0,
    zIndex: 40,
    backdropFilter: 'blur(8px)',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
  };
  
  const mainStyle = {
    flex: 1,
    display: 'flex',
    overflow: 'hidden'
  };
  
  const sidebarStyle = {
    width: sidebarCollapsed ? collapsedWidth : sidebarWidth,
    background: currentStyles.sidebar,
    borderRight: `1px solid ${currentStyles.border}`,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    position: isMobile && overlay ? 'fixed' : 'relative',
    top: isMobile && overlay ? headerHeight : 0,
    left: isMobile && overlay && !sidebarVisible ? `-${sidebarWidth}` : 0,
    height: isMobile && overlay ? `calc(100vh - ${headerHeight})` : 'auto',
    zIndex: isMobile && overlay ? 30 : 'auto',
    boxShadow: isMobile && overlay && sidebarVisible ? '4px 0 8px rgba(0, 0, 0, 0.1)' : 'none',
    overflow: 'auto'
  };
  
  const contentStyle = {
    flex: 1,
    padding: isMobile ? '16px' : isTablet ? '20px' : '24px',
    overflow: 'auto',
    marginLeft: isMobile && overlay ? 0 : 'auto'
  };
  
  const overlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.5)',
    zIndex: 25,
    display: isMobile && overlay && sidebarVisible ? 'block' : 'none'
  };
  
  return (
    <div className={`responsive-layout ${className}`} style={containerStyle} {...props}>
      {/* Overlay для мобильных */}
      <div style={overlayStyle} onClick={closeSidebar} />
      
      {/* Заголовок */}
      <header style={headerStyle}>
        <div className="flex items-center space-x-4">
          {/* Кнопка меню */}
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Toggle sidebar"
          >
            {isMobile && sidebarVisible ? <X size={20} /> : <Menu size={20} />}
          </button>
          
          {/* Заголовок и хлебные крошки */}
          <div className="flex flex-col">
            {title && (
              <h1 className="text-lg font-semibold text-gray-900">
                {title}
              </h1>
            )}
            {subtitle && (
              <p className="text-sm text-gray-500">{subtitle}</p>
            )}
            {breadcrumbs && (
              <nav className="flex items-center space-x-2 text-sm text-gray-500">
                {breadcrumbs.map((crumb, index) => (
                  <React.Fragment key={index}>
                    {index > 0 && <ChevronLeft size={14} className="rotate-180" />}
                    <span className={crumb.active ? 'text-gray-900 font-medium' : ''}>
                      {crumb.label}
                    </span>
                  </React.Fragment>
                ))}
              </nav>
            )}
          </div>
        </div>
        
        {/* Действия в заголовке */}
        <div className="flex items-center space-x-2">
          {headerActions}
          
          {/* Переключатель темы */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Toggle theme"
          >
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          
          {/* Полноэкранный режим */}
          {!isMobile && (
            <button
              onClick={toggleFullscreen}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
              aria-label="Toggle fullscreen"
            >
              {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button>
          )}
          
          {/* Уведомления */}
          <button className="p-2 rounded-lg hover:bg-gray-100 transition-colors relative">
            <Bell size={18} />
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full"></span>
          </button>
          
          {/* Профиль */}
          <button className="p-2 rounded-lg hover:bg-gray-100 transition-colors">
            <User size={18} />
          </button>
        </div>
      </header>
      
      {/* Основной контент */}
      <main style={mainStyle}>
        {/* Sidebar */}
        {sidebar && (
          <aside style={sidebarStyle}>
            {sidebar}
          </aside>
        )}
        
        {/* Контент */}
        <div style={contentStyle}>
          {children}
        </div>
      </main>
      
      {/* Футер */}
      {footer && (
        <footer className="border-t border-gray-200 bg-white p-4">
          {footer}
        </footer>
      )}
    </div>
  );
};

// Компонент для sidebar навигации
export const SidebarNav = ({ 
  items = [], 
  collapsed = false, 
  onItemClick,
  activeItem 
}) => {
  return (
    <nav className="sidebar-nav p-4">
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li key={index}>
            <button
              onClick={() => onItemClick && onItemClick(item)}
              className={`
                w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-left
                transition-colors duration-200
                ${activeItem === item.id 
                  ? 'bg-blue-100 text-blue-700 font-medium' 
                  : 'text-gray-700 hover:bg-gray-100'
                }
              `}
            >
              {item.icon && (
                <item.icon size={20} className="flex-shrink-0" />
              )}
              {!collapsed && (
                <span className="truncate">{item.label}</span>
              )}
              {!collapsed && item.badge && (
                <span className="ml-auto bg-red-500 text-white text-xs px-2 py-1 rounded-full">
                  {item.badge}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
};

// Компонент для быстрых действий
export const QuickActions = ({ actions = [] }) => {
  const { isMobile } = useBreakpoint();
  
  return (
    <div className={`quick-actions ${isMobile ? 'grid grid-cols-2 gap-2' : 'flex space-x-2'}`}>
      {actions.map((action, index) => (
        <button
          key={index}
          onClick={action.onClick}
          className={`
            flex items-center justify-center space-x-2 px-4 py-2 rounded-lg
            transition-colors duration-200
            ${action.variant === 'primary' 
              ? 'bg-blue-500 text-white hover:bg-blue-600' 
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }
          `}
        >
          {action.icon && <action.icon size={16} />}
          <span className="text-sm font-medium">{action.label}</span>
        </button>
      ))}
    </div>
  );
};

export default ResponsiveLayout;
