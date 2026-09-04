import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabQueueWorkbench.tsx'),
  'utf8'
);

const cssSource = fs.readFileSync(
  path.join(ROOT, 'pages/lab.css'),
  'utf8'
);

describe('LabQueueWorkbench UX-AUDIT-FIX11 — MaskedPhone affordance', () => {
  it('uses eye/eye-off lucide icons in MaskedPhone component', () => {
    // FIX11 (intent preserved): the eye icon is the visual clickability cue.
    // Track 3-2 supersession: <Icon name={revealed ? 'eye.slash' : 'eye'}> was
    // migrated to direct lucide <EyeOff /> / <Eye /> components (canonical
    // icon system per §3.3 / Plan v2.10 §4.1.21 — reversal of the historic
    // macos-Icon direction, same architectural intent).
    expect(source).toContain("from 'lucide-react'");
    expect(source).toContain('EyeOff');
    expect(source).toContain('<Eye');
    expect(source).not.toContain('<Icon');
  });

  it('adds aria-pressed to indicate toggle state', () => {
    expect(source).toContain('aria-pressed={revealed}');
  });

  it('adds revealed CSS class for visual state', () => {
    expect(source).toContain('lqw-masked-phone-revealed');
  });

  it('adds read-only variant when canReveal=false', () => {
    expect(source).toContain('lqw-masked-phone-readonly');
    // STRAT#18: title migrated to t18('pii.phone_restricted') — strict:true
    // migration renamed `t` to `t18` (typed alias for i18n.t).
    expect(source).toContain("t18('pii.phone_restricted')");
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
      path.join(ROOT, 'components/laboratory/VirtualizedQueueList.tsx'),
      'utf8'
    );
    expect(virtualListSource).toContain('hasMore && onLoadMore');
    expect(virtualListSource).toContain('onClick={onLoadMore}');
    expect(virtualListSource).toContain('disabled={loadingMore}');
  });

  it('STRAT#14: queue filter/sort/title labels use t() from unified i18n', () => {
    // STRAT#14: filter/sort/title/badge labels мигрированы на t()
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');

    // Title + badges — strict:true migration: t -> t18 (typed alias).
    expect(source).toContain("t18('queue.title')");
    expect(source).toContain("t18('queue.total')");
    expect(source).toContain("t18('queue.in_progress')");
    expect(source).toContain("t18('common.refresh')");

    // Search
    expect(source).toContain("t18('queue.search_placeholder')");
    expect(source).toContain("t18('queue.search_aria')");
    expect(source).toContain("t18('queue.search_clear')");

    // Filter buttons
    expect(source).toContain("t18('queue.filter_all')");
    expect(source).toContain("t18('queue.filter_active')");
    expect(source).toContain("t18('queue.filter_completed')");
    expect(source).toContain("t18('queue.filter_group_aria')");

    // Sort
    expect(source).toContain("t18('queue.sort_label')");
    expect(source).toContain("t18('queue.sort_aria')");
    expect(source).toContain("t18('queue.sort_default')");
    expect(source).toContain("t18('queue.sort_name')");
    expect(source).toContain("t18('queue.sort_time')");

    // Filter count
    expect(source).toContain("t18('queue.filter_count')");
  });

  it('STRAT#18: card strings (patient info, PII, history) use t()', () => {
    // STRAT#18: card content strings мигрированы на t()
    // STRAT#28: card rendering moved to QueueCard.jsx — check there too.
    const ROOT = path.resolve(__dirname, '../../..');
    const queueCardSource = fs.readFileSync(
      path.join(ROOT, 'components/laboratory/QueueCard.tsx'),
      'utf8'
    );

    // Strings now in QueueCard.jsx — strict:true migration wrapped some
    // i18n.t calls in a cast (e.g., pii.* keys use the typed alias).
    expect(queueCardSource).toContain("pii.phone_not_set");
    expect(queueCardSource).toContain("pii.no_services");
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

    // Empty states still in LabQueueWorkbench — strict:true: t -> t18
    expect(source).toContain("t18('queue.no_entries')");
    expect(source).toContain("t18('queue.no_matches')");

    // History panel strings still in LabQueueWorkbench
    expect(source).toContain("t18('queue.history_title')");
    expect(source).toContain("t18('queue.history_empty')");
    expect(source).toContain("t18('queue.history_report_number')");
    expect(source).toContain("t18('queue.history_created')");
    expect(source).toContain("t18('queue.history_status')");
    expect(source).toContain("t18('queue.history_flags')");
    expect(source).toContain("t18('queue.history_critical')");
  });
});
