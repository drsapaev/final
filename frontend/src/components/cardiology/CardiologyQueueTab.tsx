import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowRight, RotateCw, UserRound } from 'lucide-react';

import { api } from '../../api/client';
import { useTranslation } from '../../i18n/useTranslation';
import { queueService } from '../../services/queue';
import { AppEmpty, AppError, AppLoading, Badge, Button, Card } from '../ui/macos';
import './CardiologyQueueTab.css';

type QueueAction = 'call' | 'start_visit' | 'complete' | 'send_to_diagnostics' | 'notify_diagnostics_return' | 'mark_incomplete' | 'no_show' | 'restore_next';

export interface CardiologyQueueEntry {
  id: number | string;
  number?: number | string;
  patient_id?: number | null;
  visit_id?: number | null;
  patient_name?: string;
  phone?: string | null;
  source?: string;
  status: string;
  available_actions: QueueAction[];
}

interface DoctorQueueResponse {
  queue_exists?: boolean;
  doctor?: { id?: number; name?: string; cabinet?: string | null };
  entries?: CardiologyQueueEntry[];
}

interface StartVisitResponse {
  success?: boolean;
  entry_id?: number;
  patient_id?: number | null;
  visit_id?: number | null;
}

interface CardiologyQueueTabProps {
  onStartVisit: (entry: CardiologyQueueEntry, result: StartVisitResponse) => void;
  onOpenVisit: (entry: CardiologyQueueEntry, completed: boolean) => void;
}

function hasAction(entry: CardiologyQueueEntry, action: QueueAction): boolean {
  return Array.isArray(entry.available_actions) && entry.available_actions.includes(action);
}

function isCurrentVisit(entry: CardiologyQueueEntry): boolean {
  return ['in_progress', 'diagnostics'].includes(String(entry.status).toLowerCase());
}

function isCompletedVisit(entry: CardiologyQueueEntry): boolean {
  return ['served', 'completed', 'done'].includes(String(entry.status).toLowerCase());
}

export function CardiologyQueueTab({ onStartVisit, onOpenVisit }: CardiologyQueueTabProps): React.JSX.Element {
  const { t } = useTranslation();
  const [queue, setQueue] = useState<DoctorQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busyEntryId, setBusyEntryId] = useState<number | string | null>(null);
  const actionBusy = useRef(false);
  // CARDQ-FE-001 (audit 3886): loadQueue is triggered on mount, on every
  // queueUpdated event and by the 30s interval — every request must be
  // bound to a monotonically increasing load id; a LATE response of an
  // earlier load self-cancels (success, catch and finally alike) instead
  // of overwriting the newer snapshot with an obsolete patient list.
  const loadIdRef = useRef(0);

  const loadQueue = useCallback(async () => {
    const loadId = ++loadIdRef.current;
    setLoading(true);
    setError(false);
    try {
      const result = await queueService.getTodayQueue('cardiology') as DoctorQueueResponse | null;
      if (loadId !== loadIdRef.current) {
        // CARDQ-FE-001: a newer load has already been triggered — drop the
        // stale response (and do not touch its loading/error state).
        return;
      }
      if (!result || !Array.isArray(result.entries) || !result.doctor?.id) {
        throw new Error('Invalid doctor queue response');
      }
      setQueue(result);
    } catch {
      if (loadId !== loadIdRef.current) {
        return;
      }
      setError(true);
    } finally {
      if (loadId === loadIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadQueue();
    const refresh = (event: Event) => {
      const specialty = (event as CustomEvent<{ specialty?: string }>).detail?.specialty;
      if (!specialty || specialty === 'all' || specialty === 'cardiology' || specialty === 'cardio') {
        void loadQueue();
      }
    };
    window.addEventListener('queueUpdated', refresh);
    const interval = window.setInterval(() => void loadQueue(), 30000);
    return () => {
      window.removeEventListener('queueUpdated', refresh);
      window.clearInterval(interval);
    };
  }, [loadQueue]);

  const runAction = async (entry: CardiologyQueueEntry, action: 'call' | 'start_visit' | 'send_to_diagnostics') => {
    if (actionBusy.current) return;
    actionBusy.current = true;
    setBusyEntryId(entry.id);
    setError(false);
    try {
      if (action === 'call') {
        await queueService.callPatient(entry.id);
      } else if (action === 'send_to_diagnostics') {
        const response = await api.post(`/queue/entry/${entry.id}/diagnostics`);
        const result = response.data as { success?: boolean; entry_id?: number; new_status?: string } | null;
        if (result?.success !== true || String(result.entry_id) !== String(entry.id)
          || result.new_status !== 'diagnostics') {
          throw new Error('Diagnostics transition was not confirmed');
        }
        await loadQueue();
      } else {
        const result = await queueService.startVisit(entry.id) as StartVisitResponse | null;
        if (!result?.success || result.patient_id == null || result.visit_id == null) {
          throw new Error('Start visit response did not include canonical ids');
        }
        if (entry.status === 'diagnostics' && (
          String(result.entry_id) !== String(entry.id)
          || result.patient_id !== entry.patient_id || result.visit_id !== entry.visit_id
        )) {
          throw new Error('Resumed visit did not match the queue entry');
        }
        onStartVisit(entry, result);
      }
    } catch {
      setError(true);
    } finally {
      actionBusy.current = false;
      setBusyEntryId(null);
    }
  };

  const entries = queue?.entries ?? [];
  const statusLabels: Record<string, string> = {
    waiting: t('cardio.cardio_queue_status_waiting'),
    called: t('cardio.cardio_queue_status_called'),
    in_progress: t('cardio.cardio_queue_status_in_progress'),
    diagnostics: t('cardio.cardio_queue_status_diagnostics'),
    served: t('cardio.cardio_queue_status_completed'),
    completed: t('cardio.cardio_queue_status_completed'),
    done: t('cardio.cardio_queue_status_completed'),
    no_show: t('cardio.cardio_queue_status_no_show'),
  };

  return (
    <Card className="cardio-card-fullwidth">
      <div className="cardio-queue__header">
        <div>
          <h2 className="cardio-queue__title">{t('cardio.cardio_queue_title')}</h2>
          {queue?.doctor?.name && (
            <p className="cardio-queue__doctor">{queue.doctor.name}</p>
          )}
        </div>
        <Button variant="outline" onClick={() => void loadQueue()} disabled={loading} aria-label={t('cardio.cardio_queue_refresh')}>
          <RotateCw size={16} aria-hidden="true" />
          <span>{t('cardio.cardio_queue_refresh')}</span>
        </Button>
      </div>

      {error && (
        <AppError
          title={t('cardio.cardio_queue_error_title')}
          description={t('cardio.cardio_queue_error_desc')}
          action={<Button variant="outline" onClick={() => void loadQueue()}>{t('cardio.cardio_queue_retry')}</Button>}
        />
      )}

      {loading ? (
        <AppLoading title={t('common.loading')} />
      ) : entries.length === 0 && !error ? (
        <AppEmpty title={t('cardio.cardio_queue_empty_title')} description={t('cardio.cardio_queue_empty_desc')} />
      ) : (
        <div className="cardio-queue__list">
          {entries.map((entry) => {
            const status = String(entry.status || '').toLowerCase();
            const currentVisit = isCurrentVisit(entry);
            const completedVisit = isCompletedVisit(entry);
            const canResume = status === 'diagnostics' && hasAction(entry, 'start_visit');
            const openable = !canResume && (currentVisit || completedVisit) && entry.visit_id != null;
            const name = entry.patient_name || t('cardio.cardio_queue_unknown_patient');

            return (
              <article
                key={entry.id}
                data-testid={`cardiology-queue-entry-${entry.id}`}
                className="cardio-queue__entry"
              >
                <div className="cardio-queue__patient">
                  <UserRound size={20} aria-hidden="true" className="cardio-queue__patient-icon" />
                  <div className="cardio-queue__patient-info">
                    <div className="cardio-queue__patient-heading">
                      <strong>{entry.number != null ? `${t('cardio.cardio_queue_number')} ${entry.number}` : name}</strong>
                      {entry.number != null && <span>{name}</span>}
                      <Badge variant={completedVisit ? 'success' : currentVisit ? 'primary' : status === 'called' ? 'info' : 'default'}>
                        {statusLabels[status] || status}
                      </Badge>
                    </div>
                    {entry.phone && <div className="cardio-queue__phone">{entry.phone}</div>}
                  </div>
                </div>

                <div className="cardio-queue__actions">
                  {/* CARDQ-FE-002 (audit 3886): after a failed refresh the
                   * previous snapshot may stay visible as read-only context,
                   * but its call/start actions must NOT stay actionable as if
                   * the data were current — only a backend-confirmed fresh
                   * read may enable commands. */}
                  {hasAction(entry, 'call') && !error && (
                    <Button variant="primary" loading={busyEntryId === entry.id} disabled={busyEntryId !== null} onClick={() => void runAction(entry, 'call')}>
                      {t('cardio.cardio_queue_call')}
                    </Button>
                  )}
                  {hasAction(entry, 'start_visit') && !error && (
                    <Button variant="primary" loading={busyEntryId === entry.id} disabled={busyEntryId !== null} onClick={() => void runAction(entry, 'start_visit')}>
                      {t(canResume ? 'cardio.cardio_queue_resume_visit' : 'cardio.cardio_queue_start_visit')}
                    </Button>
                  )}
                  {status === 'in_progress' && hasAction(entry, 'send_to_diagnostics') && !error && (
                    <Button variant="outline" loading={busyEntryId === entry.id} disabled={busyEntryId !== null} onClick={() => void runAction(entry, 'send_to_diagnostics')}>
                      {t('misc.qmc_to_diagnostics')}
                    </Button>
                  )}
                  {openable && (
                    <Button variant="outline" onClick={() => onOpenVisit(entry, completedVisit)}>
                      {completedVisit ? t('cardio.cardio_queue_view_emr') : t('cardio.cardio_queue_open_visit')}
                      <ArrowRight size={16} aria-hidden="true" />
                    </Button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </Card>
  );
}

export default CardiologyQueueTab;
