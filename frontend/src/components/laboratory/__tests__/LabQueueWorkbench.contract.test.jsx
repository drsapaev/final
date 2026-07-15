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

  it('UX-AUDIT-FIX13: paginates queue rendering with PAGE_SIZE + load-more button', () => {
    // FIX13: рендерим только visibleCount записей через .slice(0, visibleCount)
    // вместо всего sortedAppointments. Кнопка «Показать ещё» увеличивает count.
    expect(source).toContain('PAGE_SIZE = 20');
    expect(source).toContain('visibleCount');
    expect(source).toContain('setVisibleCount');
    // .slice для ограничения рендера
    expect(source).toContain('sortedAppointments.slice(0, visibleCount)');
    // useEffect для сброса пагинации при смене фильтров
    expect(source).toContain('useEffect(() => {');
    expect(source).toContain('setVisibleCount(PAGE_SIZE)');
    expect(source).toContain('[searchQuery, statusFilter, sortBy]');
    // Кнопка «Показать ещё» в UI
    expect(source).toContain('Показать ещё');
    expect(source).toContain('lqw-load-more');
    // CSS-класс для контейнера кнопки
    expect(cssSource).toContain('.lqw-load-more');
    expect(cssSource).toContain('UX-AUDIT-FIX13');
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

  it('STRAT#8: uses server-side onLoadMore when hasMore=true, falls back to client-side otherwise', () => {
    // Server-side path: приоритетный
    expect(source).toContain('if (hasMore && onLoadMore)');
    expect(source).toContain('onClick={onLoadMore}');
    expect(source).toContain('disabled={loadingMore}');
    // Loading indicator
    expect(source).toContain("loadingMore ? 'arrow.clockwise' : 'arrow.down'");
    // STRAT#18: 'Загрузка…' migrated to t('queue.loading')
    expect(source).toContain("t('queue.loading')");
    // Counter показывает server-side total
    expect(source).toContain('queueTotal - appointments.length');
    // Client-side fallback остаётся
    expect(source).toContain('if (sortedAppointments.length > visibleCount)');
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
    expect(source).toContain("t('pii.phone_not_set')");
    expect(source).toContain("t('pii.phone_restricted')");
    expect(source).toContain("t('pii.hide_phone')");
    expect(source).toContain("t('pii.show_phone')");
    expect(source).toContain("t('pii.no_services')");

    // Card fields
    expect(source).toContain("t('queue.patient_no_name')");
    expect(source).toContain("t('queue.visit')");
    expect(source).toContain("t('queue.visit_not_linked')");
    expect(source).toContain("t('queue.phone')");
    expect(source).toContain("t('queue.services')");
    expect(source).toContain("t('queue.payment')");
    expect(source).toContain("t('queue.patient_id_aria')");
    expect(source).toContain("t('queue.patient_id_label')");
    expect(source).toContain("t('queue.report_exists')");
    expect(source).toContain("t('queue.report_new')");

    // Empty states
    expect(source).toContain("t('queue.no_entries')");
    expect(source).toContain("t('queue.no_matches')");

    // History panel
    expect(source).toContain("t('queue.history_title')");
    expect(source).toContain("t('queue.history_empty')");
    expect(source).toContain("t('queue.history_report_number')");
    expect(source).toContain("t('queue.history_created')");
    expect(source).toContain("t('queue.history_status')");
    expect(source).toContain("t('queue.history_flags')");
    expect(source).toContain("t('queue.history_critical')");

    // Больше нет хардкоженных русских строк в card content
    expect(source).not.toContain("'Пациент без имени'");
    expect(source).not.toContain("'Отчёт существует'");
    expect(source).not.toContain("'Новый отчёт'");
    expect(source).not.toContain('>История отчётов пациента<');
    expect(source).not.toContain("'флагов'");
    expect(source).not.toContain("'критич.'");
  });
});
