/**
 * NURSE-V2 N2-5 — the Nurse tablet workspace (canonical route /nurse).
 *
 * NOT a DoctorPanel, no Nurse→Doctor alias, no registrar/admin surfaces:
 * a minimal serving screen answering exactly three questions — where am
 * I working, who is with me now, who is next (§5). Everything renders
 * from the N2-3 server contract; a reload rebuilds the whole state from
 * the server (§8). PHI hygiene (§11): no patient names/phones/reasons in
 * the console, no client-side audit — the server UserAuditLog is SSOT.
 */

import { useCallback, useMemo, useState } from 'react';

import { useTranslation } from '../../i18n/useTranslation';
import { NurseReasonForm } from './NurseReasonForm';
import {
  NurseDrainingCard,
  NurseWorkplacePicker,
} from './NurseWorkplacePicker';
import { NurseStationBoard } from './NurseStationBoard';
import { useNurseServingBoard } from './useNurseServingBoard';
import './nurseTablet.css';

export default function NurseTabletPage() {
  const { t } = useTranslation();
  const board = useNurseServingBoard();

  const [dialog, setDialog] = useState<{
    mode: 'execution' | 'entry';
    executionId?: number;
    entryId?: number;
  } | null>(null);

  const isPending = (key: string) => board.pending.has(key);

  const selectedWorkplace = useMemo(
    () =>
      board.workplaces.find(
        (workplace) =>
          workplace.queue_resource_id === board.selectedWorkplaceId,
      ) ?? null,
    [board.workplaces, board.selectedWorkplaceId],
  );

  const current = useMemo(() => {
    if (board.board == null) {
      return null;
    }
    // Owner review (P1): the current patient is EXCLUSIVELY my_entry —
    // the server's "the caller's own claim" answer. Another nurse's
    // active entry must NEVER stand in for it: taking one used to show
    // her patient as ours and hide [Вызвать следующего], collapsing the
    // two-nurses-one-station concurrency contract (§6) into one line.
    const my = board.board.my_entry;
    if (my != null && (my.status === 'called' || my.status === 'in_progress')) {
      return my;
    }
    return null;
  }, [board.board]);

  // The station's OTHER active entries — a read-only overview block
  // ("being served by another staff member"), never a current patient
  // and never an action surface.
  const otherActive = useMemo(() => {
    if (board.board == null) {
      return [];
    }
    const myId = current?.id ?? null;
    return (board.board.active ?? []).filter(
      (entry) => entry.id !== myId,
    );
  }, [board.board, current]);

  const nextWaiting = board.board?.waiting?.[0] ?? null;
  const waitingCount = board.board?.counts?.waiting ?? 0;

  const stationLabel =
    selectedWorkplace?.resource_display_name ||
    selectedWorkplace?.resource_code ||
    t('nurse.title');
  const cabinet = selectedWorkplace?.effective_cabinet ?? null;

  const dialogBusy =
    dialog != null &&
    ((dialog.executionId != null &&
      (isPending(`complete:${dialog.executionId}`) ||
        isPending(`incomplete:${dialog.executionId}`))) ||
      (dialog.entryId != null && isPending(`entry-incomplete:${dialog.entryId}`)));

  // Stable dialog callbacks: the Modal kit re-runs its focus effect when
  // `onClose` changes identity — an inline arrow would restart it on every
  // keystroke and steal the focus mid-typing.
  const handleDialogCancel = useCallback(() => setDialog(null), []);
  const handleDialogSubmit = useCallback(
    (reason: string) => {
      setDialog((current) => {
        if (current == null) {
          return null;
        }
        if (current.mode === 'execution' && current.executionId != null) {
          void board.incompleteExecution(current.executionId, reason);
        } else if (current.mode === 'entry' && current.entryId != null) {
          void board.entryIncomplete(current.entryId, reason);
        }
        return null;
      });
    },
    [board],
  );

  return (
    <div className="nurse-tablet">
      <header className="nurse-tablet__header">
        <div className="nurse-tablet__station">
          <h1 className="nurse-tablet__title">{stationLabel}</h1>
          {board.selectedWorkplaceId != null &&
            board.workplaces.length > 1 && (
              <button
                type="button"
                className="nurse-btn nurse-btn--small"
                onClick={() => void board.resetWorkplace()}
              >
                {t('nurse.workplace_change')}
              </button>
            )}
        </div>
        <button
          type="button"
          className="nurse-btn nurse-btn--small"
          onClick={() => void board.refresh()}
          disabled={board.boardLoading}
        >
          {t('nurse.refresh')}
        </button>
      </header>

      {board.notice != null && (
        <div className="nurse-notice" role="status" aria-live="polite">
          <span>{t(board.notice)}</span>
          {board.notice === 'nurse.notice_retry' && (
            <button
              type="button"
              className="nurse-btn nurse-btn--small"
              onClick={() => void board.refresh()}
            >
              {t('nurse.notice_retry_action')}
            </button>
          )}
          <button
            type="button"
            className="nurse-notice__close"
            aria-label={t('nurse.notice_dismiss')}
            onClick={board.dismissNotice}
          >
            ×
          </button>
        </div>
      )}

      <NurseWorkplacePicker
        workplaces={board.workplaces}
        loading={board.workplacesLoading}
        selectedWorkplaceId={board.selectedWorkplaceId}
        onSelect={(id) => void board.selectWorkplace(id)}
      />

      <NurseDrainingCard
        items={board.draining}
        isPending={isPending}
        onComplete={(executionId) => void board.completeExecution(executionId)}
        onIncomplete={(executionId) =>
          setDialog({ mode: 'execution', executionId })
        }
      />

      {board.selectedWorkplaceId != null && (
        <>
          {board.boardError != null && board.board == null && (
            <div className="nurse-card nurse-card--error" role="alert">
              <p className="nurse-error__text">
                {t('errors.nurse.board_unavailable')}
              </p>
              <button
                type="button"
                className="nurse-btn nurse-btn--primary"
                onClick={() => void board.refresh()}
              >
                {t('nurse.notice_retry_action')}
              </button>
            </div>
          )}
          {board.boardError != null && board.board != null && (
            // Owner review: the read error is visible EVEN while the last
            // rendered board stays on screen (§9 stale-state contract) —
            // a transient failure must not be silent, and the data it
            // shows is honestly labeled as possibly outdated.
            <div className="nurse-notice nurse-notice--error" role="alert">
              <span>{board.boardError.message}</span>
              <button
                type="button"
                className="nurse-btn nurse-btn--small"
                onClick={() => void board.refresh()}
              >
                {t('nurse.notice_retry_action')}
              </button>
            </div>
          )}
          {(board.board != null || board.boardLoading) && (
            <NurseStationBoard
              stationLabel={stationLabel}
              cabinet={cabinet}
              current={current}
              others={otherActive}
              nextWaiting={nextWaiting}
              waitingCount={waitingCount}
              pendingKeys={board.pending}
              isPending={isPending}
              onCallNext={() => void board.callNext()}
              onStart={(entryId) => void board.start(entryId)}
              onNoShow={(entryId) => void board.noShow(entryId)}
              onEntryIncomplete={(entryId) =>
                setDialog({ mode: 'entry', entryId })
              }
              onStartExecution={(visitServiceId, queueEntryId) =>
                void board.startExecution(visitServiceId, queueEntryId)
              }
              onCompleteExecution={(executionId) =>
                void board.completeExecution(executionId)
              }
              onIncompleteExecution={(executionId) =>
                setDialog({ mode: 'execution', executionId })
              }
            />
          )}
          {board.boardLoading && board.board == null && (
            <p className="nurse-hint" aria-live="polite">
              {t('nurse.loading')}
            </p>
          )}
        </>
      )}

      <NurseReasonForm
        open={dialog != null}
        mode={dialog?.mode ?? 'execution'}
        busy={dialogBusy ?? false}
        onClose={dialogBusy ? undefined : handleDialogCancel}
        onCancel={handleDialogCancel}
        onSubmit={handleDialogSubmit}
      />
    </div>
  );
}
