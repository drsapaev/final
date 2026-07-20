
import { Button } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * SessionWarningModal — shared session expiry warning (Sprint 10).
 *
 * Replaces duplicate inline-styled modals in DentistPanelUnified and
 * DermatologistPanelUnified. Uses macos tokens + Modal component for
 * consistent styling and dark mode support.
 */
const SessionWarningModal = ({ visible, onDismiss, onExtend }) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  if (!visible) return null;

  return (
    <div
      role="alertdialog"
      aria-label="Предупреждение об истечении сессии"
      style={{
        position: 'fixed',
        top: 0, left: 0, right: 0, bottom: 0,
        background: 'color-mix(in srgb, black, transparent 50%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
      }}
    >
      <div
        className="admin-table-wrapper"
        style={{
          background: 'var(--mac-bg-primary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-lg)',
          padding: 'var(--mac-spacing-6)',
          maxWidth: '420px',
          width: '90%',
          boxShadow: 'var(--mac-shadow-lg)',
        }}
      >
        <h3 style={{
          margin: '0 0 var(--mac-spacing-3) 0',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)',
        }}>
          Сессия скоро истечёт
        </h3>
        <p style={{
          margin: '0 0 var(--mac-spacing-4) 0',
          fontSize: 'var(--mac-font-size-sm)',
          color: 'var(--mac-text-secondary)',
          lineHeight: 1.5,
        }}>
          Ваша сессия истекает. Несохранённые данные могут быть потеряны.
          Сохраните текущий приём или продлите сессию.
        </p>
        <div style={{
          display: 'flex',
          gap: 'var(--mac-spacing-2)',
          justifyContent: 'flex-end',
        }}>
          <Button variant="outline" size="small" onClick={onDismiss}>
            Позже
          </Button>
          <Button
            variant="primary"
            size="small"
            onClick={() => {
              onDismiss();
              onExtend?.();
            }}
          >
            Продлить сессию
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SessionWarningModal;
