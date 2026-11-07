import { useState, useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import logger from '../../utils/logger';
import { api } from '../../api/client';
import {

  Phone,
  Clock,
  User,
  Play,
  CheckCircle,

  RefreshCw,

  MapPin,

  Activity } from
'lucide-react';
import {
  Card,
  Button,
  Badge,
  Skeleton,
  AppEmpty,
  Alert,
} from '../ui/macos';
import {
  formatRegistrarTime,
  getRegistrarTimestampDisplay,
} from '../../utils/dateUtils';
import { useTranslation } from '../../i18n/useTranslation';

const QUEUE_ACTION_ALIASES = {
  call: ['call'],
  start_visit: ['start_visit', 'start', 'in_cabinet'],
  complete: ['complete']
} as const;

type QueueActionKey = keyof typeof QUEUE_ACTION_ALIASES;

interface QueueEntryDto {
  id: number | string;
  number: string | number;
  patient_name?: string;
  status: string;
  available_actions?: string[];
  can_call?: boolean;
  can_start_visit?: boolean;
  can_complete?: boolean;
  source?: string;
  phone?: string;
  created_at?: string;
  called_at?: string;
  [key: string]: unknown;
}

interface QueueStatsDto {
  total?: number;
  waiting?: number;
  served?: number;
  online_entries?: number;
}

interface QueueDoctor {
  name?: string;
  specialty?: string;
  cabinet?: string;
}

interface QueueDataDto {
  queue_exists?: boolean;
  opened_at?: string;
  stats?: QueueStatsDto;
  doctor?: QueueDoctor;
  entries?: QueueEntryDto[];
}

interface DoctorInfo {
  id?: number | string;
  name?: string;
  specialty?: string;
  department?: string;
  queue_settings?: {
    start_number?: string;
    max_per_day?: number;
    timezone?: string;
  };
  doctor?: {
    cabinet?: string;
  };
}

interface DoctorQueuePanelProps {
  specialty?: string;
  onPatientSelect?: (patient: Record<string, unknown>) => void;
  className?: string;
}

// DOCQ-FE-002 (audit 3886): non-2xx responses reject through the canonical
// axios client with the parsed body on error.response.data — extract the
// backend-provided detail/message the way the previous fetch code did.
function extractApiErrorDetail(error: unknown): string {
  const axiosLike = error as {
    response?: { data?: { detail?: unknown; message?: unknown } };
  };
  const data = axiosLike?.response?.data;
  const detail = data?.detail ?? data?.message;
  return typeof detail === 'string' ? detail : '';
}

const hasBackendQueueAction = (entry: QueueEntryDto | null | undefined, action: string, flagName?: string) => {
  if (flagName && entry?.[flagName] === true) {
    return true;
  }

  const actions = Array.isArray(entry?.available_actions) ? entry.available_actions : [];
  const aliasesRaw = QUEUE_ACTION_ALIASES[action as QueueActionKey];
  const aliases: string[] = aliasesRaw ? Array.from(aliasesRaw) : [action];
  return aliases.some((alias: string) => actions.includes(alias));
};

// DOCQ-FE-004 (post-merge review of #3905, P1): a resolved 2xx is NOT a
// confirmed queue command. Only an explicit `success: true` DTO confirms
// the write — the same fail-closed contract as queueService.completeVisit
// (DOCFLOW-FE-001, audit 3886): a 2xx body that is unreadable or lacks the
// ack is AMBIGUOUS (the server may have committed; no blind retry, do not
// report success), while `success: false` is an explicit rejection.
interface QueueCommandAck {
  success: boolean;
  unknown?: boolean;
  message: string;
}

const AMBIGUOUS_QUEUE_COMMAND_MESSAGE =
  'Ответ сервера не удалось прочитать — операция не подтверждена. Состояние очереди уточняется у сервера; не повторяйте операцию автоматически. / Unreadable server response — the operation is NOT confirmed. The queue state is being reconciled with the server; do not blindly retry.';

const REJECTED_QUEUE_COMMAND_MESSAGE =
  'Сервер отклонил операцию. / The server rejected the operation.';

function queueCommandAck(data: unknown): QueueCommandAck {
  if (data && typeof data === 'object' && (data as { success?: unknown }).success === true) {
    const message = (data as { message?: unknown }).message;
    return { success: true, message: typeof message === 'string' ? message : '' };
  }
  if (data === null || data === undefined || typeof data !== 'object') {
    return { success: false, unknown: true, message: AMBIGUOUS_QUEUE_COMMAND_MESSAGE };
  }
  const detail = (data as { detail?: unknown; message?: unknown }).detail
    ?? (data as { message?: unknown }).message;
  return {
    success: false,
    message: typeof detail === 'string' && detail.trim() ? detail : REJECTED_QUEUE_COMMAND_MESSAGE,
  };
}

/**
 * Панель очереди для врача - показывает пациентов из регистратуры
 * Основа: passport.md стр. 1417-1427
 */
const DoctorQueuePanel = ({
  specialty = 'cardiology',
  onPatientSelect,
  className = ''
}: DoctorQueuePanelProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  // Проверяем демо-режим в самом начале (в демо не скрываем компонент, а показываем моковые данные)
  const isDemoMode = import.meta.env.MODE === 'development' && window.location.hostname === 'localhost';

  const [loading, setLoading] = useState(true);
  const [queueData, setQueueData] = useState<QueueDataDto | null>(null);
  const [doctorInfo, setDoctorInfo] = useState<DoctorInfo | null>(null);
  const [selectedPatient, setSelectedPatient] = useState<QueueEntryDto | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string }>({ type: '', text: '' });
  // DOCQ-FE-003 (audit 3886): a distinct load-error state — a failed fetch
  // must render as an error/retry screen, never as the misleading
  // «Очередь не создана» empty state; a failed REFRESH after a successful
  // load keeps the previous rows but must flag them as possibly stale.
  const [loadError, setLoadError] = useState<string | null>(null);
  const [queueStale, setQueueStale] = useState(false);
  const loadQueueDataRef = useRef<() => void>(() => {});
  // DOCQ-FE-001 (audit 3886): request-identity guard — the panel re-runs
  // loading on `specialty` change, but the earlier specialty's in-flight
  // response may resolve later and overwrite the new specialty's queue.
  // Every async continuation is bound to the epoch+specialty it was issued
  // in and self-cancels when superseded.
  const queueEpochRef = useRef(0);
  const specialtyRef = useRef<string | null>(null);
  const queueDataRef = useRef<QueueDataDto | null>(null);

  // UX Audit Doctor H-31: unified status config from shared queueStatusConfig.js.
  // Previously: waiting=info, called=warning (different from DoctorPanel).
  // Now: waiting=warning, called=primary (matches DoctorPanel).
  const statusConfig = {
    waiting: { label: t('misc.dqp_ozhidaet'), color: 'warning', icon: Clock },
    called: { label: t('misc.dqp_vyzvan'), color: 'primary', icon: Play },
    in_progress: { label: t('misc.dqp_na_prieme'), color: 'info', icon: Activity },
    served: { label: t('misc.dqp_prinyat'), color: 'success', icon: CheckCircle }
  };

  // Источники записи
  const sourceConfig = {
    // UX Audit Doctor M-23: emoji → text labels (lucide icons need import refactor).
    online: { label: t('misc.dqp_onlayn'), icon: '📱' },
    desk: { label: t('misc.dqp_registratura'), icon: '🏥' },
    telegram: { label: 'Telegram', icon: '💬' }
  };

  useEffect(() => {
    // Проверяем, не находимся ли мы в демо-режиме (dev-моки localhost:5173;
    // medilab-demo дизъюнкт удалён в PR-UI-17-1 вместе с роутом)
    const isDemoMode =
    window.location.hostname === 'localhost' &&
    window.location.port === '5173';

    logger.log('DoctorQueuePanel useEffect:', {
      pathname: window.location.pathname,
      isDemoMode,
      specialty
    });

    if (isDemoMode) {
      // В демо-режиме используем моковые данные
      logger.log('Setting demo data for DoctorQueuePanel');
      setDoctorInfo({
        id: 1,
        name: 'Dr. Demo',
        specialty: specialty,
        department: 'Demo Department',
        queue_settings: {
          start_number: 'A000',
          max_per_day: 50,
          timezone: 'UTC+5'
        },
        doctor: {
          cabinet: '101'
        }
      });

      setQueueData({
        queue_exists: true,
        stats: { total: 2, waiting: 2, served: 0, online_entries: 1 },
        doctor: { name: 'Dr. Demo', specialty, cabinet: '101' },
        entries: [
        {
          id: 1,
          number: 'A001',
          patient_name: t('misc.dqp_ivan_ivanov'),
          status: 'waiting',
          available_actions: ['call', 'no_show'],
          can_call: true,
          can_start_visit: false,
          can_complete: false,
          source: 'online',
          phone: '+998 90 123-45-67',
          created_at: '2024-01-15T09:00:00Z'
        },
        {
          id: 2,
          number: 'A002',
          patient_name: t('misc.dqp_mariya_petrova'),
          status: 'waiting',
          available_actions: ['call', 'no_show'],
          can_call: true,
          can_start_visit: false,
          can_complete: false,
          source: 'desk',
          phone: '+998 90 765-43-21',
          created_at: '2024-01-15T09:15:00Z'
        }]

      });
    } else {
      logger.log('Loading real data for DoctorQueuePanel');
      // DOCQ-FE-001: a real specialty change claims a new request identity —
      // bump the epoch and drop the previous specialty's whole queue
      // context, so A's late responses and stale rows can never leak into
      // B's panel. Same-specialty re-runs (StrictMode/interval) bump the
      // epoch too but keep the loaded context.
      const previousSpecialty = specialtyRef.current;
      specialtyRef.current = specialty;
      queueEpochRef.current += 1;
      if (previousSpecialty !== null && previousSpecialty !== specialty) {
        queueDataRef.current = null;
        setQueueData(null);
        setMessage({ type: '', text: '' });
        setLoadError(null);
        setQueueStale(false);
      }
      loadDoctorData();
      loadQueueDataRef.current();

      // Обновляем каждые 30 секунд
      const interval = setInterval(() => {
        loadQueueDataRef.current();
      }, 30000);

      return () => clearInterval(interval);
    }
  }, [specialty]);

  const loadDoctorData = async () => {
    // Проверяем демо-режим (dev-моки localhost:5173)
    const isDemoMode =
    window.location.hostname === 'localhost' &&
    window.location.port === '5173';

    if (isDemoMode) {
      logger.log('Skipping loadDoctorData in demo mode');
      return;
    }

    // DOCQ-FE-002 (audit 3886): all doctor-queue reads and commands route
    // through the canonical api client — the shared axios instance owns the
    // expired-JWT single-flight refresh + 401 retry, CSRF and rate-limit
    // handling that a raw fetch bypassed.
    try {
      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Loading doctor info via the canonical api client');
      const { data } = await api.get('/doctor/my-info');
      setDoctorInfo(data);
    } catch (error) {
      logger.error('Ошибка загрузки информации врача:', error);
    }
  };

  const loadQueueData = async () => {
    // Проверяем демо-режим (dev-моки localhost:5173)
    const isDemoMode =
    window.location.hostname === 'localhost' &&
    window.location.port === '5173';

    if (isDemoMode) {
      logger.log('Skipping loadQueueData in demo mode');
      return;
    }

    // DOCQ-FE-001: bind this request to its epoch+specialty — a late
    // response for a superseded specialty self-cancels (success, error and
    // finally branches alike).
    const epoch = queueEpochRef.current;
    const requestSpecialty = specialty;

    try {
      setLoading(true);

      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Loading doctor queue via the canonical api client', {
        specialty,
      });
      const { data } = await api.get(`/doctor/${specialty}/queue/today`);

      if (epoch !== queueEpochRef.current || requestSpecialty !== specialtyRef.current) {
        // DOCQ-FE-001: superseded by a specialty switch — drop the stale
        // response instead of painting another specialty's patients.
        return;
      }

      queueDataRef.current = data;
      setQueueData(data);
      setLoadError(null);
      setQueueStale(false);
    } catch (error) {
      // DOCQ-FE-001: a late network failure of a superseded specialty must
      // not paint an error over the current one.
      if (epoch !== queueEpochRef.current || requestSpecialty !== specialtyRef.current) {
        return;
      }
      // DOCQ-FE-003: parse the error body safely (it may be non-JSON) and
      // record a DISTINCT load-error state; a failed refresh after a
      // successful load flags the visible rows as possibly stale instead
      // of silently keeping them as if they were fresh. Non-2xx responses
      // reject through the canonical client with the parsed body on
      // error.response.data (401s get one refresh+retry inside the client
      // before ever surfacing here).
      const detail = extractApiErrorDetail(error);
      logger.error('Ошибка загрузки очереди:', error);
      const hadPreviousData = queueDataRef.current !== null;
      setLoadError(detail || t('misc.dqp_oshibka_zagruzki_ocheredi'));
      if (hadPreviousData) {
        // DOCQ-FE-003: the stale warning Alert below the loaded rows is
        // the single surface for a failed refresh — no duplicate message.
        setQueueStale(true);
      } else {
        setMessage({ type: 'error', text: detail || t('misc.dqp_oshibka_zagruzki_ocheredi') });
      }
    } finally {
      if (epoch === queueEpochRef.current) {
        setLoading(false);
      }
    }
  };
  loadQueueDataRef.current = loadQueueData;

  const handleCallPatient = async (entryId: number | string) => {
    // В демо-режиме имитируем вызов
    if (isDemoMode) {
      setMessage({ type: 'success', text: t('misc.dqp_patsient_vyzvan_demo') });
      setQueueData((prev) => prev ? ({
        ...prev,
        entries: (prev.entries ?? []).map((e) => e.id === entryId ? { ...e, status: 'called', called_at: new Date().toISOString() } : e)
      }) : prev);
      return;
    }

    try {
      // DOCQ-FE-002: canonical client transport (refresh/retry/CSRF).
      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Calling patient via the canonical api client', {
        entryId,
      });
      const { data } = await api.post(`/doctor/queue/${entryId}/call`) as { data: unknown };
      // DOCQ-FE-004: only an explicit `success: true` ack confirms the call.
      const ack = queueCommandAck(data);
      if (ack.success !== true) {
        logger.error('[FIX:DOCTOR_QUEUE_PANEL] Call NOT confirmed by an explicit success ack', {
          entryId,
          unknown: ack.unknown === true,
        });
        setMessage({ type: 'error', text: ack.message });
        await loadQueueData();
        return;
      }
      setMessage({ type: 'success', text: ack.message });
      await loadQueueData();
    } catch (error: unknown) {
      logger.error('Ошибка вызова пациента:', error);
      setMessage({ type: 'error', text: extractApiErrorDetail(error) || (error instanceof Error ? error.message : String(error)) });
    }
  };

  const handleStartVisit = async (entryId: number | string) => {
    // В демо-режиме имитируем старт приема
    if (isDemoMode) {
      setMessage({ type: 'success', text: t('misc.dqp_priem_nachat_demo') });
      setQueueData((prev) => prev ? ({
        ...prev,
        entries: (prev.entries ?? []).map((e) => e.id === entryId ? { ...e, status: 'in_progress' } : e)
      }) : prev);
      return;
    }

    try {
      // DOCQ-FE-002: canonical client transport (refresh/retry/CSRF).
      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Starting visit via the canonical api client', {
        entryId,
      });
      const { data } = await api.post(`/doctor/queue/${entryId}/start-visit`) as { data: unknown };
      // DOCQ-FE-004: only an explicit `success: true` ack confirms the start.
      const ack = queueCommandAck(data);
      if (ack.success !== true) {
        logger.error('[FIX:DOCTOR_QUEUE_PANEL] Start visit NOT confirmed by an explicit success ack', {
          entryId,
          unknown: ack.unknown === true,
        });
        setMessage({ type: 'error', text: ack.message });
        await loadQueueData();
        return;
      }
      setMessage({ type: 'success', text: ack.message });
      await loadQueueData();
    } catch (error: unknown) {
      logger.error('Ошибка начала приема:', error);
      setMessage({ type: 'error', text: extractApiErrorDetail(error) || (error instanceof Error ? error.message : String(error)) });
    }
  };

  const handleCompleteVisit = async (entryId: number | string) => {
    // В демо-режиме имитируем завершение приема
    if (isDemoMode) {
      setMessage({ type: 'success', text: t('misc.dqp_priem_zavershen_demo') });
      setQueueData((prev) => prev ? ({
        ...prev,
        entries: (prev.entries ?? []).map((e) => e.id === entryId ? { ...e, status: 'served' } : e),
        stats: { ...prev.stats, served: (prev.stats?.served || 0) + 1, waiting: Math.max(0, (prev.stats?.waiting || 1) - 1) }
      }) : prev);
      return;
    }

    try {
      // DOCQ-FE-002: canonical client transport (refresh/retry/CSRF).
      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Completing visit via the canonical api client', {
        entryId,
      });
      const { data } = await api.post(`/doctor/queue/${entryId}/complete`, {
        // Здесь будут данные визита
      }) as { data: unknown };
      // DOCQ-FE-004: a clinical visit completion is reported ONLY on an
      // explicit `success: true` ack — any resolved 2xx without the ack is
      // an ambiguous or rejected write, never «Успешно».
      const ack = queueCommandAck(data);
      if (ack.success !== true) {
        logger.error('[FIX:DOCTOR_QUEUE_PANEL] Completion NOT confirmed by an explicit success ack', {
          entryId,
          unknown: ack.unknown === true,
        });
        setMessage({ type: 'error', text: ack.message });
        await loadQueueData();
        return;
      }
      setMessage({ type: 'success', text: ack.message });
      await loadQueueData();
    } catch (error: unknown) {
      logger.error('Ошибка завершения приема:', error);
      setMessage({ type: 'error', text: extractApiErrorDetail(error) || (error instanceof Error ? error.message : String(error)) });
    }
  };

  if (loading && !queueData) {
    return (
      <Card style={{ padding: 'var(--mac-spacing-6)' }}>
        <Skeleton type="card" count={3} />
      </Card>);

  }

  // DOCQ-FE-003 (audit 3886): a FAILED load is an error state with an
  // explicit retry — never the misleading «Очередь не создана» empty state
  // (that state stays reserved for a successful canonical response with
  // queue_exists=false).
  if (!queueData && loadError) {
    return (
      // DOCQ-FE-003: tailwind utilities instead of inline styles (ui-baseline
      // ratchet: inlineStyles/varUsagesNoFallback may only improve).
      <Card className="flex flex-col gap-4 p-6">
        <Alert
          type="error"
          title={t('misc.dqp_ochered_nedostupna')}
          description={loadError}
        />
        <div>
          <Button type="button" variant="primary" onClick={() => loadQueueDataRef.current()}>
            {t('misc.dqp_povtorit')}
          </Button>
        </div>
      </Card>
    );
  }

  if (!queueData || !queueData.queue_exists) {
    return (
      <AppEmpty
        title={t('misc.dqp_ochered_ne_sozdana')}
        description={t('misc.dqp_ochered_budet_sozdana_kogda_')} />);


  }

  const queueDoctor = queueData.doctor ?? {};
  const queueStats = queueData.stats ?? {};
  const queueEntries = queueData.entries ?? [];

  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
      {/* DOCQ-FE-003 (audit 3886): a failed refresh keeps the previous rows
       * ONLY under an explicit stale warning — the panel never pretends
       * the visible queue is fresh after a failed reload. */}
      {queueStale &&
      <Alert
        type="error"
        title={t('misc.dqp_dannye_mogli_ustaret')}
        description={t('misc.dqp_oshibka_zagruzki_ocheredi')} />}

      {/* Сообщения */}
      {message.text &&
      <Alert
        type={message.type === 'success' ? 'success' : 'error'}
        title={message.type === 'success' ? t('misc.dqp_uspeshno') : t('misc.dqp_oshibka')}
        description={message.text}
        onClose={() => setMessage({ type: '', text: '' })} />

      }

      {/* Информация о враче и очереди */}
      <Card style={{ padding: 'var(--mac-spacing-4)' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 'var(--mac-spacing-4)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <User size={24} style={{ marginRight: 'var(--mac-spacing-3)', color: 'var(--mac-accent)' }} />
            <div>
              <h3 style={{
                margin: 0,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                {queueDoctor.name}
              </h3>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)',
                gap: 'var(--mac-spacing-4)',
                marginTop: 'var(--mac-spacing-1)'
              }}>
                <span>{queueDoctor.specialty}</span>
                {queueDoctor.cabinet &&
                <>
                    <MapPin size={14} />
                    <span>Каб. {queueDoctor.cabinet}</span>
                  </>
                }
              </div>
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              Статус очереди:
            </div>
            <Badge variant={queueData.opened_at ? 'success' : 'warning'}>
              {queueData.opened_at ? t('misc.dqp_otkryta') : t('misc.dqp_ne_otkryta')}
            </Badge>
          </div>
        </div>

        {/* Статистика очереди */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: 'var(--mac-spacing-4)'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-accent)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              {queueStats.total}
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Всего
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-warning)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              {queueStats.waiting}
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Ожидают
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-success)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              {queueStats.served}
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Приняты
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-accent)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              {queueStats.online_entries}
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Онлайн
            </div>
          </div>
        </div>
      </Card>

      {/* Список пациентов в очереди */}
      <Card style={{ overflow: 'hidden' }}>
        <div style={{
          padding: 'var(--mac-spacing-4)',
          backgroundColor: 'var(--mac-bg-secondary)',
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <h3 style={{
              margin: 0,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Пациенты в очереди
            </h3>
            <Button variant="outline" onClick={loadQueueData}>
              <RefreshCw size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
              Обновить
            </Button>
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--mac-border)' }}>
          {queueEntries.length === 0 ?
          <AppEmpty
            title={t('misc.dqp_patsientov_v_ocheredi_net')}
            description={t('misc.dqp_ozhidayte_postupleniya_novyh')} /> :


          queueEntries.map((entry) => {
            const status = statusConfig[entry.status as keyof typeof statusConfig] || statusConfig.waiting;
            const source = sourceConfig[entry.source as keyof typeof sourceConfig] || sourceConfig.desk;
            const StatusIcon = status.icon;
            const canCall = hasBackendQueueAction(entry, 'call', 'can_call');
            const canStartVisit = hasBackendQueueAction(entry, 'start_visit', 'can_start_visit');
            const canComplete = hasBackendQueueAction(entry, 'complete', 'can_complete');
            const timeDisplay = getRegistrarTimestampDisplay(entry);

            return (
              <div
                key={entry.id}
                role="button"
                tabIndex={0}
                aria-label={t('misc.dqp_vybrat_patsienta_entry_patie', { number: entry.patient_name || entry.number })}
                style={{
                  padding: 'var(--mac-spacing-4)',
                  cursor: 'pointer',
                  transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                  backgroundColor: selectedPatient?.id === entry.id ? 'var(--mac-bg-accent)' : 'transparent',
                  borderBottom: '1px solid var(--mac-border)'
                }}
                onClick={() => {
                  setSelectedPatient(entry);
                  if (onPatientSelect) onPatientSelect(entry);
                }}
                onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setSelectedPatient(entry);
                    if (onPatientSelect) onPatientSelect(entry);
                  }
                }}>
                
                  <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-4)' }}>
                      {/* Номер в очереди */}
                      <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '48px',
                      height: '48px',
                      backgroundColor: 'var(--mac-bg-accent)',
                      borderRadius: '50%',
                      border: '2px solid var(--mac-accent)'
                    }}>
                        <span style={{
                        fontSize: 'var(--mac-font-size-lg)',
                        fontWeight: 'var(--mac-font-weight-bold)',
                        color: 'var(--mac-accent)'
                      }}>
                          {entry.number}
                        </span>
                      </div>

                      {/* Информация о пациенте */}
                      <div>
                        <div style={{
                        fontWeight: 'var(--mac-font-weight-semibold)',
                        color: 'var(--mac-text-primary)',
                        fontSize: 'var(--mac-font-size-md)',
                        marginBottom: 'var(--mac-spacing-1)'
                      }}>
                          {entry.patient_name}
                        </div>
                        {entry.phone &&
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: 'var(--mac-font-size-sm)',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: 'var(--mac-spacing-1)'
                      }}>
                            <Phone size={16} style={{ marginRight: 'var(--mac-spacing-1)', color: 'var(--mac-accent)' }} />
                            {entry.phone}
                          </div>
                      }
                        <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)'
                      }}>
                          <Badge variant="outline">
                            {source.icon} {source.label}
                          </Badge>
                          <span style={{
                          fontSize: 'var(--mac-font-size-xs)',
                          color: 'var(--mac-text-tertiary)'
                        }}>
                            {timeDisplay.primaryLabel}: {timeDisplay.primaryTime || '—'}
                            {timeDisplay.showChanged ? ` · ${timeDisplay.changedLabel}: ${timeDisplay.changedTime}` : ''}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-3)'
                  }}>
                      {/* Статус */}
                      <div style={{ textAlign: 'center' }}>
                        <Badge variant={status.color}>
                          <StatusIcon size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
                          {status.label}
                        </Badge>
                        {entry.called_at &&
                      <div style={{
                        fontSize: 'var(--mac-font-size-xs)',
                        color: 'var(--mac-text-tertiary)',
                        marginTop: 'var(--mac-spacing-1)'
                      }}>
                            Вызван: {formatRegistrarTime(entry.called_at) || '—'}
                          </div>
                      }
                      </div>

                      {/* Действия */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
                        {canCall &&
                      <Button
                        onClick={(e: React.MouseEvent<HTMLElement>) => {
                          e.stopPropagation();
                          handleCallPatient(entry.id);
                        }}>
                        
                            <Play size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
                            Вызвать
                          </Button>
                      }

                        {canStartVisit &&
                      <Button
                        variant="outline"
                        onClick={(e: React.MouseEvent<HTMLElement>) => {
                          e.stopPropagation();
                          handleStartVisit(entry.id);
                        }}>
                        
                            <Activity size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
                            Начать
                          </Button>
                      }

                        {canComplete &&
                      <Button
                        variant="secondary"
                        color="success"
                        onClick={(e: React.MouseEvent<HTMLElement>) => {
                          e.stopPropagation();
                          handleCompleteVisit(entry.id);
                        }}>
                        
                            <CheckCircle size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
                            Завершить
                          </Button>
                      }
                      </div>
                    </div>
                  </div>
                </div>);

          })
          }
        </div>
      </Card>

      {/* Информация о настройках очереди */}
      {doctorInfo &&
      <Card style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-bg-accent)',
        border: '1px solid var(--mac-accent)'
      }}>
          <h4 style={{
          margin: '0 0 8px 0',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-accent)',
          fontSize: 'var(--mac-font-size-md)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            ⚙️ Настройки очереди:
          </h4>
          <div style={{
          fontSize: 'var(--mac-font-size-sm)',
          color: 'var(--mac-text-secondary)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-1)'
        }}>
            <div>Стартовый номер онлайн: #{doctorInfo?.queue_settings?.start_number || '—'}</div>
            <div>Лимит в день: {doctorInfo?.queue_settings?.max_per_day ?? '—'}</div>
            <div>Часовой пояс: {doctorInfo?.queue_settings?.timezone || '—'}</div>
            {doctorInfo?.doctor?.cabinet &&
          <div>Кабинет: {doctorInfo.doctor.cabinet}</div>
          }
          </div>
        </Card>
      }
    </div>);

};


export default DoctorQueuePanel;
