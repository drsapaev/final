// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useVirtualizer } from '@tanstack/react-virtual';
// STRAT#28: QueueCard already wrapped in React.memo for per-item performance.
import QueueCard from './QueueCard';
// STRAT#27: t() for load-more button labels.
import { Button, Icon } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * STRAT#27: VirtualizedQueueList — virtualized rendering for 1000+ queue entries.
 *
 * Ранее LabQueueWorkbench рендерил все visibleCount записей через .slice().map().
 * При 100+ записях это вызывало тормоза DOM. Теперь используется
 * @tanstack/react-virtual (уже установлен в проекте, используется в ChatWindow)
 * — рендерятся только видимые в viewport карточки + overscan buffer.
 *
 * Performance: O(visible_count) вместо O(total_count) DOM nodes.
 * При 1000 записях рендерится ~15-20 карточек вместо всех 1000.
 *
 * Props:
 *   - appointments: full sorted array (virtualizer handles which to render)
 *   - selectedAppointment: for isSelected check
 *   - onOpenAppointment: click handler
 *   - onLoadMore: server-side pagination callback
 *   - hasMore: whether more entries can be loaded from server
 *   - loadingMore: loading state for load-more button
 *   - queueTotal: total entries on server (for remaining count)
 */
const CARD_ESTIMATE_HEIGHT = 180; // average card height with services + badges
const OVERSCAN = 5; // render 5 extra cards above/below viewport

export default function VirtualizedQueueList({
  appointments,
  selectedAppointment,
  onOpenAppointment,
  onLoadMore,
  hasMore = false,
  loadingMore = false,
  queueTotal = 0,
}) {
  const { t } = useTranslation();
  const scrollRef = useRef(null);

  const rowVirtualizer = useVirtualizer({
    count: appointments.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => CARD_ESTIMATE_HEIGHT,
    overscan: OVERSCAN,
  });

  // STRAT#27: auto-load more when user scrolls near the bottom
  // (infinite scroll pattern — complements the manual load-more button)
  useEffect(() => {
    if (!hasMore || loadingMore || !onLoadMore) return;
    const scrollEl = scrollRef.current;
    if (!scrollEl) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollEl;
      // Trigger load when user is within 3 card heights of the bottom
      if (scrollHeight - scrollTop - clientHeight < CARD_ESTIMATE_HEIGHT * 3) {
        onLoadMore();
      }
    };

    scrollEl.addEventListener('scroll', handleScroll, { passive: true });
    return () => scrollEl.removeEventListener('scroll', handleScroll);
  }, [hasMore, loadingMore, onLoadMore]);

  const virtualItems = rowVirtualizer.getVirtualItems();

  return (
    <div
      ref={scrollRef}
      className="lqw-virtualized-list"
      style={{
        height: '100%',
        maxHeight: '70vh',
        overflow: 'auto',
        position: 'relative',
      }}
    >
      {/* Total height spacer — virtualizer positions items absolutely */}
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualItems.map((virtualItem) => {
          const appointment = appointments[virtualItem.index];
          if (!appointment) return null;
          return (
            <div
              key={appointment.id}
              data-index={virtualItem.index}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualItem.start}px)`,
                paddingBottom: 'var(--mac-spacing-2)',
              }}
            >
              <QueueCard
                appointment={appointment}
                isSelected={selectedAppointment?.id === appointment.id}
                onOpenAppointment={onOpenAppointment}
              />
            </div>
          );
        })}
      </div>

      {/* Server-side load-more button (manual fallback for infinite scroll) */}
      {hasMore && onLoadMore && (
        <div className="lqw-load-more">
          <Button
            variant="outline"
            onClick={onLoadMore}
            disabled={loadingMore}
            aria-label={t('queue.load_more_aria')}
          >
            <Icon name={loadingMore ? 'arrow.clockwise' : 'arrow.down'} size={14} />
            {loadingMore
              ? t('queue.loading')
              : `${t('queue.show_more')} (${queueTotal - appointments.length} ${t('queue.remaining')})`}
          </Button>
        </div>
      )}
    </div>
  );
}

VirtualizedQueueList.propTypes = {
  appointments: PropTypes.array.isRequired,
  selectedAppointment: PropTypes.object,
  onOpenAppointment: PropTypes.func.isRequired,
  onLoadMore: PropTypes.func,
  hasMore: PropTypes.bool,
  loadingMore: PropTypes.bool,
  queueTotal: PropTypes.number,
};
