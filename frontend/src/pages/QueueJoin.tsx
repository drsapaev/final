import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Clock,
  Users,
  CheckCircle,
  AlertCircle,
  Phone,
  User,
  MapPin,
  Calendar,
  Timer
} from 'lucide-react';
import './QueueJoin.css';
import {
  fetchQrTokenInfo,
  startQueueJoinSession,
  completeQueueJoinSession,
} from '../api/queue';
import { formatRegistrarTime } from '../utils/dateUtils';
import {
  Input,
  Checkbox } from '../components/ui/macos';
import { useTranslation } from '../i18n/useTranslation';

const QueueJoin = () => {
  const { token: paramToken } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

  const formatSpecialistLabel = (specialist) => {
    const doctorName =
      specialist?.doctor_name ||
      specialist?.full_name ||
      specialist?.name ||
      specialist?.specialty_display ||
      specialist?.specialty ||
      t('misc.qj_specialist_default');
    const specialtyLabel =
      specialist?.specialty_display ||
      specialist?.specialty ||
      '';
    const cabinetLabel = specialist?.cabinet ? t('misc.qj_cabinet_label', { cabinet: specialist.cabinet }) : '';

    return [doctorName, specialtyLabel, cabinetLabel]
      .filter(Boolean)
      .join(' • ');
  };

  const MISSING_QUEUE_TOKEN_MESSAGE = t('misc.qj_missing_token');
  const QUEUE_JOIN_MESSAGES = {
    sessionStartFailed: t('misc.qj_session_start_failed'),
    registrationUnavailable: t('misc.qj_registration_unavailable'),
    qrTokenUnavailable: t('misc.qj_qr_token_unavailable'),
    requiredFields: t('misc.qj_required_fields'),
    sessionExpired: t('misc.qj_session_expired'),
    sessionCreateFailed: t('misc.qj_session_create_failed'),
    nameTooShort: t('misc.qj_name_too_short'),
    nameTooLong: t('misc.qj_name_too_long'),
    phoneTooShort: t('misc.qj_phone_too_short'),
    phoneTooLong: t('misc.qj_phone_too_long'),
    missingSessionToken: t('misc.qj_missing_session_token'),
    joinFailed: t('misc.qj_join_failed'),
    selectSpecialist: t('misc.qj_select_specialist'),
  };

  // Получаем токен из URL параметров или query параметров (для PWA пути)
  const token = paramToken || searchParams.get('token');
  const formStorageKey = token ? `queue_join_form_${token}` : null;

  // Состояния
  const [step, setStep] = useState('loading'); // loading, waiting, info, select-specialists, form, success, error
  const [queueInfo, setQueueInfo] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);
  const [formData, setFormData] = useState({
    patientName: '',
    phone: '',
    telegramId: ''
  } as any);
  const [selectedSpecialists, setSelectedSpecialists] = useState([]); // Выбранные специалисты для общего QR
  const [availableSpecialists, setAvailableSpecialists] = useState([]); // Список доступных специалистов из API
  const [isSpecialistsLoading, setIsSpecialistsLoading] = useState(true);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [countdown, setCountdown] = useState(null);

  const getApiErrorMessage = useCallback((err, fallbackMessage) => {
    const responseData = err?.response?.data;
    if (typeof responseData?.detail === 'string') {
      return responseData.detail;
    }
    if (Array.isArray(responseData?.detail)) {
      return responseData.detail
        .map((item) => item?.msg || String(item))
        .join(', ');
    }
    if (typeof responseData?.message === 'string') {
      return responseData.message;
    }
    return fallbackMessage;
  }, []);

  useEffect(() => {
    if (!formStorageKey) {
      return;
    }
    const saved = localStorage.getItem(formStorageKey);
    if (!saved) {
      return;
    }
    try {
      const parsed = JSON.parse(saved);
      if (parsed && typeof parsed === 'object') {
        setFormData({
          patientName: parsed.patientName || '',
          phone: parsed.phone || '',
          telegramId: parsed.telegramId || '',
        });
      }
    } catch {
      localStorage.removeItem(formStorageKey);
    }
  }, [formStorageKey]);

  useEffect(() => {
    if (!formStorageKey) {
      return;
    }
    if (!formData.patientName && !formData.phone && !formData.telegramId) {
      localStorage.removeItem(formStorageKey);
      return;
    }
    localStorage.setItem(formStorageKey, JSON.stringify(formData));
  }, [formData, formStorageKey]);

  // ✅ Функции объявлены до использования в useEffect
  const startJoinSession = useCallback(async () => {
    setIsSpecialistsLoading(true);
    try {
      const sessionData = await startQueueJoinSession(token);
      const nextQueueInfo = sessionData.queue_info || {};
      const selectableSpecialists = Array.isArray(nextQueueInfo.selectable_specialists)
        ? nextQueueInfo.selectable_specialists
        : [];

      setSessionToken(sessionData.session_token);
      localStorage.setItem(`queue_session_${token}`, sessionData.session_token);
      setQueueInfo(nextQueueInfo);
      setAvailableSpecialists(selectableSpecialists);

      if (nextQueueInfo.is_clinic_wide) {
        setStep('select-specialists');
      } else {
        setStep('info');
      }

    } catch (error: any) {
      setAvailableSpecialists([]);
      setError(getApiErrorMessage(error, QUEUE_JOIN_MESSAGES.sessionStartFailed));
      setStep('error');
    } finally {
      setIsSpecialistsLoading(false);
    }
  }, [getApiErrorMessage, token]);

  const loadTokenInfo = useCallback(async () => {
    if (!token) {
      setError(MISSING_QUEUE_TOKEN_MESSAGE);
      setStep('error');
      setIsSpecialistsLoading(false);
      return;
    }

    try {
      setStep('loading');
      setIsSpecialistsLoading(true);
      const tokenInfo = await fetchQrTokenInfo(token);
      setQueueInfo(tokenInfo);
      setAvailableSpecialists(
        Array.isArray(tokenInfo.selectable_specialists)
          ? tokenInfo.selectable_specialists
          : []
      );

      if (tokenInfo.status === 'before_start_time') {
        setQueueInfo(tokenInfo);
        setStep('waiting');
        setIsSpecialistsLoading(false);
        return;
      }

      if (!tokenInfo.queue_active || tokenInfo.allowed === false) {
        setError(tokenInfo.message || QUEUE_JOIN_MESSAGES.registrationUnavailable);
        setStep('error');
        setIsSpecialistsLoading(false);
        return;
      }

      await startJoinSession();

    } catch (error: any) {
      setAvailableSpecialists([]);
      setIsSpecialistsLoading(false);
      setError(getApiErrorMessage(error, QUEUE_JOIN_MESSAGES.qrTokenUnavailable));
      setStep('error');
    }
  }, [getApiErrorMessage, startJoinSession, token]);

  // Загрузка информации о токене при монтировании
  useEffect(() => {
    if (!token) {
      setSessionToken(null);
      setQueueInfo(null);
      setAvailableSpecialists([]);
      setIsSpecialistsLoading(false);
      setError(MISSING_QUEUE_TOKEN_MESSAGE);
      setStep('error');
      return;
    }

    // ✅ Пытаемся восстановить session_token из localStorage
    const savedSessionToken = localStorage.getItem(`queue_session_${token}`);
    if (savedSessionToken) {
      setSessionToken(savedSessionToken);
    }
    loadTokenInfo();
  }, [token, loadTokenInfo]);

  // Обратный отсчет до открытия очереди
  useEffect(() => {
    let interval;

    if (step === 'waiting' && queueInfo?.minutes_until_open) {
      setCountdown(queueInfo.minutes_until_open * 60); // переводим в секунды

      interval = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            // Время истекло, перезагружаем информацию
            loadTokenInfo();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [step, queueInfo?.minutes_until_open, loadTokenInfo]);

  const handleFormSubmit = async (e) => {
    e.preventDefault();

    if (!formData.patientName.trim() || !formData.phone.trim()) {
      setError(QUEUE_JOIN_MESSAGES.requiredFields);
      return;
    }

    // ✅ Проверяем наличие session_token
    let currentSessionToken = sessionToken;

    if (!currentSessionToken) {
      // Пытаемся восстановить из localStorage
      currentSessionToken = localStorage.getItem(`queue_session_${token}`);

      if (!currentSessionToken) {
        // Если нет сохраненной сессии, создаем новую
        setError(QUEUE_JOIN_MESSAGES.sessionExpired);
        await startJoinSession();
        currentSessionToken = sessionToken;
        if (!currentSessionToken) {
          setError(QUEUE_JOIN_MESSAGES.sessionCreateFailed);
          return;
        }
      } else {
        setSessionToken(currentSessionToken);
      }
    }

    setLoading(true);
    setError(null);

    try {
      // Валидация данных перед отправкой
      const trimmedPatientName = formData.patientName.trim();
      const trimmedPhone = formData.phone.trim();

      if (trimmedPatientName.length < 2) {
        setError(QUEUE_JOIN_MESSAGES.nameTooShort);
        setLoading(false);
        return;
      }

      if (trimmedPatientName.length > 200) {
        setError(QUEUE_JOIN_MESSAGES.nameTooLong);
        setLoading(false);
        return;
      }

      // ✅ ИСПРАВЛЕНО: Валидация узбекского номера (998 + 9 цифр = 12 цифр)
      const cleanPhone = trimmedPhone.replace(/\D/g, '');
      let normalizedPhone = cleanPhone;

      if (normalizedPhone.startsWith('8')) {
        normalizedPhone = '998' + normalizedPhone.slice(1);
      }
      if (!normalizedPhone.startsWith('998') && normalizedPhone.length > 0) {
        if (normalizedPhone.startsWith('9')) {
          normalizedPhone = '998' + normalizedPhone;
        } else {
          normalizedPhone = '998' + normalizedPhone;
        }
      }

      // Узбекский номер должен быть 12 цифр (998 + 9 цифр)
      if (normalizedPhone.length < 12) {
        setError(QUEUE_JOIN_MESSAGES.phoneTooShort);
        setLoading(false);
        return;
      }

      if (normalizedPhone.length > 12) {
        setError(QUEUE_JOIN_MESSAGES.phoneTooLong);
        setLoading(false);
        return;
      }

      if (!currentSessionToken) {
        setError(QUEUE_JOIN_MESSAGES.missingSessionToken);
        setLoading(false);
        return;
      }

      // Подготавливаем данные запроса
      // ✅ ИСПРАВЛЕНО: Используем уже нормализованный номер из валидации
      const requestBody = {
        session_token: currentSessionToken,
        patient_name: trimmedPatientName,
        phone: normalizedPhone, // ✅ Отправляем нормализованный номер (12 цифр: 998XXXXXXXXX)
        telegram_id: formData.telegramId ? parseInt(formData.telegramId) : null
      };

      // Если выбраны специалисты (общий QR), добавляем их в запрос
      if (selectedSpecialists && selectedSpecialists.length > 0) {
        requestBody.specialist_ids = selectedSpecialists;
      }

      const joinResult = await completeQueueJoinSession(requestBody);
      setResult(joinResult);
      // ✅ Очищаем session_token из localStorage после успешного присоединения
      localStorage.removeItem(`queue_session_${token}`);
      if (formStorageKey) {
        localStorage.removeItem(formStorageKey);
      }

      // ✅ Отправляем событие обновления очереди для автоматического обновления таблицы
      if (joinResult.success) {
        // Определяем specialty из результата (entries содержит department)
        const firstEntry = joinResult.entries?.[0];
        let specialty = firstEntry?.department ||
          firstEntry?.specialty ||
          queueInfo?.specialty ||
          null;

        // Нормализуем specialty и определяем departmentKey для соответствия с RegistrarPanel
        let departmentKey = null;
        if (specialty) {
          const normalized = specialty.toLowerCase();
          if (normalized === 'cardio' || normalized === 'cardiology') {
            specialty = 'cardiology';
            departmentKey = 'cardio';
          } else if (normalized === 'derma' || normalized === 'dermatology') {
            specialty = 'dermatology';
            departmentKey = 'derma';
          } else if (normalized === 'dentist' || normalized === 'dentistry' || normalized === 'stomatology') {
            specialty = 'stomatology';
            departmentKey = 'dental'; // ✅ Вкладка называется 'dental', а не 'stomatology'
          } else if (normalized === 'lab' || normalized === 'laboratory') {
            specialty = 'laboratory';
            departmentKey = 'lab';
          }
        }

        // Отправляем событие для немедленного обновления таблицы
        // Используем refreshAll для гарантированного обновления всех очередей
        const eventDetail = {
          action: 'refreshAll', // Обновляем все очереди
          specialty: specialty,
          departmentKey: departmentKey, // ✅ Добавляем departmentKey для правильной фильтрации
          entry: firstEntry || joinResult,
          timestamp: new Date().toISOString(),
          source: 'queueJoin'
        };

        window.dispatchEvent(new CustomEvent('queueUpdated', {
          detail: eventDetail
        }));

        // Дополнительно отправляем событие entryAdded для логирования
        if (firstEntry) {
          window.dispatchEvent(new CustomEvent('queueUpdated', {
            detail: {
              action: 'entryAdded',
              specialty: specialty,
              entry: firstEntry,
              timestamp: new Date().toISOString(),
              source: 'queueJoin'
            }
          }));
        }

        // ✅ Дополнительно: сохраняем флаг в localStorage для проверки обновления
        localStorage.setItem('lastQueueJoin', JSON.stringify({
          timestamp: new Date().toISOString(),
          specialty: specialty,
          departmentKey: departmentKey, // ✅ Сохраняем departmentKey для fallback механизма
          entry: firstEntry
        }));
      }

      setStep('success');

    } catch (error: any) {
      setError(getApiErrorMessage(error, QUEUE_JOIN_MESSAGES.joinFailed));
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    if (error) {
      setError(null);
    }
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // ✅ Функция форматирования узбекского номера телефона
  const formatUzbekPhone = (value) => {
    // Удаляем все нецифровые символы
    const numbers = value.replace(/\D/g, '');

    // Если начинается с 8, заменяем на 998
    let cleanNumber = numbers;
    if (cleanNumber.startsWith('8')) {
      cleanNumber = '998' + cleanNumber.slice(1);
    }

    // Если не начинается с 998, добавляем 998
    if (!cleanNumber.startsWith('998') && cleanNumber.length > 0) {
      // Если начинается с 9 (без кода страны), добавляем 998
      if (cleanNumber.startsWith('9')) {
        cleanNumber = '998' + cleanNumber;
      } else {
        cleanNumber = '998' + cleanNumber;
      }
    }

    // Ограничиваем до 12 цифр (998 + 9 цифр)
    cleanNumber = cleanNumber.slice(0, 12);

    // Форматируем в маску +998 XX XXX XX XX
    if (cleanNumber.length === 0) return '';
    if (cleanNumber.length <= 3) return `+${cleanNumber}`;
    if (cleanNumber.length <= 5) return `+998 (${cleanNumber.slice(3)}`;
    if (cleanNumber.length <= 8) return `+998 (${cleanNumber.slice(3, 5)}) ${cleanNumber.slice(5)}`;
    if (cleanNumber.length <= 10) return `+998 (${cleanNumber.slice(3, 5)}) ${cleanNumber.slice(5, 8)}-${cleanNumber.slice(8)}`;
    return `+998 (${cleanNumber.slice(3, 5)}) ${cleanNumber.slice(5, 8)}-${cleanNumber.slice(8, 10)}-${cleanNumber.slice(10)}`;
  };

  // ✅ Обработчик изменения телефона с форматированием
  const handlePhoneChange = (e) => {
    const input = e.target.value;
    const formatted = formatUzbekPhone(input);
    if (error) {
      setError(null);
    }

    // Обновляем состояние с отформатированным значением для отображения
    setFormData(prev => ({
      ...prev,
      phone: formatted
    }));
  };

  const formatWaitTime = (minutes) => {
    if (minutes < 60) {
      return t('misc.qj_wait_minutes', { minutes });
    }
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return t('misc.qj_wait_hours_minutes', { hours, mins });
  };

  const formatCountdown = (seconds) => {
    if (!seconds) return '00:00:00';

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
      return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
  };

  const pageBaseStyle = {
    background: 'var(--mac-gradient-window)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
  };

  const glassCardStyle = {
    background: 'var(--mac-card-bg)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    borderRadius: 'var(--mac-radius-xl)',
    boxShadow: 'var(--mac-main-shell-shadow)',
    border: '1px solid var(--mac-card-border)',
    padding: 'var(--mac-spacing-8) var(--mac-spacing-6)'
  };

  const titleStyle = {
    fontSize: 'var(--mac-font-size-2xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    marginBottom: 'var(--mac-spacing-2)',
    letterSpacing: '-0.02em'
  };

  const bodyTextStyle = {
    fontSize: 'var(--mac-font-size-lg)',
    color: 'var(--mac-text-secondary)',
    lineHeight: '1.5'
  };

  const mutedCaptionStyle = {
    fontSize: 'var(--mac-font-size-sm)',
    color: 'var(--mac-text-tertiary)',
    fontWeight: 'var(--mac-font-weight-medium)'
  };

  const statusActionStackStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--mac-spacing-3)'
  };

  const recoveryButtonBaseStyle = {
    width: '100%',
    padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
    borderRadius: 'var(--mac-radius-lg)',
    border: 'none',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    cursor: 'pointer',
    transition: 'background 0.2s ease, box-shadow 0.2s ease'
  };

  const primaryRecoveryButtonStyle = {
    ...recoveryButtonBaseStyle,
    background: 'var(--mac-accent-blue)',
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-accent), transparent 70%)'
  };

  const dangerRecoveryButtonStyle = {
    ...recoveryButtonBaseStyle,
    background: 'var(--mac-error)',
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-error), transparent 70%)'
  };

  const successRecoveryButtonStyle = {
    ...recoveryButtonBaseStyle,
    background: 'var(--mac-success)',
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-success), transparent 70%)'
  };

  // Компонент загрузки - macOS стиль
  if (step === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 qj-page-base">
        <div className="max-w-md w-full text-center qj-glass-card">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4 qj-spinner"></div>
          <h2 className="qj-title">{t('misc.qj_loading_title')}</h2>
          <p className="qj-body-text">{t('misc.qj_loading_info')}</p>
        </div>
      </div>
    );
  }

  // Компонент ошибки - macOS стиль
  if (step === 'error') {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 qj-page-base" aria-labelledby="queue-join-error-title">
        <div className="max-w-md w-full text-center qj-glass-card" aria-describedby="queue-join-error-message">
          <AlertCircle style={{
            width: '64px',
            height: '64px',
            color: 'var(--mac-error)',
            margin: '0 auto 16px'
          }} aria-hidden="true" />
          <h2 id="queue-join-error-title" className="qj-title">{t('common.error')}</h2>
          <p className="qj-body-text-mb6" id="queue-join-error-message" role="alert" aria-live="assertive">{error}</p>
          <div className="qj-action-stack">
            <button
              type="button"
              onClick={() => {
                setError(null);
                loadTokenInfo();
              }}
              className="qj-recovery-btn qj-recovery-btn-primary"
            >
              {t('misc.qj_retry_btn')}
            </button>
            <button
              type="button"
              onClick={() => navigate('/')}
              className="qj-recovery-btn qj-recovery-btn-danger"
            >
              {t('misc.qj_home_btn')}
            </button>
          </div>
        </div>
      </main>
    );
  }

  // Компонент ожидания открытия очереди - macOS стиль
  if (step === 'waiting') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 qj-page-base">
        <div className="max-w-md w-full text-center qj-glass-card">
          <Clock style={{
            width: '64px',
            height: '64px',
            color: 'var(--mac-warning)',
            margin: '0 auto 20px',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
          }} />
          <h2 style={{
            fontSize: 'var(--mac-font-size-3xl)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-3)',
            letterSpacing: '-0.02em'
          }}>{t('misc.qj_waiting_title')}</h2>
          <p className="qj-body-text-mb6">
            {t('misc.qj_waiting_will_open_at', { time: queueInfo?.start_time })}
          </p>

          {/* Обратный отсчет - macOS стиль */}
          <div className="qj-countdown-box">
            <div style={{
              fontSize: '44px',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-warning)',
              marginBottom: 'var(--mac-spacing-2)',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, "Courier New", monospace',
              letterSpacing: '0.02em'
            }}>
              {formatCountdown(countdown)}
            </div>
            <p className="qj-muted-caption">{t('misc.qj_waiting_until_open')}</p>
          </div>

          {/* Информация о враче и кабинете - macOS стиль */}
          <div className="qj-info-list">
            <div className="qj-info-row">
              <div className="flex items-center">
                <User style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                <span className="qj-info-label">{t('misc.qj_label_specialist')}</span>
              </div>
              <span className="qj-info-value">{queueInfo?.specialist_name}</span>
            </div>

            <div className="qj-info-row">
              <div className="flex items-center">
                <MapPin style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                <span className="qj-info-label">{t('misc.qj_label_department')}</span>
              </div>
              <span className="qj-info-value">{queueInfo?.department_name}</span>
            </div>

            <div className="qj-info-row-accent">
              <div className="flex items-center">
                <Calendar style={{ width: '18px', height: '18px', color: 'var(--mac-accent-blue)', marginRight: 'var(--mac-spacing-2)' }} />
                <span className="qj-info-label-accent">{t('misc.qj_label_appointment_day')}</span>
              </div>
              <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-accent-blue)' }}>
                {queueInfo?.target_date ? new Date(queueInfo.target_date).toLocaleDateString('ru-RU', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                }) : t('misc.qj_today')}
              </span>
            </div>
          </div>

          <div className="qj-hint">
            <p >{t('misc.qj_waiting_keep_open')}</p>
            <p>{t('misc.qj_waiting_auto_redirect')}</p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => navigate('/')}
              className="qj-btn-secondary"
              onMouseEnter={(e) => e.target.style.background = 'color-mix(in srgb, var(--mac-text-tertiary), transparent 82%)'}
              onMouseLeave={(e) => e.target.style.background = 'color-mix(in srgb, var(--mac-text-tertiary), transparent 88%)'}
            >
              {t('misc.qj_home_btn')}
            </button>
            <button
              onClick={loadTokenInfo}
              className="qj-btn-primary"
              onMouseEnter={(e) => e.target.style.background = 'var(--mac-accent-blue-hover)'}
              onMouseLeave={(e) => e.target.style.background = 'var(--mac-accent-blue)'}
            >
              {t('misc.qj_refresh_btn')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Компонент успешного присоединения - macOS стиль
  if (step === 'success') {
    // Проверяем, множественная ли регистрация
    const isMultiple = result.entries && Array.isArray(result.entries) && result.entries.length > 1;

    // Определяем название вкладки для подсказки пользователю
    const getDepartmentName = (specialty) => {
      const normalized = (specialty || '').toLowerCase();
      if (normalized === 'cardio' || normalized === 'cardiology') return t('misc.qj_dept_cardiology');
      if (normalized === 'derma' || normalized === 'dermatology') return t('misc.qj_dept_dermatology');
      if (normalized === 'dentist' || normalized === 'dentistry' || normalized === 'stomatology') return t('misc.qj_dept_dentistry');
      if (normalized === 'lab' || normalized === 'laboratory') return t('misc.qj_dept_laboratory');
      return t('misc.qj_dept_default');
    };

    const departmentName = getDepartmentName(result.entries?.[0]?.department || result.entries?.[0]?.specialty);

    return (
      <main className="min-h-screen flex items-center justify-center p-4 qj-page-base" aria-labelledby="queue-join-success-title">
        <div className="max-w-md w-full text-center qj-glass-card" role="status" aria-live="polite">
          <CheckCircle style={{
            width: '64px',
            height: '64px',
            color: 'var(--mac-success)',
            margin: '0 auto 20px'
          }} aria-hidden="true" />
          <h2 id="queue-join-success-title" className="qj-title-success">
            {isMultiple ? t('misc.qj_success_multiple_title') : t('misc.qj_success_single_title')}
          </h2>

          {isMultiple ? (
            // Множественная регистрация
            <>
              <div className="qj-success-box">
                <p className="qj-success-entries-title">
                  {t('misc.qj_success_registered_in', { count: result.entries.length })}
                </p>
                <div className="qj-success-entries-list">
                  {result.entries.map((entry, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: 'var(--mac-spacing-4)',
                        background: 'color-mix(in srgb, var(--mac-card-bg), transparent 16%)',
                        borderRadius: 'var(--mac-radius-lg)',
                        border: '1px solid color-mix(in srgb, var(--mac-success), transparent 72%)'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-3)' }}>
                        <span style={{ fontSize: 'var(--mac-font-size-3xl)' }}>{entry.icon || null}</span>
                        <div>
                          <div style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                            {entry.specialist_name || entry.department || t('misc.qj_specialist_n', { n: idx + 1 })}
                          </div>
                          <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', marginTop: 'var(--mac-spacing-1)' }}>
                            {t('misc.qj_time_value', { value: entry.queue_time ? formatRegistrarTime(entry.queue_time, 'ru-RU') : '—' })}
                          </div>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 'var(--mac-font-size-3xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-success)' }}>№{entry.queue_number || entry.number || '—'}</div>
                        <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>{t('misc.qj_in_queue')}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-tertiary)',
                marginBottom: 'var(--mac-spacing-6)',
                lineHeight: '1.5'
              }}>
                <p>{t('misc.qj_be_ready')}</p>
                <p>{t('misc.qj_we_will_notify')}</p>
                <p style={{ marginTop: 'var(--mac-spacing-3)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-accent-blue)' }}>
                  {t('misc.qj_view_entries_tabs')}
                </p>
              </div>
            </>
          ) : (
            // Одиночная регистрация
            <>
              <div className="qj-success-box-lg">
                <div className="qj-success-number">
                  №{result.queue_number}
                </div>
                <p className="qj-success-label">{t('misc.qj_your_number')}</p>
              </div>

              <div className="qj-info-list">
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                  background: 'var(--mac-bg-secondary)',
                  borderRadius: 'var(--mac-radius-lg)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <Users style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                    <span className="qj-info-label">{t('misc.qj_ahead_of_you')}</span>
                  </div>
                  <span className="qj-info-value">{t('misc.qj_count_short', { count: result.queue_number - 1 })}</span>
                </div>

                {result.estimated_wait_time && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                    background: 'var(--mac-bg-secondary)',
                    borderRadius: 'var(--mac-radius-lg)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <Timer style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                      <span className="qj-info-label">{t('misc.qj_waiting_label')}</span>
                    </div>
                    <span className="qj-info-value">{formatWaitTime(result.estimated_wait_time)}</span>
                  </div>
                )}

                {result.specialist_name && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                    background: 'var(--mac-bg-secondary)',
                    borderRadius: 'var(--mac-radius-lg)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <User style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                      <span className="qj-info-label">{t('misc.qj_label_specialist')}</span>
                    </div>
                    <span className="qj-info-value">{result.specialist_name}</span>
                  </div>
                )}
              </div>

              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-tertiary)',
                marginBottom: 'var(--mac-spacing-6)',
                lineHeight: '1.5'
              }}>
                <p>{t('misc.qj_be_ready')}</p>
                <p>{t('misc.qj_we_will_notify')}</p>
                <p style={{ marginTop: 'var(--mac-spacing-3)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-accent-blue)' }}>
                  {t('misc.qj_view_entry_tab', { name: departmentName })}
                </p>
              </div>
            </>
          )}

          <button
            onClick={() => navigate('/')}
            type="button"
            className="qj-recovery-btn qj-recovery-btn-success"
          >
            {t('misc.qj_ok_btn')}
          </button>
        </div>
      </main>
    );
  }

  // Основной интерфейс (info + form) - macOS стиль
  return (
    <div className="min-h-screen flex items-center justify-center p-4 qj-page-base">
      <div
        aria-live="polite"
        className="qj-sr-only"
      >
        {step === 'select-specialists' && t('misc.qj_sr_select_specialists_step')}
        {step === 'form' && t('misc.qj_sr_form_step')}
        {step === 'info' && t('misc.qj_sr_info_step')}
      </div>
      <div className="max-w-md w-full overflow-hidden qj-glass-card">

        {/* Заголовок с информацией об очереди - macOS стиль с правильным spacing */}
        <div className="text-white qj-main-header">
          <h1 className="qj-main-title">{t('misc.qj_main_title')}</h1>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div className="flex items-center" style={{ opacity: 0.95 }}>
              <MapPin style={{ width: '16px', height: '16px', marginRight: 'var(--mac-spacing-2)', flexShrink: 0 }} />
              <span style={{ fontSize: 'var(--mac-font-size-base)', lineHeight: '1.4' }}>{queueInfo?.department_name || t('misc.qj_general_practice')}</span>
            </div>

            <div className="flex items-center" style={{ opacity: 0.9 }}>
              <User style={{ width: '16px', height: '16px', marginRight: 'var(--mac-spacing-2)', flexShrink: 0 }} />
              <span style={{ fontSize: 'var(--mac-font-size-sm)', lineHeight: '1.4' }}>{queueInfo?.specialist_name}</span>
            </div>

            {queueInfo?.target_date && (
              <div className="flex items-center" style={{
                marginTop: 'var(--mac-spacing-2)',
                paddingTop: '12px',
                borderTop: '1px solid color-mix(in srgb, var(--mac-text-on-accent), transparent 80%)',
                opacity: 0.95
              }}>
                <Calendar style={{ width: '16px', height: '16px', marginRight: 'var(--mac-spacing-2)', flexShrink: 0 }} />
                <span style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  lineHeight: '1.4'
                }}>
                  {t('misc.qj_appointment_day_value', { date: new Date(queueInfo.target_date).toLocaleDateString('ru-RU', {
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric'
                  }) })}
                </span>
              </div>
            )}
          </div>
        </div>

        {step === 'select-specialists' && (
          <div className="qj-select-section">
            <div style={{
              marginBottom: 'var(--mac-spacing-6)',
              textAlign: 'center'
            }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                marginBottom: 'var(--mac-spacing-2)',
                letterSpacing: '-0.02em'
              }}>
                {/* P-024 fix: previously "Мутахассисларни танланг" (UZ) while the
                    rest of the screen is Russian — mixed i18n on a public kiosk flow.
                    Unified to Russian to match the surrounding copy. */}
                {t('misc.qj_select_specialists_title')}
              </h3>
              <p style={{
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-lg)',
                lineHeight: '1.5',
                margin: 0
              }}>
                {t('misc.qj_select_specialists_hint')}
              </p>
            </div>

            {/* Чекбоксы специалистов */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--mac-spacing-3)',
              marginBottom: 'var(--mac-spacing-6)'
            }}>
              {isSpecialistsLoading ? (
                <div style={{
                  padding: 'var(--mac-spacing-4)',
                  textAlign: 'center',
                  color: 'var(--mac-text-secondary)',
                  fontSize: 'var(--mac-font-size-lg)'
                }}>
                  {/* UX Audit Registrar #2: унифицирован i18n — был UZ, теперь RU. */}
                  {t('misc.qj_loading_specialists')}
                </div>
              ) : availableSpecialists.length === 0 ? (
                <div style={{
                  padding: '18px 16px',
                  textAlign: 'center',
                  color: 'var(--mac-text-secondary)',
                  fontSize: 'var(--mac-font-size-base)',
                  borderRadius: 'var(--mac-radius-lg)',
                  border: '1px dashed color-mix(in srgb, var(--mac-text-secondary), transparent 72%)',
                  background: 'color-mix(in srgb, var(--mac-bg-secondary), transparent 10%)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px'
                }}>
                  <span> {/* UX Audit Registrar #2: был UZ, теперь RU. */} {t('misc.qj_no_specialists')}</span>
                  <button
                    type="button"
                    onClick={loadTokenInfo}
                    style={{
                      alignSelf: 'center',
                      background: 'var(--mac-accent-blue)',
                      color: 'var(--mac-text-on-accent)',
                      border: 'none',
                      borderRadius: 'var(--mac-radius-md)',
                      padding: '8px 14px',
                      fontSize: 'var(--mac-font-size-sm)',
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'var(--mac-accent-blue-hover)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'var(--mac-accent-blue)';
                    }}
                  >
                    {t('misc.qj_refresh_btn')}
                  </button>
                </div>
              ) : (
                availableSpecialists.map(specialist => {
                  const isSelected = selectedSpecialists.includes(specialist.id);
                  return (
                    <label
                      key={specialist.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: 'var(--mac-spacing-4)',
                        borderRadius: 'var(--mac-radius-lg)',
                        border: `2px solid ${isSelected ? specialist.color : 'var(--mac-border)'}`,
                        background: isSelected ?
                          `color-mix(in srgb, ${specialist.color}, transparent 85%)` :
                          'var(--mac-card-bg)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        userSelect: 'none'
                      }}
                    >
                      <Checkbox aria-label={`Select specialist: ${formatSpecialistLabel(specialist)}`} checked={isSelected} onChange={() => {
                          if (error) {
                            setError(null);
                          }
                          if (isSelected) {
                            setSelectedSpecialists(prev => prev.filter(id => id !== specialist.id));
                          } else {
                            setSelectedSpecialists(prev => [...prev, specialist.id]);
                          }
                        }}
                        style={{
                          width: '24px',
                          height: '24px',
                          marginRight: 'var(--mac-spacing-3)',
                          accentColor: specialist.color,
                          cursor: 'pointer'
                        }}
                      />
                      <span style={{ fontSize: 'var(--mac-font-size-3xl)', marginRight: 'var(--mac-spacing-3)' }}>{specialist.icon}</span>
                      <span style={{
                        fontSize: 'var(--mac-font-size-xl)',
                        fontWeight: 'var(--mac-font-weight-semibold)',
                        color: isSelected ? specialist.color : 'var(--mac-text-primary)'
                      }}>
                        {formatSpecialistLabel(specialist)}
                      </span>
                    </label>
                  );
                })
              )}
            </div>

            {/* Кнопка продолжить */}
            <button
              onClick={() => {
                if (selectedSpecialists.length === 0) {
                  setError(QUEUE_JOIN_MESSAGES.selectSpecialist);
                  setTimeout(() => setError(null), 3000);
                  return;
                }
                setError(null);
                setStep('form');
              }}
              disabled={selectedSpecialists.length === 0}
              style={{
                width: '100%',
                background: selectedSpecialists.length > 0 ? 'var(--mac-accent-blue)' : 'var(--mac-border)',
                color: selectedSpecialists.length > 0 ? 'var(--mac-text-on-accent)' : 'var(--mac-text-tertiary)',
                padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
                borderRadius: 'var(--mac-radius-lg)',
                border: 'none',
                fontSize: 'var(--mac-font-size-xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                cursor: selectedSpecialists.length > 0 ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s ease',
                boxShadow: selectedSpecialists.length > 0 ? '0 4px 12px color-mix(in srgb, var(--mac-accent), transparent 70%)' : 'none'
              }}
              onMouseEnter={(e) => {
                if (selectedSpecialists.length > 0) {
                  e.target.style.background = 'var(--mac-accent-blue-hover)';
                }
              }}
              onMouseLeave={(e) => {
                if (selectedSpecialists.length > 0) {
                  e.target.style.background = 'var(--mac-accent-blue)';
                }
              }}
            >
              {t('misc.qj_continue_with_count', { count: selectedSpecialists.length })}
            </button>

            {error && (
              <div className="qj-error-banner" role="alert" aria-live="assertive">
                {error}
              </div>
            )}
          </div>
        )}

        {step === 'info' && (
          <div className="qj-select-section">
            {/* Статус очереди - macOS стиль с правильным spacing */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 'var(--mac-spacing-4)',
              marginBottom: 'var(--mac-spacing-6)'
            }}>
              <div style={{
                background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-accent), transparent 88%) 0%, color-mix(in srgb, var(--mac-accent), transparent 93%) 100%)',
                borderRadius: 'var(--mac-radius-xl)',
                padding: '24px 20px',
                border: '1px solid color-mix(in srgb, var(--mac-accent), transparent 76%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '140px'
              }}>
                <Users style={{
                  width: '32px',
                  height: '32px',
                  color: 'var(--mac-accent-blue)',
                  marginBottom: 'var(--mac-spacing-3)'
                }} />
                <div style={{
                  fontSize: '36px',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-accent-blue)',
                  letterSpacing: '-0.02em',
                  lineHeight: '1',
                  marginBottom: 'var(--mac-spacing-2)'
                }}>{queueInfo?.queue_length || 0}</div>
                <div style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-tertiary)',
                  fontWeight: 'var(--mac-font-weight-medium)'
                }}>{t('misc.qj_in_queue')}</div>
              </div>

              <div style={{
                background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-success), transparent 88%) 0%, color-mix(in srgb, var(--mac-success), transparent 93%) 100%)',
                borderRadius: 'var(--mac-radius-xl)',
                padding: '24px 20px',
                border: '1px solid color-mix(in srgb, var(--mac-success), transparent 76%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '140px'
              }}>
                <Clock style={{
                  width: '32px',
                  height: '32px',
                  color: 'var(--mac-success)',
                  marginBottom: 'var(--mac-spacing-3)'
                }} />
                <div style={{
                  fontSize: '36px',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-success)',
                  letterSpacing: '-0.02em',
                  lineHeight: '1',
                  marginBottom: 'var(--mac-spacing-2)'
                }}>~{(queueInfo?.queue_length || 0) * 15}</div>
                <div style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-tertiary)',
                  fontWeight: 'var(--mac-font-weight-medium)'
                }}>{t('misc.qj_estimated_wait')}</div>
              </div>
            </div>

            {/* Текст и кнопка с правильными отступами */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              gap: 'var(--mac-spacing-5)'
            }}>
              <p style={{
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-lg)',
                lineHeight: '1.5',
                margin: 0,
                maxWidth: '320px'
              }}>
                {t('misc.qj_fill_form_hint')}
              </p>
              <button
                onClick={() => setStep('form')}
                style={{
                  width: '100%',
                  background: 'var(--mac-accent-blue)',
                  color: 'var(--mac-text-on-accent)',
                  padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
                  borderRadius: 'var(--mac-radius-lg)',
                  border: 'none',
                  fontSize: 'var(--mac-font-size-xl)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-accent), transparent 70%)'
                }}
                onMouseEnter={(e) => e.target.style.background = 'var(--mac-accent-blue-hover)'}
                onMouseLeave={(e) => e.target.style.background = 'var(--mac-accent-blue)'}
              >
                {t('misc.qj_continue_btn')}
              </button>
            </div>
          </div>
        )}

        {step === 'form' && (
          <div className="qj-select-section">
            <form onSubmit={handleFormSubmit} className="qj-form">
              {/* ФИО - macOS стиль */}
              <div>
                <label
                  htmlFor="queue-patient-name"
                  className="qj-form-label"
                >
                  {t('misc.qj_form_label_full_name')}
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: 'var(--mac-text-tertiary)' }} />
                  <Input
                    id="queue-patient-name"
                    name="patient_name"
                    type="text"
                    aria-label={t('misc.qj_form_aria_full_name')}
                    value={formData.patientName}
                    onChange={(e) => handleInputChange('patientName', e.target.value)}
                    style={{
                      width: '100%',
                      paddingLeft: '40px',
                      paddingRight: '16px',
                      paddingTop: '12px',
                      paddingBottom: '12px',
                      border: '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)',
                      borderRadius: 'var(--mac-radius-lg)',
                      fontSize: 'var(--mac-font-size-xl)',
                      fontFamily: 'inherit',
                      background: 'var(--mac-bg-secondary)',
                      transition: 'all 0.2s ease',
                      outline: 'none',
                      color: 'var(--mac-text-primary)'
                    }}
                    onFocus={(e) => {
                      e.target.style.border = '1px solid var(--mac-accent)';
                      e.target.style.boxShadow = '0 0 0 3px color-mix(in srgb, var(--mac-accent), transparent 86%)';
                    }}
                    onBlur={(e) => {
                      e.target.style.border = '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)';
                      e.target.style.boxShadow = 'none';
                    }}
                    placeholder={t('misc.qj_form_placeholder_full_name')}
                    autoComplete="name"
                    autoFocus
                    aria-required="true"
                    aria-invalid={Boolean(error && !formData.patientName.trim())}
                    aria-describedby={error ? 'queue-join-error' : undefined}
                    required
                  />
                </div>
              </div>

              {/* Телефон - macOS стиль с форматированием */}
              <div>
                <label
                  htmlFor="queue-phone"
                  className="qj-form-label"
                >
                  {t('misc.qj_form_label_phone')}
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: 'var(--mac-text-tertiary)' }} />
                  <Input
                    id="queue-phone"
                    name="phone"
                    type="tel"
                    aria-label={t('misc.qj_form_aria_phone')}
                    value={formData.phone}
                    onChange={handlePhoneChange}
                    onKeyDown={(e) => {
                      // Разрешаем: цифры, Backspace, Delete, стрелки, Tab, Enter
                      const allowedKeys = [
                        'Backspace', 'Delete', 'ArrowLeft', 'ArrowRight',
                        'ArrowUp', 'ArrowDown', 'Tab', 'Enter', 'Home', 'End'
                      ];

                      if (allowedKeys.includes(e.key) || e.ctrlKey || e.metaKey) {
                        return;
                      }

                      // Разрешаем только цифры и + в начале
                      if (!/\d/.test(e.key) && !(e.key === '+' && e.target.selectionStart === 0)) {
                        e.preventDefault();
                      }
                    }}
                    onPaste={(e) => {
                      e.preventDefault();
                      const pastedText = e.clipboardData.getData('text');
                      const formatted = formatUzbekPhone(pastedText);
                      setFormData(prev => ({
                        ...prev,
                        phone: formatted
                      }));
                    }}
                    style={{
                      width: '100%',
                      paddingLeft: '40px',
                      paddingRight: '16px',
                      paddingTop: '12px',
                      paddingBottom: '12px',
                      border: '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)',
                      borderRadius: 'var(--mac-radius-lg)',
                      fontSize: 'var(--mac-font-size-xl)',
                      fontFamily: 'inherit',
                      background: 'var(--mac-bg-secondary)',
                      transition: 'all 0.2s ease',
                      outline: 'none',
                      color: 'var(--mac-text-primary)'
                    }}
                    onFocus={(e) => {
                      e.target.style.border = '1px solid var(--mac-accent)';
                      e.target.style.boxShadow = '0 0 0 3px color-mix(in srgb, var(--mac-accent), transparent 86%)';
                    }}
                    onBlur={(e) => {
                      e.target.style.border = '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)';
                      e.target.style.boxShadow = 'none';
                    }}
                    placeholder="+998 (90) 123-45-67"
                    autoComplete="tel"
                    inputMode="tel"
                    aria-required="true"
                    aria-invalid={Boolean(error && !formData.phone.trim())}
                    aria-describedby={error ? 'queue-join-error queue-phone-hint' : 'queue-phone-hint'}
                    required
                  />
                </div>
                <div id="queue-phone-hint" style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', marginTop: 'var(--mac-spacing-1)' }}>
                  {t('misc.qj_form_phone_format')}
                </div>
              </div>

              {/* Telegram ID (опционально) - macOS стиль */}
              <div>
                <label
                  htmlFor="queue-telegram-id"
                  className="qj-form-label"
                >
                  {t('misc.qj_form_label_telegram')}
                </label>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', marginBottom: 'var(--mac-spacing-2)' }}>
                  {t('misc.qj_form_hint_telegram')}
                </div>
                <Input
                  id="queue-telegram-id"
                  name="telegram_id"
                  type="number"
                  aria-label={t('misc.qj_form_aria_telegram')}
                  value={formData.telegramId}
                  onChange={(e) => handleInputChange('telegramId', e.target.value)}
                  style={{
                    width: '100%',
                    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                    border: '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)',
                    borderRadius: 'var(--mac-radius-lg)',
                    fontSize: 'var(--mac-font-size-xl)',
                    fontFamily: 'inherit',
                    background: 'var(--mac-bg-secondary)',
                    transition: 'all 0.2s ease',
                    outline: 'none',
                    color: 'var(--mac-text-primary)'
                  }}
                  onFocus={(e) => {
                    e.target.style.border = '1px solid var(--mac-accent)';
                    e.target.style.boxShadow = '0 0 0 3px color-mix(in srgb, var(--mac-accent), transparent 86%)';
                  }}
                  onBlur={(e) => {
                    e.target.style.border = '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)';
                    e.target.style.boxShadow = 'none';
                  }}
                  placeholder={t('misc.qj_form_placeholder_optional')}
                />
              </div>

              {error && (
                <div style={{
                  background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-error), transparent 88%) 0%, color-mix(in srgb, var(--mac-error), transparent 93%) 100%)',
                  border: '1px solid color-mix(in srgb, var(--mac-error), transparent 72%)',
                  borderRadius: 'var(--mac-radius-lg)',
                  padding: 'var(--mac-spacing-3)'
                }} id="queue-join-error" role="alert" aria-live="assertive">
                  <div className="flex items-center">
                    <AlertCircle className="h-5 w-5 mr-2" style={{ color: 'var(--mac-error)' }} />
                    <span style={{ color: 'var(--mac-error)', fontSize: 'var(--mac-font-size-base)' }}>{error}</span>
                  </div>
                </div>
              )}

              {/* Кнопки - macOS стиль */}
              <div className="flex" style={{ gap: 'var(--mac-spacing-3)', paddingTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => setStep('info')}
                  style={{
                    flex: 1,
                    background: 'color-mix(in srgb, var(--mac-text-tertiary), transparent 88%)',
                    color: 'var(--mac-accent-blue)',
                    padding: '14px 20px',
                    borderRadius: 'var(--mac-radius-lg)',
                    border: 'none',
                    fontSize: 'var(--mac-font-size-xl)',
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={(e) => e.target.style.background = 'color-mix(in srgb, var(--mac-text-tertiary), transparent 82%)'}
                  onMouseLeave={(e) => e.target.style.background = 'color-mix(in srgb, var(--mac-text-tertiary), transparent 88%)'}
                >
                  {t('misc.qj_back_btn')}
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    background: loading ? 'var(--mac-text-tertiary)' : 'var(--mac-accent-blue)',
                    color: 'var(--mac-text-on-accent)',
                    padding: '14px 20px',
                    borderRadius: 'var(--mac-radius-lg)',
                    border: 'none',
                    fontSize: 'var(--mac-font-size-xl)',
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: loading ? 'none' : '0 4px 12px color-mix(in srgb, var(--mac-accent), transparent 70%)'
                  }}
                  onMouseEnter={(e) => !loading && (e.target.style.background = 'var(--mac-accent-blue-hover)')}
                  onMouseLeave={(e) => !loading && (e.target.style.background = 'var(--mac-accent-blue)')}
                >
                  {loading ? t('misc.qj_joining_btn') : t('misc.qj_join_btn')}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

export default QueueJoin;
