import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/VirtualizedQueueList.tsx'),
  'utf8'
);

describe('VirtualizedQueueList STRAT#27 — @tanstack/react-virtual', () => {
  it('imports useVirtualizer from @tanstack/react-virtual', () => {
    expect(source).toContain("from '@tanstack/react-virtual'");
    expect(source).toContain('useVirtualizer');
  });

  it('imports QueueCard for per-item rendering', () => {
    expect(source).toContain("from './QueueCard'");
    expect(source).toContain('QueueCard');
  });

  it('imports t from unified i18n for load-more labels', () => {
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');
  });

  it('configures virtualizer with count, estimateSize, overscan', () => {
    expect(source).toContain('count: appointments.length');
    expect(source).toContain('estimateSize');
    expect(source).toContain('CARD_ESTIMATE_HEIGHT');
    expect(source).toContain('overscan: OVERSCAN');
  });

  it('renders virtual items with absolute positioning', () => {
    expect(source).toContain('getVirtualItems()');
    expect(source).toContain("'absolute'");
    expect(source).toContain('translateY');
  });

  it('has infinite scroll via scroll event listener', () => {
    expect(source).toContain('addEventListener');
    expect(source).toContain('scroll');
    expect(source).toContain('onLoadMore()');
  });

  it('has manual load-more button as fallback', () => {
    expect(source).toContain('hasMore && onLoadMore');
    expect(source).toContain('onClick={onLoadMore}');
    expect(source).toContain('disabled={loadingMore}');
    expect(source).toContain("t('queue.load_more_aria')");
    expect(source).toContain("t('queue.loading')");
    expect(source).toContain("t('queue.show_more')");
  });

  it('accepts all expected props', () => {
    const expectedProps = [
      'appointments',
      'selectedAppointment',
      'onOpenAppointment',
      'onLoadMore',
      'hasMore',
      'loadingMore',
      'queueTotal',
    ];
    for (const prop of expectedProps) {
      expect(source).toContain(prop);
    }
  });

  it('has STRAT#27 marker in JSDoc', () => {
    expect(source).toContain('STRAT#27');
  });
});

// ─── PR7: honest pagination + measurement + inflight guard ───
describe('VirtualizedQueueList PR7 — honest pagination and measurement', () => {
  it('measures real card heights via virtualizer measureElement', () => {
    expect(source).toContain('measureElement');
    expect(source).toContain('ref={measureElement}');
  });

  it('never shows a negative remaining count', () => {
    expect(source).toContain('Math.max(0, queueTotal - appointments.length)');
  });

  it('guards against concurrent load-more bursts with an in-flight ref', () => {
    expect(source).toContain('loadMoreInFlightRef');
    expect(source).toContain('if (loadMoreInFlightRef.current) return;');
    expect(source).toContain('loadMoreInFlightRef.current = true;');
  });
});

// ─── PR7 behavioral: remaining label + in-flight guard (jsdom, RO stub) ───
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, vi } from 'vitest';

import VirtualizedQueueListRaw from '../VirtualizedQueueList';
import { ThemeProvider } from '@/contexts/ThemeContext';

const VirtualizedQueueList = VirtualizedQueueListRaw as unknown as React.ComponentType<Record<string, unknown>>;

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// jsdom has no ResizeObserver; @tanstack/react-virtual needs it.
(globalThis as Record<string, unknown>).ResizeObserver = ResizeObserverStub;

function makeAppointments(n: number) {
  return Array.from({ length: n }, (_unused, i) => ({
    id: i + 1,
    patient_fio: `Пациент ${i + 1}`,
    status: 'waiting',
  }));
}

describe('VirtualizedQueueList PR7 behavioral', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('never renders a negative remaining count', () => {
    render(
      <ThemeProvider>
        <VirtualizedQueueList
          appointments={makeAppointments(10)}
          selectedAppointment={null}
          onOpenAppointment={vi.fn()}
          onLoadMore={vi.fn()}
          hasMore={true}
          loadingMore={false}
          queueTotal={5}
        />
      </ThemeProvider>
    );
    const button = screen.getByRole('button');
    expect(button.textContent).toContain('(0');
    expect(button.textContent).not.toMatch(/\(-\d+/);
  });

  it('a synchronous scroll burst triggers load-more only once', () => {
    const onLoadMore = vi.fn();
    const { container } = render(
      <ThemeProvider>
        <VirtualizedQueueList
          appointments={makeAppointments(30)}
          selectedAppointment={null}
          onOpenAppointment={vi.fn()}
          onLoadMore={onLoadMore}
          hasMore={true}
          loadingMore={false}
          queueTotal={120}
        />
      </ThemeProvider>
    );
    const scrollEl = container.querySelector('.lqw-virtualized-list') as HTMLElement;
    expect(scrollEl).not.toBeNull();
    // Simulate a burst: many scroll events in one tick, parent state not yet updated.
    for (let i = 0; i < 8; i += 1) {
      fireEvent.scroll(scrollEl);
    }
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });
});
