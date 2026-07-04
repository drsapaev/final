import { useState, useEffect, useCallback, useMemo } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import ModernDialog from '../dialogs/ModernDialog';
import { toast } from 'react-toastify';
import PropTypes from 'prop-types';
// UX Audit Stage 3 (Queue issue 7.3):
// Заменены SF Symbols (Icon) на lucide-react — единая библиотека иконок.
// Раньше Queue был единственным экраном, использующим SF Symbols.
import {
  QrCode, Building2, CheckCircle, Settings, Bell, User, Clock, ArrowDownCircle, RefreshCw,
} from 'lucide-react';
import {
  Button, CardContent, Badge, Select,
} from '../ui/macos';
import { getLocalDateString } from '../../utils/dateUtils';
import { useQueueManager } from '../../hooks/useQueueManager';
import QueueTable from './QueueTable';
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
}) => {
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
    callNextPatientInQueue

  } = useQueueManager();

  const [internalDoctor, setInternalDoctor] = useState('');
  const [internalDate, setInternalDate] = useState(getLocalDateString());
  const effectiveDoctor = selectedDoctor !== undefined && selectedDoctor !== '' ? selectedDoctor : internalDoctor;
  const effectiveDate = selectedDate !== undefined && selectedDate !== '' ? selectedDate : internalDate;
  const [showQrDialog, setShowQrDialog] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Переводы
  const t = {
    ru: {
      title: 'Управление онлайн-очередью',
      generateQr: 'Генерировать QR код',
      refreshQueue: 'Обновить очередь',
      openReception: 'Открыть прием',
      receptionOpen: 'Прием открыт',
      autoRefresh: 'Автообновление',
      statistics: 'Статистика',
      currentQueue: 'Текущая очередь',
      totalEntries: 'Всего записей',
      waiting: 'Ожидают',
      completed: 'Завершено',
      available: 'Свободно',
      selectDoctor: 'Выберите врача',
      // UX Audit Stage 3 (Queue issue 7.1): добавлен перевод для loading-состояния.
      // Раньше был хардкод в unicode-escape: '\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...'
      loadingDoctors: 'Загрузка специалистов...',
      queueEmpty: 'Очередь пуста',
      queueNotFound: 'Очередь не найдена',
      patient: 'Пациент',
      phone: 'Телефон',
      time: 'Время',
      status: 'Статус',
      actions: 'Действия',
      call: 'Вызвать',
      called: 'Вызван',
      cancel: 'Отмена',
      download: 'Скачать',
      print: 'Печать',
      clinicQr: 'Общий QR клиники',
      doctorQr: 'QR для специалиста'
    }
  }[language] || {};

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

  // Polling для автообновления
  useEffect(() => {
    let interval;
    if (autoRefresh && effectiveDoctor && effectiveDate) {
      interval = setInterval(() => {
        loadQueue();
      }, 30000); // 30 секунд
    }
    return () => clearInterval(interval);
  }, [autoRefresh, effectiveDoctor, effectiveDate, loadQueue]);

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
      toast.error('Выберите врача и дату');
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
      toast.success('QR код сгенерирован');
    } catch (error) {
      toast.error(error.message || 'Ошибка генерации QR кода');
    }
  };

  // Генерация общего QR кода клиники
  const generateClinicQR = async () => {
    if (!effectiveDate) {
      toast.error('Выберите дату');
      return;
    }

    try {
      await generateClinicQRCode({ targetDate: effectiveDate });
      setShowQrDialog(true);
      toast.success('Общий QR код клиники сгенерирован');
    } catch (error) {
      toast.error(error.message || 'Ошибка генерации общего QR кода');
    }
  };

  // Открытие приема
  const openReception = async () => {
    if (!effectiveDoctor) {
      toast.error('Выберите врача');
      return;
    }

    if (queueData?.is_open) {
      toast.info('Прием уже открыт');
      return;
    }

    try {
      const result = await openReceptionForDoctor({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate
      });

      toast.success(result?.message || 'Прием открыт. Онлайн-набор закрыт.');
      await loadQueue();

      if (onQueueUpdate) {
        onQueueUpdate();
      }
    } catch (error) {
      toast.error(error.message || 'Ошибка открытия приема');
    }
  };

  // Вызов пациента
  const callPatient = async () => {
    if (!effectiveDoctor) {
      toast.error('Выберите врача');
      return;
    }

    try {
      const result = await callNextPatientInQueue({
        specialistId: effectiveDoctor,
        targetDate: effectiveDate
      });

      if (result?.success && result?.patient) {
        toast.success(
          `Вызван пациент: ${result.patient.name} (№${result.patient.number})`
        );
      } else {
        toast.info(result?.message || 'Нет пациентов в очереди');
      }

      await loadQueue();
    } catch (error) {
      toast.error(error.message || 'Ошибка вызова пациента');
    }
  };

  const downloadQR = () => {
    if (!qrData) {
      toast.error('QR данные недоступны');
      return;
    }

    if (qrData.qr_code_base64) {
      const link = document.createElement('a');
      link.download = `qr-queue-${qrData.day}-${qrData.specialist_name.replace(/\s+/g, '_')}.png`;
      link.href = qrData.qr_code_base64;
      link.click();
      toast.success('QR код скачан');
    } else {
      toast.error('QR изображение недоступно');
    }
  };

  const doctorOptions = useMemo(() => {
    if (!Array.isArray(specialists) || specialists.length === 0) return [];

    return specialists.
    filter((d) => d.id !== undefined && d.id !== null).
    map((d) => {
      const doctorName = d.doctor_name || d.full_name || d.user?.full_name || d.name || `Врач #${d.id}`;
      const specialtyLabel = d.specialty_display || d.specialty || '';
      const cabinetInfo = d.cabinet ? ` (Каб. ${d.cabinet})` : '';
      return {
        id: d.id,
        label: `${doctorName}${specialtyLabel ? ` • ${specialtyLabel}` : ''}${cabinetInfo}`,
        specialty: d.specialty
      };
    }).
    sort((a, b) => a.label.localeCompare(b.label));
  }, [specialists]);

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
              <div className="mqm-stat-label">{t.totalEntries}</div>
            </div>
          </div>

          <div className="mqm-card mqm-stat-card">
            <div className="mqm-stat-icon warning">
              <QrCode size={20} color="white" aria-hidden="true" />
            </div>
            <div>
              <div className="mqm-stat-value">{statistics.waiting}</div>
              <div className="mqm-stat-label">{t.waiting}</div>
            </div>
          </div>

          <div className="mqm-card mqm-stat-card">
            <div className="mqm-stat-icon success">
              <CheckCircle size={20} color="white" aria-hidden="true" />
            </div>
            <div>
              <div className="mqm-stat-value">{statistics.completed}</div>
              <div className="mqm-stat-label">{t.completed}</div>
            </div>
          </div>
        </div>
      }

      {/* Панель управления */}
      <div className="mqm-card mqm-controls-card">
        <div className="mqm-controls-header">
          <h3 className="mqm-title">
            {t.title}
          </h3>

          <div className="mqm-controls-grid">
            <div className="mqm-input-group">
              <label className="mqm-label" htmlFor="modern-queue-date">
                Дата
              </label>
              <input
                id="modern-queue-date"
                type="date"
                aria-label="Дата очереди"
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
                Врач
              </label>
              <Select
                id="modern-queue-doctor"
                aria-label={t.selectDoctor}
                value={effectiveDoctor === '' ? '' : String(effectiveDoctor)}
                onChange={(newDoctor) => {
                  setInternalDoctor(newDoctor);
                  if (onDoctorChange) {
                    onDoctorChange(newDoctor);
                  }
                }}
                options={[
                  // UX Audit Stage 3 (Queue issue 7.1):
                  // Заменены unicode-escape '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435...'
                  // на читаемые t.selectDoctor / t.loadingDoctors.
                  { value: '', label: doctorOptions.length > 0 ? t.selectDoctor : t.loadingDoctors },
                  ...doctorOptions.map((opt) => ({
                    value: String(opt.id),
                    label: opt.label
                  }))
                ]}
                className="mqm-select"
                style={{ width: '100%' }}></Select>
            </div>

            <div className="mqm-actions">
              <Button
                variant="primary"
                size="default"
                onClick={generateQR}
                disabled={!effectiveDoctor || loading}
                className="mqm-button-icon"
                title="Генерировать QR для выбранного специалиста">

                <QrCode size={16} color="white" aria-hidden="true" />
                {t.doctorQr}
              </Button>

              <Button
                variant="outline"
                size="default"
                onClick={generateClinicQR}
                disabled={loading}
                className="mqm-button-icon"
                title="Генерировать общий QR код для всех специалистов клиники">

                <Building2 size={16} style={{ color: 'var(--mac-text-primary)' }} aria-hidden="true" />
                {t.clinicQr}
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
                  'Выберите врача' :
                  queueData?.is_open ?
                  'Прием уже открыт' :
                  'Открыть прием и закрыть онлайн-запись'
                  }>

                  <CheckCircle size={16} color="white" aria-hidden="true" />
                  {t.openReception}
                </Button>);

            })()}

            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
              <Button
                variant="outline"
                size="default"
                onClick={loadQueue}
                disabled={!effectiveDoctor || loading}
                className="mqm-button-icon">

                <Settings size={16} style={{ color: 'var(--mac-text-primary)' }} aria-hidden="true" />
                {t.refreshQueue}
              </Button>

              <Button
                variant="primary"
                size="default"
                onClick={callPatient}
                disabled={!effectiveDoctor || loading}
                className="mqm-button-icon"
                title="Backend call-next command">
                <Bell size={16} color="white" aria-hidden="true" />
                {t.call}
              </Button>

              <button
                type="button"
                style={{
                  cursor: 'pointer',
                  border: 'none',
                  background: 'transparent',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center'
                }}
                onClick={() => setAutoRefresh(!autoRefresh)}
                aria-label={autoRefresh ? 'Отключить автообновление очереди' : 'Включить автообновление очереди'}
                title={autoRefresh ? 'Автообновление включено' : 'Автообновление выключено'}>

                <RefreshCw
                  size={20}
                  aria-hidden="true"
                  style={{ color: autoRefresh ? 'var(--mac-success)' : 'var(--mac-text-tertiary)' }} />

              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Текущая очередь */}
      <div className="mqm-card">
        <CardContent style={{ padding: 'var(--mac-spacing-5)' }}>
          <div className="mqm-queue-header">
            <h3 className="mqm-title">
              {t.currentQueue}
            </h3>
            {queueData &&
            <Badge variant={queueData.is_open ? 'success' : 'secondary'}>
                {queueData.is_open ? t.receptionOpen : queueData.online_start_time ? `Откроется в ${queueData.online_start_time}` : 'Откроется'}
              </Badge>
            }
          </div>

          <QueueTable
            queueData={queueData}
            effectiveDoctor={effectiveDoctor}
            onGenerateQR={generateQR}
            loading={loading}
            t={t} />

        </CardContent>
      </div>

      {/* Диалог QR кода */}
      <ModernDialog
        isOpen={showQrDialog}
        onClose={() => setShowQrDialog(false)}
        title={qrData?.is_clinic_wide ? 'Общий QR код клиники' : 'QR код для записи'}
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
                <Building2 size={14} style={{ marginRight: '6px' }} aria-hidden="true" />
                Общий QR код клиники
              </Badge> :

            <Badge variant="success" className="mqm-qr-badge">
                <User size={14} style={{ marginRight: '6px' }} aria-hidden="true" />
                QR код специалиста
              </Badge>
            }
          </div>

          {/* Информация о враче/отделении */}
          <div className="mqm-qr-info-card">
            <div className="mqm-qr-info-row">
              <span className="mqm-qr-label">Специалист:</span>
              <span className="mqm-qr-value highlight">
                {qrData?.specialist_name || (qrData?.is_clinic_wide ? 'Все специалисты' : 'Не указан')}
              </span>
            </div>
            <div className="mqm-qr-info-row">
              <span className="mqm-qr-label">Отделение:</span>
              <span className="mqm-qr-value">
                {qrData?.department_name || (qrData?.is_clinic_wide ? 'Клиника' : qrData?.department)}
              </span>
            </div>
            {qrData?.target_date &&
            <div className="mqm-qr-info-row">
                <span className="mqm-qr-label">Дата приема:</span>
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
                <span>Генерация QR кода...</span>
              </div>
            }
          </div>

          {/* Инструкция и срок действия */}
          <div className="mqm-qr-footer-info">
            <p className="mqm-qr-instruction">
              Отсканируйте камеру телефона для записи в очередь
            </p>
            <p className="mqm-qr-expiry">
              <Clock size={14} style={{ marginRight: '4px', verticalAlign: 'text-bottom' }} aria-hidden="true" />
              Действует до: {qrData?.expires_at ? new Date(qrData.expires_at).toLocaleString('ru-RU', {
                day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
              }) : '—'}
            </p>
          </div>

          {/* Кнопки действий */}
          <div className="mqm-qr-actions">
            <Button
              variant="primary"
              onClick={downloadQR}
              className="mqm-qr-action-btn">

              <ArrowDownCircle size={14} style={{ marginRight: '8px' }} aria-hidden="true" />
              {t.download}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setShowQrDialog(false)}
              className="mqm-qr-action-btn">

              {t.close || 'Закрыть'}
            </Button>
          </div>
        </div>
      </ModernDialog>
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
