import React, { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { X } from 'lucide-react';
import './ModernDialog.css';
import { useTranslation } from '../../i18n/useTranslation';
import logger from '../../utils/logger';

// REG-FE-077 (follow-up audit 2026-11-02): стек открытых диалогов —
// единственный владелец блокировки скролла body и клавиатурного
// перехвата. Прежде каждый экземпляр вешал свой глобальный keydown и
// безусловно очищал body.style.overflow при закрытии: два вложенных
// диалога — закрытие внутреннего разблокировало скролл за внешним,
// а Escape закрывал оба сразу.
const dialogStack: HTMLElement[] = [];

interface DialogAction {
  label?: string;
  variant?: string;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  icon?: ReactNode;
  className?: string;
  style?: CSSProperties;
  props?: Record<string, unknown>;
}

interface ModernDialogProps {
  isOpen?: boolean;
  onClose?: () => void;
  title?: ReactNode;
  children?: ReactNode;
  customHeader?: ReactNode;
  /**
   * REG-FE-075 (follow-up audit 2026-11-02): доступное имя диалога для
   * случаев, когда заголовок — НЕ строка (customHeader-композиция без
   * текстового `title`). Без него role="dialog" оставался безымянным для
   * скринридеров.
   */
  ariaLabel?: string;
  actions?: ReactNode | DialogAction[];
  maxWidth?: string;
  maxHeight?: string;
  showCloseButton?: boolean;
  closeOnBackdrop?: boolean;
  closeOnEscape?: boolean;
  className?: string;
  dialogClassName?: string;
  dialogStyle?: CSSProperties;
  [key: string]: unknown;
}

const ModernDialog = ({
  isOpen,
  onClose,
  title,
  children,
  customHeader,
  ariaLabel,
  actions,
  maxWidth = '28rem',
  maxHeight = 'calc(100dvh - 2rem)',
  showCloseButton = true,
  closeOnBackdrop = true,
  closeOnEscape = true,
  className = '',
  dialogClassName = '',
  dialogStyle = {},
  ...props
}: ModernDialogProps) => {
  // UX Audit Registrar #5: useTheme() удалён — getColor/theme больше не нужны
  // (все стили перенесены в CSS с macos tokens + [data-theme="dark"] selectors).
  const dialogRef = useRef<HTMLDivElement>(null);

  // REG-FE-076 (follow-up audit 2026-11-02): ловушка фокуса считает только
  // РЕАЛЬНО доступных кандидатов — прежде селектор включал disabled-кнопки
  // и скрытые элементы: «последний tabbable» мог оказаться недостижимым, и
  // Tab с последней живой кнопки выпадал из диалога (реальный кейс
  // CancelDialog: действие disabled, а предшествующая кнопка — последняя
  // «tabbable» по старому подсчёту).
  const FOCUSABLE_SELECTOR =
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  const isFocusableCandidate = (el: Element): el is HTMLElement => {
    const html = el as HTMLElement;
    if ('disabled' in html && (html as { disabled?: boolean }).disabled) return false;
    if (el.getAttribute('aria-hidden') === 'true') return false;
    // jsdom не реализует checkVisibility — там считаем видимым;
    // в реальном браузере скрытые кандидаты отфильтровываются.
    if (typeof html.checkVisibility === 'function') {
      return html.checkVisibility();
    }
    return true;
  };
  const getFocusableCandidates = (): HTMLElement[] =>
    Array.from(dialogRef.current?.querySelectorAll(FOCUSABLE_SELECTOR) ?? []).filter(
      isFocusableCandidate,
    );

  // Фокус-ловушка, стек диалогов и возврат фокуса
  useEffect(() => {
    if (!isOpen) return;

    // REG-FE-080 (follow-up audit 2026-11-02): запоминаем триггер — после
    // закрытия клавиатурный пользователь возвращается на место, а не
    // «проваливается» в body.
    const previouslyFocused = (document.activeElement as HTMLElement | null) ?? null;

    // REG-FE-077 (follow-up audit 2026-11-02): владелец стека. Скролл body
    // блокирует только ПЕРВЫЙ открытый диалог и возвращает только
    // ПОСЛЕДНИЙ закрытый — прежде каждый экземпляр очищал overflow,
    // разблокируя скролл за ещё открытым внешним диалогом. Клавиатуру
    // (Escape/Tab) обрабатывает только ВЕРХНИЙ диалог — внутренние
    // экземпляры больше не соревнуются глобальными слушателями.
    const stackEntry: HTMLElement = dialogRef.current ?? document.createElement('div');
    dialogStack.push(stackEntry);
    if (dialogStack.length === 1) {
      document.body.style.overflow = 'hidden';
    }
    if (process.env.NODE_ENV !== 'production'
      && customHeader && typeof title !== 'string' && !ariaLabel) {
      // REG-FE-075: композиция без доступного имени — заметно в разработке.
      logger.warn(
        '[ModernDialog] customHeader без строкового title/ariaLabel: '
          + 'у диалога нет доступного имени (REG-FE-075).',
      );
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      // REG-FE-077: не верхний диалог клавиатуру не перехватывает.
      if (dialogStack[dialogStack.length - 1] !== stackEntry) return;

      if (e.key === 'Escape' && closeOnEscape) {
        e.preventDefault();
        onClose?.();
      }

      if (e.key === 'Tab') {
        const focusableElements = getFocusableCandidates();

        if (focusableElements.length > 0) {
          const firstElement = focusableElements[0];
          const lastElement = focusableElements[focusableElements.length - 1];

          if (e.shiftKey && document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          } else if (!e.shiftKey && document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    // Фокус на первый доступный элемент (REG-FE-076: тоже отфильтрованный)
    const focusTimer = setTimeout(() => {
      const firstFocusable = getFocusableCandidates()[0];
      if (firstFocusable) {
        firstFocusable.focus();
      }
    }, 100);

    return () => {
      clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleKeyDown);
      // REG-FE-077: снять только СВОЮ регистрацию; скролл возвращает
      // последний закрытый.
      const stackIndex = dialogStack.lastIndexOf(stackEntry);
      if (stackIndex !== -1) {
        dialogStack.splice(stackIndex, 1);
      }
      if (dialogStack.length === 0) {
        document.body.style.overflow = '';
      }
      // REG-FE-080: вернуть фокус триггеру, если он ещё в документе и
      // фокус сейчас внутри закрывающегося диалога (или потерян в body).
      const currentActive = document.activeElement as HTMLElement | null;
      if (
        previouslyFocused
        && previouslyFocused.isConnected
        && (!currentActive
          || currentActive === document.body
          || dialogRef.current?.contains(currentActive))
      ) {
        previouslyFocused.focus();
      }
    };
  }, [isOpen, closeOnEscape, onClose, customHeader, title, ariaLabel]);

  if (!isOpen) return null;

  // UX Audit Registrar #5: backdropButtonStyle и dialogStyles вынесены в CSS,
  // но dialogStyles всё ещё нужен для maxWidth/maxHeight/dialogStyle props.
  const dialogStyles = {
    maxWidth,
    maxHeight,
    ...dialogStyle
  };

  // REG-FE-075 (follow-up audit 2026-11-02): у диалога ВСЕГДА есть
  // доступное имя, когда его можно вывести: строковый title (напрямую или
  // через customHeader-композицию) либо явный ariaLabel. Прежняя логика
  // давала имя только паре customHeader+строковый-title; композиция без
  // title оставалась безымянной для скринридеров.
  const dialogLabelProps = customHeader
    ? { 'aria-label': typeof title === 'string' ? title : ariaLabel }
    : title
      ? { 'aria-labelledby': 'dialog-title' }
      : { 'aria-label': ariaLabel };

  return (
    <div
      className={`modern-dialog-backdrop modern-dialog-backdrop--overlay ${className}`}
      role="presentation"
      {...props}>
      {closeOnBackdrop &&
      <button
        type="button"
        className="modern-dialog-backdrop-button"
        onClick={onClose}
        tabIndex={-1}
        aria-label="Закрыть диалог" />

      }
      
      <div
        ref={dialogRef}
        className={`modern-dialog-container modern-dialog-container--styled ${dialogClassName}`}
        role="dialog"
        aria-modal="true"
        {...dialogLabelProps}
        style={dialogStyles}>
        
        {/* Заголовок */}
        {(customHeader || title || showCloseButton) &&
        <div className="modern-dialog-header">
            {customHeader ?
          customHeader :

          <>
                {title &&
            <h3
              id="dialog-title"
              className="modern-dialog-title modern-dialog-title--styled">
              
                    {title}
                  </h3>
            }
                {showCloseButton &&
            <button
              type="button"
              className="modern-dialog-close modern-dialog-close--styled"
              onClick={onClose}
              aria-label="Закрыть диалог">
              
                    <X size={20} />
                  </button>
            }
              </>
          }
          </div>
        }

        {/* Контент */}
        <div className="modern-dialog-content">
          {children}
        </div>

        {/* Действия */}
        {Array.isArray(actions) && actions.length > 0 &&
        <div
          className="modern-dialog-actions modern-dialog-actions--styled">

            {(actions as DialogAction[]).map((action, index) =>
          <button
            key={index}
            type="button"
            className={`modern-dialog-action ${action.variant || 'secondary'} ${action.className || ''}`}
            onClick={action.onClick}
            disabled={action.disabled}
            style={action.style}
            {...action.props}>
            
                {action.icon && <span className="action-icon">{action.icon}</span>}
                {action.label}
              </button>
          )}
          </div>
        }
      </div>
    </div>);

};


export default ModernDialog;
