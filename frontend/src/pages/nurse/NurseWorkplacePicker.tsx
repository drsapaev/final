/**
 * NURSE-V2 N2-5 — workplace selection (§4) and the drain-recovery card.
 *
 * 0 workplaces -> «Нет назначенного рабочего места» (no queue, no patient
 * data); 1 -> auto-selected by the state hook; >1 -> this simple picker.
 * The stored localStorage id is a UI HINT only — the workplaces GET is
 * the access SSOT (§4).
 *
 * The draining card (§8) surfaces the N2-3 follow-up discovery: work the
 * nurse STARTED on a station whose assignment was deactivated mid-flight
 * — she may still finish it through the existing terminal endpoints.
 */

import type {
  NurseServingDrainingExecutionItemDto,
  NurseWorkplace,
} from '@/api/nurseServing';

import { useTranslation } from '../../i18n/useTranslation';

export type NurseWorkplacePickerProps = {
  workplaces: NurseWorkplace[];
  loading: boolean;
  selectedWorkplaceId: number | null;
  onSelect: (queueResourceId: number) => void;
};

export function NurseWorkplacePicker({
  workplaces,
  loading,
  selectedWorkplaceId,
  onSelect,
}: NurseWorkplacePickerProps) {
  const { t } = useTranslation();

  if (loading) {
    return <p className="nurse-hint">{t('nurse.loading')}</p>;
  }

  if (workplaces.length === 0) {
    return (
      <div className="nurse-card nurse-card--empty">
        <h2 className="nurse-empty__title">{t('nurse.workplace_none')}</h2>
        <p className="nurse-empty__hint">{t('nurse.workplace_none_hint')}</p>
      </div>
    );
  }

  if (workplaces.length === 1) {
    // auto-selected — the picker itself renders nothing
    return null;
  }

  return (
    <div className="nurse-card nurse-card--picker">
      <h2 className="nurse-picker__title">{t('nurse.workplace_select')}</h2>
      <ul className="nurse-picker__list">
        {workplaces.map((workplace) => {
          const selected = workplace.queue_resource_id === selectedWorkplaceId;
          return (
            <li key={workplace.assignment_id}>
              <button
                type="button"
                className={`nurse-btn nurse-btn--choice ${
                  selected ? 'nurse-btn--selected' : ''
                }`}
                aria-pressed={selected}
                onClick={() => onSelect(workplace.queue_resource_id)}
              >
                <span className="nurse-btn__label">
                  {workplace.resource_display_name ||
                    workplace.resource_code ||
                    `#${workplace.queue_resource_id}`}
                </span>
                {workplace.effective_cabinet != null && (
                  <span className="nurse-btn__meta">
                    {t('nurse.station_cabinet', {
                      cabinet: workplace.effective_cabinet,
                    })}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export type NurseDrainingCardProps = {
  items: NurseServingDrainingExecutionItemDto[];
  isPending: (key: string) => boolean;
  onComplete: (executionId: number) => void;
  onIncomplete: (executionId: number) => void;
};

export function NurseDrainingCard({
  items,
  isPending,
  onComplete,
  onIncomplete,
}: NurseDrainingCardProps) {
  const { t } = useTranslation();

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="nurse-card nurse-card--draining">
      <h2 className="nurse-draining__title">{t('nurse.draining_title')}</h2>
      <p className="nurse-draining__hint">{t('nurse.draining_hint')}</p>
      <ul className="nurse-draining__list">
        {items.map((item) => (
          <li key={item.execution.id} className="nurse-draining__item">
            <div className="nurse-draining__info">
              <span className="nurse-draining__station">
                {item.station.resource_display_name ||
                  item.station.resource_code ||
                  `#${item.station.queue_resource_id}`}
                {item.station.effective_cabinet != null
                  ? ` · ${t('nurse.station_cabinet', { cabinet: item.station.effective_cabinet })}`
                  : ''}
              </span>
              <span className="nurse-draining__who">
                {t('nurse.queue_number', { number: String(item.entry.number) })}
                {item.entry.patient_name
                  ? ` · ${item.entry.patient_name}`
                  : ''}
              </span>
              <span className="nurse-draining__service">
                {item.service.name ||
                  item.service.code ||
                  `#${item.service.visit_service_id}`}
                {` · ${t('nurse.service_attempt', {
                  attempt: String(item.execution.attempt_no),
                })}`}
              </span>
            </div>
            <div className="nurse-draining__actions">
              <button
                type="button"
                className="nurse-btn nurse-btn--success"
                disabled={isPending(`complete:${item.execution.id}`)}
                onClick={() => onComplete(item.execution.id)}
              >
                {t('nurse.action_service_complete')}
              </button>
              <button
                type="button"
                className="nurse-btn nurse-btn--warning"
                disabled={isPending(`incomplete:${item.execution.id}`)}
                onClick={() => onIncomplete(item.execution.id)}
              >
                {t('nurse.action_service_incomplete')}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
