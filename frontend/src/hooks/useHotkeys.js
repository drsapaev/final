import { useEffect, useCallback } from 'react';

/**
 * Хук для управления горячими клавишами в админ панели
 * Основан на документации: Ctrl+P - печать, Ctrl+K - поиск, Ctrl+S - сохранить
 */
export const useHotkeys = (shortcuts = {}) => {
  const handleKeyDown = useCallback((event) => {
    // Проверяем модификаторы
    const isCtrl = event.ctrlKey || event.metaKey;
    const isShift = event.shiftKey;
    const isAlt = event.altKey;
    
    // Создаем ключ комбинации
    let combination = '';
    if (isCtrl) combination += 'ctrl+';
    if (isShift) combination += 'shift+';
    if (isAlt) combination += 'alt+';
    combination += event.key.toLowerCase();
    
    // Ищем соответствующий shortcut
    const shortcut = shortcuts[combination];
    if (shortcut) {
      event.preventDefault();
      event.stopPropagation();
      
      if (typeof shortcut === 'function') {
        shortcut(event);
      } else if (shortcut.handler) {
        shortcut.handler(event);
      }
    }
  }, [shortcuts]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);
};

/**
 * Предустановленные горячие клавиши для админ панели
 */
export const useAdminHotkeys = (handlers = {}) => {
  const shortcuts = {
    // Основные действия
    'ctrl+s': handlers.save || (() => console.log('Сохранить')),
    'ctrl+k': handlers.search || (() => console.log('Поиск')),
    'ctrl+p': handlers.print || (() => console.log('Печать')),
    'ctrl+r': handlers.refresh || (() => console.log('Обновить')),
    
    // Навигация
    'ctrl+1': handlers.dashboard || (() => console.log('Дашборд')),
    'ctrl+2': handlers.users || (() => console.log('Пользователи')),
    'ctrl+3': handlers.doctors || (() => console.log('Врачи')),
    'ctrl+4': handlers.services || (() => console.log('Услуги')),
    'ctrl+5': handlers.settings || (() => console.log('Настройки')),
    
    // Модальные окна
    'escape': handlers.closeModal || (() => console.log('Закрыть модальное окно')),
    'ctrl+n': handlers.createNew || (() => console.log('Создать новый')),
    
    // Специальные
    'ctrl+shift+o': handlers.openQueue || (() => console.log('Открыть прием')),
    'ctrl+alt+t': handlers.testSystem || (() => console.log('Тестировать систему')),
    
    // Помощь
    'f1': handlers.help || (() => console.log('Справка')),
    'ctrl+/': handlers.shortcuts || (() => console.log('Показать горячие клавиши'))
  };

  useHotkeys(shortcuts);
  
  return shortcuts;
};
