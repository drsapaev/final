import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import UnifiedSidebar from './UnifiedSidebar';
import { useTheme } from '../../contexts/ThemeContext';
import '../../styles/unified-sidebar.css';

/**
 * Унифицированный макет с сайдбаром
 * Используется во всех панелях для единообразия
 */
const UnifiedLayout = ({ children, showSidebar = true }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const location = useLocation();
  const { isDark } = useTheme();

  // Определяем мобильное устройство
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Автоматически сворачиваем сайдбар на мобильных устройствах
  useEffect(() => {
    if (isMobile) {
      setIsCollapsed(true);
    }
  }, [isMobile]);

  const toggleSidebar = () => {
    setIsCollapsed(!isCollapsed);
  };

  // Стили для основного контента
  const mainContentStyle = {
    marginLeft: showSidebar ? (isCollapsed ? '80px' : '280px') : '0',
    minHeight: '100vh',
    width: '100%',
    maxWidth: '100%',
    backgroundColor: isDark ? '#0f172a' : '#f8fafc',
    transition: 'margin-left 0.3s ease',
    padding: '20px',
    overflow: 'auto' // Разрешаем скролл для просмотра всего контента
  };

  // Стили для мобильных устройств
  if (isMobile) {
    mainContentStyle.marginLeft = '0';
  }

  return (
    <div 
      className={`unified-layout ${isDark ? 'dark' : 'light'}`}
      style={{
        display: 'flex',
        minHeight: '100vh',
        backgroundColor: isDark ? '#0f172a' : '#f8fafc'
      }}
    >
      
      {/* Сайдбар */}
      {showSidebar && (
        <UnifiedSidebar 
          isCollapsed={isCollapsed}
          onToggle={toggleSidebar}
        />
      )}


      {/* Основной контент */}
      <main 
        style={{
          ...mainContentStyle,
          width: '100%',
          maxWidth: '100%',
          flex: 1
        }}
        className="unified-main-content"
      >
        {children}
      </main>

      {/* Оверлей для мобильных устройств */}
      {isMobile && !isCollapsed && showSidebar && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            zIndex: 999
          }}
          onClick={() => setIsCollapsed(true)}
        />
      )}
    </div>
  );
};

export default UnifiedLayout;

