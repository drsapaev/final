/**
 * DataCard — canonical data panel primitive for the clinic UI kit.
 *
 * PR-UI-11-1 (dashboard data-first) per `docs/UI_REMEDIATION_PLAN.md` §PR-UI-11.
 *
 * ## Purpose
 *
 * `Card` is a generic container. `StatCard` is a single metric. `DataCard`
 * fills the gap between them: a titled panel for **lists / timelines /
 * activity feeds / queue summaries**. The header carries title +
 * description + optional action; the body encapsulates the three async
 * branches (loading skeleton, error state, empty state, populated content)
 * that every data-driven dashboard section repeats.
 *
 * ## Migration path
 *
 * New canonical primitive introduced in PR-UI-11-1. Replaces the inline
 * `MacOSCard className="admin-bg-var-mac-gradient-..."` + ad-hoc
 * `loading ? <Skeleton> : error ? <AppEmpty> : empty ? ... : <body>`
 * pattern previously copy-pasted in AdminDashboard.tsx. Legacy `MacOSCard`
 * consumers in other files (66 files, 329 JSX uses) are NOT migrated in
 * this increment — they are scheduled for PR-UI-11-2+ follow-ups following
 * the PR-UI-09c incremental precedent.
 *
 * ## Zero-glass invariant
 *
 * Per `AGENTS_UI.md` antipattern table, glass/backdrop-filter surfaces are
 * forbidden on cards. DataCard renders ONLY the canonical `Card` background
 * (`var(--mac-card-bg)`); no gradients, no `color-mix(in srgb, ..., white 72%)`
 * inset surfaces, no `backdrop-filter`. The header divider is a 1px
 * `var(--mac-separator)` rule.
 *
 * ## API
 *
 * The `loading` / `error` / `empty` / `children` branches are mutually
 * exclusive in that order. Callers can supply a custom `loadingSkeleton`
 * for non-default skeleton layouts (e.g., timeline rows, KPI tiles).
 */

import React, { type CSSProperties, type ReactNode } from 'react';

import { AlertCircle, RefreshCw } from 'lucide-react';

import Card from './macos/Card';
import { AppEmpty } from './macos/AppState';
import Skeleton from './macos/Skeleton';
import Button from './macos/Button';

export type DataCardVariant = 'default' | 'outlined' | 'filled';
export type DataCardDensity = 'compact' | 'default' | 'comfortable';

export interface DataCardProps {
  /** Optional header title. When omitted along with `action` / `icon` /
   * `description`, the header is not rendered. */
  title?: ReactNode;
  /** Optional sub-label rendered under the title. */
  description?: ReactNode;
  /** Optional leading icon rendered in the title row. */
  icon?: ReactNode;
  /** Optional trailing action node — typically a `Button` or a small
   * toolbar. Rendered at the right edge of the header. */
  action?: ReactNode;
  /** Optional badge rendered next to the title. Commonly a count. */
  badge?: ReactNode;
  /** Body content. Ignored when `loading`, `error`, or `empty` is active. */
  children?: ReactNode;
  /** When `true`, renders `loadingSkeleton` (or a default Skeleton variant)
   * instead of `children`. Also sets `aria-busy` on the section. */
  loading?: boolean;
  /** Custom skeleton rendered when `loading` is `true`. Defaults to a
   * three-line text skeleton; callers can pass a richer layout. */
  loadingSkeleton?: ReactNode;
  /** When non-null, the body shows an error state. Pass the error message
   * string; it is rendered via `AppEmpty.title`. Mutually exclusive with
   * `loading`. */
  error?: string | null;
  /** When non-null, the body shows the empty state. Rendered via
   * `AppEmpty.title`. Mutually exclusive with `loading` and `error`. */
  empty?: string | null;
  /** Optional retry handler. When provided and `error` is set, a Retry
   * button is rendered below the error message. */
  onRetry?: () => void;
  /** Optional retry button label (defaults to a localized "Retry"). */
  retryLabel?: ReactNode;
  /** Optional visual variant. Defaults to `default` (Card surface). */
  variant?: DataCardVariant | string;
  /** Optional density. Defaults to `default` (20px padding). */
  density?: DataCardDensity | string;
  /** Custom className on the outer section. */
  className?: string;
  /** Custom className on the body wrapper. */
  bodyClassName?: string;
  /** Custom inline style on the outer section. */
  style?: CSSProperties;
  /** ARIA label for the outer section. */
  ariaLabel?: string;
  /** Role for the outer section. Defaults to `group`. */
  role?: string;
}

const densityPadding: Record<DataCardDensity, CardPaddingValue> = {
  compact: 'small',
  default: 'default',
  comfortable: 'large',
};

// Card's padding prop accepts the literal strings 'none' | 'small' | 'default'
// | 'large' but its TypeScript type widens to `string`. We re-narrow here so
// callers of DataCard get autocompletion + type-safety on the density enum.
type CardPaddingValue = 'none' | 'small' | 'default' | 'large';

const variantToCardVariant: Record<DataCardVariant, string> = {
  default: 'default',
  outlined: 'outlined',
  filled: 'filled',
};

const DataCard: React.FC<DataCardProps> = ({
  title,
  description,
  icon,
  action,
  badge,
  children,
  loading = false,
  loadingSkeleton,
  error = null,
  empty = null,
  onRetry,
  retryLabel = 'Повторить',
  variant = 'default',
  density = 'default',
  className = '',
  bodyClassName = '',
  style,
  ariaLabel,
  role = 'group',
}) => {
  const showHeader = Boolean(title || description || icon || action || badge);
  const cardVariant = variantToCardVariant[variant as DataCardVariant] ?? 'default';
  const cardPadding = densityPadding[density as DataCardDensity] ?? 'default';

  const renderBody = (): ReactNode => {
    if (loading) {
      return loadingSkeleton ?? <Skeleton type="text" count={3} />;
    }
    if (error) {
      return (
        <AppEmpty
          icon={AlertCircle}
          title={error}
          action={onRetry ? (
            <Button onClick={onRetry} variant="primary" size="small">
              <RefreshCw size={14} aria-hidden="true" />
              {retryLabel}
            </Button>
          ) : undefined}
        />
      );
    }
    if (empty) {
      return <AppEmpty title={empty} />;
    }
    return children;
  };

  return (
    <Card
      variant={cardVariant}
      padding={cardPadding}
      className={`data-card ${className}`.trim()}
      style={style}
      role={role}
      aria-label={ariaLabel}
      aria-busy={loading || undefined}
    >
      {showHeader && (
        <header
          className="data-card__header"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            marginBottom: '16px',
            paddingBottom: '12px',
            borderBottom: '1px solid var(--mac-separator)',
          }}
        >
          <div
            className="data-card__title-row"
            style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}
          >
            {icon && (
              <span className="data-card__icon" style={{ display: 'inline-flex', flexShrink: 0 }}>
                {icon}
              </span>
            )}
            <div className="data-card__title-block" style={{ minWidth: 0, flex: 1 }}>
              {title && (
                <h3
                  className="data-card__title"
                  style={{
                    margin: 0,
                    fontSize: 'var(--mac-font-size-lg)',
                    fontWeight: 600,
                    color: 'var(--mac-text-primary)',
                    lineHeight: 1.3,
                  }}
                >
                  {title}
                </h3>
              )}
              {description && (
                <p
                  className="data-card__description"
                  style={{
                    margin: 0,
                    marginTop: title ? '4px' : 0,
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)',
                    lineHeight: 1.4,
                  }}
                >
                  {description}
                </p>
              )}
            </div>
            {badge && (
              <span className="data-card__badge" style={{ flexShrink: 0 }}>
                {badge}
              </span>
            )}
          </div>
          {action && (
            <div className="data-card__action" style={{ flexShrink: 0 }}>
              {action}
            </div>
          )}
        </header>
      )}
      <div className={`data-card__body ${bodyClassName}`.trim()}>{renderBody()}</div>
    </Card>
  );
};

DataCard.displayName = 'DataCard';

export default DataCard;
