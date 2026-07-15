import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/VirtualizedQueueList.jsx'),
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

  it('imports t from labTranslations for load-more labels', () => {
    expect(source).toContain("from './utils/labTranslations'");
    expect(source).toContain('import { t }');
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

  it('has PropTypes for all props', () => {
    expect(source).toContain('appointments: PropTypes.array.isRequired');
    expect(source).toContain('onOpenAppointment: PropTypes.func.isRequired');
    expect(source).toContain('hasMore: PropTypes.bool');
    expect(source).toContain('loadingMore: PropTypes.bool');
    expect(source).toContain('queueTotal: PropTypes.number');
  });

  it('has STRAT#27 marker in JSDoc', () => {
    expect(source).toContain('STRAT#27');
  });
});
