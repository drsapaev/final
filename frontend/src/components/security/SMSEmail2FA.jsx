import React, { useState, useEffect } from 'react';
import { Card, Button } from '../ui/native';
import {
  Mail,
  Phone,
  Clock,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Send,
  Shield,
  Key,
  Eye,
  EyeOff
} from 'lucide-react';
import { tokenManager } from '../../utils/tokenManager';

/**
 * Компонент для SMS/Email двухфакторной аутентификации
 * Поддерживает отправку кодов по SMS и Email
 */
const SMSEmail2FA = ({
  method = 'sms', // 'sms' или 'email'
  onSuccess,
  onCancel,
  phoneNumber = '',
  emailAddress = ''
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [code, setCode] = useState('');
  const [timeLeft, setTimeLeft] = useState(0);
  const [canResend, setCanResend] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [showCode, setShowCode] = useState(false);

  const maxAttempts = 3;
  const codeLength = 6;
  const resendDelay = 60; // секунд

  useEffect(() => {
    if (timeLeft > 0) {
      const timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
      return () => clearTimeout(timer);
    } else {
      setCanResend(true);
    }
  }, [timeLeft]);

  const sendCode = async () => {
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch('/api/v1/2fa/send-code', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          method: method,
          phone_number: phoneNumber,
          email_address: emailAddress
        })
      });

      const data = await response.json();

      if (response.ok) {
        setSuccess(`Код отправлен на ${method === 'sms' ? phoneNumber : emailAddress}`);
        setTimeLeft(resendDelay);
        setCanResend(false);
        setAttempts(0);
      } else {
        setError(data.detail || 'Ошибка отправки кода');
      }
    } catch (err) {
      setError('Ошибка отправки кода');
    } finally {
      setLoading(false);
    }
  };

  const verifyCode = async () => {
    if (!code || code.length !== codeLength) {
      setError('Введите 6-значный код');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/2fa/verify-code', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          method: method,
          code: code,
          phone_number: phoneNumber,
          email_address: emailAddress
        })
      });

      const data = await response.json();

      if (response.ok) {
        setSuccess('Код подтвержден успешно!');
        if (onSuccess) {
          onSuccess(data);
        }
      } else {
        setError(data.detail || 'Неверный код');
        setAttempts(prev => prev + 1);

        if (attempts + 1 >= maxAttempts) {
          setError('Превышено количество попыток. Попробуйте позже.');
          setCanResend(false);
        }
      }
    } catch (err) {
      setError('Ошибка проверки кода');
    } finally {
      setLoading(false);
    }
  };

  const handleCodeChange = (e) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, codeLength);
    setCode(value);
    setError('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && code.length === codeLength) {
      verifyCode();
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getMethodIcon = () => {
    return method === 'sms' ? (
      <Phone className="w-6 h-6 text-blue-600" />
    ) : (
      <Mail className="w-6 h-6 text-green-600" />
    );
  };

  const getMethodLabel = () => {
    return method === 'sms' ? 'SMS' : 'Email';
  };

  const getMaskedContact = () => {
    if (method === 'sms' && phoneNumber) {
      const phone = phoneNumber.replace(/(\d{3})(\d{3})(\d{2})(\d{2})/, '+7 ($1) $2-**-**');
      return phone;
    } else if (method === 'email' && emailAddress) {
      const [local, domain] = emailAddress.split('@');
      const maskedLocal = local.slice(0, 2) + '*'.repeat(local.length - 2);
      return `${maskedLocal}@${domain}`;
    }
    return '';
  };

  return (
    <div className="max-w-md mx-auto">
      <Card className="p-6">
        <div className="text-center mb-6">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-blue-50 rounded-full">
              {getMethodIcon()}
            </div>
          </div>
          <h3 className="text-xl font-semibold mb-2">
            Подтверждение через {getMethodLabel()}
          </h3>
          <p className="text-gray-600">
            Мы отправили 6-значный код на:
          </p>
          <p className="font-medium text-gray-900 mt-1">
            {getMaskedContact()}
          </p>
        </div>

        {/* Ввод кода */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Код подтверждения
            </label>
            <div className="relative">
              <input
                type={showCode ? 'text' : 'password'}
                value={code}
                onChange={handleCodeChange}
                onKeyPress={handleKeyPress}
                placeholder="000000"
                className="w-full px-4 py-3 text-center text-2xl font-mono border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                maxLength={codeLength}
                disabled={loading}
              />
              <button
                type="button"
                onClick={() => setShowCode(!showCode)}
                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showCode ? (
                  <EyeOff className="w-5 h-5" />
                ) : (
                  <Eye className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          {/* Кнопки */}
          <div className="space-y-3">
            <Button
              onClick={verifyCode}
              disabled={loading || code.length !== codeLength || attempts >= maxAttempts}
              className="w-full"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4 mr-2" />
              )}
              Подтвердить код
            </Button>

            <div className="flex space-x-2">
              <Button
                onClick={sendCode}
                disabled={loading || !canResend}
                variant="outline"
                className="flex-1"
              >
                <Send className="w-4 h-4 mr-2" />
                {canResend ? 'Отправить код' : `Повторно через ${formatTime(timeLeft)}`}
              </Button>

              {onCancel && (
                <Button
                  onClick={onCancel}
                  variant="outline"
                  className="flex-1"
                >
                  Отмена
                </Button>
              )}
            </div>
          </div>

          {/* Статус попыток */}
          {attempts > 0 && attempts < maxAttempts && (
            <div className="text-center">
              <p className="text-sm text-yellow-600">
                Осталось попыток: {maxAttempts - attempts}
              </p>
            </div>
          )}

          {attempts >= maxAttempts && (
            <div className="text-center">
              <p className="text-sm text-red-600">
                Превышено количество попыток. Попробуйте позже.
              </p>
            </div>
          )}
        </div>

        {/* Уведомления */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-600" />
              <span className="text-sm text-red-800">{error}</span>
            </div>
          </div>
        )}

        {success && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="text-sm text-green-800">{success}</span>
            </div>
          </div>
        )}

        {/* Дополнительная информация */}
        <div className="mt-6 pt-4 border-t border-gray-200">
          <div className="text-xs text-gray-500 space-y-1">
            <p>• Код действителен в течение 5 минут</p>
            <p>• Не передавайте код третьим лицам</p>
            <p>• Если код не пришел, проверьте спам</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default SMSEmail2FA;

