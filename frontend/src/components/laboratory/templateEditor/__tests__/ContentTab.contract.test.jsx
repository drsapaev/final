import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/templateEditor/ContentTab.jsx'),
  'utf8'
);

describe('ContentTab UX-AUDIT-FIX4 — confirm dialog on field/section delete', () => {
  it('imports useConfirm from common/ConfirmDialog', () => {
    expect(source).toContain("from '../../common/ConfirmDialog'");
    expect(source).toContain('useConfirm');
  });

  it('wraps section removal in confirm dialog', () => {
    expect(source).toContain('async function handleRemoveSection(');
    const handlerStart = source.indexOf('async function handleRemoveSection(');
    const handlerEnd = source.indexOf('\n  }', handlerStart);
    const handlerBody = source.slice(handlerStart, handlerEnd);

    expect(handlerBody).toContain('await confirm(');
    expect(handlerBody).toContain("'Удалить секцию?'");
    expect(handlerBody).toContain("intent: 'danger'");
    expect(handlerBody).toContain('if (ok) onRemoveSection(sectionIndex)');
  });

  it('wraps field removal in confirm dialog', () => {
    expect(source).toContain('async function handleRemoveField(');
    const handlerStart = source.indexOf('async function handleRemoveField(');
    const handlerEnd = source.indexOf('\n  }', handlerStart);
    const handlerBody = source.slice(handlerStart, handlerEnd);

    expect(handlerBody).toContain('await confirm(');
    expect(handlerBody).toContain("'Удалить показатель?'");
    expect(handlerBody).toContain("intent: 'danger'");
    expect(handlerBody).toContain('if (ok) onRemoveField(sectionIndex, fieldIndex)');
  });

  it('wires the new handlers into trash buttons', () => {
    const trashSectionIdx = source.indexOf('aria-label="Удалить секцию"');
    expect(trashSectionIdx).toBeGreaterThan(-1);
    const sectionButtonLine = source.lastIndexOf('onClick=', trashSectionIdx);
    const sectionButtonEnd = source.indexOf('aria-label="Удалить секцию"', sectionButtonLine);
    const sectionOnClickBody = source.slice(sectionButtonLine, sectionButtonEnd);
    expect(sectionOnClickBody).toContain('handleRemoveSection');
    expect(sectionOnClickBody).not.toContain('onRemoveSection(sectionIndex);');

    const trashFieldIdx = source.indexOf('aria-label="Удалить поле"');
    expect(trashFieldIdx).toBeGreaterThan(-1);
    const fieldButtonLine = source.lastIndexOf('onClick=', trashFieldIdx);
    const fieldButtonEnd = source.indexOf('aria-label="Удалить поле"', fieldButtonLine);
    const fieldOnClickBody = source.slice(fieldButtonLine, fieldButtonEnd);
    expect(fieldOnClickBody).toContain('handleRemoveField');
    expect(fieldOnClickBody).not.toContain('onRemoveField(sectionIndex, fieldIndex);');
  });

  it('UX-AUDIT-FIX5: hides raw JSON textareas behind Developer mode toggle', () => {
    // FIX5: raw JSON (visibility_rule_text / highlight_rule_text) рендерится
    // только когда developerMode === true. По умолчанию выключен.
    expect(source).toContain("useState(false)");
    expect(source).toContain('developerMode');
    // Тоггл в шапке ContentTab
    expect(source).toContain('Режим разработчика');
    expect(source).toContain('setDeveloperMode');
    // Raw JSON details обёрнут в условие
    expect(source).toContain('{developerMode && (');
    expect(source).toContain('<details className="ltw-details">');
    // Raw JSON textareas всё ещё доступны (не удалены, а скрыты)
    expect(source).toContain('visibility_rule_text');
    expect(source).toContain('highlight_rule_text');
  });

  it('UX-AUDIT-FIX7: bulk-loads all reference ranges from catalog in one click', () => {
    // FIX7: bulk-кнопка «Загрузить все нормы» в шапке ContentTab.
    // Должна итерировать по всем секциям/полям и вызывать
    // onLoadCatalogReferenceRange для полей с reference_mode='catalog'.
    expect(source).toContain('handleBulkLoadCatalogReferenceRanges');
    expect(source).toContain("reference_mode === 'catalog'");
    expect(source).toContain('onLoadCatalogReferenceRange(sectionIndex, fieldIndex, field.analyte_code)');
    // Кнопка в UI
    expect(source).toContain('Загрузить все нормы');
    // Disabled когда нет валидных полей
    expect(source).toContain("disabled={!draftVersion?.sections?.some");
    // Иконка square.and.arrow.down.on.square
    expect(source).toContain('square.and.arrow.down.on.square');
  });
});
