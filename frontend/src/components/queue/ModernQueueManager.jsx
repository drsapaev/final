import { useState, useEffect, useCallback, useMemo } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import ModernDialog from '../dialogs/ModernDialog';
import { toast } from 'react-toastify';
import PropTypes from 'prop-types';
import { Button, Card, CardContent, Badge, Icon } from '../ui/macos';
import { getLocalDateString, getTomorrowDateString } from '../../utils/dateUtils';
import { useQueueManager } from '../../hooks/useQueueManager';
import QueueTable from './QueueTable';
import './ModernQueueManager.css';

const ModernQueueManager = ({
  selectedDate = getLocalDateString(),
  selectedDoctor = '',
  onQueueUpdate,
  language = 'ru',
  doctors = [],
  onDoctorChange,
  onDateChange,
  searchQuery,
}) => {
  const {
    loading,
    queueData,
    statistics,
    qrData,
    loadQueueSnapshot,
    generateDoctorQRCode,
    generateClinicQRCode,
    openReceptionForDoctor,
    callNextPatientInQueue,
    setQrData,
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
        doctor,
      });
    } catch (error) {
      // Не показываем тост при автообновлении, чтобы не спамить
      console.error('Ошибка загрузки очереди:', error);
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
      console.log('[ModernQueueManager] Получено событие queueUpdated:', event.detail);
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
        specialistName: doctor?.full_name || doctor?.name,
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
        targetDate: effectiveDate,
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
        targetDate: effectiveDate,
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

  // Мемоизация списка врачей для выпадающего списка
  const doctorOptions = useMemo(() => {
    if (!doctors || doctors.length === 0) return [];

    // Группируем врачей по специальности, чтобы избежать дубликатов в списке выбора очереди
    // (если очередь привязана к специальности, а не к конкретному врачу)
    const seenSpecialties = new Set();

    // Маппинг специальностей на русские названия (можно расширить)
    const specialtyNames = {
      'cardiology': 'Кардиолог',
      'cardio': 'Кардиолог',
      'dermatology': 'Дерматолог',
      'derma': 'Дерматолог',
      'stomatology': 'Стоматолог',
      'dentist': 'Стоматолог',
      'dentistry': 'Стоматолог',
      'laboratory': 'Лаборатория',
      'lab': 'Лаборатория',
      'neurology': 'Невролог',
      'pediatrics': 'Педиатр',
      'therapy': 'Терапевт',
      'surgery': 'Хирург',
      'ophthalmology': 'Окулист',
      'ent': 'ЛОР',
      'gynecology': 'Гинеколог',
      'urology': 'Уролог',
      'endocrinology': 'Эндокринолог',
      'traumatology': 'Травматолог',
      'ultrasound': 'УЗИ'
    };

    const normalizeSpecialty = (spec) => {
      const s = spec?.toLowerCase();
      if (s === 'cardio') return 'cardiology';
      if (s === 'derma') return 'dermatology';
      if (s === 'dentist' || s === 'dentistry') return 'stomatology';
      if (s === 'lab') return 'laboratory';
      return s;
    };

    return doctors
      .filter(d => d.specialty) // Только врачи со специальностью
      .reduce((acc, d) => {
        const normalizedSpec = normalizeSpecialty(d.specialty);

        // Если специальность уже была, пропускаем (для группировки очередей)
        // Если нужно показывать всех врачей, уберите эту проверку
        if (seenSpecialties.has(normalizedSpec)) {
          return acc;
        }
        seenSpecialties.add(normalizedSpec);

        const specialtyLabel = specialtyNames[normalizedSpec] || d.specialty;
        const cabinetInfo = d.cabinet ? ` (Каб. ${d.cabinet})` : '';

        acc.push({
          id: d.id,
          label: `${specialtyLabel}${cabinetInfo}`,
          specialty: normalizedSpec
        });
        return acc;
      }, [])
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [doctors]);

  return (
    <div className="modern-queue-manager">
      {/* Статистические карточки */}
      {statistics && (
        <div className="mqm-stats-grid">
          <div className="mqm-card mqm-stat-card">
            <div className="mqm-stat-icon primary">
              <Icon name="person" size="large" color="white" />
            </div>
            <div>
              <div className="mqm-stat-value">{statistics.total_entries}</div>
              <div className="mqm-stat-label">{t.totalEntries}</div>
            </div>
          </div>

          <div className="mqm-card mqm-stat-card">
            <div className="mqm-stat-icon warning">
              <Icon name="magnifyingglass" size="large" style={{ color: 'white' }} />
            </div>
            <div>
              <div className="mqm-stat-value">{statistics.waiting}</div>
              <div className="mqm-stat-label">{t.waiting}</div>
            </div>
          </div>

          <div className="mqm-card mqm-stat-card">
            <div className="mqm-stat-icon success">
              <Icon name="checkmark.circle" size="large" style={{ color: 'white' }} />
            </div>
            <div>
              <div className="mqm-stat-value">{statistics.completed}</div>
              <div className="mqm-stat-label">{t.completed}</div>
            </div>
          </div>
        </div>
      )}

      {/* Панель управления */}
      <div className="mqm-card mqm-controls-card">
        <div className="mqm-controls-header">
          <h3 className="mqm-title">
            {t.title}
          </h3>

          <div className="mqm-controls-grid">
            <div className="mqm-input-group">
              <label className="mqm-label">
                Дата
              </label>
              <input
                type="date"
                value={effectiveDate}
                // Min удален, чтобы можно было смотреть историю и текущий день в любое время
                onChange={(e) => {
                  const newDate = e.target.value;
                  setInternalDate(newDate);
                  if (onDateChange) {
                    onDateChange(newDate);
                  }
                }}
                className="mqm-input"
              />
            </div>

            <div className="mqm-input-group">
              <label className="mqm-label">
                Врач
              </label>
              <select
                value={effectiveDoctor}
                onChange={(e) => {
                  const newDoctor = e.target.value;
                  setInternalDoctor(newDoctor);
                  if (onDoctorChange) {
                    onDoctorChange(newDoctor);
                  }
                }}
                className="mqm-select"
              >
                <option value="">Выберите специалиста</option>
                {doctorOptions.length > 0 ? (
                  doctorOptions.map(opt => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))
                ) : (
                  <option disabled>Загрузка специалистов...</option>
                )}
              </select>
            </div>

            <div className="mqm-actions">
              <Button
                variant="primary"
                size="default"
                onClick={generateQR}
                disabled={!effectiveDoctor || loading}
                className="mqm-button-icon"
                title="Генерировать QR для выбранного специалиста"
              >
                <Icon name="magnifyingglass" size="small" style={{ color: 'white' }} />
                {t.doctorQr}
              </Button>

              <Button
                variant="outline"
                size="default"
                onClick={generateClinicQR}
                disabled={loading}
                className="mqm-button-icon"
                title="Генерировать общий QR код для всех специалистов клиники"
              >
                <Icon name="square.grid.2x2" size="small" style={{ color: 'var(--mac-text-primary)' }} />
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
                    !effectiveDoctor
                      ? 'Выберите врача'
                      : queueData?.is_open
                        ? 'Прием уже открыт'
                        : 'Открыть прием и закрыть онлайн-запись'
                  }
                >
                  <Icon name="checkmark.circle" size="small" style={{ color: 'white' }} />
                  {t.openReception}
                </Button>
              );
            })()}

            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
              <Button
                variant="outline"
                size="default"
                onClick={loadQueue}
                disabled={!effectiveDoctor || loading}
                className="mqm-button-icon"
              >
                <Icon name="gear" size="small" style={{ color: 'var(--mac-text-primary)' }} />
                {t.refreshQueue}
              </Button>

              <div
                style={{ cursor: 'pointer' }}
                onClick={() => setAutoRefresh(!autoRefresh)}
                title={autoRefresh ? 'Автообновление включено' : 'Автообновление выключено'}
              >
                <Icon
                  name={autoRefresh ? 'arrow.clockwise.circle.fill' : 'arrow.clockwise.circle'}
                  size="medium"
                  style={{ color: autoRefresh ? 'var(--mac-success)' : 'var(--mac-text-tertiary)' }}
                />
              </div>
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
            {queueData && (
              <Badge variant={queueData.is_open ? 'success' : 'secondary'}>
                {queueData.is_open ? t.receptionOpen : `Откроется в ${queueData.online_start_time || '09:00'}`}
              </Badge>
            )}
          </div>

          <QueueTable
            queueData={queueData}
            effectiveDoctor={effectiveDoctor}
            onGenerateQR={generateQR}
            onCallPatient={callPatient}
            loading={loading}
            t={t}
          />
        </CardContent>
      </div>

      {/* Диалог QR кода */}
      <ModernDialog
        isOpen={showQrDialog}
        onClose={() => setShowQrDialog(false)}
        title={qrData?.is_clinic_wide ? 'Общий QR код клиники' : 'QR код для записи'}
        maxWidth="32rem"
      >
        <div className="mqm-qr-modal-content">
          {/* Badge для типа QR */}
          <div className="mqm-qr-badge-container">
            {qrData?.is_clinic_wide ? (
              <Badge variant="primary" className="mqm-qr-badge">
                <Icon name="building.2.fill" size="small" style={{ marginRight: '6px' }} />
                Общий QR код клиники
              </Badge>
            ) : (
              <Badge variant="success" className="mqm-qr-badge">
                <Icon name="person.fill" size="small" style={{ marginRight: '6px' }} />
                QR код специалиста
              </Badge>
            )}
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
            {qrData?.target_date && (
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
            )}
          </div>

          {/* QR Код */}
          <div className="mqm-qr-code-container">
            {qrData?.qr_code_base64 ? (
              <img
                src={qrData.qr_code_base64}
                alt="QR Code"
                className="mqm-qr-image"
              />
            ) : qrData?.token ? (
              <QRCodeSVG
                value={`https://med-queue.uz/queue/join?token=${qrData.token}`}
                size={240}
                level="H"
                includeMargin={true}
                className="mqm-qr-svg"
              />
            ) : (
              <div className="mqm-qr-loading">
                <div className="mqm-spinner"></div>
                <span>Генерация QR кода...</span>
              </div>
            )}
          </div>

          {/* Инструкция и срок действия */}
          <div className="mqm-qr-footer-info">
            <p className="mqm-qr-instruction">
              Отсканируйте камеру телефона для записи в очередь
            </p>
            <p className="mqm-qr-expiry">
              <Icon name="clock" size="small" style={{ marginRight: '4px', verticalAlign: 'text-bottom' }} />
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
              className="mqm-qr-action-btn"
            >
              <Icon name="arrow.down.circle" size="small" style={{ marginRight: '8px' }} />
              {t.download}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setShowQrDialog(false)}
              className="mqm-qr-action-btn"
            >
              {t.close || 'Закрыть'}
            </Button>
          </div>
        </div>
      </ModernDialog>
    </div>
  );
};

ModernQueueManager.propTypes = {
  selectedDate: PropTypes.string,
  selectedDoctor: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onQueueUpdate: PropTypes.func,
  language: PropTypes.string,
  doctors: PropTypes.array,
  onDoctorChange: PropTypes.func,
  onDateChange: PropTypes.func,
  searchQuery: PropTypes.string,
};

export default ModernQueueManager;
