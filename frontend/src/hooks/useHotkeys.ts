import { useCallback, useEffect } from 'react';
import logger from '../utils/logger';

type ShortcutHandler = (event: KeyboardEvent) => void;

interface ShortcutEntry {
  handler: ShortcutHandler;
}

type ShortcutMap = Record<string, ShortcutHandler | ShortcutEntry>;

interface AdminHotkeyHandlers {
  save?: ShortcutHandler;
  search?: ShortcutHandler;
  print?: ShortcutHandler;
  refresh?: ShortcutHandler;
  dashboard?: ShortcutHandler;
  users?: ShortcutHandler;
  doctors?: ShortcutHandler;
  services?: ShortcutHandler;
  settings?: ShortcutHandler;
  closeModal?: ShortcutHandler;
  createNew?: ShortcutHandler;
  openQueue?: ShortcutHandler;
  testSystem?: ShortcutHandler;
  help?: ShortcutHandler;
  shortcuts?: ShortcutHandler;
}

/**
 * Хук для управления горячими клавишами.
 * Основан на документации: Ctrl+P — печать, Ctrl+K — поиск, Ctrl+S — сохранить.
 */
export const useHotkeys = (shortcuts: ShortcutMap = {}): void => {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent): void => {
      const isCtrl = event.ctrlKey || event.metaKey;
      const isShift = event.shiftKey;
      const isAlt = event.altKey;

      let combination = '';
      if (isCtrl) combination += 'ctrl+';
      if (isShift) combination += 'shift+';
      if (isAlt) combination += 'alt+';
      combination += (event.key || '').toLowerCase();

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
    },
    [shortcuts],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);
};

/**
 * Предустановленные горячие клавиши для админ панели.
 */
export const useAdminHotkeys = (handlers: AdminHotkeyHandlers = {}): ShortcutMap => {
  const noop = (): void => {
    /* no-op */
  };

  const shortcuts: ShortcutMap = {
    'ctrl+s': handlers.save || (() => { logger.log('Сохранить'); noop(); }),
    'ctrl+k': handlers.search || (() => { logger.log('Поиск'); noop(); }),
    'ctrl+p': handlers.print || (() => { logger.log('Печать'); noop(); }),
    'ctrl+r': handlers.refresh || (() => { logger.log('Обновить'); noop(); }),
    'ctrl+1': handlers.dashboard || (() => { logger.log('Дашборд'); noop(); }),
    'ctrl+2': handlers.users || (() => { logger.log('Пользователи'); noop(); }),
    'ctrl+3': handlers.doctors || (() => { logger.log('Врачи'); noop(); }),
    'ctrl+4': handlers.services || (() => { logger.log('Услуги'); noop(); }),
    'ctrl+5': handlers.settings || (() => { logger.log('Настройки'); noop(); }),
    escape: handlers.closeModal || (() => { logger.log('Закрыть модальное окно'); noop(); }),
    'ctrl+n': handlers.createNew || (() => { logger.log('Создать новый'); noop(); }),
    'ctrl+shift+o': handlers.openQueue || (() => { logger.log('Открыть приём'); noop(); }),
    'ctrl+alt+t': handlers.testSystem || (() => { logger.log('Тестировать систему'); noop(); }),
    f1: handlers.help || (() => { logger.log('Справка'); noop(); }),
    'ctrl+/': handlers.shortcuts || (() => { logger.log('Показать горячие клавиши'); noop(); }),
  };

  useHotkeys(shortcuts);

  return shortcuts;
};
