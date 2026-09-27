/**
 * NURSE-V2 N2-5 — the station board: «Где я работаю? Кто сейчас? Кто следующий?».
 *
 * The active card follows the SERVER state (§5):
 *  - waiting / no current -> [Вызвать следующего];
 *  - called               -> [Начать приём] [Пациент не явился] [Завершить без выполнения];
 *  - in_progress          -> the station-routed service list (each with its own actions).
 * NO visit-close action exists here (§5): «Выполнено» completes a
 * ServiceExecution, the Visit stays open — the server decides the flip.
 *
 * Owner review round (P1, the D1 handover): when the current card is a
 * server-proven takeover (the claim owner's assignment is gone), the
 * called-state start action reads [Принять пациента] and the card carries
 * the handover banner; the others block adds the explicit takeover
 * action ONLY on rows the server marks actionable — an owner still
 * working keeps her row read-only.
 */

import type { NurseBoardEntry } from '@/api/nurseServing';

import { useTranslation } from '../../i18n/useTranslation';
import { NurseServiceList } from './NurseServiceList';

export type NurseStationBoardProps = {
  stationLabel: string;
  cabinet: string | null;
  current: NurseBoardEntry | null;
  /** The station's OTHER active entries (owner review): read-only
   * overview — "being served by another staff member" — except a
   * server-proven handover row, which carries the takeover action. */
  others: NurseBoardEntry[];
  nextWaiting: NurseBoardEntry | null;
  waitingCount: number;
  pendingKeys: Set<string>;
  isPending: (key: string) => boolean;
  onCallNext: () => void;
  onStart: (entryId: number) => void;
  onNoShow: (entryId: number) => void;
  onEntryIncomplete: (entryId: number) => void;
  onStartExecution: (visitServiceId: number, queueEntryId: number) => void;
  onCompleteExecution: (executionId: number) => void;
  onIncompleteExecution: (executionId: number) => void;
};

const ENTRY_ACTIVE = new Set(['called', 'in_progress']);

export function NurseStationBoard({
  stationLabel,
  cabinet,
  current,
  others,
  nextWaiting,
  waitingCount,
  isPending,
  onCallNext,
  onStart,
  onNoShow,
  onEntryIncomplete,
  onStartExecution,
  onCompleteExecution,
  onIncompleteExecution,
}: NurseStationBoardProps) {
  const { t } = useTranslation();
  const callNextBusy = isPending('call-next');
  const statusKey =
    current != null ? `nurse.entry_status_${current.status}` : null;
  // Owner review round (P1): a server-proven takeover — not my claim,
  // but the board says the claim owner is gone and I may act.
  const isTakeover = current != null && current.is_my_claim !== true;

  return (
    <section className="nurse-board" aria-label={stationLabel}>
      {current != null && ENTRY_ACTIVE.has(current.status) ? (
        <div className="nurse-card nurse-card--current">
          <div className="nurse-card__head">
            <span className="nurse-card__caption">
              {t('nurse.board_current')}
            </span>
            {cabinet != null && (
              <span className="nurse-card__cabinet">
                {t('nurse.station_cabinet', { cabinet })}
              </span>
            )}
          </div>
          {isTakeover && (
            // The D1 handover banner: the patient was called by a staffer
            // who no longer holds an active assignment on this station —
            // the server explicitly hands the service to the current user.
            <p className="nurse-handover__banner" role="status">
              {t('nurse.handover_banner')}
            </p>
          )}
          <div className="nurse-current__who">
            <span className="nurse-current__number">
              {t('nurse.queue_number', { number: String(current.number) })}
            </span>
            <span className="nurse-current__name">
              {current.patient_name || t('nurse.patient_unnamed')}
            </span>
            {statusKey != null && (
              <span className={`nurse-badge nurse-badge--${current.status}`}>
                {t(statusKey)}
              </span>
            )}
          </div>

          {current.status === 'called' && (
            <div className="nurse-actions">
              <button
                type="button"
                className="nurse-btn nurse-btn--primary nurse-btn--xl"
                disabled={isPending(`start:${current.id}`)}
                onClick={() => onStart(current.id)}
              >
                {isTakeover
                  ? t('nurse.action_takeover')
                  : t('nurse.action_start')}
              </button>
              <button
                type="button"
                className="nurse-btn nurse-btn--danger"
                disabled={isPending(`no-show:${current.id}`)}
                onClick={() => onNoShow(current.id)}
              >
                {t('nurse.action_no_show')}
              </button>
              <button
                type="button"
                className="nurse-btn nurse-btn--warning"
                disabled={isPending(`entry-incomplete:${current.id}`)}
                onClick={() => onEntryIncomplete(current.id)}
              >
                {t('nurse.action_entry_incomplete')}
              </button>
            </div>
          )}

          {current.status === 'in_progress' && (
            <NurseServiceList
              services={current.services ?? []}
              pendingStartExecution={(visitServiceId) =>
                isPending(`execution:${visitServiceId}`)
              }
              pendingComplete={(executionId) =>
                isPending(`complete:${executionId}`) ||
                isPending(`incomplete:${executionId}`)
              }
              onStartExecution={(visitServiceId) =>
                onStartExecution(visitServiceId, current.id)
              }
              onCompleteExecution={onCompleteExecution}
              onIncompleteExecution={onIncompleteExecution}
            />
          )}
        </div>
      ) : (
        <div className="nurse-card nurse-card--idle">
          <div className="nurse-card__head">
            <span className="nurse-card__caption">
              {t('nurse.board_current')}
            </span>
            {cabinet != null && (
              <span className="nurse-card__cabinet">
                {t('nurse.station_cabinet', { cabinet })}
              </span>
            )}
          </div>
          <p className="nurse-idle__text">{t('nurse.board_no_current')}</p>
          <div className="nurse-actions">
            <button
              type="button"
              className="nurse-btn nurse-btn--primary nurse-btn--xl"
              disabled={callNextBusy || waitingCount === 0}
              onClick={onCallNext}
            >
              {t('nurse.action_call_next')}
            </button>
          </div>
        </div>
      )}

      {others.length > 0 && (
        <div className="nurse-card nurse-card--others">
          <div className="nurse-card__head">
            <span className="nurse-card__caption">
              {t('nurse.board_other_staff')}
            </span>
          </div>
          <ul className="nurse-others__list">
            {others.map((entry) => {
              const otherStatusKey = `nurse.entry_status_${entry.status}`;
              // Owner review round (P1): ONLY a server-proven actionable
              // row gets the takeover action — the claim owner's active
              // assignment keeps her entry read-only for the colleagues.
              const actionable = entry.actionable_by_current_user === true;
              return (
                <li key={entry.id} className="nurse-others__row">
                  <span className="nurse-next__number">
                    {t('nurse.queue_number', { number: String(entry.number) })}
                  </span>
                  <span className="nurse-next__name">
                    {entry.patient_name || t('nurse.patient_unnamed')}
                  </span>
                  <span className={`nurse-badge nurse-badge--${entry.status}`}>
                    {t(otherStatusKey)}
                  </span>
                  {actionable ? (
                    <>
                      <span className="nurse-others__note">
                        {t('nurse.others_handover')}
                      </span>
                      <button
                        type="button"
                        className="nurse-btn nurse-btn--small nurse-btn--primary"
                        disabled={isPending(`start:${entry.id}`)}
                        onClick={() => onStart(entry.id)}
                      >
                        {entry.status === 'called'
                          ? t('nurse.action_takeover')
                          : t('nurse.action_takeover_continue')}
                      </button>
                    </>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="nurse-card nurse-card--next">
        <div className="nurse-card__head">
          <span className="nurse-card__caption">{t('nurse.board_next')}</span>
          <span className="nurse-card__count">
            {t('nurse.board_waiting_count', { count: String(waitingCount) })}
          </span>
        </div>
        {nextWaiting != null ? (
          <div className="nurse-next__row">
            <span className="nurse-next__number">
              {t('nurse.queue_number', { number: String(nextWaiting.number) })}
            </span>
            <span className="nurse-next__name">
              {nextWaiting.patient_name || t('nurse.patient_unnamed')}
            </span>
          </div>
        ) : (
          <p className="nurse-idle__text">{t('nurse.board_empty_waiting')}</p>
        )}
      </div>
    </section>
  );
}
