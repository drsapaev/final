import React, { useEffect, useId, useRef, type CSSProperties, type ReactNode } from 'react';
import { X } from 'lucide-react';
import './ModernDialog.css';
import logger from '../../utils/logger';

// REG-FE-077 (follow-up audit 2026-11-02): стек открытых диалогов —
// единственный владелец блокировки скролла body и клавиатурного
// перехвата. Прежде каждый экземпляр вешал свой глобальный keydown и
// безусловно очищал body.style.overflow при закрытии: два вложенных
// диалога — закрытие внутреннего разблокировало скролл за внешним,
// а Escape закрывал оба сразу.
const dialogStack: HTMLElement[] = [];

// REG-FE-076: only available controls participate in the focus trap.
const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
const isFocusableCandidate = (el: Element): el is HTMLElement => {
  const html = el as HTMLElement;
  if ('disabled' in html && (html as { disabled?: boolean }).disabled) return false;
  if (el.getAttribute('aria-hidden') === 'true') return false;
  // jsdom does not implement checkVisibility.
  if (typeof html.checkVisibility === 'function') {
    return html.checkVisibility();
  }
  return true;
};
const getFocusableCandidates = (dialog: HTMLElement): HTMLElement[] =>
  Array.from(dialog.querySelectorAll(FOCUSABLE_SELECTOR)).filter(isFocusableCandidate);

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
  const focusOriginRef = useRef<HTMLElement | null>(null);
  const initialFocusSourceRef = useRef<HTMLElement | null>(null);
  const hasFocusedInsideRef = useRef(false);
  const titleId = useId();

  const hasUnnamedCustomHeader = Boolean(customHeader) && typeof title !== 'string' && !ariaLabel;
  useEffect(() => {
    if (isOpen && process.env.NODE_ENV !== 'production' && hasUnnamedCustomHeader) {
      logger.warn(
        '[ModernDialog] customHeader без строкового title/ariaLabel: '
          + 'у диалога нет доступного имени (REG-FE-075).',
      );
    }
  }, [isOpen, hasUnnamedCustomHeader]);

  // The stack and focus belong to an open/close session. A fresh header,
  // callback, or title during typing must not close and reopen that session.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!isOpen || !dialog) return;

    // REG-FE-080 (follow-up audit 2026-11-02): запоминаем триггер — после
    // закрытия клавиатурный пользователь возвращается на место, а не
    // «проваливается» в body.
    // Child autoFocus can run before this effect. In that case focus capture
    // retains the element that was active before focus entered the dialog.
    const activeElement = document.activeElement as HTMLElement | null;
    const previouslyFocused = activeElement && dialog.contains(activeElement)
      ? focusOriginRef.current
      : activeElement;
    if (!hasFocusedInsideRef.current) {
      initialFocusSourceRef.current = activeElement;
    }

    // REG-FE-077 (follow-up audit 2026-11-02): владелец стека. Скролл body
    // блокирует только ПЕРВЫЙ открытый диалог и возвращает только
    // ПОСЛЕДНИЙ закрытый — прежде каждый экземпляр очищал overflow,
    // разблокируя скролл за ещё открытым внешним диалогом. Клавиатуру
    // (Escape/Tab) обрабатывает только ВЕРХНИЙ диалог — внутренние
    // экземпляры больше не соревнуются глобальными слушателями.
    const stackEntry = dialog;
    // React runs child effects before parent effects when both mount at once.
    // Keep an enclosing dialog below any already registered descendants.
    const firstDescendantIndex = dialogStack.findIndex((entry) => dialog.contains(entry));
    if (firstDescendantIndex === -1) {
      dialogStack.push(stackEntry);
    } else {
      dialogStack.splice(firstDescendantIndex, 0, stackEntry);
    }
    if (dialogStack.length === 1) {
      document.body.style.overflow = 'hidden';
    }

    return () => {
      // REG-FE-077: снять только СВОЮ регистрацию; скролл возвращает
      // последний закрытый.
      const stackIndex = dialogStack.lastIndexOf(stackEntry);
      if (stackIndex !== -1) {
        dialogStack.splice(stackIndex, 1);
      }
      if (dialogStack.length === 0) {
        document.body.style.overflow = '';
      }
      // React StrictMode can replay this effect while the dialog is still
      // mounted. Restore and clear the origin only when it actually closes.
      if (!dialog.isConnected) {
        // REG-FE-080: return focus only if it has not moved elsewhere.
        const currentActive = document.activeElement as HTMLElement | null;
        if (
          previouslyFocused
          && previouslyFocused.isConnected
          && (!currentActive
            || currentActive === document.body
            || dialog.contains(currentActive))
        ) {
          previouslyFocused.focus();
        }
        focusOriginRef.current = null;
        initialFocusSourceRef.current = null;
        hasFocusedInsideRef.current = false;
      }
    };
  }, [isOpen]);

  // Initialize focus, or recover it when a wizard step removes the active
  // control. Header/content updates must preserve focus that is already inside.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!isOpen || !dialog) return;

    const focusTimer = setTimeout(() => {
      const activeElement = document.activeElement;
      if (dialogStack[dialogStack.length - 1] !== dialog
        || dialog.contains(activeElement)) return;
      // A separate modal (such as the wizard's confirmation) can take focus
      // without joining this stack. Do not pull focus back from another control.
      // The element active at open is the exception for initial focus.
      if (activeElement && activeElement !== document.body
        && (hasFocusedInsideRef.current || activeElement !== initialFocusSourceRef.current)) return;
      getFocusableCandidates(dialog)[0]?.focus();
    }, 100);

    return () => clearTimeout(focusTimer);
  }, [isOpen, customHeader, title, ariaLabel, children]);

  // Keyboard options may change while open; updating this listener must not
  // reset focus or change which dialog is on top.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!isOpen || !dialog) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (dialogStack[dialogStack.length - 1] !== dialog) return;
      const activeElement = document.activeElement;
      const focusedModal = activeElement?.closest('[role="dialog"][aria-modal="true"]');
      if (focusedModal && focusedModal !== dialog && !focusedModal.contains(dialog)) return;

      if (e.key === 'Escape' && closeOnEscape) {
        e.preventDefault();
        onClose?.();
      }

      if (e.key === 'Tab') {
        const focusableElements = getFocusableCandidates(dialog);
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
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, closeOnEscape, onClose]);

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
      ? { 'aria-labelledby': titleId }
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
        onFocusCapture={(event) => {
          if (!event.currentTarget.contains(event.target)) return;
          hasFocusedInsideRef.current = true;
          if (event.relatedTarget instanceof HTMLElement
            && !event.currentTarget.contains(event.relatedTarget)) {
            focusOriginRef.current = event.relatedTarget;
          }
        }}
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
              id={titleId}
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
