import PropTypes from 'prop-types';
import { Icon } from '../ui/macos';
import {
  LAB_REPORT_STATUS_CONFIG,
  getLabReportStepIndex,
} from './utils/labStatusConfig';

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
 */
export default function LabStatusStepper({ status }) {
  const currentIndex = getLabReportStepIndex(status);
  if (currentIndex < 0) {
    // Неизвестный статус — fallback на Badge в родительском компоненте
    return null;
  }

  return (
    <div
      role="navigation"
      aria-label="Прогресс бланка"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-1)',
        flexWrap: 'wrap',
        marginTop: 'var(--mac-spacing-2)',
      }}
    >
      {LAB_REPORT_STATUS_CONFIG.map((step, index) => {
        const isCompleted = index < currentIndex;
        const isCurrent = index === currentIndex;
        const isFuture = index > currentIndex;
        const isLast = index === LAB_REPORT_STATUS_CONFIG.length - 1;

        return (
          <div
            key={step.key}
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}
          >
            <div
              className={`lab-status-step ${isCurrent ? 'lab-status-step-current' : ''} ${isCompleted ? 'lab-status-step-completed' : ''} ${isFuture ? 'lab-status-step-future' : ''}`}
              aria-current={isCurrent ? 'step' : undefined}
              title={
                isCompleted
                  ? `${step.label} — пройден`
                  : isCurrent
                    ? `${step.label} — текущий шаг`
                    : `${step.label} — предстоит`
              }
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
