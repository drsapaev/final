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
    expect(source).toContain('title="Доступ к номеру ограничен ролью"');
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
});
