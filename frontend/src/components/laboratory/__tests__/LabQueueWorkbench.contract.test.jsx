import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabQueueWorkbench.jsx'),
  'utf8'
);

const cssSource = fs.readFileSync(
  path.join(ROOT, 'pages/lab.css'),
  'utf8'
);

describe('LabQueueWorkbench UX-AUDIT-FIX11 — MaskedPhone affordance', () => {
  it('uses eye/eye.slash icons in MaskedPhone component', () => {
    // FIX11: иконка глаза — визуальный cue кликабельности.
    expect(source).toContain('<Icon name={revealed ? \'eye.slash\' : \'eye\'}');
    expect(source).toContain('<Icon name="eye.slash"');
  });

  it('adds aria-pressed to indicate toggle state', () => {
    expect(source).toContain('aria-pressed={revealed}');
  });

  it('adds revealed CSS class for visual state', () => {
    expect(source).toContain('lqw-masked-phone-revealed');
  });

  it('adds read-only variant when canReveal=false', () => {
    expect(source).toContain('lqw-masked-phone-readonly');
    // STRAT#18: title migrated to t('pii.phone_restricted')
    expect(source).toContain("t('pii.phone_restricted')");
  });

  it('registers hover/focus styles in lab.css', () => {
    expect(cssSource).toContain('.lqw-masked-phone:hover');
    expect(cssSource).toContain('.lqw-masked-phone:focus-visible');
    expect(cssSource).toContain('.lqw-masked-phone-revealed');
    expect(cssSource).toContain('.lqw-masked-phone-readonly');
    expect(cssSource).toContain('.lqw-masked-phone-text');
    // UX-AUDIT-FIX11 marker
    expect(cssSource).toContain('UX-AUDIT-FIX11');
  });

  it('UX-AUDIT-FIX13 / STRAT#27: uses VirtualizedQueueList for rendering (replaces .slice().map())', () => {
    // STRAT#27: .slice(0, visibleCount).map() replaced with <VirtualizedQueueList>
    expect(source).toContain('VirtualizedQueueList');
    expect(source).toContain('appointments={sortedAppointments}');
    // No more client-side slicing — virtualizer handles what to render
    expect(source).not.toContain('sortedAppointments.slice(0, visibleCount)');
  });

  it('STRAT#8: accepts server-side pagination props (onLoadMore, hasMore, loadingMore, queueTotal)', () => {
    // STRAT#8: новые props от LabPanel для server-side pagination
    expect(source).toContain('onLoadMore,');
    expect(source).toContain('hasMore = false,');
    expect(source).toContain('loadingMore = false,');
    expect(source).toContain('queueTotal = 0,');
    // PropTypes добавлены
    expect(source).toContain('onLoadMore: PropTypes.func');
    expect(source).toContain('hasMore: PropTypes.bool');
    expect(source).toContain('loadingMore: PropTypes.bool');
    expect(source).toContain('queueTotal: PropTypes.number');
  });

  it('STRAT#8 / STRAT#27: passes server-side pagination props to VirtualizedQueueList', () => {
    // STRAT#27: load-more logic moved to VirtualizedQueueList component.
    // LabQueueWorkbench passes props through.
    expect(source).toContain('onLoadMore={onLoadMore}');
    expect(source).toContain('hasMore={hasMore}');
    expect(source).toContain('loadingMore={loadingMore}');
    expect(source).toContain('queueTotal={queueTotal}');
    // VirtualizedQueueList handles the actual load-more rendering
    const virtualListSource = fs.readFileSync(
      path.join(ROOT, 'components/laboratory/VirtualizedQueueList.jsx'),
      'utf8'
    );
    expect(virtualListSource).toContain('hasMore && onLoadMore');
    expect(virtualListSource).toContain('onClick={onLoadMore}');
    expect(virtualListSource).toContain('disabled={loadingMore}');
  });

  it('STRAT#14: queue filter/sort/title labels use t() from labTranslations', () => {
    // STRAT#14: filter/sort/title/badge labels мигрированы на t()
    expect(source).toContain("from './utils/labTranslations'");
    expect(source).toContain('import { t }');

    // Title + badges
    expect(source).toContain("t('queue.title')");
    expect(source).toContain("t('queue.total')");
    expect(source).toContain("t('queue.in_progress')");
    expect(source).toContain("t('common.refresh')");

    // Search
    expect(source).toContain("t('queue.search_placeholder')");
    expect(source).toContain("t('queue.search_aria')");
    expect(source).toContain("t('queue.search_clear')");

    // Filter buttons
    expect(source).toContain("t('queue.filter_all')");
    expect(source).toContain("t('queue.filter_active')");
    expect(source).toContain("t('queue.filter_completed')");
    expect(source).toContain("t('queue.filter_group_aria')");

    // Sort
    expect(source).toContain("t('queue.sort_label')");
    expect(source).toContain("t('queue.sort_aria')");
    expect(source).toContain("t('queue.sort_default')");
    expect(source).toContain("t('queue.sort_name')");
    expect(source).toContain("t('queue.sort_time')");

    // Filter count
    expect(source).toContain("t('queue.filter_count')");
  });

  it('STRAT#18: card strings (patient info, PII, history) use t()', () => {
    // STRAT#18: card content strings мигрированы на t()
    // STRAT#28: card rendering moved to QueueCard.jsx — check there too.
    const ROOT = path.resolve(__dirname, '../../..');
    const queueCardSource = fs.readFileSync(
      path.join(ROOT, 'components/laboratory/QueueCard.jsx'),
      'utf8'
    );

    // Strings now in QueueCard.jsx
    expect(queueCardSource).toContain("t('pii.phone_not_set')");
    expect(queueCardSource).toContain("t('pii.no_services')");
    expect(queueCardSource).toContain("t('queue.patient_no_name')");
    expect(queueCardSource).toContain("t('queue.visit')");
    expect(queueCardSource).toContain("t('queue.visit_not_linked')");
    expect(queueCardSource).toContain("t('queue.phone')");
    expect(queueCardSource).toContain("t('queue.services')");
    expect(queueCardSource).toContain("t('queue.payment')");
    expect(queueCardSource).toContain("t('queue.patient_id_aria')");
    expect(queueCardSource).toContain("t('queue.patient_id_label')");
    expect(queueCardSource).toContain("t('queue.report_exists')");
    expect(queueCardSource).toContain("t('queue.report_new')");

    // Empty states still in LabQueueWorkbench
    expect(source).toContain("t('queue.no_entries')");
    expect(source).toContain("t('queue.no_matches')");

    // History panel strings still in LabQueueWorkbench
    expect(source).toContain("t('queue.history_title')");
    expect(source).toContain("t('queue.history_empty')");
    expect(source).toContain("t('queue.history_report_number')");
    expect(source).toContain("t('queue.history_created')");
    expect(source).toContain("t('queue.history_status')");
    expect(source).toContain("t('queue.history_flags')");
    expect(source).toContain("t('queue.history_critical')");
  });
});
