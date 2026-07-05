import { useState, useEffect, useCallback } from 'react';
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
import {
  fetchQrTokenInfo,
  startQueueJoinSession,
  completeQueueJoinSession,
} from '../api/queue';
import { formatRegistrarTime } from '../utils/dateUtils';
import { Input,
  Checkbox } from '../components/ui/macos';

const formatSpecialistLabel = (specialist) => {
  const doctorName =
    specialist?.doctor_name ||
    specialist?.full_name ||
    specialist?.name ||
    specialist?.specialty_display ||
    specialist?.specialty ||
    'Специалист';
  const specialtyLabel =
    specialist?.specialty_display ||
    specialist?.specialty ||
    '';
  const cabinetLabel = specialist?.cabinet ? `Каб. ${specialist.cabinet}` : '';

  return [doctorName, specialtyLabel, cabinetLabel]
    .filter(Boolean)
    .join(' • ');
};

const MISSING_QUEUE_TOKEN_MESSAGE = 'QR-код не найден. Откройте ссылку из клиники или отсканируйте QR-код заново.';
const QUEUE_JOIN_MESSAGES = {
  sessionStartFailed: 'Не удалось начать сессию очереди.',
  registrationUnavailable: 'Запись в очередь недоступна.',
  qrTokenUnavailable: 'QR-токен не найден или срок его действия истек.',
  requiredFields: 'Заполните обязательные поля.',
  sessionExpired: 'Сессия очереди истекла. Создаем новую сессию...',
  sessionCreateFailed: 'Не удалось создать сессию очереди. Обновите страницу.',
  nameTooShort: 'Введите полное имя пациента (минимум 2 символа).',
  nameTooLong: 'ФИО слишком длинное (максимум 200 символов).',
  phoneTooShort: 'Телефон указан не полностью (минимум 12 цифр: +998 XX XXX XX XX).',
  phoneTooLong: 'Телефон слишком длинный (максимум 12 цифр).',
  missingSessionToken: 'Сессия очереди недоступна или истекла. Обновите страницу.',
  joinFailed: 'Не удалось присоединиться к очереди.',
  selectSpecialist: 'Выберите специалиста.',
};

const QueueJoin = () => {
  const { token: paramToken } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

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
  });
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

    } catch (error) {
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

    } catch (error) {
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

    } catch (error) {
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
      return `${minutes} мин`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours} соат ${mins} мин`;
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
      <div className="min-h-screen flex items-center justify-center p-4" style={pageBaseStyle}>
        <div className="max-w-md w-full text-center" style={glassCardStyle}>
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" style={{
            borderColor: 'var(--mac-accent-blue)'
          }}></div>
          <h2 style={titleStyle}>Загрузка...</h2>
          <p style={bodyTextStyle}>Информация об очереди</p>
        </div>
      </div>
    );
  }

  // Компонент ошибки - macOS стиль
  if (step === 'error') {
    return (
      <main className="min-h-screen flex items-center justify-center p-4" style={pageBaseStyle} aria-labelledby="queue-join-error-title">
        <div className="max-w-md w-full text-center" style={glassCardStyle} aria-describedby="queue-join-error-message">
          <AlertCircle style={{
            width: '64px',
            height: '64px',
            color: 'var(--mac-error)',
            margin: '0 auto 16px'
          }} aria-hidden="true" />
          <h2 id="queue-join-error-title" style={{
            ...titleStyle,
            marginBottom: 'var(--mac-spacing-3)',
          }}>Ошибка</h2>
          <p style={{
            ...bodyTextStyle,
            marginBottom: 'var(--mac-spacing-6)',
          }} id="queue-join-error-message" role="alert" aria-live="assertive">{error}</p>
          <div style={statusActionStackStyle}>
            <button
              type="button"
              onClick={() => {
                setError(null);
                loadTokenInfo();
              }}
              style={primaryRecoveryButtonStyle}
            >
              Попробовать снова
            </button>
            <button
              type="button"
              onClick={() => navigate('/')}
              style={dangerRecoveryButtonStyle}
            >
              Главная страница
            </button>
          </div>
        </div>
      </main>
    );
  }

  // Компонент ожидания открытия очереди - macOS стиль
  if (step === 'waiting') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={pageBaseStyle}>
        <div className="max-w-md w-full text-center" style={glassCardStyle}>
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
          }}>Очередь скоро откроется</h2>
          <p style={{
            ...bodyTextStyle,
            marginBottom: 'var(--mac-spacing-6)',
          }}>
            Запись в очередь откроется в {queueInfo?.start_time}
          </p>

          {/* Обратный отсчет - macOS стиль */}
          <div style={{
            background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-warning), transparent 88%) 0%, color-mix(in srgb, var(--mac-warning), transparent 93%) 100%)',
            borderRadius: 'var(--mac-radius-xl)',
            padding: 'var(--mac-spacing-6)',
            marginBottom: 'var(--mac-spacing-6)',
            border: '1px solid color-mix(in srgb, var(--mac-warning), transparent 76%)'
          }}>
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
            <p style={mutedCaptionStyle}>до открытия записи</p>
          </div>

          {/* Информация о враче и кабинете - macOS стиль */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)', marginBottom: 'var(--mac-spacing-6)' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
              background: 'var(--mac-bg-secondary)',
              borderRadius: 'var(--mac-radius-lg)'
            }}>
              <div className="flex items-center">
                <User style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                <span style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>Специалист</span>
              </div>
              <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>{queueInfo?.specialist_name}</span>
            </div>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
              background: 'var(--mac-bg-secondary)',
              borderRadius: 'var(--mac-radius-lg)'
            }}>
              <div className="flex items-center">
                <MapPin style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                <span style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>Бўлим</span>
              </div>
              <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>{queueInfo?.department_name}</span>
            </div>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
              background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-accent), transparent 88%) 0%, color-mix(in srgb, var(--mac-accent), transparent 93%) 100%)',
              borderRadius: 'var(--mac-radius-lg)',
              border: '1px solid color-mix(in srgb, var(--mac-accent), transparent 76%)'
            }}>
              <div className="flex items-center">
                <Calendar style={{ width: '18px', height: '18px', color: 'var(--mac-accent-blue)', marginRight: 'var(--mac-spacing-2)' }} />
                <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-accent-blue)' }}>День приёма</span>
              </div>
              <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-accent-blue)' }}>
                {queueInfo?.target_date ? new Date(queueInfo.target_date).toLocaleDateString('ru-RU', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                }) : 'Сегодня'}
              </span>
            </div>
          </div>

          <div style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-tertiary)',
            marginBottom: 'var(--mac-spacing-6)',
            textAlign: 'center',
            lineHeight: '1.5'
          }}>
            <p style={{ marginBottom: 'var(--mac-spacing-2)' }}>Не закрывайте эту страницу</p>
            <p>Когда запись откроется, вы будете автоматически перенаправлены</p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => navigate('/')}
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
              Главная страница
            </button>
            <button
              onClick={loadTokenInfo}
              style={{
                flex: 1,
                background: 'var(--mac-accent-blue)',
                color: 'var(--mac-text-on-accent)',
                padding: '14px 20px',
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
              Обновить
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
      if (normalized === 'cardio' || normalized === 'cardiology') return 'Кардиология';
      if (normalized === 'derma' || normalized === 'dermatology') return 'Дерматология';
      if (normalized === 'dentist' || normalized === 'dentistry' || normalized === 'stomatology') return 'Стоматология';
      if (normalized === 'lab' || normalized === 'laboratory') return 'Лаборатория';
      return 'соответствующей';
    };

    const departmentName = getDepartmentName(result.entries?.[0]?.department || result.entries?.[0]?.specialty);

    return (
      <main className="min-h-screen flex items-center justify-center p-4" style={pageBaseStyle} aria-labelledby="queue-join-success-title">
        <div className="max-w-md w-full text-center" style={glassCardStyle} role="status" aria-live="polite">
          <CheckCircle style={{
            width: '64px',
            height: '64px',
            color: 'var(--mac-success)',
            margin: '0 auto 20px'
          }} aria-hidden="true" />
          <h2 id="queue-join-success-title" style={{
            fontSize: 'var(--mac-font-size-3xl)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-6)',
            letterSpacing: '-0.02em'
          }}>
            {isMultiple ? 'Вы зарегистрированы в очередях!' : 'Вы в очереди!'}
          </h2>

          {isMultiple ? (
            // Множественная регистрация
            <>
              <div style={{
                background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-success), transparent 88%) 0%, color-mix(in srgb, var(--mac-success), transparent 93%) 100%)',
                borderRadius: 'var(--mac-radius-xl)',
                padding: 'var(--mac-spacing-6)',
                marginBottom: 'var(--mac-spacing-6)',
                border: '1px solid color-mix(in srgb, var(--mac-success), transparent 76%)'
              }}>
                <p style={{
                  fontSize: 'var(--mac-font-size-lg)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: 'var(--mac-spacing-4)',
                  textAlign: 'center'
                }}>
                  Вы зарегистрированы в {result.entries.length} очередях:
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
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
                            {entry.specialist_name || entry.department || `Специалист ${idx + 1}`}
                          </div>
                          <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', marginTop: 'var(--mac-spacing-1)' }}>
                            Время: {entry.queue_time ? formatRegistrarTime(entry.queue_time, 'ru-RU') : '—'}
                          </div>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 'var(--mac-font-size-3xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-success)' }}>№{entry.queue_number || entry.number || '—'}</div>
                        <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>в очереди</div>
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
                <p>Пожалуйста, будьте готовы к приёму.</p>
                <p>Мы сообщим вам, когда подойдёт ваша очередь.</p>
                <p style={{ marginTop: 'var(--mac-spacing-3)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-accent-blue)' }}>
                  Записи можно посмотреть во вкладках специалистов
                </p>
              </div>
            </>
          ) : (
            // Одиночная регистрация
            <>
              <div style={{
                background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-success), transparent 88%) 0%, color-mix(in srgb, var(--mac-success), transparent 93%) 100%)',
                borderRadius: 'var(--mac-radius-xl)',
                padding: 'var(--mac-spacing-8) var(--mac-spacing-6)',
                marginBottom: 'var(--mac-spacing-6)',
                border: '1px solid color-mix(in srgb, var(--mac-success), transparent 76%)'
              }}>
                <div style={{
                  fontSize: '48px',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-success)',
                  marginBottom: 'var(--mac-spacing-2)',
                  letterSpacing: '-0.02em'
                }}>
                  №{result.queue_number}
                </div>
                <p style={{ fontSize: 'var(--mac-font-size-lg)', color: 'var(--mac-text-secondary)', fontWeight: 'var(--mac-font-weight-medium)' }}>Ваш номер в очереди</p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)', marginBottom: 'var(--mac-spacing-6)' }}>
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
                    <span style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>Олдингизда</span>
                  </div>
                  <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>{result.queue_number - 1} к.</span>
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
                      <span style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>Кутиш</span>
                    </div>
                    <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>{formatWaitTime(result.estimated_wait_time)}</span>
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
                      <span style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>Специалист</span>
                    </div>
                    <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>{result.specialist_name}</span>
                  </div>
                )}
              </div>

              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-tertiary)',
                marginBottom: 'var(--mac-spacing-6)',
                lineHeight: '1.5'
              }}>
                <p>Пожалуйста, будьте готовы к приёму.</p>
                <p>Мы сообщим вам, когда подойдёт ваша очередь.</p>
                <p style={{ marginTop: 'var(--mac-spacing-3)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-accent-blue)' }}>
                  Запись можно посмотреть во вкладке «{departmentName}»
                </p>
              </div>
            </>
          )}

          <button
            onClick={() => navigate('/')}
            type="button"
            style={successRecoveryButtonStyle}
          >
            Тушунарли
          </button>
        </div>
      </main>
    );
  }

  // Основной интерфейс (info + form) - macOS стиль
  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={pageBaseStyle}>
      <div
        aria-live="polite"
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          margin: -1,
          padding: 0,
          overflow: 'hidden',
          clip: 'rect(0, 0, 0, 0)',
          border: 0
        }}
      >
        {step === 'select-specialists' && 'Выберите специалистов и продолжайте регистрацию.'}
        {step === 'form' && 'Заполните обязательные поля: ФИО и телефон.'}
        {step === 'info' && 'Проверьте информацию по очереди и перейдите к форме.'}
      </div>
      <div className="max-w-md w-full overflow-hidden" style={glassCardStyle}>

        {/* Заголовок с информацией об очереди - macOS стиль с правильным spacing */}
        <div className="text-white" style={{
          background: 'linear-gradient(135deg, var(--mac-accent) 0%, var(--mac-accent-purple) 100%)',
          borderRadius: '20px 20px 0 0',
          padding: 'var(--mac-spacing-6)'
        }}>
          <h1 style={{
            fontSize: '26px',
            fontWeight: 'var(--mac-font-weight-semibold)',
            marginBottom: 'var(--mac-spacing-4)',
            letterSpacing: '-0.02em',
            lineHeight: '1.2'
          }}>Присоединиться к очереди</h1>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div className="flex items-center" style={{ opacity: 0.95 }}>
              <MapPin style={{ width: '16px', height: '16px', marginRight: 'var(--mac-spacing-2)', flexShrink: 0 }} />
              <span style={{ fontSize: 'var(--mac-font-size-base)', lineHeight: '1.4' }}>{queueInfo?.department_name || 'Умумий амалиёт'}</span>
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
                  День приёма: {new Date(queueInfo.target_date).toLocaleDateString('ru-RU', {
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric'
                  })}
                </span>
              </div>
            )}
          </div>
        </div>

        {step === 'select-specialists' && (
          <div style={{ padding: 'var(--mac-spacing-6)' }}>
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
                Выберите специалистов
              </h3>
              <p style={{
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-lg)',
                lineHeight: '1.5',
                margin: 0
              }}>
                Можно выбрать несколько специалистов одновременно
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
                  Загрузка специалистов...
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
                  <span> {/* UX Audit Registrar #2: был UZ, теперь RU. */} Сейчас нет специалистов для выбора через QR.</span>
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
                    Обновить
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
              Давом этиш ({selectedSpecialists.length})
            </button>

            {error && (
              <div style={{
                marginTop: 'var(--mac-spacing-4)',
                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                borderRadius: 'var(--mac-radius-md)',
                background: 'var(--mac-error-bg)',
                border: '1px solid var(--mac-error-border)',
                color: 'var(--mac-error)',
                fontSize: 'var(--mac-font-size-base)',
                textAlign: 'center'
              }} role="alert" aria-live="assertive">
                {error}
              </div>
            )}
          </div>
        )}

        {step === 'info' && (
          <div style={{ padding: 'var(--mac-spacing-6)' }}>
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
                }}>в очереди</div>
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
                }}>мин кутиш</div>
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
                Заполните форму ниже, чтобы присоединиться к очереди
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
                Давом этиш
              </button>
            </div>
          </div>
        )}

        {step === 'form' && (
          <div style={{ padding: 'var(--mac-spacing-6)' }}>
            <form onSubmit={handleFormSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
              {/* ФИО - macOS стиль */}
              <div>
                <label
                  htmlFor="queue-patient-name"
                  style={{
                  display: 'block',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: 'var(--mac-spacing-2)'
                }}
                >
                  ФИО *
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: 'var(--mac-text-tertiary)' }} />
                  <Input
                    id="queue-patient-name"
                    name="patient_name"
                    type="text"
                    aria-label="ФИО пациента"
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
                    placeholder="Введите фамилию и имя"
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
                  style={{
                  display: 'block',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: 'var(--mac-spacing-2)'
                }}
                >
                  Номер телефона *
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: 'var(--mac-text-tertiary)' }} />
                  <Input
                    id="queue-phone"
                    name="phone"
                    type="tel"
                    aria-label="Номер телефона пациента"
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
                  Формат: +998 (XX) XXX-XX-XX
                </div>
              </div>

              {/* Telegram ID (опционально) - macOS стиль */}
              <div>
                <label
                  htmlFor="queue-telegram-id"
                  style={{
                  display: 'block',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: 'var(--mac-spacing-2)'
                }}
                >
                  Telegram ID (ихтиёрий)
                </label>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', marginBottom: 'var(--mac-spacing-2)' }}>
                  Для уведомлений в Telegram
                </div>
                <Input
                  id="queue-telegram-id"
                  name="telegram_id"
                  type="number"
                  aria-label="Telegram ID (необязательно)"
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
                  placeholder="(необязательно)"
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
                  Ортга
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
                  {loading ? 'Присоединяемся...' : 'Присоединиться'}
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
