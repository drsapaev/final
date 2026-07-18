
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
/**
 * Shared ConfirmDialog component + useConfirm hook.
 *
 * P-013 fix: replaces 28 `window.confirm()` calls scattered across the codebase.
 * Native browser confirm() dialogs break the macOS-style visual language of the
 * app and cannot express the specific action being confirmed (they always show
 * a generic "OK / Cancel"). This module provides:
 *
 *   1. <ConfirmDialog /> — declarative component for cases where the caller
 *      already manages open/close state.
 *
 *   2. useConfirm() — imperative hook that returns a `confirm(options)` function.
 *      The hook renders a single ConfirmDialog mounted at the app root via
 *      React Portal, so any deep component can call `await confirm({...})`
 *      without prop-drilling open state.
 *
 * Migration guide:
 *   // Before:
 *   const ok = window.confirm('Delete patient ' + name + '?');
 *   if (ok) await deletePatient(id);
 *
 *   // After:
 *   const confirm = useConfirm();
 *   const ok = await confirm({
 *     title: 'Удаление пациента',
 *     message: `Удалить пациента ${name}? Действие необратимо.`,
 *     confirmLabel: i18n.t('misc.delete'),
 *     cancelLabel: i18n.t('misc.cancel'),
 *     intent: 'danger',  // 'danger' | 'warning' | 'primary'
 *   });
 *   if (ok) await deletePatient(id);
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, Trash2, AlertOctagon, CheckCircle2 } from 'lucide-react';
import { Modal as ModalRaw } from '../ui/macos';
import { Button } from '../ui/macos';
import { Input } from '../ui/macos';
import React from "react";
const Modal = ModalRaw as unknown as React.ComponentType<Record<string, unknown>>;

const INTENT_CONFIG = {
  danger: {
    icon: Trash2,
    iconColor: 'var(--mac-error, #ff3b30)',
    confirmVariant: 'danger',
  },
  warning: {
    icon: AlertTriangle,
    iconColor: 'var(--mac-warning, #ff9500)',
    confirmVariant: 'warning',
  },
  destructive: {
    // alias for danger with stronger warning icon
    icon: AlertOctagon,
    iconColor: 'var(--mac-error, #ff3b30)',
    confirmVariant: 'danger',
  },
  primary: {
    icon: CheckCircle2,
    iconColor: 'var(--mac-success, #34c759)',
    confirmVariant: 'primary',
  },
};

const DEFAULT_INTENT = 'warning';

/**
 * Declarative ConfirmDialog. Use this if you prefer to manage isOpen state
 * in the parent component. For most use cases, useConfirm() below is simpler.
 */
export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title = 'Подтверждение',
  message,
  description,
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  intent = DEFAULT_INTENT,
  requireText = null, // optional: require user to type this exact text to enable confirm
}) {
  const config = INTENT_CONFIG[intent] || INTENT_CONFIG[DEFAULT_INTENT];
  const Icon = config.icon;
  const [typedText, setTypedText] = useState('');

  useEffect(() => {
    if (!isOpen) setTypedText('');
  }, [isOpen]);

  const isConfirmDisabled = requireText !== null && typedText !== requireText;

  const handleConfirm = () => {
    // t accessed via closure or i18n.t()
    onConfirm?.();
    onClose?.();
  };

  const handleCancel = () => {
    onClose?.();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleCancel}
      title={title}
      size="small"
      closable
    >
      <div style={{
        display: 'flex',
        gap: 'var(--mac-spacing-4)',
        alignItems: 'flex-start',
        padding: '8px 4px',
      }}>
        <div style={{
          flexShrink: 0,
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: `color-mix(in srgb, ${config.iconColor} 14%, transparent)`,
        }}>
          <Icon size={20} style={{ color: config.iconColor }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            marginBottom: description || message ? '8px' : 0,
            lineHeight: 1.3,
          }}>
            {title}
          </div>
          {message && (
            <div style={{
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              lineHeight: 1.5,
              marginBottom: description ? '8px' : 0,
            }}>
              {message}
            </div>
          )}
          {description && (
            <div style={{
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)',
              lineHeight: 1.5,
            }}>
              {description}
            </div>
          )}
          {requireText !== null && (
            <div style={{ marginTop: 'var(--mac-spacing-3)' }}>
              <label
                htmlFor="confirm-dialog-require-text"
                style={{
                  display: 'block',
                  fontSize: 'var(--mac-font-size-xs)',
                  color: 'var(--mac-text-secondary)',
                  marginBottom: 'var(--mac-spacing-2)',
                }}
              >
                Введите <code style={{
                  padding: '2px 6px',
                  backgroundColor: 'var(--mac-bg-secondary, rgba(0,0,0,0.05))',
                  borderRadius: 'var(--mac-radius-sm)',
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                  fontSize: 'var(--mac-font-size-xs)',
                }}>{requireText}</code> для подтверждения:
              </label>
              <Input
                id="confirm-dialog-require-text"
                type="text"
                value={typedText}
                onChange={(e) => setTypedText(e.target.value)}
                autoFocus
                aria-label={`Введите ${requireText} для подтверждения действия`}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: 'var(--mac-radius-md)',
                  border: '1px solid var(--mac-border, rgba(0,0,0,0.12))',
                  backgroundColor: 'var(--mac-bg-primary, #fff)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          )}
        </div>
      </div>
      <div style={{
        display: 'flex',
        justifyContent: 'flex-end',
        gap: 'var(--mac-spacing-2)',
        marginTop: 'var(--mac-spacing-5)',
      }}>
        <Button
          variant="outline"
          size="default"
          onClick={handleCancel}
        >
          {cancelLabel}
        </Button>
        <Button
          variant={config.confirmVariant}
          size="default"
          onClick={handleConfirm}
          disabled={isConfirmDisabled}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

/**
 * Imperative confirm hook. Returns a function `confirm(options)` that returns
 * a Promise<boolean>. The hook mounts a single ConfirmDialog at the app root
 * via React Portal, so callers don't need to manage open state.
 *
 * Usage:
 *   const confirm = useConfirm();
 *   async function handleDelete() {
 *     const ok = await confirm({
 *       title: 'Удалить пациента?',
 *       message: 'Действие необратимо.',
 *       intent: 'danger',
 *       confirmLabel: t('misc.delete'),
 *     });
 *     if (ok) await api.delete(`/patients/${id}`);
 *   }
 */
export function useConfirm() {
  const [state, setState] = useState({
    isOpen: false,
    options: {},
  });
  const resolverRef = useRef(null);

  const confirm = useCallback((options) => {
    return new Promise((resolve) => {
      // If a previous confirm is somehow still open, resolve it as false
      // (user implicitly cancelled by triggering a new confirm).
      if (resolverRef.current) {
        resolverRef.current(false);
        resolverRef.current = null;
      }
      resolverRef.current = resolve;
      setState({ isOpen: true, options });
    });
  }, []);

  const handleClose = useCallback(() => {
    setState((prev) => ({ ...prev, isOpen: false }));
    if (resolverRef.current) {
      resolverRef.current(false);
      resolverRef.current = null;
    }
  }, []);

  const handleConfirm = useCallback(() => {
    setState((prev) => ({ ...prev, isOpen: false }));
    if (resolverRef.current) {
      resolverRef.current(true);
      resolverRef.current = null;
    }
  }, []);

  // Cleanup on unmount: resolve any pending promise as false
  useEffect(() => {
    return () => {
      if (resolverRef.current) {
        resolverRef.current(false);
        resolverRef.current = null;
      }
    };
  }, []);

  // Render the dialog via portal to document.body so it overlays everything
  const ConfirmDialogSelf = ConfirmDialog as unknown as React.ComponentType<Record<string, unknown>>;
  const dialog = typeof document !== 'undefined' ? createPortal(
    <ConfirmDialogSelf
      isOpen={state.isOpen}
      onClose={handleClose}
      onConfirm={handleConfirm}
      {...state.options}
    />,
    document.body
  ) : null;

  return [confirm, dialog];
}

export default ConfirmDialog;
