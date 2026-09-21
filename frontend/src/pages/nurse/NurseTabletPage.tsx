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

import { useMemo, useState } from 'react';

import { useTranslation } from '../../i18n/useTranslation';
import { NurseIncompleteDialog } from './NurseIncompleteDialog';
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
    const my = board.board.my_entry;
    if (my != null && (my.status === 'called' || my.status === 'in_progress')) {
      return my;
    }
    const active = (board.board.active ?? []).find(
      (entry) => entry.status === 'called' || entry.status === 'in_progress',
    );
    return active ?? null;
  }, [board.board]);

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

  const handleDialogSubmit = (reason: string) => {
    if (dialog == null) {
      return;
    }
    if (dialog.mode === 'execution' && dialog.executionId != null) {
      void board.incompleteExecution(dialog.executionId, reason);
    } else if (dialog.mode === 'entry' && dialog.entryId != null) {
      void board.entryIncomplete(dialog.entryId, reason);
    }
    setDialog(null);
  };

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
          {(board.board != null || board.boardLoading) && (
            <NurseStationBoard
              stationLabel={stationLabel}
              cabinet={cabinet}
              current={current}
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

      <NurseIncompleteDialog
        open={dialog != null}
        mode={dialog?.mode ?? 'execution'}
        busy={dialogBusy ?? false}
        onCancel={() => setDialog(null)}
        onSubmit={handleDialogSubmit}
      />
    </div>
  );
}
