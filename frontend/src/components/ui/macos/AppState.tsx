// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React from 'react';
import PropTypes from 'prop-types';

import Alert from './Alert';
import MacOSEmptyState from './MacOSEmptyState';
import { useTranslation } from '../../../i18n/useTranslation';

const fontFamily = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif';

const loadingSizes = {
  sm: { spinner: 20, padding: '24px', title: 'var(--mac-font-size-base)', gap: '10px' },
  small: { spinner: 20, padding: '24px', title: 'var(--mac-font-size-base)', gap: '10px' },
  md: { spinner: 28, padding: '32px', title: 'var(--mac-font-size-lg)', gap: '12px' },
  medium: { spinner: 28, padding: '32px', title: 'var(--mac-font-size-lg)', gap: '12px' },
  lg: { spinner: 40, padding: '48px', title: 'var(--mac-font-size-xl)', gap: '16px' },
  large: { spinner: 40, padding: '48px', title: 'var(--mac-font-size-xl)', gap: '16px' }
};

const getLoadingSize = (size) => loadingSizes[size] || loadingSizes.md;

const normalizeIcon = (icon) => {
  if (!React.isValidElement(icon)) {
    return icon;
  }

  return function AppEmptyIcon(props) {
    return React.cloneElement(icon, {
      ...props,
      style: {
        ...props.style,
        ...icon.props.style
      }
    });
  };
};

export const AppLoading = React.forwardRef(({
  title = 'Загрузка…',
  description,
  size = 'md',
  ariaLabel,
  className = '',
  style = {}
}, ref) => {
  const currentSize = getLoadingSize(size);

  return (
    <section
      ref={ref}
      className={`mac-app-loading ${className}`.trim()}
      role="status"
      aria-live="polite"
      aria-label={ariaLabel || title}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: currentSize.gap,
        minHeight: '160px',
        padding: currentSize.padding,
        color: 'var(--mac-text-primary)',
        textAlign: 'center',
        fontFamily,
        ...style
      }}
    >
      <svg
        aria-hidden="true"
        className="mac-app-loading-spinner"
        width={currentSize.spinner}
        height={currentSize.spinner}
        viewBox="0 0 24 24"
        fill="none"
        style={{
          color: 'var(--mac-accent-blue)',
          animation: 'mac-app-loading-spin 0.9s linear infinite'
        }}
      >
        <circle
          cx="12"
          cy="12"
          r="9"
          stroke="currentColor"
          strokeWidth="3"
          strokeDasharray="18 18"
          strokeLinecap="round"
          opacity="0.9"
        />
      </svg>

      <div>
        <h3
          style={{
            margin: 0,
            fontSize: currentSize.title,
            fontWeight: 'var(--mac-font-weight-semibold)',
            lineHeight: 1.3
          }}
        >
          {title}
        </h3>

        {description && (
          <p
            style={{
              margin: '6px 0 0',
              maxWidth: 420,
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-base)',
              lineHeight: 1.5
            }}
          >
            {description}
          </p>
        )}
      </div>

      <style>{`
        @keyframes mac-app-loading-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        @media (prefers-reduced-motion: reduce) {
          .mac-app-loading-spinner {
            animation: none !important;
          }
        }
      `}</style>
    </section>
  );
});

AppLoading.displayName = 'AppLoading';

export const AppEmpty = React.forwardRef(({
  title = 'Нет данных',
  description = 'Здесь пока нет данных для отображения.',
  action,
  icon,
  className = '',
  style = {}
}, ref) => (
  <section
    ref={ref}
    className={`mac-app-empty ${className}`.trim()}
    aria-label={title}
    style={style}
  >
    <MacOSEmptyState
      title={title}
      description={description}
      action={action}
      icon={normalizeIcon(icon)}
      variant="minimal"
    />
  </section>
));

AppEmpty.displayName = 'AppEmpty';

export const AppError = React.forwardRef(({
  title = 'Не удалось загрузить данные',
  description = 'Проверьте соединение и попробуйте еще раз.',
  action,
  severity = 'error',
  className = '',
  style = {}
}, ref) => (
  <section
    ref={ref}
    className={`mac-app-error ${className}`.trim()}
    style={style}
  >
    <Alert
      type={severity}
      title={title}
      description={description}
      action={action}
    />
  </section>
));

AppError.displayName = 'AppError';

AppLoading.propTypes = {
  ariaLabel: PropTypes.string,
  className: PropTypes.string,
  description: PropTypes.node,
  size: PropTypes.oneOf(['sm', 'small', 'md', 'medium', 'lg', 'large']),
  style: PropTypes.object,
  title: PropTypes.node
};

AppEmpty.propTypes = {
  action: PropTypes.node,
  className: PropTypes.string,
  description: PropTypes.node,
  icon: PropTypes.oneOfType([PropTypes.elementType, PropTypes.node]),
  style: PropTypes.object,
  title: PropTypes.string
};

AppError.propTypes = {
  action: PropTypes.node,
  className: PropTypes.string,
  description: PropTypes.node,
  severity: PropTypes.oneOf(['info', 'success', 'warning', 'error']),
  style: PropTypes.object,
  title: PropTypes.node
};
