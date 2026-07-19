import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useCallback, useMemo } from 'react';
import type { CSSProperties } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import ModernDialog from '../dialogs/ModernDialog';
import { toast } from 'react-toastify';
import PropTypes from 'prop-types';
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
// UX Audit Stage 3 (Queue issue 7.1):
// WebSocket подписка для мгновенных обновлений очереди вместо 30s polling.
import { useQueueWebSocket } from '../../hooks/useQueueWebSocket';
import QueueTableRaw from './QueueTable';
const QueueTable = QueueTableRaw as unknown as React.ComponentType<Record<string, unknown>>;
import logger from '../../utils/logger';
import './ModernQueueManager.css';

const ModernQueueManager = ({
  selectedDate = getLocalDateString(),
  selectedDoctor = '',
  onQueueUpdate,
  language = 'ru',
  doctors = [],
  onDoctorChange,
  onDateChange
}: any) => {
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

  } = useQueueManager() as any;

  const [internalDoctor, setInternalDoctor] = useState('');
  const [internalDate, setInternalDate] = useState(getLocalDateString());
  const effectiveDoctor = selectedDoctor !== undefined && selectedDoctor !== '' ? selectedDoctor : internalDoctor;
  const effectiveDate = selectedDate !== undefined && selectedDate !== '' ? selectedDate : internalDate;
  const [showQrDialog, setShowQrDialog] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // UX Audit Registrar #2: useConfirm hook для замены window.confirm().
  // Возвращает [confirm, dialog]; dialog должен быть отрендерен в JSX.
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;

  // i18next translation function.
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

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
    if (!effectiveDoctor) {
      return;
    }

    const doctor = doctors.find(
      (candidate) => String(candidate.id) === String(effectiveDoctor)
    );

    try {
      await loadQueueSnapshot({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate,
        doctor
      });
    } catch (error) {
      // Не показываем тост при автообновлении, чтобы не спамить
      logger.error('Ошибка загрузки очереди:', error);
    }
  }, [effectiveDoctor, effectiveDate, doctors, loadQueueSnapshot]);

  // Автоматическая загрузка при изменении врача или даты
  useEffect(() => {
    if (effectiveDoctor) {
      loadQueue();
    }
  }, [effectiveDoctor, effectiveDate, loadQueue]);

  // Polling для автообновления (fallback для WebSocket)
  // UX Audit Stage 3 (Queue issue 7.1):
  // Polling увеличен с 30s до 60s — теперь это fallback для WebSocket.
  // WebSocket (useQueueWebSocket ниже) даёт мгновенные обновления.
  // Если WS упал, polling 60s всё ещё обновляет очередь.
  useEffect(() => {
    let interval;
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
    specialistId: effectiveDoctor,
    date: effectiveDate,
    enabled: Boolean(effectiveDoctor && effectiveDate),
    onUpdate: loadQueue,
  });

  // Слушатель событий от QueueJoin для мгновенного обновления
  useEffect(() => {
    const handleQueueUpdate = (event) => {
      logger.log('[ModernQueueManager] Получено событие queueUpdated:', event.detail);
      // Обновляем очередь при любом событии добавления
      if (event.detail?.action === 'refreshAll' || event.detail?.action === 'entryAdded') {
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
      toast.error(error.message || t('misc.mqm_qr_gen_error'));
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
      toast.error(error.message || t('misc.mqm_clinic_qr_gen_error'));
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
      toast.error(error.message || t('misc.mqm_reception_open_error'));
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
      toast.error(error.message || t('misc.mqm_reception_close_error'));
    }
  };

  // Вызов пациента
  const callPatient = async () => {
    if (!effectiveDoctor) {
      toast.error(t('misc.mqm_select_doctor_only'));
      return;
    }

    try {
      const result = await callNextPatientInQueue({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate
      });

      if (result?.success && result?.patient) {
        toast.success(
          t('misc.mqm_patient_called', { name: result.patient.name, number: result.patient.number })
        );
      } else {
        toast.info(result?.message || t('misc.mqm_no_patients'));
      }

      await loadQueue();
    } catch (error) {
      toast.error(error.message || t('misc.mqm_call_patient_error'));
    }
  };

  const downloadQR = () => {
    if (!qrData) {
      toast.error(t('misc.mqm_qr_unavailable'));
      return;
    }

    if (qrData.qr_code_base64) {
      const link = document.createElement('a');
      link.download = `qr-queue-${qrData.day}-${qrData.specialist_name.replace(/\s+/g, '_')}.png`;
      link.href = qrData.qr_code_base64;
      link.click();
      toast.success(t('misc.mqm_qr_downloaded'));
    } else {
      toast.error(t('misc.mqm_qr_image_unavailable'));
    }
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
            {t('misc.mqm_title')}
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
                onChange={(e) => {
                  const newDate = e.target.value;
                  setInternalDate(newDate);
                  if (onDateChange) {
                    onDateChange(newDate);
                  }
                }}
                className="mqm-input" />

            </div>

            <div className="mqm-input-group">
              <label className="mqm-label" htmlFor="modern-queue-doctor">
                {t('misc.mqm_label_doctor')}
              </label>
              <Select
                id="modern-queue-doctor"
                aria-label={t('misc.mqm_select_doctor')}
                value={effectiveDoctor === '' ? '' : String(effectiveDoctor)}
                onChange={(newDoctor: unknown) => {
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

            <div className="mqm-actions">
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
            </div>

            {(() => {
              const isDisabled = !effectiveDoctor || loading || queueData?.is_open;
              return (
                <Button
                  variant="success"
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
            {queueData?.is_open && (
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

          <QueueTable
            queueData={queueData}
            effectiveDoctor={effectiveDoctor}
            onGenerateQR={generateQR}
            loading={loading}
            t={queueTableT} />

        </CardContent>
      </div>

      {/* Диалог QR кода */}
      <ModernDialog
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

            qrData?.token ?
            <QRCodeSVG
              value={`https://med-queue.uz/queue/join?token=${qrData.token}`}
              size={240}
              level="H"
              includeMargin={true}
              className="mqm-qr-svg" /> :


            <div className="mqm-qr-loading">
                <div className="mqm-spinner"></div>
                <span>{t('misc.mqm_qr_generating')}</span>
              </div>
            }
          </div>

          {/* Инструкция и срок действия */}
          <div className="mqm-qr-footer-info">
            <p className="mqm-qr-instruction">
              {t('misc.mqm_qr_instruction')}
            </p>
            <p className="mqm-qr-expiry">
              <Clock size={14} className="mqm-icon-margin-right-1" aria-hidden="true" />
              {qrData?.expires_at
                ? t('misc.mqm_qr_valid_until', { time: new Date(qrData.expires_at).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) })
                : t('misc.mqm_qr_valid_until_empty')}
            </p>
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
      </ModernDialog>

      {/* UX Audit Registrar #2: ConfirmDialog (useConfirm hook). */}
      {confirmDialog as unknown as React.ReactNode}
    </div>);

};

ModernQueueManager.propTypes = {
  selectedDate: PropTypes.string,
  selectedDoctor: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onQueueUpdate: PropTypes.func,
  language: PropTypes.string,
  doctors: PropTypes.array,
  onDoctorChange: PropTypes.func,
  onDateChange: PropTypes.func,
  searchQuery: PropTypes.string
};

export default ModernQueueManager;
