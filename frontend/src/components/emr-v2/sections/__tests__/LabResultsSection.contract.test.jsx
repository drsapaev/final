import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/emr-v2/sections/LabResultsSection.jsx'),
  'utf8'
);

const iconSource = fs.readFileSync(
  path.join(ROOT, 'components/ui/macos/Icon.tsx'),
  'utf8'
);

describe('LabResultsSection UX-AUDIT-FIX6 — migrate lucide-react to macos Icon', () => {
  it('does not import from lucide-react anymore', () => {
    expect(source).not.toContain("from 'lucide-react'");
    expect(source).not.toContain('FileText, Download, TestTube, Plus');
  });

  it('imports Icon from macos UI library', () => {
    expect(source).toContain("from '../../ui/macos'");
    expect(source).toContain('Icon');
  });

  it('uses macos Icon names for all 4 migrated icons', () => {
    // FileText → doc.text
    expect(source).toContain('<Icon name="doc.text"');
    // Download → square.and.arrow.down
    expect(source).toContain('<Icon name="square.and.arrow.down"');
    // TestTube → testtube.2
    expect(source).toContain('<Icon name="testtube.2"');
    // Plus → plus
    expect(source).toContain('<Icon name="plus"');
  });

  it('registers square.and.arrow.down in macos Icon.jsx (previously missing)', () => {
    // Ранее 'square.and.arrow.down' отсутствовал в Icon.jsx — fallback на
    // 'questionmark'. Теперь SVG-path определён.
    expect(iconSource).toContain("'square.and.arrow.down'");
    expect(iconSource).toContain('UX-AUDIT-FIX6');
  });

  it('UX-AUDIT-FIX9: requires confirm dialog before creating lab order', () => {
    // FIX9: handleOrder ранее мгновенно создавал заказ через
    // labReportingApi.createOrder без подтверждения. Теперь обёрнут в
    // useConfirm() — соответствует Nielsen Heuristic #5 (Error Prevention).
    expect(source).toContain("from '../../common/ConfirmDialog'");
    expect(source).toContain('useConfirm');

    // Ищем функцию handleOrder
    const fnStart = source.indexOf('const handleOrder = async (templateId, templateName) => {');
    expect(fnStart).toBeGreaterThan(-1);
    const fnEnd = source.indexOf('\n  };', fnStart);
    const fnBody = source.slice(fnStart, fnEnd);

    expect(fnBody).toContain('await confirm(');
    // STRAT#12: строка мигрирована на t('confirm.order_title')
    expect(fnBody).toContain("t('confirm.order_title')");
    expect(fnBody).toContain('if (!ok) return;');
    // createOrder должен вызываться ПОСЛЕ confirm
    const confirmIdx = fnBody.indexOf('await confirm(');
    const createIdx = fnBody.indexOf('labReportingApi.createOrder(');
    expect(createIdx).toBeGreaterThan(confirmIdx);
  });

  it('UX-AUDIT-FIX10: uses labUiLabels SSOT instead of local STATUS_LABELS', () => {
    // FIX10: локальные STATUS_LABELS / STATUS_VARIANTS удалены.
    // LabResultsSection импортирует formatLabStatus / getLabStatusVariant
    // из labUiLabels.js — единый источник истины.
    expect(source).toContain("from '../../laboratory/labUiLabels'");
    expect(source).toContain('formatLabStatus');
    expect(source).toContain('getLabStatusVariant');

    // Локальные константы удалены
    expect(source).not.toContain('const STATUS_LABELS = {');
    expect(source).not.toContain('const STATUS_VARIANTS = {');

    // Использование в render: formatLabStatus(instance.status)
    expect(source).toContain('formatLabStatus(instance.status)');
    expect(source).toContain('getLabStatusVariant(instance.status)');
  });

  it('STRAT#12: order confirm dialog uses t() and tInterpolate() from unified i18n', () => {
    // STRAT#12: order confirm dialog мигрирован на t()
    expect(source).toContain("from '../../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');

    // Order dialog
    expect(source).toContain("t('confirm.order_title')");
    expect(source).toContain("t('confirm.order_message', { name: templateName })");
    expect(source).toContain("t('confirm.order_description')");
    expect(source).toContain("t('confirm.order_confirm')");
    expect(source).toContain("t('confirm.cancel')");

    // Больше нет хардкоженных русских строк в confirm() calls
    expect(source).not.toContain("title: 'Заказать анализы?'");
    expect(source).not.toContain("confirmLabel: 'Заказать'");
    expect(source).not.toContain("cancelLabel: 'Отмена'");
  });

  it('STRAT#20: empty-state strings use t() from unified i18n', () => {
    // STRAT#20: empty-state strings мигрированы на t('empty.*')
    expect(source).toContain("t('empty.loading_results')");
    expect(source).toContain("t('empty.no_lab_results')");
    expect(source).toContain("t('empty.loading_templates')");
    expect(source).toContain("t('empty.no_templates')");

    // Больше нет хардкоженных русских строк для empty states
    expect(source).not.toContain('Загрузка результатов анализов…');
    expect(source).not.toContain('Нет готовых результатов анализов для этого пациента.');
    expect(source).not.toContain('Загрузка шаблонов…');
    expect(source).not.toContain('Нет опубликованных шаблонов анализов.');
  });
});
