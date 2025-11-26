import React, { useState, useEffect } from 'react';
import { Menu, X, ChevronLeft, Search, Plus } from 'lucide-react';
import { Button } from '../ui/native';

/**
 * Компонент для оптимизации админ панели на мобильных устройствах
 */
export const MobileNavigation = ({ sections, currentSection, onNavigate, className = '' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  if (!isMobile) return null;

  return (
    <>
      {/* Мобильная шапка */}
      <div className={`md:hidden bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-4 py-3 ${className}`}>
        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => setIsOpen(true)}
            className="p-2"
          >
            <Menu size={20} />
          </Button>
          
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
            Админ панель
          </h1>
          
          <div className="flex gap-2">
            <Button variant="ghost" className="p-2">
              <Search size={20} />
            </Button>
            <Button variant="ghost" className="p-2">
              <Plus size={20} />
            </Button>
          </div>
        </div>
      </div>

      {/* Мобильное меню */}
      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Overlay */}
          <div 
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={() => setIsOpen(false)}
          />
          
          {/* Sidebar */}
          <div className="fixed left-0 top-0 bottom-0 w-80 bg-white dark:bg-gray-900 shadow-xl overflow-y-auto">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Навигация
                </h2>
                <Button
                  variant="ghost"
                  onClick={() => setIsOpen(false)}
                  className="p-2"
                >
                  <X size={20} />
                </Button>
              </div>
            </div>
            
            <div className="p-4">
              {sections.map((section, sectionIndex) => (
                <div key={sectionIndex} className="mb-6">
                  <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
                    {section.title}
                  </h3>
                  <div className="space-y-1">
                    {section.items.map((item, itemIndex) => {
                      const isActive = currentSection === item.to.split('/')[2];
                      const IconComponent = item.icon;
                      
                      return (
                        <button
                          key={itemIndex}
                          onClick={() => {
                            onNavigate(item.to);
                            setIsOpen(false);
                          }}
                          className={`w-full flex items-center px-3 py-2 rounded-md text-left transition-colors ${
                            isActive
                              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                              : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                          }`}
                        >
                          <IconComponent size={18} className="mr-3" />
                          <span className="text-sm font-medium">{item.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

/**
 * Компонент для адаптивных таблиц
 */
export const ResponsiveTable = ({ 
  columns, 
  data, 
  onRowClick, 
  mobileCardRenderer,
  className = '' 
}) => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  if (isMobile && mobileCardRenderer) {
    // Мобильный вид - карточки
    return (
      <div className={`space-y-3 ${className}`}>
        {data.map((row, index) => (
          <div
            key={row.id || index}
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            onClick={() => onRowClick && onRowClick(row)}
          >
            {mobileCardRenderer(row)}
          </div>
        ))}
      </div>
    );
  }

  // Десктопный вид - таблица
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full">
        <thead className="bg-gray-50 dark:bg-gray-800">
          <tr>
            {columns.map((column, index) => (
              <th
                key={index}
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
          {data.map((row, rowIndex) => (
            <tr
              key={row.id || rowIndex}
              className="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
              onClick={() => onRowClick && onRowClick(row)}
            >
              {columns.map((column, colIndex) => (
                <td key={colIndex} className="px-6 py-4 whitespace-nowrap">
                  {column.render ? column.render(row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

/**
 * Компонент быстрых действий для мобильных
 */
export const MobileQuickActions = ({ actions, className = '' }) => {
  return (
    <div className={`md:hidden fixed bottom-4 right-4 ${className}`}>
      <div className="flex flex-col gap-2">
        {actions.map((action, index) => (
          <Button
            key={index}
            onClick={action.onClick}
            className="w-14 h-14 rounded-full shadow-lg"
            variant={action.variant || 'default'}
            disabled={action.disabled}
          >
            <action.icon size={20} />
          </Button>
        ))}
      </div>
    </div>
  );
};

/**
 * Хук для определения размера экрана
 */
export const useScreenSize = () => {
  const [screenSize, setScreenSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 0,
    height: typeof window !== 'undefined' ? window.innerHeight : 0,
    isMobile: false,
    isTablet: false,
    isDesktop: false
  });

  useEffect(() => {
    const updateScreenSize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      
      setScreenSize({
        width,
        height,
        isMobile: width < 768,
        isTablet: width >= 768 && width < 1024,
        isDesktop: width >= 1024
      });
    };

    updateScreenSize();
    window.addEventListener('resize', updateScreenSize);
    return () => window.removeEventListener('resize', updateScreenSize);
  }, []);

  return screenSize;
};

export default { MobileNavigation, ResponsiveTable, MobileQuickActions, useScreenSize };

