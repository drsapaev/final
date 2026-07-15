import PropTypes from 'prop-types';
import { Icon } from '../ui/macos';
import {
  LAB_REPORT_STATUS_CONFIG,
  getLabReportStepIndex,
} from './utils/labStatusConfig';
import { t } from './utils/labTranslations';

/**
 * P-04 fix: LabStatusStepper выделен в отдельный файл.
 *
 * P-20 fix (визуальный stepper жизненного цикла лабораторного бланка):
 * State machine: DRAFT → IN_PROGRESS → READY → FINALIZED → PRINTED
 * (с возможностью revise() — возвратом на DRAFT из FINALIZED).
 *
 * Раньше статус отображался одним Badge без контекста «куда двигаться
 * дальше». Stepper показывает пройденные шаги, текущий и будущие.
 *
 * L-H-3 fix: вместо локального LAB_REPORT_STEPS используется единый
 * источник истины — utils/labStatusConfig.js. Маппинг статусов больше
 * не дублируется между этим файлом и labUiLabels.js.
 *
 * UX-AUDIT-QW3: шаг READY скрыт из степпера. Кнопка «Mark Ready» была
 * убрана в WF-round5 (была функционально пустой — backend разрешал
 * одинаковые действия для DRAFT/IN_PROGRESS/READY). Пользователь видел
 * шаг, к которому не мог прийти вручную — это вызывало когнитивный
 * диссонанс. Если backend явно вернёт status='READY' (через mark_ready),
 * индекс вычисляется по полной конфигурации, поэтому READY всё равно
 * корректно отрисуется как current step. Скрытие влияет только на
 * будущее/прошлое отображение шага, когда текущий статус — другой.
 *
 * STRAT#6: все русские строки мигрированы на t() из labTranslations.
 * step.label всё ещё берётся из labStatusConfig (SSOT для статус-маппинга),
 * но вспомогательные тексты (aria-label, title-атрибуты) теперь через t().
 */
const HIDDEN_STEPPER_STATUSES = new Set(['READY']);

// Видимые шаги степпера. READY исключён: нет ручного действия для перехода.
const VISIBLE_STEPPER_STEPS = LAB_REPORT_STATUS_CONFIG.filter(
  (step) => !HIDDEN_STEPPER_STATUSES.has(step.key)
);

export default function LabStatusStepper({ status }) {
  // Индекс считаем по полной конфигурации, чтобы READY (если пришёл с бэкенда)
  // корректно отображался как текущий шаг.
  const fullIndex = getLabReportStepIndex(status);
  if (fullIndex < 0) {
    // Неизвестный статус — fallback на Badge в родительском компоненте
    return null;
  }

  // Маппинг полного индекса на видимый индекс: если текущий статус — READY,
  // показываем его на месте IN_PROGRESS (как «почти готов»).
  const currentIndex = HIDDEN_STEPPER_STATUSES.has(status)
    ? VISIBLE_STEPPER_STEPS.findIndex((s) => s.key === 'IN_PROGRESS')
    : VISIBLE_STEPPER_STEPS.findIndex((s) => s.key === status);

  return (
    <div
      role="navigation"
      aria-label={t('workbench.progress_aria_label')}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-1)',
        flexWrap: 'wrap',
        marginTop: 'var(--mac-spacing-2)',
      }}
    >
      {VISIBLE_STEPPER_STEPS.map((step, index) => {
        const isCompleted = index < currentIndex;
        const isCurrent = index === currentIndex;
        const isFuture = index > currentIndex;
        const isLast = index === VISIBLE_STEPPER_STEPS.length - 1;

        // STRAT#6: title-атрибуты через t() для i18n
        const titleSuffix = isCompleted
          ? t('workbench.step_completed')
          : isCurrent
            ? t('workbench.step_current')
            : t('workbench.step_upcoming');

        return (
          <div
            key={step.key}
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}
          >
            <div
              className={`lab-status-step ${isCurrent ? 'lab-status-step-current' : ''} ${isCompleted ? 'lab-status-step-completed' : ''} ${isFuture ? 'lab-status-step-future' : ''}`}
              aria-current={isCurrent ? 'step' : undefined}
              title={`${step.label} — ${titleSuffix}`}
            >
              {isCompleted && (
                <Icon name="checkmark.circle.fill" size={12} />
              )}
              {isCurrent && (
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: 'white',
                    display: 'inline-block',
                  }}
                  aria-hidden="true"
                />
              )}
              {step.label}
            </div>
            {!isLast && (
              <div
                className={`lab-status-connector ${isFuture ? 'lab-status-connector-future' : ''}`}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

LabStatusStepper.propTypes = {
  status: PropTypes.string,
};
