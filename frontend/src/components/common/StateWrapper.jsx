/**
 * StateWrapper — generic loading / error / empty state wrapper for Unified*
 * panels and any component that fetches async data.
 *
 * P-025 fix: UnifiedSettings, UnifiedUserManagement, UnifiedFinance, UnifiedReports
 * all delegated loading/error/empty handling to their child components, with no
 * fallback — if a child failed or returned no data, the user saw a blank panel.
 * (Note: UnifiedAITools, UnifiedTelegramManagement were removed as dead code in
 * Step 2; UnifiedNotifications was wired to /admin/push-notifications in Step 3.)
 *
 * Usage:
 *   <StateWrapper
 *     isLoading={loading}
 *     error={error}
 *     isEmpty={!loading && !error && (!data || data.length === 0)}
 *     emptyTitle="Настроек пока нет"
 *     emptyMessage="Создайте первую настройку, чтобы увидеть её здесь."
 *     emptyAction={<Button onClick={handleCreate}>Создать</Button>}
 *   >
 *     {children}
 *   </StateWrapper>
 *
 * Falls through to children when none of the states apply.
 */
import { useEffect, useRef, useState } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { MacOSEmptyState } from '../ui/macos';
import { Skeleton } from '../ui/macos';
import { Button } from '../ui/macos';

const DEFAULT_SKELETON_ROWS = 4;

export function StateWrapper({
  isLoading = false,
  error = null,
  isEmpty = false,
  emptyTitle = 'Нет данных',
  emptyMessage = 'Записи пока не созданы. Создайте первую, чтобы увидеть её здесь.',
  emptyAction = null,
  emptyIcon = null,
  skeletonRows = DEFAULT_SKELETON_ROWS,
  skeletonHeight = 56,
  errorTitle = 'Не удалось загрузить данные',
  onRetry = null,
  children,
}) {
  // Track whether the user has ever seen data, so we can keep showing
  // stale content with a refresh banner instead of a hard empty state
  // when a refetch fails. (Pattern borrowed from React Query's stale-while-revalidate.)
  const hasHadDataRef = useRef(false);
  const [, forceTick] = useState(0);

  useEffect(() => {
    if (!isLoading && !error && !isEmpty) {
      hasHadDataRef.current = true;
      forceTick((t) => t + 1);
    }
  }, [isLoading, error, isEmpty]);

  // First load: show skeleton
  if (isLoading && !hasHadDataRef.current) {
    return (
      <div style={{ padding: '16px 8px', display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
        {Array.from({ length: skeletonRows }).map((_, i) => (
          <Skeleton
            key={i}
            height={skeletonHeight}
            width="100%"
            borderRadius="12px"
          />
        ))}
      </div>
    );
  }

  // Hard error and never had data: show error state
  if (error && !hasHadDataRef.current) {
    const errMsg = typeof error === 'string' ? error : (error?.message || error?.toString?.() || 'Неизвестная ошибка');
    return (
      <MacOSEmptyState
        icon={<AlertCircle size={36} style={{ color: 'var(--mac-error, #ff3b30)' }} />}
        title={errorTitle}
        message={errMsg}
        action={
          onRetry ? (
            <Button variant="outline" size="md" onClick={onRetry}>
              <RefreshCw size={14} style={{ marginRight: 6 }} />
              Повторить
            </Button>
          ) : null
        }
      />
    );
  }

  // Empty state (and never had data)
  if (isEmpty && !hasHadDataRef.current) {
    return (
      <MacOSEmptyState
        icon={emptyIcon}
        title={emptyTitle}
        message={emptyMessage}
        action={emptyAction}
      />
    );
  }

  // Otherwise: render children. If there's a background error and we have
  // stale data, surface a subtle warning banner at the top.
  return (
    <>
      {error && hasHadDataRef.current && (
        <div
          role="alert"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '10px 14px',
            marginBottom: 'var(--mac-spacing-3)',
            borderRadius: 'var(--mac-radius-lg)',
            backgroundColor: 'color-mix(in srgb, var(--mac-warning, #ff9500) 8%, transparent)',
            border: '1px solid color-mix(in srgb, var(--mac-warning, #ff9500) 35%, transparent)',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
          }}
        >
          <AlertCircle size={16} style={{ color: 'var(--mac-warning, #ff9500)', flexShrink: 0 }} />
          <span style={{ flex: 1 }}>
            Не удалось обновить данные. Показаны последние сохранённые значения.
          </span>
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
            >
              <RefreshCw size={12} style={{ marginRight: 4 }} />
              Повторить
            </Button>
          )}
        </div>
      )}
      {children}
    </>
  );
}

export default StateWrapper;
