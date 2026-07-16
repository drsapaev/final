import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabStatusStepper.tsx'),
  'utf8'
);

describe('LabStatusStepper UX-AUDIT-QW3 — hide unreachable READY step', () => {
  it('filters READY out of the visible stepper steps', () => {
    // QW3 fix: READY не имеет ручного действия (кнопка Mark Ready убрана в WF-round5).
    // Шаг должен быть исключён из visible steps, чтобы пользователь не видел
    // недостижимый шаг.
    expect(source).toContain("HIDDEN_STEPPER_STATUSES");
    expect(source).toContain("'READY'");
    expect(source).toContain('VISIBLE_STEPPER_STEPS');
    expect(source).toContain('LAB_REPORT_STATUS_CONFIG.filter');
  });

  it('still renders READY as current step if backend explicitly sets it', () => {
    // Backend может вернуть status=READY через mark_ready(). В этом случае
    // степпер должен показать READY как текущий шаг (на месте IN_PROGRESS).
    expect(source).toContain("HIDDEN_STEPPER_STATUSES.has(status)");
    expect(source).toContain("findIndex((s) => s.key === 'IN_PROGRESS')");
  });

  it('keeps using the unified status config as source of truth', () => {
    expect(source).toContain('from \'./utils/labStatusConfig\'');
    expect(source).toContain('LAB_REPORT_STATUS_CONFIG');
    expect(source).toContain('getLabReportStepIndex');
  });

  it('STRAT#6: uses t() for aria-label and title attributes', () => {
    // Все вспомогательные строки мигрированы на t() из labTranslations
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');
    // aria-label через t()
    expect(source).toContain("aria-label={t('workbench.progress_aria_label')}");
    // title-атрибуты через t()
    expect(source).toContain("t('workbench.step_completed')");
    expect(source).toContain("t('workbench.step_current')");
    expect(source).toContain("t('workbench.step_upcoming')");
    // Больше нет хардкоженных русских строк
    expect(source).not.toContain('aria-label="Прогресс бланка"');
    expect(source).not.toContain('— пройден');
    expect(source).not.toContain('— текущий шаг');
    expect(source).not.toContain('— предстоит');
  });

  it('has STRAT#6 marker in JSDoc', () => {
    expect(source).toContain('STRAT#6');
  });
});
