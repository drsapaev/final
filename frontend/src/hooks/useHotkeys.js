import { useEffect, useCallback } from 'react';

import logger from '../utils/logger';
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
    combination += (event.key || '').toLowerCase();
    
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
    'ctrl+s': handlers.save || (() => logger.log('Сохранить')),
    'ctrl+k': handlers.search || (() => logger.log('Поиск')),
    'ctrl+p': handlers.print || (() => logger.log('Печать')),
    'ctrl+r': handlers.refresh || (() => logger.log('Обновить')),
    
    // Навигация
    'ctrl+1': handlers.dashboard || (() => logger.log('Дашборд')),
    'ctrl+2': handlers.users || (() => logger.log('Пользователи')),
    'ctrl+3': handlers.doctors || (() => logger.log('Врачи')),
    'ctrl+4': handlers.services || (() => logger.log('Услуги')),
    'ctrl+5': handlers.settings || (() => logger.log('Настройки')),
    
    // Модальные окна
    'escape': handlers.closeModal || (() => logger.log('Закрыть модальное окно')),
    'ctrl+n': handlers.createNew || (() => logger.log('Создать новый')),
    
    // Специальные
    'ctrl+shift+o': handlers.openQueue || (() => logger.log('Открыть прием')),
    'ctrl+alt+t': handlers.testSystem || (() => logger.log('Тестировать систему')),
    
    // Помощь
    'f1': handlers.help || (() => logger.log('Справка')),
    'ctrl+/': handlers.shortcuts || (() => logger.log('Показать горячие клавиши'))
  };

  useHotkeys(shortcuts);
  
  return shortcuts;
};
