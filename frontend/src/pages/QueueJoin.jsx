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

const QueueJoin = () => {
  const { token: paramToken } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Получаем токен из URL параметров или query параметров (для PWA пути)
  const token = paramToken || searchParams.get('token');

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
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [countdown, setCountdown] = useState(null);

  // Загрузка списка доступных специалистов
  useEffect(() => {
    const loadSpecialists = async () => {
      try {
        // Используем относительный путь для проксирования через Vite
        const response = await fetch('/api/v1/queue/available-specialists');
        if (response.ok) {
          const data = await response.json();
          // ✅ Фильтруем специалистов: исключаем 'ecg' и 'general'
          const filteredSpecialists = (data.specialists || []).filter(specialist => {
            const specialty = (specialist.specialty || '').toLowerCase();
            return specialty !== 'ecg' && specialty !== 'general';
          });
          setAvailableSpecialists(filteredSpecialists);
        } else {
          // Fallback на статический список
          setAvailableSpecialists([
            { id: 1, specialty_display: 'Кардиолог', icon: '❤️', color: '#FF3B30' },
            { id: 2, specialty_display: 'Дерматолог-косметолог', icon: '✨', color: '#FF9500' },
            { id: 3, specialty_display: 'Стоматолог', icon: '🦷', color: '#007AFF' },
            { id: 4, specialty_display: 'Лаборатория', icon: '🔬', color: '#34C759' }
          ]);
        }
      } catch {
        // Fallback на статический список
        setAvailableSpecialists([
          { id: 1, specialty_display: 'Кардиолог', icon: '❤️', color: '#FF3B30' },
          { id: 2, specialty_display: 'Дерматолог-косметолог', icon: '✨', color: '#FF9500' },
          { id: 3, specialty_display: 'Стоматолог', icon: '🦷', color: '#007AFF' },
          { id: 4, specialty_display: 'Лаборатория', icon: '🔬', color: '#34C759' }
        ]);
      }
    };

    loadSpecialists();
  }, []);

  // ✅ Функции объявлены до использования в useEffect
  const startJoinSession = useCallback(async () => {
    try {
      // Используем относительный путь для проксирования через Vite
      const response = await fetch('/api/v1/queue/join/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token }),
      });

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch {
          const text = await response.text();
          throw new Error(
            text || `Ошибка сервера: ${response.status} ${response.statusText}`
          );
        }

        const errorMessage = errorData.detail || errorData.message || 'Сессияни бошлашда хатолик';
        throw new Error(errorMessage);
      }

      const sessionData = await response.json();

      setSessionToken(sessionData.session_token);
      localStorage.setItem(`queue_session_${token}`, sessionData.session_token);
      setQueueInfo(sessionData.queue_info);

      if (sessionData.queue_info?.is_clinic_wide) {
        setStep('select-specialists');
      } else {
        setStep('info');
      }

    } catch (err) {
      setError(err.message || 'Сессияни бошлашда хатолик');
      setStep('error');
    }
  }, [token]);

  const loadTokenInfo = useCallback(async () => {
    try {
      setStep('loading');

      // Используем относительный путь для проксирования через Vite
      const response = await fetch(`/api/v1/queue/qr-tokens/${token}/info`);

      if (!response.ok) {
        throw new Error('QR токен топилмади ёки муддати тугаган');
      }

      const tokenInfo = await response.json();
      setQueueInfo(tokenInfo);

      if (!tokenInfo.queue_active) {
        setError('Навбат ҳозирда фаол эмас');
        setStep('error');
        return;
      }

      if (tokenInfo.status === 'before_start_time') {
        setQueueInfo(tokenInfo);
        setStep('waiting');
        return;
      } else if (tokenInfo.status === 'after_end_time') {
        setError(`Ёзилиш ${tokenInfo.end_time}да ёпилган`);
        setStep('error');
        return;
      } else if (tokenInfo.status === 'closed_reception_opened') {
        setError('Ёзилиш ёпилган - қабул аллақачон очилган');
        setStep('error');
        return;
      } else if (tokenInfo.status === 'limit_reached') {
        setError(`Ёзилиш лимитига етилди (${tokenInfo.max_entries})`);
        setStep('error');
        return;
      } else if (tokenInfo.allowed === false) {
        setError(tokenInfo.message || 'Ёзилиш мавжуд эмас');
        setStep('error');
        return;
      }

      await startJoinSession();

    } catch (err) {
      setError(err.message);
      setStep('error');
    }
  }, [startJoinSession, token]);

  // Загрузка информации о токене при монтировании
  useEffect(() => {
    if (token) {
      // ✅ Пытаемся восстановить session_token из localStorage
      const savedSessionToken = localStorage.getItem(`queue_session_${token}`);
      if (savedSessionToken) {
        setSessionToken(savedSessionToken);
      }
      loadTokenInfo();
    }
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
      setError('Илтимос, барча мажбурий майдонларни тўлдиринг');
      return;
    }

    // ✅ Проверяем наличие session_token
    let currentSessionToken = sessionToken;

    if (!currentSessionToken) {
      // Пытаемся восстановить из localStorage
      currentSessionToken = localStorage.getItem(`queue_session_${token}`);

      if (!currentSessionToken) {
        // Если нет сохраненной сессии, создаем новую
        setError('Сессия муддати тугади. Янги сессия яратилмоқда...');
        await startJoinSession();
        currentSessionToken = sessionToken;
        if (!currentSessionToken) {
          setError('Сессияни яратиб бўлмади. Илтимос, саҳифани янгиланг.');
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
        setError('Илтимос, тўлиқ исм-шариф киритинг (камда 2 та белги)');
        setLoading(false);
        return;
      }

      if (trimmedPatientName.length > 200) {
        setError('Исм-шариф жуда узун (максимум 200 та белги)');
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
        setError('Телефон рақами тўлиқ эмас (камда 12 та рақам: +998 XX XXX XX XX)');
        setLoading(false);
        return;
      }

      if (normalizedPhone.length > 12) {
        setError('Телефон рақами жуда узун (максимум 12 та рақам)');
        setLoading(false);
        return;
      }

      if (!currentSessionToken) {
        setError('Сессия токени топилмади. Илтимос, саҳифани янгиланг.');
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

      // Используем относительный путь для проксирования через Vite
      const response = await fetch('/api/v1/queue/join/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch {
          const errorText = await response.text();
          throw new Error(errorText || `Ошибка сервера: ${response.status} ${response.statusText}`);
        }

        // Обрабатываем разные форматы ошибок
        const errorMessage = errorData.detail ||
          (Array.isArray(errorData.detail) ? errorData.detail.map(e => e.msg || e).join(', ') : null) ||
          errorData.message ||
          'Навбатга қўшилишда хатолик';
        throw new Error(errorMessage);
      }

      const joinResult = await response.json();
      setResult(joinResult);
      // ✅ Очищаем session_token из localStorage после успешного присоединения
      localStorage.removeItem(`queue_session_${token}`);

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

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
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

  // Компонент загрузки - macOS стиль
  if (step === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{
        background: 'var(--mac-gradient-window)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
      }}>
        <div className="max-w-md w-full text-center" style={{
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRadius: '20px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1), 0 2px 8px rgba(0, 0, 0, 0.06)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          padding: '32px 24px'
        }}>
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" style={{
            borderColor: '#007AFF'
          }}></div>
          <h2 style={{
            fontSize: '22px',
            fontWeight: '600',
            color: '#1C1C1E',
            marginBottom: '8px',
            letterSpacing: '-0.02em'
          }}>Юкланмоқда...</h2>
          <p style={{
            fontSize: '15px',
            color: '#636366',
            lineHeight: '1.5'
          }}>Навбат ҳақида маълумот олиш</p>
        </div>
      </div>
    );
  }

  // Компонент ошибки - macOS стиль
  if (step === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{
        background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
      }}>
        <div className="max-w-md w-full text-center" style={{
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRadius: '20px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1), 0 2px 8px rgba(0, 0, 0, 0.06)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          padding: '32px 24px'
        }}>
          <AlertCircle style={{
            width: '64px',
            height: '64px',
            color: '#FF3B30',
            margin: '0 auto 16px'
          }} />
          <h2 style={{
            fontSize: '22px',
            fontWeight: '600',
            color: '#1C1C1E',
            marginBottom: '12px',
            letterSpacing: '-0.02em'
          }}>Хатолик</h2>
          <p style={{
            fontSize: '15px',
            color: '#636366',
            marginBottom: '24px',
            lineHeight: '1.5'
          }}>{error}</p>
          <button
            onClick={() => navigate('/')}
            style={{
              width: '100%',
              background: '#FF3B30',
              color: 'white',
              padding: '16px 24px',
              borderRadius: '12px',
              border: 'none',
              fontSize: '17px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: '0 4px 12px rgba(255, 59, 48, 0.3)'
            }}
            onMouseEnter={(e) => e.target.style.background = '#D70015'}
            onMouseLeave={(e) => e.target.style.background = '#FF3B30'}
          >
            Асосий саҳифа
          </button>
        </div>
      </div>
    );
  }

  // Компонент ожидания открытия очереди - macOS стиль
  if (step === 'waiting') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{
        background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
      }}>
        <div className="max-w-md w-full text-center" style={{
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRadius: '20px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1), 0 2px 8px rgba(0, 0, 0, 0.06)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          padding: '32px 24px'
        }}>
          <Clock style={{
            width: '64px',
            height: '64px',
            color: '#FF9500',
            margin: '0 auto 20px',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
          }} />
          <h2 style={{
            fontSize: '24px',
            fontWeight: '600',
            color: '#1C1C1E',
            marginBottom: '12px',
            letterSpacing: '-0.02em'
          }}>Навбат тез орада очилади</h2>
          <p style={{
            fontSize: '15px',
            color: '#636366',
            marginBottom: '24px',
            lineHeight: '1.5'
          }}>
            Навбатга ёзилиш {queueInfo?.start_time}да очилади
          </p>

          {/* Обратный отсчет - macOS стиль */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(255, 149, 0, 0.1) 0%, rgba(255, 149, 0, 0.05) 100%)',
            borderRadius: '16px',
            padding: '24px',
            marginBottom: '24px',
            border: '1px solid rgba(255, 149, 0, 0.15)'
          }}>
            <div style={{
              fontSize: '44px',
              fontWeight: '600',
              color: '#FF9500',
              marginBottom: '8px',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, "Courier New", monospace',
              letterSpacing: '0.02em'
            }}>
              {formatCountdown(countdown)}
            </div>
            <p style={{
              fontSize: '13px',
              color: '#8E8E93',
              fontWeight: '500'
            }}>ёзилиш очилишига қадар</p>
          </div>

          {/* Информация о враче и кабинете - macOS стиль */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              background: 'rgba(242, 242, 247, 0.6)',
              borderRadius: '12px'
            }}>
              <div className="flex items-center">
                <User style={{ width: '18px', height: '18px', color: '#8E8E93', marginRight: '8px' }} />
                <span style={{ fontSize: '14px', color: '#636366' }}>Мутахассис</span>
              </div>
              <span style={{ fontSize: '14px', fontWeight: '600', color: '#1C1C1E' }}>{queueInfo?.specialist_name}</span>
            </div>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              background: 'rgba(242, 242, 247, 0.6)',
              borderRadius: '12px'
            }}>
              <div className="flex items-center">
                <MapPin style={{ width: '18px', height: '18px', color: '#8E8E93', marginRight: '8px' }} />
                <span style={{ fontSize: '14px', color: '#636366' }}>Бўлим</span>
              </div>
              <span style={{ fontSize: '14px', fontWeight: '600', color: '#1C1C1E' }}>{queueInfo?.department_name}</span>
            </div>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              background: 'linear-gradient(135deg, rgba(0, 122, 255, 0.1) 0%, rgba(0, 122, 255, 0.05) 100%)',
              borderRadius: '12px',
              border: '1px solid rgba(0, 122, 255, 0.15)'
            }}>
              <div className="flex items-center">
                <Calendar style={{ width: '18px', height: '18px', color: '#007AFF', marginRight: '8px' }} />
                <span style={{ fontSize: '14px', fontWeight: '500', color: '#007AFF' }}>Қабул куни</span>
              </div>
              <span style={{ fontSize: '14px', fontWeight: '600', color: '#007AFF' }}>
                {queueInfo?.target_date ? new Date(queueInfo.target_date).toLocaleDateString('uz-UZ', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                }) : 'Бугун'}
              </span>
            </div>
          </div>

          <div style={{
            fontSize: '13px',
            color: '#8E8E93',
            marginBottom: '24px',
            textAlign: 'center',
            lineHeight: '1.5'
          }}>
            <p style={{ marginBottom: '8px' }}>📱 Бу саҳифани очиқ қолдиринг</p>
            <p>Ёзилиш очилганда сизни автоматик равишда йўналтирамиз</p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => navigate('/')}
              style={{
                flex: 1,
                background: 'rgba(142, 142, 147, 0.12)',
                color: '#007AFF',
                padding: '14px 20px',
                borderRadius: '12px',
                border: 'none',
                fontSize: '17px',
                fontWeight: '600',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => e.target.style.background = 'rgba(142, 142, 147, 0.18)'}
              onMouseLeave={(e) => e.target.style.background = 'rgba(142, 142, 147, 0.12)'}
            >
              Асосий саҳифа
            </button>
            <button
              onClick={loadTokenInfo}
              style={{
                flex: 1,
                background: '#FF9500',
                color: 'white',
                padding: '14px 20px',
                borderRadius: '12px',
                border: 'none',
                fontSize: '17px',
                fontWeight: '600',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: '0 4px 12px rgba(255, 149, 0, 0.3)'
              }}
              onMouseEnter={(e) => e.target.style.background = '#E68900'}
              onMouseLeave={(e) => e.target.style.background = '#FF9500'}
            >
              Янгилаш
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
      <div className="min-h-screen flex items-center justify-center p-4" style={{
        background: 'var(--mac-gradient-window)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
      }}>
        <div className="max-w-md w-full text-center" style={{
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRadius: '20px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1), 0 2px 8px rgba(0, 0, 0, 0.06)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          padding: '32px 24px'
        }}>
          <CheckCircle style={{
            width: '64px',
            height: '64px',
            color: '#34C759',
            margin: '0 auto 20px'
          }} />
          <h2 style={{
            fontSize: '24px',
            fontWeight: '600',
            color: '#1C1C1E',
            marginBottom: '24px',
            letterSpacing: '-0.02em'
          }}>
            {isMultiple ? 'Сиз навбатларга рўйхатдан ўтдингиз!' : 'Сиз навбатда!'}
          </h2>

          {isMultiple ? (
            // Множественная регистрация
            <>
              <div style={{
                background: 'linear-gradient(135deg, rgba(52, 199, 89, 0.1) 0%, rgba(52, 199, 89, 0.05) 100%)',
                borderRadius: '16px',
                padding: '24px',
                marginBottom: '24px',
                border: '1px solid rgba(52, 199, 89, 0.15)'
              }}>
                <p style={{
                  fontSize: '15px',
                  fontWeight: '600',
                  color: '#1C1C1E',
                  marginBottom: '16px',
                  textAlign: 'center'
                }}>
                  Сиз {result.entries.length} навбатга рўйхатдан ўтдингиз:
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {result.entries.map((entry, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '16px',
                        background: 'rgba(255, 255, 255, 0.8)',
                        borderRadius: '12px',
                        border: '1px solid rgba(52, 199, 89, 0.2)'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '24px' }}>{entry.icon || '👨‍⚕️'}</span>
                        <div>
                          <div style={{ fontSize: '15px', fontWeight: '600', color: '#1C1C1E' }}>
                            {entry.specialist_name || entry.department || `Мутахассис ${idx + 1}`}
                          </div>
                          <div style={{ fontSize: '12px', color: '#8E8E93', marginTop: '4px' }}>
                            Вақт: {entry.queue_time ? new Date(entry.queue_time).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }) : '—'}
                          </div>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '28px', fontWeight: '600', color: '#34C759' }}>№{entry.queue_number || entry.number || '—'}</div>
                        <div style={{ fontSize: '11px', color: '#8E8E93' }}>навбатда</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{
                fontSize: '13px',
                color: '#8E8E93',
                marginBottom: '24px',
                lineHeight: '1.5'
              }}>
                <p>Илтимос, қабулга тайёр бўлинг.</p>
                <p>Навбатингиз келганда сизга хабар берамиз.</p>
                <p style={{ marginTop: '12px', fontWeight: '500', color: '#007AFF' }}>
                  💡 Ёзилмаларни мутахассислар вкладкаларида кўришингиз мумкин
                </p>
              </div>
            </>
          ) : (
            // Одиночная регистрация
            <>
              <div style={{
                background: 'linear-gradient(135deg, rgba(52, 199, 89, 0.1) 0%, rgba(52, 199, 89, 0.05) 100%)',
                borderRadius: '16px',
                padding: '32px 24px',
                marginBottom: '24px',
                border: '1px solid rgba(52, 199, 89, 0.15)'
              }}>
                <div style={{
                  fontSize: '48px',
                  fontWeight: '600',
                  color: '#34C759',
                  marginBottom: '8px',
                  letterSpacing: '-0.02em'
                }}>
                  №{result.queue_number}
                </div>
                <p style={{ fontSize: '15px', color: '#636366', fontWeight: '500' }}>Навбатдаги рақамингиз</p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  background: 'rgba(242, 242, 247, 0.6)',
                  borderRadius: '12px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <Users style={{ width: '18px', height: '18px', color: '#8E8E93', marginRight: '8px' }} />
                    <span style={{ fontSize: '14px', color: '#636366' }}>Олдингизда</span>
                  </div>
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#1C1C1E' }}>{result.queue_number - 1} к.</span>
                </div>

                {result.estimated_wait_time && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    background: 'rgba(242, 242, 247, 0.6)',
                    borderRadius: '12px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <Timer style={{ width: '18px', height: '18px', color: '#8E8E93', marginRight: '8px' }} />
                      <span style={{ fontSize: '14px', color: '#636366' }}>Кутиш</span>
                    </div>
                    <span style={{ fontSize: '14px', fontWeight: '600', color: '#1C1C1E' }}>{formatWaitTime(result.estimated_wait_time)}</span>
                  </div>
                )}

                {result.specialist_name && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    background: 'rgba(242, 242, 247, 0.6)',
                    borderRadius: '12px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <User style={{ width: '18px', height: '18px', color: '#8E8E93', marginRight: '8px' }} />
                      <span style={{ fontSize: '14px', color: '#636366' }}>Мутахассис</span>
                    </div>
                    <span style={{ fontSize: '14px', fontWeight: '600', color: '#1C1C1E' }}>{result.specialist_name}</span>
                  </div>
                )}
              </div>

              <div style={{
                fontSize: '13px',
                color: '#8E8E93',
                marginBottom: '24px',
                lineHeight: '1.5'
              }}>
                <p>Илтимос, қабулга тайёр бўлинг.</p>
                <p>Навбатингиз келганда сизга хабар берамиз.</p>
                <p style={{ marginTop: '12px', fontWeight: '500', color: '#007AFF' }}>
                  💡 Ёзилмани {departmentName} вкладкасида кўришингиз мумкин
                </p>
              </div>
            </>
          )}

          <button
            onClick={() => navigate('/')}
            style={{
              width: '100%',
              background: '#34C759',
              color: 'white',
              padding: '16px 24px',
              borderRadius: '12px',
              border: 'none',
              fontSize: '17px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: '0 4px 12px rgba(52, 199, 89, 0.3)'
            }}
            onMouseEnter={(e) => e.target.style.background = '#30D158'}
            onMouseLeave={(e) => e.target.style.background = '#34C759'}
          >
            Тушунарли
          </button>
        </div>
      </div>
    );
  }

  // Основной интерфейс (info + form) - macOS стиль
  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{
      background: 'var(--mac-gradient-window)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
    }}>
      <div className="max-w-md w-full overflow-hidden" style={{
        background: 'rgba(255, 255, 255, 0.85)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRadius: '20px',
        boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1), 0 2px 8px rgba(0, 0, 0, 0.06)',
        border: '1px solid rgba(255, 255, 255, 0.6)'
      }}>

        {/* Заголовок с информацией об очереди - macOS стиль с правильным spacing */}
        <div className="text-white" style={{
          background: 'linear-gradient(135deg, #007AFF 0%, #5856D6 100%)',
          borderRadius: '20px 20px 0 0',
          padding: '24px'
        }}>
          <h1 style={{
            fontSize: '26px',
            fontWeight: '600',
            marginBottom: '16px',
            letterSpacing: '-0.02em',
            lineHeight: '1.2'
          }}>Навбатга қўшилиш</h1>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div className="flex items-center" style={{ opacity: 0.95 }}>
              <MapPin style={{ width: '16px', height: '16px', marginRight: '8px', flexShrink: 0 }} />
              <span style={{ fontSize: '14px', lineHeight: '1.4' }}>{queueInfo?.department_name || 'Умумий амалиёт'}</span>
            </div>

            <div className="flex items-center" style={{ opacity: 0.9 }}>
              <User style={{ width: '16px', height: '16px', marginRight: '8px', flexShrink: 0 }} />
              <span style={{ fontSize: '13px', lineHeight: '1.4' }}>{queueInfo?.specialist_name}</span>
            </div>

            {queueInfo?.target_date && (
              <div className="flex items-center" style={{
                marginTop: '8px',
                paddingTop: '12px',
                borderTop: '1px solid rgba(255, 255, 255, 0.2)',
                opacity: 0.95
              }}>
                <Calendar style={{ width: '16px', height: '16px', marginRight: '8px', flexShrink: 0 }} />
                <span style={{
                  fontSize: '13px',
                  fontWeight: '500',
                  lineHeight: '1.4'
                }}>
                  Қабул куни: {new Date(queueInfo.target_date).toLocaleDateString('uz-UZ', {
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
          <div style={{ padding: '24px' }}>
            <div style={{
              marginBottom: '24px',
              textAlign: 'center'
            }}>
              <h3 style={{
                fontSize: '20px',
                fontWeight: '600',
                color: '#1C1C1E',
                marginBottom: '8px',
                letterSpacing: '-0.02em'
              }}>
                Мутахассисларни танланг
              </h3>
              <p style={{
                color: '#636366',
                fontSize: '15px',
                lineHeight: '1.5',
                margin: 0
              }}>
                Бир нечта мутахассисни бир вақтда танлаш мумкин
              </p>
            </div>

            {/* Чекбоксы специалистов */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              marginBottom: '24px'
            }}>
              {availableSpecialists.length === 0 ? (
                <div style={{
                  padding: '16px',
                  textAlign: 'center',
                  color: 'var(--mac-text-secondary)',
                  fontSize: '15px'
                }}>
                  Мутахассислар юкланмоқда...
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
                        padding: '16px',
                        borderRadius: '12px',
                        border: `2px solid ${isSelected ? specialist.color : '#E5E5EA'}`,
                        background: isSelected ? `${specialist.color}15` : '#FFFFFF',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        userSelect: 'none'
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {
                          if (isSelected) {
                            setSelectedSpecialists(prev => prev.filter(id => id !== specialist.id));
                          } else {
                            setSelectedSpecialists(prev => [...prev, specialist.id]);
                          }
                        }}
                        style={{
                          width: '24px',
                          height: '24px',
                          marginRight: '12px',
                          accentColor: specialist.color,
                          cursor: 'pointer'
                        }}
                      />
                      <span style={{ fontSize: '24px', marginRight: '12px' }}>{specialist.icon}</span>
                      <span style={{
                        fontSize: '17px',
                        fontWeight: '600',
                        color: isSelected ? specialist.color : '#1C1C1E'
                      }}>
                        {specialist.specialty_display || specialist.name}
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
                  setError('Кам деганда бир мутахассисни танланг');
                  setTimeout(() => setError(null), 3000);
                  return;
                }
                setStep('form');
              }}
              disabled={selectedSpecialists.length === 0}
              style={{
                width: '100%',
                background: selectedSpecialists.length > 0 ? '#007AFF' : '#E5E5EA',
                color: selectedSpecialists.length > 0 ? 'white' : '#8E8E93',
                padding: '16px 24px',
                borderRadius: '12px',
                border: 'none',
                fontSize: '17px',
                fontWeight: '600',
                cursor: selectedSpecialists.length > 0 ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s ease',
                boxShadow: selectedSpecialists.length > 0 ? '0 4px 12px rgba(0, 122, 255, 0.3)' : 'none'
              }}
              onMouseEnter={(e) => {
                if (selectedSpecialists.length > 0) {
                  e.target.style.background = '#0051D5';
                }
              }}
              onMouseLeave={(e) => {
                if (selectedSpecialists.length > 0) {
                  e.target.style.background = '#007AFF';
                }
              }}
            >
              Давом этиш ({selectedSpecialists.length})
            </button>

            {error && (
              <div style={{
                marginTop: '16px',
                padding: '12px 16px',
                borderRadius: '8px',
                background: '#FFF3F3',
                border: '1px solid #FFE5E5',
                color: '#FF3B30',
                fontSize: '14px',
                textAlign: 'center'
              }}>
                {error}
              </div>
            )}
          </div>
        )}

        {step === 'info' && (
          <div style={{ padding: '24px' }}>
            {/* Статус очереди - macOS стиль с правильным spacing */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '16px',
              marginBottom: '24px'
            }}>
              <div style={{
                background: 'linear-gradient(135deg, rgba(0, 122, 255, 0.1) 0%, rgba(0, 122, 255, 0.05) 100%)',
                borderRadius: '16px',
                padding: '24px 20px',
                border: '1px solid rgba(0, 122, 255, 0.15)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '140px'
              }}>
                <Users style={{
                  width: '32px',
                  height: '32px',
                  color: '#007AFF',
                  marginBottom: '12px'
                }} />
                <div style={{
                  fontSize: '36px',
                  fontWeight: '600',
                  color: '#007AFF',
                  letterSpacing: '-0.02em',
                  lineHeight: '1',
                  marginBottom: '8px'
                }}>{queueInfo?.queue_length || 0}</div>
                <div style={{
                  fontSize: '13px',
                  color: '#8E8E93',
                  fontWeight: '500'
                }}>навбатда</div>
              </div>

              <div style={{
                background: 'linear-gradient(135deg, rgba(52, 199, 89, 0.1) 0%, rgba(52, 199, 89, 0.05) 100%)',
                borderRadius: '16px',
                padding: '24px 20px',
                border: '1px solid rgba(52, 199, 89, 0.15)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '140px'
              }}>
                <Clock style={{
                  width: '32px',
                  height: '32px',
                  color: '#34C759',
                  marginBottom: '12px'
                }} />
                <div style={{
                  fontSize: '36px',
                  fontWeight: '600',
                  color: '#34C759',
                  letterSpacing: '-0.02em',
                  lineHeight: '1',
                  marginBottom: '8px'
                }}>~{(queueInfo?.queue_length || 0) * 15}</div>
                <div style={{
                  fontSize: '13px',
                  color: '#8E8E93',
                  fontWeight: '500'
                }}>мин кутиш</div>
              </div>
            </div>

            {/* Текст и кнопка с правильными отступами */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              gap: '20px'
            }}>
              <p style={{
                color: '#636366',
                fontSize: '15px',
                lineHeight: '1.5',
                margin: 0,
                maxWidth: '320px'
              }}>
                Навбатга қўшилиш учун қуйидаги формани тўлдиринг
              </p>
              <button
                onClick={() => setStep('form')}
                style={{
                  width: '100%',
                  background: '#007AFF',
                  color: 'white',
                  padding: '16px 24px',
                  borderRadius: '12px',
                  border: 'none',
                  fontSize: '17px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  boxShadow: '0 4px 12px rgba(0, 122, 255, 0.3)'
                }}
                onMouseEnter={(e) => e.target.style.background = '#0051D5'}
                onMouseLeave={(e) => e.target.style.background = '#007AFF'}
              >
                Давом этиш
              </button>
            </div>
          </div>
        )}

        {step === 'form' && (
          <div style={{ padding: '24px' }}>
            <form onSubmit={handleFormSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* ФИО - macOS стиль */}
              <div>
                <label style={{
                  display: 'block',
                  fontSize: '13px',
                  fontWeight: '500',
                  color: '#3C3C43',
                  marginBottom: '8px'
                }}>
                  ФИО *
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: '#8E8E93' }} />
                  <input
                    type="text"
                    value={formData.patientName}
                    onChange={(e) => handleInputChange('patientName', e.target.value)}
                    style={{
                      width: '100%',
                      paddingLeft: '40px',
                      paddingRight: '16px',
                      paddingTop: '12px',
                      paddingBottom: '12px',
                      border: '1px solid rgba(60, 60, 67, 0.18)',
                      borderRadius: '10px',
                      fontSize: '17px',
                      fontFamily: 'inherit',
                      background: 'rgba(242, 242, 247, 0.6)',
                      transition: 'all 0.2s ease',
                      outline: 'none'
                    }}
                    onFocus={(e) => {
                      e.target.style.border = '1px solid #007AFF';
                      e.target.style.boxShadow = '0 0 0 3px rgba(0, 122, 255, 0.1)';
                    }}
                    onBlur={(e) => {
                      e.target.style.border = '1px solid rgba(60, 60, 67, 0.18)';
                      e.target.style.boxShadow = 'none';
                    }}
                    placeholder="Фамилия исмингизни киритинг"
                    required
                  />
                </div>
              </div>

              {/* Телефон - macOS стиль с форматированием */}
              <div>
                <label style={{
                  display: 'block',
                  fontSize: '13px',
                  fontWeight: '500',
                  color: '#3C3C43',
                  marginBottom: '8px'
                }}>
                  Телефон рақами *
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: '#8E8E93' }} />
                  <input
                    type="tel"
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
                      border: '1px solid rgba(60, 60, 67, 0.18)',
                      borderRadius: '10px',
                      fontSize: '17px',
                      fontFamily: 'inherit',
                      background: 'rgba(242, 242, 247, 0.6)',
                      transition: 'all 0.2s ease',
                      outline: 'none'
                    }}
                    onFocus={(e) => {
                      e.target.style.border = '1px solid #007AFF';
                      e.target.style.boxShadow = '0 0 0 3px rgba(0, 122, 255, 0.1)';
                    }}
                    onBlur={(e) => {
                      e.target.style.border = '1px solid rgba(60, 60, 67, 0.18)';
                      e.target.style.boxShadow = 'none';
                    }}
                    placeholder="+998 (90) 123-45-67"
                    required
                  />
                </div>
                <div style={{ fontSize: '11px', color: '#8E8E93', marginTop: '4px' }}>
                  Формат: +998 (XX) XXX-XX-XX
                </div>
              </div>

              {/* Telegram ID (опционально) - macOS стиль */}
              <div>
                <label style={{
                  display: 'block',
                  fontSize: '13px',
                  fontWeight: '500',
                  color: '#3C3C43',
                  marginBottom: '8px'
                }}>
                  Telegram ID (ихтиёрий)
                </label>
                <div style={{ fontSize: '11px', color: '#8E8E93', marginBottom: '8px' }}>
                  Telegramда хабардор қилиш учун
                </div>
                <input
                  type="number"
                  value={formData.telegramId}
                  onChange={(e) => handleInputChange('telegramId', e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    border: '1px solid rgba(60, 60, 67, 0.18)',
                    borderRadius: '10px',
                    fontSize: '17px',
                    fontFamily: 'inherit',
                    background: 'rgba(242, 242, 247, 0.6)',
                    transition: 'all 0.2s ease',
                    outline: 'none'
                  }}
                  onFocus={(e) => {
                    e.target.style.border = '1px solid #007AFF';
                    e.target.style.boxShadow = '0 0 0 3px rgba(0, 122, 255, 0.1)';
                  }}
                  onBlur={(e) => {
                    e.target.style.border = '1px solid rgba(60, 60, 67, 0.18)';
                    e.target.style.boxShadow = 'none';
                  }}
                  placeholder="Мажбурий эмас"
                />
              </div>

              {error && (
                <div style={{
                  background: 'linear-gradient(135deg, rgba(255, 59, 48, 0.1) 0%, rgba(255, 59, 48, 0.05) 100%)',
                  border: '1px solid rgba(255, 59, 48, 0.2)',
                  borderRadius: '12px',
                  padding: '12px'
                }}>
                  <div className="flex items-center">
                    <AlertCircle className="h-5 w-5 mr-2" style={{ color: '#FF3B30' }} />
                    <span style={{ color: '#FF3B30', fontSize: '14px' }}>{error}</span>
                  </div>
                </div>
              )}

              {/* Кнопки - macOS стиль */}
              <div className="flex" style={{ gap: '12px', paddingTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => setStep('info')}
                  style={{
                    flex: 1,
                    background: 'rgba(142, 142, 147, 0.12)',
                    color: '#007AFF',
                    padding: '14px 20px',
                    borderRadius: '12px',
                    border: 'none',
                    fontSize: '17px',
                    fontWeight: '600',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={(e) => e.target.style.background = 'rgba(142, 142, 147, 0.18)'}
                  onMouseLeave={(e) => e.target.style.background = 'rgba(142, 142, 147, 0.12)'}
                >
                  Ортга
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    background: loading ? '#8E8E93' : '#007AFF',
                    color: 'white',
                    padding: '14px 20px',
                    borderRadius: '12px',
                    border: 'none',
                    fontSize: '17px',
                    fontWeight: '600',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: loading ? 'none' : '0 4px 12px rgba(0, 122, 255, 0.3)'
                  }}
                  onMouseEnter={(e) => !loading && (e.target.style.background = '#0051D5')}
                  onMouseLeave={(e) => !loading && (e.target.style.background = '#007AFF')}
                >
                  {loading ? 'Қўшилмоқда...' : 'Қўшилиш'}
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
