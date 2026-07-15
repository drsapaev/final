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
    // STRAT#11: строка мигрирована на t('confirm.delete_section_title')
    expect(handlerBody).toContain("t('confirm.delete_section_title')");
    expect(handlerBody).toContain("intent: 'danger'");
    expect(handlerBody).toContain('if (ok) onRemoveSection(sectionIndex)');
  });

  it('wraps field removal in confirm dialog', () => {
    expect(source).toContain('async function handleRemoveField(');
    const handlerStart = source.indexOf('async function handleRemoveField(');
    const handlerEnd = source.indexOf('\n  }', handlerStart);
    const handlerBody = source.slice(handlerStart, handlerEnd);

    expect(handlerBody).toContain('await confirm(');
    // STRAT#11: строка мигрирована на t('confirm.delete_field_title')
    expect(handlerBody).toContain("t('confirm.delete_field_title')");
    expect(handlerBody).toContain("intent: 'danger'");
    expect(handlerBody).toContain('if (ok) onRemoveField(sectionIndex, fieldIndex)');
  });

  it('wires the new handlers into trash buttons', () => {
    // STRAT#23: aria-labels migrated to t()
    const trashSectionIdx = source.indexOf("t('content.delete_section')");
    expect(trashSectionIdx).toBeGreaterThan(-1);
    const trashFieldIdx = source.indexOf("t('content.delete_field')");
    expect(trashFieldIdx).toBeGreaterThan(-1);
  });

  it('UX-AUDIT-FIX5: hides raw JSON textareas behind Developer mode toggle', () => {
    // FIX5: raw JSON (visibility_rule_text / highlight_rule_text) рендерится
    // только когда developerMode === true. По умолчанию выключен.
    expect(source).toContain("useState(false)");
    expect(source).toContain('developerMode');
    // STRAT#23: 'Режим разработчика' migrated to t('content.developer_mode')
    expect(source).toContain("t('content.developer_mode')");
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
    // Кнопка в UI — STRAT#23: migrated to t('content.load_all_norms')
    expect(source).toContain("t('content.load_all_norms')");
    // Disabled когда нет валидных полей
    expect(source).toContain("disabled={!draftVersion?.sections?.some");
    // Иконка square.and.arrow.down.on.square
    expect(source).toContain('square.and.arrow.down.on.square');
  });

  it('UX-AUDIT-FIX14: uses parent-provided datalist IDs instead of hardcoded', () => {
    // FIX14: ID для <datalist> ранее были захардкожены как
    // 'lab-analyte-catalog' / 'lab-unit-catalog'. Теперь принимаются
    // через props analyteCatalogId / unitCatalogId (значения по умолчанию
    // сохранены для backward compat).
    expect(source).toContain('analyteCatalogId');
    expect(source).toContain('unitCatalogId');
    // Используются в input list=...
    expect(source).toContain('list={analyteCatalogId}');
    expect(source).toContain('list={unitCatalogId}');
    // Больше нет хардкоженных строковых ID в list=
    expect(source).not.toContain('list="lab-analyte-catalog"');
    expect(source).not.toContain('list="lab-unit-catalog"');
    // PropTypes добавлены
    expect(source).toContain('analyteCatalogId: PropTypes.string');
    expect(source).toContain('unitCatalogId: PropTypes.string');
  });

  it('STRAT#11: both delete dialogs use t() and tInterpolate() from labTranslations', () => {
    // STRAT#11: delete section и delete field dialogs мигрированы на t()
    expect(source).toContain("from '../utils/labTranslations'");
    expect(source).toContain('import { t, tInterpolate }');

    // Delete section dialog
    expect(source).toContain("t('confirm.delete_section_title')");
    expect(source).toContain("tInterpolate('confirm.delete_section_message',");
    expect(source).toContain("t('confirm.delete_section_description')");
    expect(source).toContain("t('confirm.delete_section_confirm')");

    // Delete field dialog
    expect(source).toContain("t('confirm.delete_field_title')");
    expect(source).toContain("tInterpolate('confirm.delete_field_message',");
    expect(source).toContain("t('confirm.delete_field_description')");
    expect(source).toContain("t('confirm.delete_field_confirm')");

    // Общий cancel label
    expect(source).toContain("t('confirm.cancel')");

    // Больше нет хардкоженных русских строк в confirm() calls
    expect(source).not.toContain("title: 'Удалить секцию?'");
    expect(source).not.toContain("title: 'Удалить показатель?'");
    expect(source).not.toContain("confirmLabel: 'Удалить секцию'");
    expect(source).not.toContain("confirmLabel: 'Удалить поле'");
    expect(source).not.toContain("cancelLabel: 'Отмена'");
  });

  it('STRAT#23: field/section labels use t() from content.* namespace', () => {
    // STRAT#23: all ContentTab UI labels мигрированы на t('content.*')
    expect(source).toContain("t('content.header')");
    expect(source).toContain("t('content.add_section')");
    expect(source).toContain("t('content.add_field')");
    expect(source).toContain("t('content.developer_mode')");
    expect(source).toContain("t('content.load_all_norms')");
    expect(source).toContain("t('content.section_key')");
    expect(source).toContain("t('content.section_title')");
    expect(source).toContain("t('content.field_key')");
    expect(source).toContain("t('content.field_label')");
    expect(source).toContain("t('content.value_type')");
    expect(source).toContain("t('content.unit')");
    expect(source).toContain("t('content.analyte_code')");
    expect(source).toContain("t('content.unit_code')");
    expect(source).toContain("t('content.reference_mode')");
    expect(source).toContain("t('content.reference_text')");
    expect(source).toContain("t('content.required_label')");
    expect(source).toContain("t('content.move_section_up')");
    expect(source).toContain("t('content.move_section_down')");
    expect(source).toContain("t('content.move_field_up')");
    expect(source).toContain("t('content.move_field_down')");
    expect(source).toContain("t('content.duplicate_field')");
    expect(source).toContain("t('content.delete_section')");
    expect(source).toContain("t('content.delete_field')");
    expect(source).toContain("t('content.section_fallback')");
    expect(source).toContain("t('content.field_fallback')");
  });
});
