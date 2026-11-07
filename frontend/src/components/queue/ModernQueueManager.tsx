import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { CSSProperties } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import ModernDialog from '../dialogs/ModernDialog';
import { toast } from 'react-toastify';
// UX Audit Registrar #2: useConfirm hook для замены window.confirm().
import { useConfirm } from '../common/ConfirmDialog';
// UX Audit Stage 3 (Queue issue 7.3):
// Заменены SF Symbols (Icon) на lucide-react — единая библиотека иконок.
// Раньше Queue был единственным экраном, использующим SF Symbols.
import {
  QrCode, Building2, CheckCircle, Settings, Bell, User, Clock, ArrowDownCircle, RefreshCw, X,
} from 'lucide-react';
import {
  Button, CardContent, Badge, Select,
  Input } from '../ui/macos';
import { getLocalDateString } from '../../utils/dateUtils';
import { useQueueManager } from '../../hooks/useQueueManager';
import type { QueueActionResponse } from '../../types/domain/queue';
// UX Audit Stage 3 (Queue issue 7.1):
// WebSocket подписка для мгновенных обновлений очереди вместо 30s polling.
import { useQueueWebSocket } from '../../hooks/useQueueWebSocket';
import QueueTable, { type QueueTableData } from './QueueTable';
// RQ-11: честный показ срока действия QR (F-10) — классификация expires_at
// из серверного ответа и подписи для скачиваемого PNG (pure-хелпер).
import { buildQrDownloadCaptions, resolveQrExpiryView } from './qrExpiry';
import logger from '../../utils/logger';
import { getErrorMessage } from '../../utils/type-guards';
import './ModernQueueManager.css';

// === Domain types ===
// ModernQueueManager is a registrar/queue-management surface.
// The parent owns the date + doctor selection; ModernQueueManager
// receives them as controlled props and emits change events.
// Doctors shape is dynamic (backend-driven), so it rides via index sig.

export interface ModernQueueManagerDoctor {
  id: string | number;
  full_name?: string;
  name?: string;
  specialty?: string;
  specialty_display?: string;
  department?: string;
  cabinet?: string | number;
  [key: string]: unknown;
}

export interface ModernQueueManagerProps {
  /** The caller's workflow controls which queue-management actions are visible. */
  mode: 'doctor' | 'registrar';
  /** Currently selected date (YYYY-MM-DD). */
  selectedDate?: string;
  /** Currently selected doctor id. */
  selectedDoctor?: string | number;
  /** Called when the queue snapshot needs to be reloaded. */
  onQueueUpdate?: () => void | Promise<void>;
  /** Called after a doctor explicitly starts a patient returned by call-next. */
  onStartVisit?: (patient: NonNullable<QueueActionResponse['patient']>) => boolean | void | Promise<boolean | void>;
  /** Active UI language. */
  language?: string;
  /** Doctor lookup array (passed from parent). */
  doctors?: ModernQueueManagerDoctor[];
  /** Called when the user changes the doctor selection. */
  onDoctorChange?: (doctorId: string) => void;
  /** Called when the user changes the date. */
  onDateChange?: (date: string) => void;
  /** Optional UI theme override. */
  theme?: string;
  /** Optional search query (observed in QueueView caller). */
  searchQuery?: string;
  [key: string]: unknown;
}

// PR-3856 review follow-up: stable default for the optional `doctors` prop.
// A fresh `[]` literal per render changed the prop identity, which flowed
// into the loadQueue useCallback deps and re-triggered the snapshot-load
// effect on every render for consumers that omit the prop.
const EMPTY_DOCTORS: ModernQueueManagerDoctor[] = [];

const ModernQueueManager = ({
  mode,
  selectedDate = getLocalDateString(),
  // PR-3856 review follow-up: NO default for selectedDoctor — `undefined` now
  // strictly means "uncontrolled mode" (internal UI state drives the
  // selection), while any passed value (INCLUDING the empty string) means
  // "controlled mode" where the prop is authoritative.
  selectedDoctor,
  onQueueUpdate,
  onStartVisit,
  language = 'ru',
  // PR-3856 review follow-up: a stable module-level default — a fresh `[]`
  // per render changed the `doctors` identity, which (through the
  // loadQueue → effect chain) could re-trigger snapshot loads on every
  // render for consumers that omit the prop.
  doctors = EMPTY_DOCTORS,
  onDoctorChange,
  onDateChange
}: ModernQueueManagerProps) => {
  const isRegistrarMode = mode === 'registrar';
  const {
    loading,
    queueData,
    statistics,
    qrData,
    specialists,
    loadQueueSnapshot,
    generateDoctorQRCode,
    generateClinicQRCode,
    openReceptionForDoctor,
    closeReceptionForDoctor,
    callNextPatientInQueue

  } = useQueueManager();

  const [internalDoctor, setInternalDoctor] = useState('');
  const [internalDate, setInternalDate] = useState(getLocalDateString());
  // PR-3856 review follow-up (controlled vs uncontrolled): when the parent
  // passes `selectedDoctor`, the prop is authoritative INCLUDING the empty
  // string — a parent-driven reset (7 → '') must clear the selection
  // instead of falling back to the last internal UI choice. `undefined`
  // (prop not passed) keeps the uncontrolled internal-state mode.
  const effectiveDoctor = selectedDoctor !== undefined ? String(selectedDoctor) : internalDoctor;
  const effectiveDate = selectedDate !== undefined && selectedDate !== '' ? selectedDate : internalDate;
  const [showQrDialog, setShowQrDialog] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [calledPatients, setCalledPatients] = useState<NonNullable<QueueActionResponse['patient']>[]>([]);
  const [startingQueueEntryId, setStartingQueueEntryId] = useState<string | number | null>(null);
  // QMAN-FE-001 (audit 3886): a failed load of the CURRENT selection must be
  // visible and recoverable — the previous selection's queue is no longer
  // presented as current (the hook clears it fail-closed).
  const [queueLoadError, setQueueLoadError] = useState<string | null>(null);
  // QMAN-FE-002 (audit 3886): the live doctor/date selection must be
  // reachable from a ref so a pending call-next response for a superseded
  // selection can be dropped before it appends to the new selection's
  // called list.
  const selectionIdentityRef = useRef({ specialistId: effectiveDoctor, targetDate: effectiveDate });
  selectionIdentityRef.current = { specialistId: effectiveDoctor, targetDate: effectiveDate };

  // QMAN-FE-002 (audit 3886): called entries belong to ONE doctor/date
  // selection. A selection transition invalidates the local called list —
  // entries called under the previous selection must not expose Start
  // Visit actions under the new one (backend authorization stays the
  // SSOT; this only stops presenting stale local state as actionable).
  useEffect(() => {
    setCalledPatients([]);
  }, [effectiveDoctor, effectiveDate]);

  // RQ-11 (F-10): классификация срока из серверного expires_at (valid/expired/
  // unspecified). Пересчитывается при открытии диалога, чтобы истекший код
  // показывался честно, а не как «действует до: —».
  // QR-FE-004 (follow-up audit 2026-11-02): пересчёт больше НЕ заморожен
  // мемо-зависимостями — диалог, открытый ЗА минуту до истечения, доживает
  // тик до самого горизонта и честно перекрашивается в «истек» (и подпись
  // скачиваемого постера тоже). Ограниченный таймер до expires_at, без
  // интервальной нагрузки.
  const [qrExpiryNow, setQrExpiryNow] = useState(() => Date.now());
  useEffect(() => {
    if (!showQrDialog || !qrData?.expires_at) return;
    const horizon = Date.parse(qrData.expires_at);
    if (Number.isNaN(horizon)) return;
    const delay = horizon - Date.now();
    if (delay <= 0) {
      setQrExpiryNow(Date.now());
      return;
    }
    const timer = setTimeout(() => setQrExpiryNow(Date.now()), delay + 100);
    return () => clearTimeout(timer);
  }, [showQrDialog, qrData?.expires_at]);
  const qrExpiryView = useMemo(
    () => resolveQrExpiryView(qrData?.expires_at, showQrDialog ? new Date(qrExpiryNow) : undefined),
    [qrData?.expires_at, showQrDialog, qrExpiryNow]
  );

  // UX Audit Registrar #2: useConfirm hook для замены window.confirm().
  // Возвращает [confirm, dialog]; dialog должен быть отрендерен в JSX.
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;

  // i18next translation function.
  const { t: rawT } = useTranslation();
  const t = rawT;

  // Compatibility object passed to <QueueTable t={...} /> — QueueTable still
  // expects an object with named keys (selectDoctor, patient, phone, etc.),
  // so we wrap the i18next t() calls into that shape here.
  const queueTableT = useMemo(() => ({
    selectDoctor: t('misc.mqm_select_doctor'),
    patient: t('misc.mqm_patient'),
    phone: t('misc.mqm_phone'),
    time: t('misc.mqm_time'),
    status: t('misc.mqm_status'),
    actions: t('misc.mqm_actions'),
    called: t('misc.mqm_called'),
    queueEmpty: t('misc.mqm_queue_empty'),
    queueNotFound: t('misc.mqm_queue_not_found'),
  }), [t]);

  // Загрузка данных очереди
  const loadQueue = useCallback(async () => {
    // REG-FE-068: пустой выбор — валидный переход жизненного цикла: хук
    // очистит снапшот и сместит эпоху (запоздалый ответ предыдущего врача
    // не сможет воскресить его очередь). Раньше здесь был ранний return —
    // очередь отменённого врача оставалась на экране.
    const doctor = doctors.find(
      (candidate) => String(candidate.id) === String(effectiveDoctor)
    );

    try {
      await loadQueueSnapshot({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate,
        doctor
      });
      setQueueLoadError(null);
    } catch (error) {
      // QMAN-FE-001 (audit 3886): a failed load of the CURRENT selection is
      // surfaced as a recoverable error with a retry — the hook has already
      // cleared the previous selection's data, so nothing stale is
      // presented as current. (No toast: the polling fallback would spam.)
      logger.error('Ошибка загрузки очереди:', error);
      // Localized headline always; the raw failure detail rides along in
      // parentheses so the doctor sees both the meaning and the cause.
      const loadFailureDetail = getErrorMessage(error);
      setQueueLoadError(
        loadFailureDetail
          ? `${t('misc.mqm_queue_load_failed')} (${loadFailureDetail})`
          : t('misc.mqm_queue_load_failed')
      );
    }
    // `t` is intentionally NOT a dependency: useTranslation returns a fresh
    // function identity on every render, and adding it here would re-create
    // `loadQueue` on every render and re-trigger the auto-load effect in an
    // endless snapshot loop (surfaced by the PR-UI-12-4 e2e geometry check).
    // The translation is locale-pure for a fixed key — a stale closure only
    // means the previous locale's text for one error message.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveDoctor, effectiveDate, doctors, loadQueueSnapshot]);

  // Автоматическая загрузка при изменении врача или даты
  useEffect(() => {
    loadQueue();
  }, [effectiveDoctor, effectiveDate, loadQueue]);

  // Polling для автообновления (fallback для WebSocket)
  // UX Audit Stage 3 (Queue issue 7.1):
  // Polling увеличен с 30s до 60s — теперь это fallback для WebSocket.
  // WebSocket (useQueueWebSocket ниже) даёт мгновенные обновления.
  // Если WS упал, polling 60s всё ещё обновляет очередь.
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    if (autoRefresh && effectiveDoctor && effectiveDate) {
      interval = setInterval(() => {
        loadQueue();
      }, 60000); // 60 секунд (было 30)
    }
    return () => clearInterval(interval);
  }, [autoRefresh, effectiveDoctor, effectiveDate, loadQueue]);

  // UX Audit Stage 3 (Queue issue 7.1):
  // WebSocket подписка для мгновенных обновлений.
  // При получении queue_update события — перезагружаем snapshot очереди.
  // Polling выше остаётся как fallback (60s).
  const { isConnected: wsConnected, connectionState: wsState } = useQueueWebSocket({
    specialistId: String(effectiveDoctor ?? ''),
    date: effectiveDate,
    enabled: Boolean(effectiveDoctor && effectiveDate),
    onUpdate: loadQueue,
  });

  // Слушатель событий от QueueJoin для мгновенного обновления
  useEffect(() => {
    const handleQueueUpdate = (event: Event) => {
      const detail = (event as CustomEvent).detail as { action?: string } | undefined;
      logger.log('[ModernQueueManager] Получено событие queueUpdated:', detail);
      // Обновляем очередь при любом событии добавления
      if (detail?.action === 'refreshAll' || detail?.action === 'entryAdded') {
        loadQueue();
      }
    };

    window.addEventListener('queueUpdated', handleQueueUpdate);
    return () => window.removeEventListener('queueUpdated', handleQueueUpdate);
  }, [loadQueue]);

  // Генерация QR кода для одного специалиста
  const generateQR = async () => {
    if (!effectiveDoctor || !effectiveDate) {
      toast.error(t('misc.mqm_select_doctor_and_date'));
      return;
    }

    const doctor = doctors.find(
      (item) => String(item.id) === String(effectiveDoctor)
    );

    try {
      await generateDoctorQRCode({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate,
        department: doctor?.department || doctor?.specialty || 'general',
        specialistName: doctor?.full_name || doctor?.name
      });
      setShowQrDialog(true);
      toast.success(t('misc.mqm_qr_generated'));
    } catch (error) {
      toast.error(getErrorMessage(error) || t('misc.mqm_qr_gen_error'));
    }
  };

  // Генерация общего QR кода клиники
  const generateClinicQR = async () => {
    if (!effectiveDate) {
      toast.error(t('misc.mqm_select_date'));
      return;
    }

    try {
      await generateClinicQRCode({ targetDate: effectiveDate });
      setShowQrDialog(true);
      toast.success(t('misc.mqm_clinic_qr_generated'));
    } catch (error) {
      toast.error(getErrorMessage(error) || t('misc.mqm_clinic_qr_gen_error'));
    }
  };

  // Открытие приема
  // UX Audit Registrar #6: добавлен confirmation dialog.
  // «Открыть приём» — необратимое действие: закрывает онлайн-запись.
  // Раньше выполнялось без подтверждения.
  const openReception = async () => {
    if (!effectiveDoctor) {
      toast.error(t('misc.mqm_select_doctor_only'));
      return;
    }

    if (queueData?.is_open) {
      toast.info(t('misc.mqm_reception_already_open'));
      return;
    }

    // Confirmation: открытие приёма закрывает онлайн-запись для новых пациентов.
    // UX Audit Registrar #2: window.confirm() → useConfirm hook.
    const doctorName = doctors.find((d) => String(d.id) === String(effectiveDoctor))?.full_name || t('misc.mqm_selected_doctor_default');
    const confirmed = await confirm({
      title: t('misc.mqm_confirm_open_title'),
      message: t('misc.mqm_confirm_open_message', { doctorName }),
      description: t('misc.mqm_confirm_open_desc'),
      confirmLabel: t('misc.mqm_confirm_open_label'),
      cancelLabel: t('misc.cancel'),
      intent: 'warning',
    });
    if (!confirmed) {
      return;
    }

    try {
      const result = await openReceptionForDoctor({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate
      });

      toast.success(result?.message || t('misc.mqm_reception_opened'));
      await loadQueue();

      if (onQueueUpdate) {
        onQueueUpdate();
      }
    } catch (error) {
      toast.error(getErrorMessage(error) || t('misc.mqm_reception_open_error'));
    }
  };

  // UX Audit Registrar #7: Закрытие приёма (открывает онлайн-запись обратно).
  const closeReception = async () => {
    if (!effectiveDoctor) {
      toast.error(t('misc.mqm_select_doctor_only'));
      return;
    }

    if (!queueData?.is_open) {
      toast.info(t('misc.mqm_reception_already_closed'));
      return;
    }

    // UX Audit Registrar #2: window.confirm() → useConfirm hook.
    const confirmed = await confirm({
      title: t('misc.mqm_confirm_close_title'),
      message: t('misc.mqm_confirm_close_message'),
      description: t('misc.mqm_confirm_close_desc'),
      confirmLabel: t('misc.mqm_confirm_close_label'),
      cancelLabel: t('misc.cancel'),
      intent: 'primary',
    });
    if (!confirmed) {
      return;
    }

    try {
      const result = await closeReceptionForDoctor({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate
      });

      toast.success(result?.message || t('misc.mqm_reception_closed'));
      await loadQueue();

      if (onQueueUpdate) {
        onQueueUpdate();
      }
    } catch (error) {
      toast.error(getErrorMessage(error) || t('misc.mqm_reception_close_error'));
    }
  };

  // Вызов пациента
  const callPatient = async () => {
    if (!effectiveDoctor) {
      toast.error(t('misc.mqm_select_doctor_only'));
      return;
    }

    // QMAN-FE-002 (audit 3886): snapshot the selection identity this call
    // belongs to; a response that resolves after the selection moved to
    // another doctor/date must not append to the new selection's list.
    const callIdentity = { specialistId: effectiveDoctor, targetDate: effectiveDate };

    try {
      const result = await callNextPatientInQueue({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate
      });

      const selectionMoved =
        String(selectionIdentityRef.current.specialistId) !== String(callIdentity.specialistId) ||
        String(selectionIdentityRef.current.targetDate) !== String(callIdentity.targetDate);

      if (result?.success && result?.patient) {
        if (onStartVisit && result.patient.id !== null && result.patient.id !== undefined) {
          if (selectionMoved) {
            // The call succeeded for the PREVIOUS selection — report it but
            // never expose its Start Visit action under the new selection.
            logger.warn('[ModernQueueManager] call-next resolved for a superseded selection — dropping the local called entry');
          } else {
            setCalledPatients((current) => current.some((patient) => String(patient.id) === String(result.patient?.id))
              ? current
              : [...current, result.patient!]);
          }
        } else if (onStartVisit) {
          toast.error(t('dental.dental_panel_start_visit_failed'));
        }
        toast.success(
          t('misc.mqm_patient_called', { name: result.patient.name, number: result.patient.number })
        );
      } else {
        toast.info(result?.message || t('misc.mqm_no_patients'));
      }

      await loadQueue();
    } catch (error) {
      toast.error(getErrorMessage(error) || t('misc.mqm_call_patient_error'));
    }
  };

  const startCalledPatientVisit = async (patient: NonNullable<QueueActionResponse['patient']>) => {
    if (!onStartVisit || patient.id === null || patient.id === undefined) return;

    setStartingQueueEntryId(patient.id);
    try {
      const started = await onStartVisit(patient);
      if (started !== false) {
        setCalledPatients((current) => current.filter((candidate) => String(candidate.id) !== String(patient.id)));
      }
    } catch {
      toast.error(t('dental.dental_panel_start_visit_failed'));
    } finally {
      setStartingQueueEntryId(null);
    }
  };

  // RQ-11 (F-10): скачанный PNG честно сообщает срок действия токена —
  // подписи «действует до / истек» + пометка «временный код» рисуются на
  // изображении, чтобы плакат не обещал бессрочный доступ. Серверный TTL и
  // single-use защиты не меняются.
  const downloadQR = () => {
    if (!qrData) {
      toast.error(t('misc.mqm_qr_unavailable'));
      return;
    }

    if (!qrData.qr_code_base64) {
      toast.error(t('misc.mqm_qr_image_unavailable'));
      return;
    }

    const captions = buildQrDownloadCaptions({
      state: qrExpiryView.state,
      formattedExpiresAt: qrExpiryView.formattedExpiresAt,
      labels: {
        validUntil: qrExpiryView.formattedExpiresAt
          ? t('misc.mqm_qr_valid_until', { time: qrExpiryView.formattedExpiresAt })
          : '',
        expired: t('misc.mqm_qr_download_expired'),
        temporaryNote: t('misc.mqm_qr_download_note'),
      },
    });

    const finishDownload = (dataUrl: string) => {
      const link = document.createElement('a');
      link.download = `qr-queue-${qrData.day}-${(qrData.specialist_name || 'doctor').replace(/\s+/g, '_')}.png`;
      link.href = dataUrl;
      link.click();
      toast.success(t('misc.mqm_qr_downloaded'));
    };

    // Fallback без canvas (недоступен ctx/jsdom): прежнее поведение.
    const downloadRaw = () => finishDownload(qrData.qr_code_base64 as string);

    // RQ-11: canvas 2D не поддерживает var(--mac-*) — резолвим дизайн-токены
    // в рантайме, чтобы PNG следовал активной теме (fallback — CSS-имена).
    const resolveColorToken = (token: string, fallback: string): string => {
      try {
        return getComputedStyle(document.documentElement).getPropertyValue(token).trim() || fallback;
      } catch {
        return fallback;
      }
    };
    const canvasPalette = {
      background: resolveColorToken('--mac-bg-primary', 'white'),
      primaryText: resolveColorToken('--mac-text-primary', 'black'),
      noteText: resolveColorToken('--mac-text-secondary', 'gray'),
    };

    const image = new Image();
    image.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        const padding = 24;
        const captionArea = captions.primaryLine ? 84 : 56;
        canvas.width = image.width + padding * 2;
        canvas.height = image.height + padding * 2 + captionArea;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          downloadRaw();
          return;
        }
        ctx.fillStyle = canvasPalette.background;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(image, padding, padding);
        ctx.textAlign = 'center';
        if (captions.primaryLine) {
          ctx.fillStyle = canvasPalette.primaryText;
          ctx.font = '600 18px system-ui, sans-serif';
          ctx.fillText(captions.primaryLine, canvas.width / 2, image.height + padding + 36);
        }
        ctx.fillStyle = canvasPalette.noteText;
        ctx.font = '14px system-ui, sans-serif';
        ctx.fillText(
          captions.noteLine,
          canvas.width / 2,
          image.height + padding + (captions.primaryLine ? 64 : 36)
        );
        finishDownload(canvas.toDataURL('image/png'));
      } catch {
        downloadRaw();
      }
    };
    image.onerror = downloadRaw;
    image.src = qrData.qr_code_base64;
  };

  const doctorOptions = useMemo(() => {
    if (!Array.isArray(specialists) || specialists.length === 0) return [];

    return specialists.
    filter((d) => d.id !== undefined && d.id !== null).
    map((d) => {
      const doctorName = d.doctor_name || d.full_name || d.user?.full_name || d.name || t('misc.mqm_doctor_number', { id: d.id });
      const specialtyLabel = d.specialty_display || d.specialty || '';
      const cabinetInfo = d.cabinet ? t('misc.mqm_cabinet_info', { cabinet: d.cabinet }) : '';
      return {
        id: d.id,
        label: `${doctorName}${specialtyLabel ? ` • ${specialtyLabel}` : ''}${cabinetInfo}`,
        specialty: d.specialty
      };
    }).
    sort((a, b) => a.label.localeCompare(b.label));
  }, [specialists, t]);

  return (
    <div className="modern-queue-manager">
      {/* Статистические карточки */}
      {statistics &&
      <div className="mqm-stats-grid">
          <div className="mqm-card mqm-stat-card">
            <div className="mqm-stat-icon primary">
              <User size={20} color="white" aria-hidden="true" />
            </div>
            <div>
              <div className="mqm-stat-value">{statistics.total_entries}</div>
              <div className="mqm-stat-label">{t('misc.mqm_total_entries')}</div>
            </div>
          </div>

          <div className="mqm-card mqm-stat-card">
            <div className="mqm-stat-icon warning">
              <QrCode size={20} color="white" aria-hidden="true" />
            </div>
            <div>
              <div className="mqm-stat-value">{statistics.waiting}</div>
              <div className="mqm-stat-label">{t('misc.mqm_waiting')}</div>
            </div>
          </div>

          <div className="mqm-card mqm-stat-card">
            <div className="mqm-stat-icon success">
              <CheckCircle size={20} color="white" aria-hidden="true" />
            </div>
            <div>
              <div className="mqm-stat-value">{statistics.completed}</div>
              <div className="mqm-stat-label">{t('misc.mqm_completed')}</div>
            </div>
          </div>
        </div>
      }

      {/* Панель управления */}
      <div className="mqm-card mqm-controls-card">
        <div className="mqm-controls-header">
          <h3 className="mqm-title">
            {mode === 'doctor' ? t('nav.queue') : t('misc.mqm_title')}
          </h3>

          <div className="mqm-controls-grid">
            <div className="mqm-input-group">
              <label className="mqm-label" htmlFor="modern-queue-date">
                {t('misc.mqm_label_date')}
              </label>
              <Input
                id="modern-queue-date"
                type="date"
                aria-label={t('misc.mqm_aria_queue_date')}
                value={effectiveDate}
                // UX Audit Stage 3 (Queue issue 7.1):
                // Min удален, чтобы можно было смотреть историю и текущий день в любое время.
                // Max добавлен — без него можно создать очередь на 2030 год.
                // Раньше: только комментарий, без max.
                max={getLocalDateString()}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
                  const newDate = e.target.value;
                  setInternalDate(newDate);
                  if (onDateChange) {
                    onDateChange(newDate);
                  }
                }}
                className="mqm-input" />

            </div>

            {isRegistrarMode && (
            <div className="mqm-input-group">
              <label className="mqm-label" htmlFor="modern-queue-doctor">
                {t('misc.mqm_label_doctor')}
              </label>
              <Select
                id="modern-queue-doctor"
                aria-label={t('misc.mqm_select_doctor')}
                value={effectiveDoctor === '' ? '' : String(effectiveDoctor)}
                onValueChange={(newDoctor) => {
                  const v = String(newDoctor);
                  setInternalDoctor(v);
                  if (onDoctorChange) {
                    onDoctorChange(v);
                  }
                }}
                options={[
                  // UX Audit Stage 3 (Queue issue 7.1):
                  // Заменены unicode-escape '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435...'
                  // на читаемые t.selectDoctor / t.loadingDoctors.
                  { value: '', label: doctorOptions.length > 0 ? t('misc.mqm_select_doctor') : t('misc.mqm_loading_doctors') },
                  ...doctorOptions.map((opt) => ({
                    value: String(opt.id),
                    label: opt.label
                  }))
                ]}
                className="mqm-select mqm-select-full"></Select>
            </div>
            )}

            {isRegistrarMode && <div className="mqm-actions">
              <Button
                variant="primary"
                size="default"
                onClick={generateQR}
                disabled={!effectiveDoctor || loading}
                className="mqm-button-icon"
                title={t('misc.mqm_title_gen_doctor_qr')}>

                <QrCode size={16} color="white" aria-hidden="true" />
                {t('misc.mqm_doctor_qr')}
              </Button>

              <Button
                variant="outline"
                size="default"
                onClick={generateClinicQR}
                disabled={loading}
                className="mqm-button-icon"
                title={t('misc.mqm_title_gen_clinic_qr')}>

                <Building2 size={16} className="mqm-icon-primary" aria-hidden="true" />
                {t('misc.mqm_clinic_qr')}
              </Button>
            </div>}

            {isRegistrarMode && (() => {
              const isDisabled = !effectiveDoctor || loading || queueData?.is_open;
              return (
                <Button
                  variant="primary"
                  size="default"
                  className="mqm-reception-btn"
                  onClick={openReception}
                  disabled={isDisabled}
                  title={
                  !effectiveDoctor ?
                  t('misc.mqm_select_doctor_only') :
                  queueData?.is_open ?
                  t('misc.mqm_reception_already_open') :
                  t('misc.mqm_title_open_reception')
                  }>

                  <CheckCircle size={16} color="white" aria-hidden="true" />
                  {t('misc.mqm_open_reception')}
                </Button>);

            })()}

            {/* UX Audit Registrar #7: «Закрыть приём» кнопка.
                Раньше не было в UI — только «Открыть».
                Показывается когда приём открыт (queueData.is_open === true). */}
            {isRegistrarMode && queueData?.is_open && (
              <Button
                variant="outline"
                size="default"
                className="mqm-reception-btn"
                onClick={closeReception}
                disabled={loading}
                title={t('misc.mqm_title_close_reception')}
              >
                <X size={16} aria-hidden="true" />
                {t('misc.mqm_btn_close_reception')}
              </Button>
            )}

            <div className="mqm-inline-label">
              <Button
                variant="outline"
                size="default"
                onClick={loadQueue}
                disabled={!effectiveDoctor || loading}
                className="mqm-button-icon">

                <Settings size={16} className="mqm-icon-primary" aria-hidden="true" />
                {t('misc.mqm_refresh_queue')}
              </Button>

              <Button
                variant="primary"
                size="default"
                onClick={callPatient}
                disabled={!effectiveDoctor || loading}
                className="mqm-button-icon"
                title="Backend call-next command">
                <Bell size={16} color="white" aria-hidden="true" />
                {t('misc.mqm_call')}
              </Button>

              <button
                type="button"
                className="mqm-auto-refresh-toggle"
                onClick={() => setAutoRefresh(!autoRefresh)}
                aria-label={autoRefresh ? t('misc.mqm_aria_auto_refresh_off') : t('misc.mqm_aria_auto_refresh_on')}
                title={autoRefresh ? t('misc.mqm_title_auto_refresh_on') : t('misc.mqm_title_auto_refresh_off')}>

                <RefreshCw
                  size={20}
                  aria-hidden="true"
                  className={autoRefresh ? 'mqm-auto-refresh-icon-on' : 'mqm-auto-refresh-icon-off'} />

              </button>

              {/* UX Audit Stage 3 (Queue issue 7.1):
                  WebSocket connection indicator.
                  Зелёный — подключено (мгновенные обновления).
                  Жёлтый — переподключение.
                  Серый — отключено (работает polling 60s). */}
              {effectiveDoctor && effectiveDate && (
                <span
                  className="mqm-ws-indicator"
                  aria-label={
                    wsState === 'connected' ? t('misc.mqm_ws_aria_connected') :
                    wsState === 'reconnecting' ? t('misc.mqm_ws_aria_reconnecting') :
                    wsState === 'connecting' ? t('misc.mqm_ws_aria_connecting') :
                    t('misc.mqm_ws_aria_disconnected')
                  }
                  title={
                    wsState === 'connected' ? t('misc.mqm_ws_title_connected') :
                    wsState === 'reconnecting' ? t('misc.mqm_ws_title_reconnecting') :
                    wsState === 'connecting' ? t('misc.mqm_ws_title_connecting') :
                    t('misc.mqm_ws_title_disconnected')
                  }
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    marginLeft: 8,
                    fontSize: 11,
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    color: wsState === 'connected' ? 'var(--mac-success)' :
                           wsState === 'reconnecting' || wsState === 'connecting' ? 'var(--mac-warning)' :
                           'var(--mac-text-tertiary)',
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: 'currentColor',
                      animation: wsState === 'connecting' || wsState === 'reconnecting' ? 'pulse 1.5s infinite' : 'none',
                    }}
                    aria-hidden="true"
                  />
                  {/* PR-24: simplified WebSocket indicator — dot only, no dev jargon */}
                  <span style={{ fontSize: '11px', color: 'var(--mac-text-tertiary)' }}>
                    {wsState === 'connected' ? t('misc.mqm_ws_label_auto') : wsState === 'reconnecting' || wsState === 'connecting' ? t('misc.mqm_ws_label_reconnecting') : t('misc.mqm_ws_label_polling')}
                  </span>
                </span>
              )}
            </div>
          </div>
        </div>
        {!isRegistrarMode && onStartVisit && calledPatients.length > 0 && (
          <section className="mqm-called-visits" aria-label={t('dental.dental_panel_called_waiting')}>
            <h4 className="mqm-called-visits-title">{t('dental.dental_panel_called_waiting')}</h4>
            <ul className="mqm-called-visits-list">
              {calledPatients.map((patient) => {
                const patientName = patient.name || t('dental.dental_panel_patient_default');
                const ticketNumber = patient.number === null || patient.number === undefined ? '—' : String(patient.number);
                return (
                  <li key={String(patient.id)} className="mqm-called-visit-item">
                    <span className="mqm-called-visit-name">{patientName} · №{ticketNumber}</span>
                    <Button
                      variant="primary"
                      size="default"
                      className="mqm-button-icon"
                      aria-label={t('dental.dental_panel_start_visit_for', { name: patientName, number: ticketNumber })}
                      disabled={startingQueueEntryId !== null}
                      onClick={() => { void startCalledPatientVisit(patient); }}
                    >
                      {t('dental.dental_panel_start_visit')}
                    </Button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>

      {/* Текущая очередь */}
      <div className="mqm-card">
        <CardContent className="mqm-card-content-padded">
          <div className="mqm-queue-header">
            <h3 className="mqm-title">
              {t('misc.mqm_current_queue')}
            </h3>
            {queueData &&
            <Badge variant={queueData.is_open ? 'success' : 'secondary'}>
                {queueData.is_open ? t('misc.mqm_reception_open') : queueData.online_start_time ? t('misc.mqm_will_open_at', { time: queueData.online_start_time }) : t('misc.mqm_will_open')}
              </Badge>
            }
          </div>

          {/* QMAN-FE-001 (audit 3886): a failed load of the CURRENT selection
              is visible and recoverable — the previous selection's queue has
              been cleared by the hook and must not be presented as current. */}
          {queueLoadError && (
            <div className="mqm-queue-load-error" role="alert">
              <span>{queueLoadError}</span>
              <Button
                variant="outline"
                size="small"
                onClick={() => { void loadQueue(); }}
              >
                {t('misc.mqm_retry_load')}
              </Button>
            </div>
          )}

          <QueueTable
            queueData={queueData as unknown as QueueTableData | null}
            effectiveDoctor={String(effectiveDoctor ?? '')}
            onGenerateQR={isRegistrarMode ? generateQR : undefined}
            loading={loading}
            t={queueTableT} />

        </CardContent>
      </div>

      {/* Диалог QR кода */}
      {isRegistrarMode && <ModernDialog
        isOpen={showQrDialog}
        onClose={() => setShowQrDialog(false)}
        title={qrData?.is_clinic_wide ? t('misc.mqm_dialog_title_clinic_qr') : t('misc.mqm_dialog_title_doctor_qr')}
        maxWidth="32rem"
        maxHeight="calc(100dvh - 2rem)"
        dialogClassName="mqm-qr-dialog"
        dialogStyle={{
          backgroundColor: 'var(--mac-bg-primary)'
        }}>

        <div className="mqm-qr-modal-content">
          {/* Badge для типа QR */}
          <div className="mqm-qr-badge-container">
            {qrData?.is_clinic_wide ?
            <Badge variant="primary" className="mqm-qr-badge">
                <Building2 size={14} className="mqm-icon-margin-right-6px" aria-hidden="true" />
                {t('misc.mqm_badge_clinic_qr')}
              </Badge> :

            <Badge variant="success" className="mqm-qr-badge">
                <User size={14} className="mqm-icon-margin-right-6px" aria-hidden="true" />
                {t('misc.mqm_badge_doctor_qr')}
              </Badge>
            }
          </div>

          {/* Информация о враче/отделении */}
          <div className="mqm-qr-info-card">
            <div className="mqm-qr-info-row">
              <span className="mqm-qr-label">{t('misc.mqm_label_specialist')}</span>
              <span className="mqm-qr-value highlight">
                {qrData?.specialist_name || (qrData?.is_clinic_wide ? t('misc.mqm_value_all_specialists') : t('misc.mqm_value_not_specified'))}
              </span>
            </div>
            <div className="mqm-qr-info-row">
              <span className="mqm-qr-label">{t('misc.mqm_label_department')}</span>
              <span className="mqm-qr-value">
                {qrData?.department_name || (qrData?.is_clinic_wide ? t('misc.mqm_value_clinic') : qrData?.department)}
              </span>
            </div>
            {qrData?.target_date &&
            <div className="mqm-qr-info-row">
                <span className="mqm-qr-label">{t('misc.mqm_label_appointment_date')}</span>
                <span className="mqm-qr-value">
                  {new Date(qrData.target_date).toLocaleDateString('ru-RU', {
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric'
                })}
                </span>
              </div>
            }
          </div>

          {/* QR Код */}
          <div className="mqm-qr-code-container">
            {qrData?.qr_code_base64 ?
            <img
              src={qrData.qr_code_base64}
              alt="QR Code"
              className="mqm-qr-image" /> :

            /* QR-FE-003: SVG-fallback кодирует ТОЛЬКО серверный qr_url —
               канонический origin этого развёртывания. Хардкод
               med-queue.uz удалён: клиника на другом домене больше не
               отправляет пациентов на чужой сайт. */
            qrData?.qr_url ?
            <QRCodeSVG
              value={qrData.qr_url}
              size={240}
              level="H"
              includeMargin={true}
              className="mqm-qr-svg" /> :

            qrData?.token ?
            <div className="mqm-qr-loading" data-testid="mqm-qr-url-missing">
                <div className="mqm-spinner"></div>
                <span>{t('misc.mqm_qr_unavailable')}</span>
              </div> :


            <div className="mqm-qr-loading">
                <div className="mqm-spinner"></div>
                <span>{t('misc.mqm_qr_generating')}</span>
              </div>
            }
          </div>

          {/* Инструкция и срок действия (RQ-11: valid/expired/unspecified
              честно различаются; формат — канонический клиник-таймзоны) */}
          <div className="mqm-qr-footer-info">
            <p className="mqm-qr-instruction">
              {t('misc.mqm_qr_instruction')}
            </p>
            <p className={`mqm-qr-expiry${qrExpiryView.state === 'expired' ? ' mqm-qr-expiry-expired' : ''}`}>
              <Clock size={14} className="mqm-icon-margin-right-1" aria-hidden="true" />
              {qrExpiryView.state === 'expired'
                ? t('misc.mqm_qr_expired')
                : qrExpiryView.state === 'valid'
                  ? t('misc.mqm_qr_valid_until', { time: qrExpiryView.formattedExpiresAt })
                  : t('misc.mqm_qr_limited')}
            </p>
            {qrExpiryView.state === 'expired' && (
              <p className="mqm-qr-expiry-hint">{t('misc.mqm_qr_expired_hint')}</p>
            )}
          </div>

          {/* Кнопки действий */}
          <div className="mqm-qr-actions">
            <Button
              variant="primary"
              onClick={downloadQR}
              className="mqm-qr-action-btn">

              <ArrowDownCircle size={14} className="mqm-icon-margin-right-2" aria-hidden="true" />
              {t('misc.mqm_download')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setShowQrDialog(false)}
              className="mqm-qr-action-btn">

              {t('misc.mqm_close')}
            </Button>
          </div>
        </div>
      </ModernDialog>}

      {/* UX Audit Registrar #2: ConfirmDialog (useConfirm hook). */}
      {confirmDialog}
    </div>);

};


export default ModernQueueManager;
