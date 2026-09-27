/**
 * NURSE-V2 N2-5 — the station-routed service list of the current patient.
 *
 * Operational state only (§6): name/code, status, the latest attempt, the
 * active execution — NOT a full medical history. Actions follow the
 * SERVER state (§5): [Начать услугу] for a pending service without an
 * execution; [Выполнено] / [Не завершено] for an active execution.
 * «Выполнено» completes THIS ServiceExecution — never the Visit (no
 * visit-close action exists anywhere on the tablet).
 */

import type { NurseStationService } from '@/api/nurseServing';

import { useTranslation } from '../../i18n/useTranslation';

export type NurseServiceListProps = {
  services: NurseStationService[];
  pendingStartExecution: (visitServiceId: number) => boolean;
  pendingComplete: (executionId: number) => boolean;
  onStartExecution: (visitServiceId: number) => void;
  onCompleteExecution: (executionId: number) => void;
  onIncompleteExecution: (executionId: number) => void;
};

function serviceStatusKey(service: NurseStationService): string {
  if (service.in_progress_execution_id != null) {
    return 'nurse.service_status_in_progress';
  }
  switch (service.latest_attempt_status) {
    case 'completed':
      return 'nurse.service_status_completed';
    case 'incomplete':
      return 'nurse.service_status_incomplete';
    default:
      return 'nurse.service_status_pending';
  }
}

export function NurseServiceList({
  services,
  pendingStartExecution,
  pendingComplete,
  onStartExecution,
  onCompleteExecution,
  onIncompleteExecution,
}: NurseServiceListProps) {
  const { t } = useTranslation();

  if (services.length === 0) {
    return (
      <p className="nurse-services__empty">{t('nurse.services_empty')}</p>
    );
  }

  return (
    <ul className="nurse-services" aria-label={t('nurse.services_aria')}>
      {services.map((service) => {
        const statusKey = serviceStatusKey(service);
        const hasActive = service.in_progress_execution_id != null;
        const startBusy = pendingStartExecution(service.visit_service_id);
        return (
          <li
            key={service.visit_service_id}
            className={`nurse-service ${
              hasActive ? 'nurse-service--active' : ''
            }`}
          >
            <div className="nurse-service__info">
              <span className="nurse-service__name">
                {service.name || service.code || `#${service.visit_service_id}`}
                {service.qty > 1 ? ` ×${service.qty}` : ''}
              </span>
              <span className="nurse-service__meta">
                {service.code ? `${service.code} · ` : ''}
                {t(statusKey)}
                {service.latest_attempt_no != null
                  ? ` · ${t('nurse.service_attempt', { attempt: String(service.latest_attempt_no) })}`
                  : ''}
              </span>
            </div>
            <div className="nurse-service__actions">
              {!hasActive && service.pending && (
                <button
                  type="button"
                  className="nurse-btn nurse-btn--primary"
                  disabled={startBusy}
                  onClick={() => onStartExecution(service.visit_service_id)}
                >
                  {t('nurse.action_service_start')}
                </button>
              )}
              {hasActive && (
                <>
                  <button
                    type="button"
                    className="nurse-btn nurse-btn--success"
                    disabled={pendingComplete(service.in_progress_execution_id ?? 0)}
                    onClick={() =>
                      onCompleteExecution(service.in_progress_execution_id ?? 0)
                    }
                  >
                    {t('nurse.action_service_complete')}
                  </button>
                  <button
                    type="button"
                    className="nurse-btn nurse-btn--warning"
                    disabled={pendingComplete(service.in_progress_execution_id ?? 0)}
                    onClick={() =>
                      onIncompleteExecution(service.in_progress_execution_id ?? 0)
                    }
                  >
                    {t('nurse.action_service_incomplete')}
                  </button>
                </>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
