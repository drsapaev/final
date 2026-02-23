import { useState } from 'react';
import { HelpCircle, Keyboard, X } from 'lucide-react';
import { Card, Button } from '../ui/native';

/**
 * Компонент контекстных подсказок для админ панели
 */
const HelpTooltip = ({ content, shortcuts = [], position = 'top' }) => {
  const [isVisible, setIsVisible] = useState(false);

  const positionClasses = {
    top: 'bottom-full left-1/2 transform -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 transform -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 transform -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 transform -translate-y-1/2 ml-2'
  };

  return (
    <div className="relative inline-block">
      <button
        type="button"
        className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        onClick={() => setIsVisible(!isVisible)}
      >
        <HelpCircle size={16} />
      </button>
      
      {isVisible && (
        <div className={`absolute z-50 ${positionClasses[position]} w-80`}>
          <Card className="p-4 shadow-lg border border-gray-200 dark:border-gray-700">
            <div className="space-y-3">
              {/* Основная подсказка */}
              <div className="text-sm text-gray-700 dark:text-gray-300">
                {content}
              </div>
              
              {/* Горячие клавиши */}
              {shortcuts.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                    Горячие клавиши:
                  </div>
                  <div className="space-y-1">
                    {shortcuts.map((shortcut, index) => (
                      <div key={index} className="flex items-center justify-between text-xs">
                        <span className="text-gray-600 dark:text-gray-400">{shortcut.description}</span>
                        <kbd className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-gray-800 dark:text-gray-200 font-mono">
                          {shortcut.keys}
                        </kbd>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            {/* Стрелка подсказки */}
            <div className={`absolute w-3 h-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 transform rotate-45 ${
              position === 'top' ? 'top-full left-1/2 -translate-x-1/2 -translate-y-1/2 border-t-0 border-l-0' :
              position === 'bottom' ? 'bottom-full left-1/2 -translate-x-1/2 translate-y-1/2 border-b-0 border-r-0' :
              position === 'left' ? 'left-full top-1/2 -translate-x-1/2 -translate-y-1/2 border-l-0 border-b-0' :
              'right-full top-1/2 translate-x-1/2 -translate-y-1/2 border-r-0 border-t-0'
            }`} />
          </Card>
        </div>
      )}
    </div>
  );
};

/**
 * Модальное окно со всеми горячими клавишами
 */
export const HotkeysModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const hotkeyCategories = [
    {
      title: 'Основные действия',
      shortcuts: [
        { keys: 'Ctrl+S', description: 'Сохранить изменения' },
        { keys: 'Ctrl+R', description: 'Обновить данные' },
        { keys: 'Ctrl+K', description: 'Открыть поиск' },
        { keys: 'Ctrl+P', description: 'Печать документа' },
        { keys: 'Ctrl+N', description: 'Создать новый элемент' },
        { keys: 'Esc', description: 'Закрыть модальное окно' }
      ]
    },
    {
      title: 'Навигация',
      shortcuts: [
        { keys: 'Ctrl+1', description: 'Перейти к дашборду' },
        { keys: 'Ctrl+2', description: 'Управление пользователями' },
        { keys: 'Ctrl+3', description: 'Управление врачами' },
        { keys: 'Ctrl+4', description: 'Справочник услуг' },
        { keys: 'Ctrl+5', description: 'Настройки системы' }
      ]
    },
    {
      title: 'Специальные функции',
      shortcuts: [
        { keys: 'Ctrl+Shift+O', description: 'Открыть прием (очередь)' },
        { keys: 'Ctrl+Alt+T', description: 'Тестировать систему' },
        { keys: 'F1', description: 'Справка' },
        { keys: 'Ctrl+/', description: 'Показать горячие клавиши' }
      ]
    }
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <Card className="w-full max-w-2xl m-4 p-6 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <Keyboard size={24} className="mr-3 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Горячие клавиши
            </h2>
          </div>
          <Button variant="ghost" onClick={onClose}>
            <X size={20} />
          </Button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {hotkeyCategories.map((category, categoryIndex) => (
            <div key={categoryIndex}>
              <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-3">
                {category.title}
              </h3>
              <div className="space-y-2">
                {category.shortcuts.map((shortcut, index) => (
                  <div key={index} className="flex items-center justify-between py-2 px-3 bg-gray-50 dark:bg-gray-800 rounded">
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      {shortcut.description}
                    </span>
                    <kbd className="px-2 py-1 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded text-xs font-mono text-gray-800 dark:text-gray-200">
                      {shortcut.keys}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        
        <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 text-center">
            💡 Горячие клавиши работают в любом разделе админ панели
          </p>
        </div>
      </Card>
    </div>
  );
};

export default HelpTooltip;

