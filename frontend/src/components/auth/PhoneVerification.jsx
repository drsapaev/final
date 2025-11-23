import React, { useState, useEffect } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Input,
  Label
} from '../ui/native';
import {
  Phone,
  Shield,
  Clock,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Send
} from 'lucide-react';
import { api } from '../../utils/api';
import { toast } from 'react-toastify';

const PhoneVerification = ({ 
  phone, 
  purpose = 'verification', 
  onVerified, 
  onCancel,
  customMessage,
  showPhoneInput = false,
  title = 'Верификация телефона'
}) => {
  const [currentPhone, setCurrentPhone] = useState(phone || '');
  const [verificationCode, setVerificationCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [attemptsLeft, setAttemptsLeft] = useState(3);
  const [verificationStatus, setVerificationStatus] = useState(null);

  useEffect(() => {
    if (phone && !showPhoneInput) {
      checkVerificationStatus();
    }
  }, [phone, purpose]);

  useEffect(() => {
    let timer;
    if (timeLeft > 0) {
      timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [timeLeft]);

  const formatPhone = (value) => {
    // Удаляем все символы кроме цифр
    const digits = value.replace(/\D/g, '');
    
    // Добавляем +998 если номер начинается с 9
    if (digits.startsWith('9') && digits.length <= 9) {
      return `+998${digits}`;
    }
    
    // Если уже есть +998, оставляем как есть
    if (digits.startsWith('998')) {
      return `+${digits}`;
    }
    
    return value;
  };

  const validatePhone = (phone) => {
    const phoneRegex = /^\+998\d{9}$/;
    return phoneRegex.test(phone);
  };

  const checkVerificationStatus = async () => {
    if (!currentPhone || !validatePhone(currentPhone)) return;

    try {
      const response = await api.get('/phone-verification/status', {
        params: { phone: currentPhone, purpose }
      });

      setVerificationStatus(response.data);
      
      if (response.data.exists && !response.data.verified) {
        setCodeSent(true);
        setTimeLeft(response.data.time_left_minutes * 60);
        setAttemptsLeft(response.data.max_attempts - response.data.attempts);
      }
    } catch (error) {
      console.error('Error checking verification status:', error);
    }
  };

  const sendVerificationCode = async () => {
    if (!currentPhone || !validatePhone(currentPhone)) {
      toast.error('Введите корректный номер телефона в формате +998XXXXXXXXX');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        phone: currentPhone,
        purpose: purpose
      };

      if (customMessage) {
        payload.custom_message = customMessage;
      }

      const response = await api.post('/phone-verification/send-code', payload);

      if (response.data.success) {
        setCodeSent(true);
        setTimeLeft(response.data.expires_in_minutes * 60);
        setAttemptsLeft(3);
        toast.success('Код верификации отправлен на ваш номер');
      }
    } catch (error) {
      console.error('Error sending verification code:', error);
      
      if (error.response?.status === 429) {
        toast.error('Слишком частые запросы. Попробуйте позже.');
      } else if (error.response?.status === 502) {
        toast.error('Ошибка отправки SMS. Проверьте номер телефона.');
      } else {
        toast.error('Ошибка отправки кода верификации');
      }
    } finally {
      setLoading(false);
    }
  };

  const verifyCode = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      toast.error('Введите 6-значный код');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/phone-verification/verify-code', {
        phone: currentPhone,
        code: verificationCode,
        purpose: purpose
      });

      if (response.data.success) {
        toast.success('Номер телефона успешно подтвержден!');
        if (onVerified) {
          onVerified({
            phone: currentPhone,
            verified_at: response.data.verified_at
          });
        }
      }
    } catch (error) {
      console.error('Error verifying code:', error);
      
      const errorData = error.response?.data?.detail;
      
      if (error.response?.status === 404) {
        toast.error('Код не найден или истек');
        setCodeSent(false);
      } else if (error.response?.status === 410) {
        toast.error('Код истек. Запросите новый код');
        setCodeSent(false);
      } else if (error.response?.status === 429) {
        toast.error('Превышено количество попыток');
        setCodeSent(false);
      } else if (errorData?.attempts_left !== undefined) {
        setAttemptsLeft(errorData.attempts_left);
        toast.error(`Неверный код. Осталось попыток: ${errorData.attempts_left}`);
      } else {
        toast.error('Ошибка проверки кода');
      }
    } finally {
      setLoading(false);
    }
  };

  const cancelVerification = async () => {
    try {
      await api.delete('/phone-verification/cancel', {
        params: { phone: currentPhone, purpose }
      });
      
      setCodeSent(false);
      setVerificationCode('');
      setTimeLeft(0);
      setVerificationStatus(null);
      
      if (onCancel) {
        onCancel();
      }
    } catch (error) {
      console.error('Error cancelling verification:', error);
    }
  };

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const handlePhoneChange = (e) => {
    const formatted = formatPhone(e.target.value);
    setCurrentPhone(formatted);
  };

  const handleCodeChange = (e) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
    setVerificationCode(value);
  };

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-blue-500" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Ввод номера телефона */}
        {(showPhoneInput || !phone) && (
          <div className="space-y-2">
            <Label htmlFor="phone">Номер телефона</Label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                id="phone"
                type="tel"
                value={currentPhone}
                onChange={handlePhoneChange}
                placeholder="+998XXXXXXXXX"
                className="pl-10"
                disabled={codeSent}
              />
            </div>
            {currentPhone && !validatePhone(currentPhone) && (
              <p className="text-sm text-red-500">
                Номер должен быть в формате +998XXXXXXXXX
              </p>
            )}
          </div>
        )}

        {/* Статус верификации */}
        {verificationStatus && verificationStatus.verified && (
          <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle className="h-4 w-4 text-green-500" />
            <span className="text-sm text-green-700">
              Номер телефона уже подтвержден
            </span>
          </div>
        )}

        {/* Отправка кода */}
        {!codeSent && (!verificationStatus || !verificationStatus.verified) && (
          <Button
            onClick={sendVerificationCode}
            disabled={loading || !currentPhone || !validatePhone(currentPhone)}
            className="w-full"
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Отправка...
              </>
            ) : (
              <>
                <Send className="h-4 w-4 mr-2" />
                Отправить код
              </>
            )}
          </Button>
        )}

        {/* Ввод кода верификации */}
        {codeSent && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="code">Код верификации</Label>
              <Input
                id="code"
                type="text"
                value={verificationCode}
                onChange={handleCodeChange}
                placeholder="000000"
                maxLength={6}
                className="text-center text-lg tracking-widest"
              />
              <p className="text-sm text-gray-600">
                Код отправлен на номер {currentPhone}
              </p>
            </div>

            {/* Таймер и попытки */}
            <div className="flex items-center justify-between text-sm text-gray-600">
              <div className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                <span>
                  {timeLeft > 0 ? `Код действителен: ${formatTime(timeLeft)}` : 'Код истек'}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <AlertTriangle className="h-4 w-4" />
                <span>Попыток: {attemptsLeft}</span>
              </div>
            </div>

            {/* Кнопки */}
            <div className="flex gap-2">
              <Button
                onClick={verifyCode}
                disabled={loading || !verificationCode || verificationCode.length !== 6 || timeLeft === 0}
                className="flex-1"
              >
                {loading ? 'Проверка...' : 'Подтвердить'}
              </Button>
              
              <Button
                onClick={timeLeft > 0 ? cancelVerification : sendVerificationCode}
                variant="outline"
                disabled={loading}
                className="flex-1"
              >
                {timeLeft > 0 ? 'Отменить' : 'Повторить'}
              </Button>
            </div>
          </div>
        )}

        {/* Информация о целях верификации */}
        <div className="text-xs text-gray-500 space-y-1">
          {purpose === 'verification' && (
            <p>• Подтверждение номера телефона для безопасности аккаунта</p>
          )}
          {purpose === 'password_reset' && (
            <p>• Сброс пароля через SMS код</p>
          )}
          {purpose === 'phone_change' && (
            <p>• Смена номера телефона в профиле</p>
          )}
          {purpose === 'registration' && (
            <p>• Подтверждение номера при регистрации</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default PhoneVerification;


