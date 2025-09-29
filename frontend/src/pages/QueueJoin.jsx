import React, { useState, useEffect } from 'react';
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
  const [step, setStep] = useState('loading'); // loading, waiting, info, form, success, error
  const [queueInfo, setQueueInfo] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);
  const [formData, setFormData] = useState({
    patientName: '',
    phone: '',
    telegramId: ''
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [countdown, setCountdown] = useState(null);

  // Загрузка информации о токене при монтировании
  useEffect(() => {
    if (token) {
      loadTokenInfo();
    }
  }, [token]);

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
  }, [step, queueInfo?.minutes_until_open]);

  const loadTokenInfo = async () => {
    try {
      setStep('loading');
      
      const response = await fetch(`/api/v1/qr-tokens/${token}/info`);
      
      if (!response.ok) {
        throw new Error('QR токен не найден или истек');
      }
      
      const tokenInfo = await response.json();
      setQueueInfo(tokenInfo);
      
      if (!tokenInfo.queue_active) {
        setError('Очередь в данный момент не активна');
        setStep('error');
        return;
      }
      
      // Проверяем временные ограничения
      if (tokenInfo.status === 'before_start_time') {
        setQueueInfo(tokenInfo);
        setStep('waiting');
        return;
      } else if (tokenInfo.status === 'after_end_time') {
        setError(`Запись закрыта в ${tokenInfo.end_time}`);
        setStep('error');
        return;
      } else if (tokenInfo.status === 'closed_reception_opened') {
        setError('Запись закрыта - прием уже открыт');
        setStep('error');
        return;
      } else if (tokenInfo.status === 'limit_reached') {
        setError(`Достигнут лимит записей (${tokenInfo.max_entries})`);
        setStep('error');
        return;
      } else if (tokenInfo.allowed === false) {
        setError(tokenInfo.message || 'Запись недоступна');
        setStep('error');
        return;
      }
      
      // Начинаем сессию присоединения
      await startJoinSession();
      
    } catch (err) {
      setError(err.message);
      setStep('error');
    }
  };

  const startJoinSession = async () => {
    try {
      const response = await fetch('/api/v1/queue/join/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка начала сессии');
      }
      
      const sessionData = await response.json();
      setSessionToken(sessionData.session_token);
      setQueueInfo(sessionData.queue_info);
      setStep('info');
      
    } catch (err) {
      setError(err.message);
      setStep('error');
    }
  };

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.patientName.trim() || !formData.phone.trim()) {
      setError('Пожалуйста, заполните все обязательные поля');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/v1/queue/join/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_token: sessionToken,
          patient_name: formData.patientName,
          phone: formData.phone,
          telegram_id: formData.telegramId ? parseInt(formData.telegramId) : null
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка присоединения к очереди');
      }
      
      const joinResult = await response.json();
      setResult(joinResult);
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

  const formatWaitTime = (minutes) => {
    if (minutes < 60) {
      return `${minutes} мин`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours} ч ${mins} мин`;
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

  // Компонент загрузки
  if (step === 'loading') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Загрузка...</h2>
          <p className="text-gray-600">Получаем информацию об очереди</p>
        </div>
      </div>
    );
  }

  // Компонент ошибки
  if (step === 'error') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 to-pink-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Ошибка</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="w-full bg-red-600 text-white py-3 px-4 rounded-lg hover:bg-red-700 transition-colors"
          >
            На главную
          </button>
        </div>
      </div>
    );
  }

  // Компонент ожидания открытия очереди
  if (step === 'waiting') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <Clock className="h-16 w-16 text-orange-500 mx-auto mb-4 animate-pulse" />
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Очередь скоро откроется</h2>
          <p className="text-gray-600 mb-6">
            Запись в очередь откроется в {queueInfo?.start_time}
          </p>
          
          {/* Обратный отсчет */}
          <div className="bg-orange-50 rounded-xl p-6 mb-6">
            <div className="text-4xl font-bold text-orange-600 mb-2 font-mono">
              {formatCountdown(countdown)}
            </div>
            <p className="text-gray-600">до открытия записи</p>
          </div>
          
          {/* Информация о враче и кабинете */}
          <div className="space-y-4 mb-6">
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center">
                <User className="h-5 w-5 text-gray-500 mr-2" />
                <span className="text-gray-600">Специалист</span>
              </div>
              <span className="font-semibold text-sm">{queueInfo?.specialist_name}</span>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center">
                <MapPin className="h-5 w-5 text-gray-500 mr-2" />
                <span className="text-gray-600">Отделение</span>
              </div>
              <span className="font-semibold text-sm">{queueInfo?.department_name}</span>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center">
                <Calendar className="h-5 w-5 text-gray-500 mr-2" />
                <span className="text-gray-600">Текущее время</span>
              </div>
              <span className="font-semibold">{queueInfo?.current_time}</span>
            </div>
          </div>
          
          <div className="text-sm text-gray-500 mb-6">
            <p className="mb-2">📱 Оставьте эту страницу открытой</p>
            <p>Мы автоматически перенаправим вас, когда запись откроется</p>
          </div>
          
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/')}
              className="flex-1 bg-gray-200 text-gray-700 py-3 px-4 rounded-lg hover:bg-gray-300 transition-colors"
            >
              На главную
            </button>
            <button
              onClick={loadTokenInfo}
              className="flex-1 bg-orange-600 text-white py-3 px-4 rounded-lg hover:bg-orange-700 transition-colors"
            >
              Обновить
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Компонент успешного присоединения
  if (step === 'success') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Вы в очереди!</h2>
          
          <div className="bg-green-50 rounded-xl p-6 mb-6">
            <div className="text-4xl font-bold text-green-600 mb-2">
              №{result.queue_number}
            </div>
            <p className="text-gray-600">Ваш номер в очереди</p>
          </div>
          
          <div className="space-y-4 mb-6">
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center">
                <Users className="h-5 w-5 text-gray-500 mr-2" />
                <span className="text-gray-600">Впереди вас</span>
              </div>
              <span className="font-semibold">{result.queue_number - 1} чел.</span>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center">
                <Timer className="h-5 w-5 text-gray-500 mr-2" />
                <span className="text-gray-600">Ожидание</span>
              </div>
              <span className="font-semibold">{formatWaitTime(result.estimated_wait_time)}</span>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center">
                <User className="h-5 w-5 text-gray-500 mr-2" />
                <span className="text-gray-600">Специалист</span>
              </div>
              <span className="font-semibold text-sm">{result.specialist_name}</span>
            </div>
          </div>
          
          <div className="text-sm text-gray-500 mb-6">
            <p>Пожалуйста, будьте готовы к приему.</p>
            <p>Мы уведомим вас, когда подойдет ваша очередь.</p>
          </div>
          
          <button
            onClick={() => navigate('/')}
            className="w-full bg-green-600 text-white py-3 px-4 rounded-lg hover:bg-green-700 transition-colors"
          >
            Понятно
          </button>
        </div>
      </div>
    );
  }

  // Основной интерфейс (info + form)
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden">
        
        {/* Заголовок с информацией об очереди */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6">
          <h1 className="text-2xl font-bold mb-2">Присоединиться к очереди</h1>
          <div className="flex items-center mb-2">
            <MapPin className="h-4 w-4 mr-2" />
            <span className="text-blue-100">{queueInfo?.department_name}</span>
          </div>
          <div className="flex items-center">
            <User className="h-4 w-4 mr-2" />
            <span className="text-blue-100 text-sm">{queueInfo?.specialist_name}</span>
          </div>
        </div>

        {step === 'info' && (
          <div className="p-6">
            {/* Статус очереди */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-blue-50 rounded-xl p-4 text-center">
                <Users className="h-8 w-8 text-blue-600 mx-auto mb-2" />
                <div className="text-2xl font-bold text-blue-600">{queueInfo?.queue_length}</div>
                <div className="text-sm text-gray-600">в очереди</div>
              </div>
              
              <div className="bg-green-50 rounded-xl p-4 text-center">
                <Clock className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <div className="text-2xl font-bold text-green-600">~{queueInfo?.queue_length * 15}</div>
                <div className="text-sm text-gray-600">мин ожидание</div>
              </div>
            </div>

            <div className="text-center mb-6">
              <p className="text-gray-600 mb-4">
                Заполните форму ниже, чтобы присоединиться к очереди
              </p>
              <button
                onClick={() => setStep('form')}
                className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Продолжить
              </button>
            </div>
          </div>
        )}

        {step === 'form' && (
          <div className="p-6">
            <form onSubmit={handleFormSubmit} className="space-y-4">
              {/* ФИО */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  ФИО *
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                  <input
                    type="text"
                    value={formData.patientName}
                    onChange={(e) => handleInputChange('patientName', e.target.value)}
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Введите ваше ФИО"
            required
                  />
                </div>
              </div>

              {/* Телефон */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Номер телефона *
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                  <input
                    type="tel"
            value={formData.phone}
                    onChange={(e) => handleInputChange('phone', e.target.value)}
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="+998901234567"
                    required
                  />
                </div>
              </div>

              {/* Telegram ID (опционально) */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Telegram ID (опционально)
                </label>
                <input
                  type="number"
                  value={formData.telegramId}
                  onChange={(e) => handleInputChange('telegramId', e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Для уведомлений в Telegram"
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                  <div className="flex items-center">
                    <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                    <span className="text-red-700 text-sm">{error}</span>
                  </div>
                </div>
              )}

              {/* Кнопки */}
              <div className="flex space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setStep('info')}
                  className="flex-1 bg-gray-200 text-gray-800 py-3 px-4 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  Назад
                </button>
                <button
                  type="submit"
            disabled={loading}
                  className="flex-1 bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
