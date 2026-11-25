import type { queueService } from '../services/queue';
import notify from '../services/notify';

type NextCall = Awaited<ReturnType<typeof queueService.callNextWaiting>>;
type Translate = (key: string, values?: Record<string, unknown>) => string;

/** The visit is already complete. Never interpret a failed optional call as a failed visit or retry it. */
export async function reportVisitCompletionCall(
  callNext: () => Promise<NextCall>,
  t: Translate,
  calledWithNumberKey: string,
): Promise<void> {
  try {
    const next = await callNext();
    if (next?.success === true) {
      const number = next.entry?.number;
      notify.success(typeof number === 'number' || (typeof number === 'string' && number.trim())
        ? t(calledWithNumberKey, { number })
        : t('misc.visit_completed_next_patient_called'));
      if (next.displayDelivery === 'unconfirmed' || next.displayDelivery === 'partial') {
        notify.warning(t('misc.queue_called_display_unconfirmed'));
      }
    } else if (next?.noCandidate === true) {
      notify.info(t('misc.visit_completed_no_next_patient'));
    } else {
      notify.warning(t('misc.visit_completed_call_next_unconfirmed'));
    }
  } catch {
    notify.warning(t('misc.visit_completed_call_next_unconfirmed'));
  }
}
