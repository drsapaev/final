import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabStatusStepper.jsx'),
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
});
