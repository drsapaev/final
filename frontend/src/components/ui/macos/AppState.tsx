import React, { useId, type ReactNode, type CSSProperties, type ComponentType, type ReactElement } from 'react';
import Alert from './Alert';
import { useTranslation } from '@/i18n/useTranslation';

const fontFamily = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif';

type LoadingSize = 'sm' | 'small' | 'md' | 'medium' | 'lg' | 'large';
type AppErrorSeverity = 'info' | 'success' | 'warning' | 'error';

interface LoadingSizeStyle {
  spinner: number;
  padding: string;
  title: string;
  gap: string;
}

interface IconWrapperProps {
  style?: CSSProperties;
}

const loadingSizes: Record<LoadingSize, LoadingSizeStyle> = {
  sm: { spinner: 20, padding: '24px', title: 'var(--mac-font-size-base)', gap: '10px' },
  small: { spinner: 20, padding: '24px', title: 'var(--mac-font-size-base)', gap: '10px' },
  md: { spinner: 28, padding: '32px', title: 'var(--mac-font-size-lg)', gap: '12px' },
  medium: { spinner: 28, padding: '32px', title: 'var(--mac-font-size-lg)', gap: '12px' },
  lg: { spinner: 40, padding: '48px', title: 'var(--mac-font-size-xl)', gap: '16px' },
  large: { spinner: 40, padding: '48px', title: 'var(--mac-font-size-xl)', gap: '16px' }
};

const getLoadingSize = (size: LoadingSize): LoadingSizeStyle => loadingSizes[size] || loadingSizes.md;

// Wrap a React element (an icon rendered with props) into a function
// component so the icon branch in AppEmpty below can render it as a
// component and clone+merge styles. When the icon is already a component
// type or anything else, pass through unchanged.
const normalizeIcon = (
  icon: ReactNode | ComponentType<IconWrapperProps> | undefined
): ReactNode | ComponentType<IconWrapperProps> | undefined => {
  if (!React.isValidElement(icon)) {
    return icon;
  }

  const iconElement = icon as ReactElement<{ style?: CSSProperties }>;
  return function AppEmptyIcon(props: IconWrapperProps) {
    return React.cloneElement(iconElement, {
      ...props,
      style: {
        ...props.style,
        ...iconElement.props.style
      }
    });
  };
};

interface AppLoadingProps {
  title?: ReactNode;
  description?: ReactNode;
  size?: LoadingSize;
  ariaLabel?: string;
  className?: string;
  style?: CSSProperties;
}

interface AppEmptyProps {
  title?: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode | ComponentType<IconWrapperProps>;
  className?: string;
  style?: CSSProperties;
}

interface AppErrorProps {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  severity?: AppErrorSeverity;
  className?: string;
  style?: CSSProperties;
}

export const AppLoading = React.forwardRef<HTMLElement, AppLoadingProps>(({
  title = 'Загрузка…',
  description,
  size = 'md',
  ariaLabel,
  className = '',
  style = {}
}, ref) => {
  const { t } = useTranslation();
  void t;
  const currentSize = getLoadingSize(size);

  return (
    <section
      ref={ref}
      className={`mac-app-loading ${className}`.trim()}
      role="status"
      aria-live="polite"
      aria-label={ariaLabel || (typeof title === 'string' ? title : undefined)}
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

// Alert is still an implicit-any component. Cast it to a permissive
// signature so this file can pass strict tsc without waiting for that
// component to be migrated.
type AnyComponent = React.ComponentType<Record<string, unknown>>;
const AlertAny = Alert as unknown as AnyComponent;

// PR-UI-07a-8a: AppEmpty owns its rendering. The markup below is inlined
// verbatim from MacOSEmptyState (size="md", variant="minimal") — the former
// internal delegation target. The DOM contract is unchanged and is guarded
// by __tests__/AppEmpty.icon.test.tsx (PR-8B icon-discrimination coverage).
export const AppEmpty = React.forwardRef<HTMLElement, AppEmptyProps>(({
  title = 'Нет данных',
  description = 'Здесь пока нет данных для отображения.',
  action,
  icon,
  className = '',
  style = {}
}, ref) => {
  const descriptionId = useId();
  const hasDescription = Boolean(description);

  // size="md" / variant="minimal" styles (inlined from MacOSEmptyState).
  const contentStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    padding: '32px',
    background: 'transparent',
    border: 'none',
    borderRadius: '0',
    gap: '16px'
  };

  const iconStyle: CSSProperties = {
    width: 48,
    height: 48,
    color: 'var(--mac-text-tertiary)',
    opacity: 0.6
  };

  const titleStyle = {
    fontSize: 'var(--mac-font-size-lg)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    margin: 0,
    lineHeight: 1.3
  };

  const descriptionStyle = {
    fontSize: 'var(--mac-font-size-base)',
    color: 'var(--mac-text-secondary)',
    margin: 0,
    lineHeight: 1.5,
    maxWidth: '400px'
  };

  const actionStyle = {
    marginTop: '8px'
  };

  const normalizedIcon = normalizeIcon(icon);

  // PR-8B icon-type discrimination, inlined from MacOSEmptyState. A value
  // is renderable as <Icon /> if it is a function component or a component
  // object with $$typeof (forwardRef, memo, lazy) that is NOT a ReactElement
  // and NOT a portal. ReactElements (pre-rendered icons like <Package />)
  // were normalized above into wrapper components that clone+merge styles.
  // Strings, numbers, portals and arrays are plain ReactNode children and
  // render through the <span>{icon}</span> branch without iconStyle.
  // The previous `typeof Icon === 'function'` check missed forwardRef/memo
  // objects (lucide-react) and crashed with "Objects are not valid as a
  // React child" — see MacOSEmptyState.forwardRef.test.tsx history.
  const REACT_PORTAL_TYPE = Symbol.for('react.portal');
  const isIconComponent =
    normalizedIcon !== null &&
    normalizedIcon !== undefined &&
    (typeof normalizedIcon === 'function' ||
      (typeof normalizedIcon === 'object' &&
        normalizedIcon !== null &&
        '$$typeof' in normalizedIcon &&
        !React.isValidElement(normalizedIcon) &&
        (normalizedIcon as { $$typeof: symbol }).$$typeof !== REACT_PORTAL_TYPE));

  // The union type `ReactNode | ComponentType` doesn't narrow via the
  // boolean flag above — same local cast pattern as the former
  // MacOSEmptyState.tsx:160 / StatCard.tsx icon branches.
  const IconComponent = isIconComponent ? (normalizedIcon as React.ElementType) : null;

  return (
    <section
      ref={ref}
      className={`mac-app-empty ${className}`.trim()}
      aria-label={title}
      style={style}
    >
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        aria-describedby={hasDescription ? descriptionId : undefined}
        style={contentStyle}
      >
        {IconComponent && <IconComponent aria-hidden="true" focusable="false" style={iconStyle} />}
        {normalizedIcon && !isIconComponent && <span aria-hidden="true">{normalizedIcon as ReactNode}</span>}

        <h3 style={titleStyle}>{title}</h3>

        {hasDescription && (
          <p id={descriptionId} style={descriptionStyle}>{description}</p>
        )}

        {action && (
          <div style={actionStyle}>
            {action}
          </div>
        )}
      </div>
    </section>
  );
});

AppEmpty.displayName = 'AppEmpty';

export const AppError = React.forwardRef<HTMLElement, AppErrorProps>(({
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
    <AlertAny
      type={severity}
      title={title}
      description={description}
      action={action}
    />
  </section>
));

AppError.displayName = 'AppError';

