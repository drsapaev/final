/**
 * REG-FE-078/079 (follow-up audit 2026-11-02): CSS-контракт таблицы
 * записей (EnhancedAppointmentsTable).
 *
 * 078 (P2): .eat-toolbar требовал min-width:600px внутри clipped-предка
 *      (overflow:hidden корня .enhanced-table) — на узких экранах правые
 *      фильтры/экспорт уходили за границу. Контракт после фикса:
 *      минимальной ширины НЕТ, внутренний контейнер переносится (wrap).
 * 079 (P3): правило `.enhanced-table div { color: … !important }` красило
 *      ЛЮБОЙ div, затирая семантические цвета бейджей. Контракт после
 *      фикса: широкого правила НЕТ, окраска перечисляет конкретные
 *      текстовые контейнеры.
 *
 * Source-contract тест (прецедент репо: wizard-тесты читают исходник).
 * Red-first: оба паттерна присутствовали в префиксном CSS.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const cssPath = path.resolve(__dirname, '../EnhancedAppointmentsTable.css');
const css = fs.readFileSync(cssPath, 'utf-8').replace(/\r\n/g, '\n');

const extractBlock = (source: string, selector: string): string => {
  const start = source.indexOf(selector);
  expect(start, `selector not found: ${selector}`).toBeGreaterThanOrEqual(0);
  const end = source.indexOf('}', start);
  return source.slice(start, end);
};

describe('REG-FE-078: responsive toolbar', () => {
  it('.eat-toolbar no longer demands min-width: 600px', () => {
    const block = extractBlock(css, '.eat-toolbar {');
    expect(block).not.toMatch(/min-width\s*:\s*600px/);
  });

  it('.eat-toolbar-inner wraps instead of clipping controls', () => {
    const block = extractBlock(css, '.eat-toolbar-inner {');
    expect(block).toMatch(/flex-wrap\s*:\s*wrap/);
    expect(block).not.toMatch(/flex-wrap\s*:\s*nowrap/);
  });
});

describe('REG-FE-079: no blanket !important div color', () => {
  it('the broad `.enhanced-table div` rule is gone', () => {
    expect(css).not.toMatch(/\.enhanced-table\s+div\s*\{/);
  });

  it('text color targets concrete containers', () => {
    // Суженная окраска перечисляет реальные текстовые контейнеры.
    expect(css).toMatch(/\.enhanced-table\s+tbody\s+td\s+div/);
    expect(css).toMatch(/\.enhanced-table\s+\.eat-toolbar/);
  });
});
