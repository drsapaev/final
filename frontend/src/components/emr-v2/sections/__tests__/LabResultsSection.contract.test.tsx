import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/emr-v2/sections/LabResultsSection.tsx'),
  'utf8'
);

describe('LabResultsSection icon contract — Track 3-2 forward-guard', () => {
  /*
   * REVERSAL DOCUMENTATION (Do not treat the old test as unexplained regression):
   * - UX-AUDIT-FIX6 era: lucide-react was replaced with macos <Icon name="..."> —
   *   at the time the macos SF-Symbols wrapper was treated as the canonical icon
   *   system for consistency.
   * - Plan §3.3 / §4.1.17 (v2.6): the canonical end-state is the OPPOSITE —
   *   "Icon-систем: 2 → 1 (lucide-react)"; the macos Icon wrapper is the legacy
   *   surface slated for decommission.
   * - Track 3 (user decision, Plan v2.10 §4.1.21): explicit supersession —
   *   migrate all consumers to direct lucide imports, then delete Icon.tsx.
   * The architectural intent of FIX6 (icons follow ONE canonical system) is
   * preserved; only the direction has been corrected.
   */

  it('imports icons directly from lucide-react (canonical icon system)', () => {
    expect(source).toContain("from 'lucide-react'");
    expect(source).toContain('Download, FileText, Plus, TestTube2');
  });

  it('does not render the legacy macos <Icon> wrapper anymore', () => {
    expect(source).not.toContain('<Icon');
    const macosImport = source.match(/import\s*\{([^}]*)\}\s*from\s*'\.\.\/\.\.\/ui\/macos'/);
    expect((macosImport?.[1] ?? '')).not.toMatch(/\bIcon\b/);
  });

  it('renders the 4 canonical lucide components (was: SF-symbol names)', () => {
    // FileText (was doc.text), Download (was square.and.arrow.down),
    // TestTube2 (was testtube.2), Plus (was plus)
    expect(source).toContain('<FileText');
    expect(source).toContain('<Download');
    expect(source).toContain('<TestTube2');
    expect(source).toContain('<Plus');
  });

  it('square.and.arrow.down fallback questionmark is structurally impossible now', () => {
    // UX-AUDIT-FIX6 originally registered the missing 'square.and.arrow.down'
    // SF-name in Icon.jsx. Track 3-2 removes the name→path map entirely:
    // direct lucide imports cannot fall back to questionmark. Superseded
    // guard: the component import must be present (no registry to audit).
    expect(source).toContain('Download');
  });

  it('UX-AUDIT-FIX9: requires confirm dialog before creating lab order', () => {
    // FIX9: handleOrder ранее мгновенно создавал заказ через
    // labReportingApi.createOrder без подтверждения. Теперь обёрнут в
    // useConfirm() — соответствует Nielsen Heuristic #5 (Error Prevention).
    expect(source).toContain("from '../../common/ConfirmDialog'");
    expect(source).toContain('useConfirm');

    // Ищем функцию handleOrder — strict:true added param types.
    const fnStart = source.indexOf('const handleOrder = async (templateId: string | number, templateName: string) => {');
    expect(fnStart).toBeGreaterThan(-1);
    const fnEnd = source.indexOf('\n  };', fnStart);
    const fnBody = source.slice(fnStart, fnEnd);

    expect(fnBody).toMatch(/await\s+\(?confirm/);
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

    // Использование в render: strict:true migration added `|| ''` null-coalesce
    // to coerce `instance.status` (which may be undefined) to a string.
    expect(source).toContain('formatLabStatus(instance.status || \'\')');
    expect(source).toContain('getLabStatusVariant(instance.status || \'\')');
  });

  it('STRAT#12: order confirm dialog uses t() and tInterpolate() from unified i18n', () => {
    // STRAT#12: order confirm dialog мигрирован на t()
    // Strict:true migration: useTranslation import path moved from
    // '@/components/i18n/useTranslation' to '@/i18n/useTranslation'.
    expect(source).toContain("from '@/i18n/useTranslation'");
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
