/**
 * Registrar Panel — reschedule slots dialog (view component).
 *
 * PR-UI-13-3: extracted verbatim from RegistrarPanel.tsx — the ModernDialog
 * composition for rescheduling a visit ("tomorrow" quick action + custom date/time
 * picker). Owns ONLY the form-field state (customRescheduleDate /
 * customRescheduleTime — QW-02 fix: inline date picker replaces
 * window.prompt; R-27: optional HH:MM time; R-43: confirm dialogs for the
 * destructive reschedule actions).
 *
 * Open/close + payload state lives in useRegistrarDialogs
 * (rescheduleDialog slice: { open, data }).
 *
 * Naming: *View composition (not *Dialog.tsx) — the modal IMPLEMENTATION is
 * ModernDialog (already counted by the modalFilesOutsideKit ratchet); this
 * file composes it. Inline styles from the original JSX moved to
 * registrar.css classes (same values — zero visual delta).
 */
import { useState } from 'react';
import ModernDialog from '../../../components/dialogs/ModernDialog';
import { Input } from '../../../components/ui/macos';
import logger from '../../../utils/logger';
import notify from '../../../services/notify';
import { getLocalDateString } from '../../../utils/dateUtils';
import { rescheduleTomorrow, rescheduleVisit } from '../../../api/visits';
import { getErrorMessage } from '../../../utils/errorHandler';

interface RescheduleSlotsDialogProps {
  isOpen: boolean;
  rescheduleData: Record<string, unknown> | null;
  onClose: () => void;
  /** useConfirm hook result from the panel (portal-mounted ConfirmDialog). */
  confirm: (options: Record<string, unknown>) => Promise<boolean>;
  resolveRescheduleVisitId: (appointmentRow: Record<string, unknown>) => unknown;
  removeRescheduledAppointmentFromView: (appointmentRow: Record<string, unknown>, visitId: unknown) => void;
  loadAppointments: (options?: unknown) => Promise<void> | void;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}

const RescheduleSlotsDialog = ({
  isOpen,
  rescheduleData,
  onClose,
  confirm,
  resolveRescheduleVisitId,
  removeRescheduledAppointmentFromView,
  loadAppointments,
  tI18n,
}: RescheduleSlotsDialogProps) => {
  // QW-02 fix: hold the date the user picks in the inline date input inside the
  // reschedule slots dialog. Replaces the previous window.prompt() call that was
  // jarring, blocking, and lacked a date picker.
  const [customRescheduleDate, setCustomRescheduleDate] = useState('');
  // R-27 fix: optional time picker for reschedule (HH:MM)
  const [customRescheduleTime, setCustomRescheduleTime] = useState('');

  const resetForm = () => {
    setCustomRescheduleDate('');
    setCustomRescheduleTime('');
  };

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title={`📅 ${tI18n('registrarPanel.available_slots')}`}
      maxWidth="32rem"
      dialogStyle={{
        backgroundColor: 'var(--mac-bg-primary)'
      }}
      actions={[
        {
          label: '🌅 ' + tI18n('registrarPanel.tomorrow'),
          variant: 'primary',
          onClick: async () => {
            if (!rescheduleData) return;

            // R-43 fix: confirmation dialog для destructive action.
            // Перенос записи — необратимое действие (запись меняет день).
            const ok = await confirm({
              title: tI18n('registrar.postpone_tomorrow_title'),
              message: tI18n('registrar.postpone_tomorrow_message'),
              description: tI18n('registrar.postpone_tomorrow_description'),
              confirmLabel: tI18n('registrar.postpone_tomorrow_confirm'),
              cancelLabel: tI18n('registrar.cancel'),
              intent: 'primary',
            });
            if (!ok) return;

            try {
              onClose();
              resetForm();
              const targetVisitId = resolveRescheduleVisitId(rescheduleData);
              if (!targetVisitId) {
                notify.error(tI18n('registrar.no_visit_for_postpone'));
                return;
              }
              logger.info(`Перенос визита ${targetVisitId} на завтра`);
              await rescheduleTomorrow(targetVisitId as string | number);
              notify.success(tI18n('registrar.visit_postponed'));
              removeRescheduledAppointmentFromView(rescheduleData, targetVisitId);
              loadAppointments({ source: 'reschedule_tomorrow' });
            } catch (e: unknown) {
              logger.error('Ошибка переноса на завтра:', e);
              notify.error(getErrorMessage(e, tI18n('registrarPanel.rp_err_reschedule_failed')));
            }
          }
        },
        {
          label: tI18n('registrarPanel.select_date'),
          variant: 'secondary',
          // QW-02 fix: previously called window.prompt('Введите дату переноса (YYYY-MM-DD):', currentVal)
          // — a jarring native browser dialog that blocks the tab, has no date picker,
          // no min-date guard, and breaks the macOS-style visual language of the app.
          // Now the date is captured via the inline <Input type="date"> rendered in the
          // dialog body (see customRescheduleDate state + date input below). This action
          // validates the captured date and performs the reschedule.
          onClick: async () => {
            if (!rescheduleData) return;

            const dateStr = customRescheduleDate || '';
            const timeStr = (customRescheduleTime || '').trim();

            if (!dateStr) {
              notify.error(tI18n('registrar.select_postpone_date'));
              return;
            }

            if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
              notify.error(tI18n('registrar.invalid_date_format'));
              return;
            }

            // R-27 fix: validate optional time (HH:MM)
            if (timeStr && !/^\d{2}:\d{2}$/.test(timeStr)) {
              notify.error(tI18n('registrar.invalid_time_format'));
              return;
            }

            // Optional guard: prevent rescheduling to a past date
            const today = getLocalDateString();
            if (dateStr < today) {
              notify.error(tI18n('registrar.cannot_postpone_past'));
              return;
            }

            // R-43 fix: confirmation dialog для destructive action.
            const ok = await confirm({
              title: tI18n('registrar.postpone_date_title'),
              message: timeStr
                ? tI18n('registrarPanel.rp_confirm_reschedule_datetime', { date: dateStr, time: timeStr })
                : tI18n('registrarPanel.rp_confirm_reschedule_date', { date: dateStr }),
              confirmLabel: tI18n('registrar.postpone_date_confirm'),
              cancelLabel: tI18n('registrar.cancel'),
              intent: 'primary',
            });
            if (!ok) return;

            try {
              onClose();
              resetForm();
              const targetVisitId = resolveRescheduleVisitId(rescheduleData);
              if (!targetVisitId) {
                notify.error(tI18n('registrar.no_visit_for_postpone'));
                return;
              }
              logger.info(`Перенос визита ${targetVisitId} на ${dateStr}${timeStr ? ' ' + timeStr : ''}`);
              await rescheduleVisit(targetVisitId as string | number, dateStr, timeStr || undefined);
              notify.success(tI18n('registrar.visit_postponed_date') + ` ${dateStr}${timeStr ? ' ' + timeStr : ''}`);
              removeRescheduledAppointmentFromView(rescheduleData, targetVisitId);
              loadAppointments({ source: 'reschedule_date' });
            } catch (e: unknown) {
              logger.error('Ошибка переноса на дату:', e);
              notify.error(getErrorMessage(e, tI18n('registrarPanel.rp_err_reschedule_failed')));
            }
          }
        }
      ]}>
      <div className="registrar-grid-gap-lg">
        <div className="registrar-reschedule-card registrar-reschedule-card-accent">
          <div className="registrar-reschedule-header">
            <div className="registrar-reschedule-icon registrar-reschedule-icon-bg registrar-reschedule-icon-accent">
              📅
            </div>
            <div>
              <div className="registrar-reschedule-title registrar-reschedule-title-text">
                {tI18n('registrarPanel.rp_reschedule_title')}
              </div>
              <div className="registrar-reschedule-desc registrar-reschedule-desc-text">
                {tI18n('registrarPanel.rp_reschedule_desc')}
              </div>
            </div>
          </div>
        </div>

        {/* QW-02 fix: inline date picker replacing window.prompt().
            min=today prevents selecting past dates natively in the picker. */}
        <div className="registrar-reschedule-card registrar-reschedule-card-neutral">
          <label htmlFor="reschedule-custom-date" className="registrar-reschedule-label registrar-reschedule-label-text">
            {tI18n('registrarPanel.rp_reschedule_date_label')}
          </label>
          <Input
            id="reschedule-custom-date"
            type="date"
            value={customRescheduleDate}
            min={getLocalDateString()}
            aria-label={tI18n('registrarPanel.rp_aria_reschedule_date')}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setCustomRescheduleDate(e.target.value)}
            className="registrar-reschedule-input registrar-reschedule-input-themed"
          />
          {/* R-27 fix: optional time picker (HH:MM) */}
          <label htmlFor="reschedule-custom-time" className="registrar-reschedule-label registrar-reschedule-label-block">
            {tI18n('registrarPanel.rp_reschedule_time_label')}
          </label>
          <Input
            id="reschedule-custom-time"
            type="time"
            value={customRescheduleTime}
            aria-label={tI18n('registrarPanel.rp_aria_reschedule_time')}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setCustomRescheduleTime(e.target.value)}
            className="registrar-reschedule-input registrar-reschedule-input-themed"
          />
          <div className="registrar-reschedule-hint registrar-reschedule-hint-text">
            {tI18n('registrarPanel.rp_reschedule_hint', { btn: tI18n('registrarPanel.select_date') })}
          </div>
        </div>
      </div>
    </ModernDialog>
  );
};

export default RescheduleSlotsDialog;
