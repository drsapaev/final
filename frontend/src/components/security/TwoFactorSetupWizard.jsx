import React, { useState, useEffect } from 'react';
import { Card, Button } from '../ui/native';
import tokenManager from '../../utils/tokenManager';
import {
  Shield,
  Smartphone,
  Mail,
  Phone,
  Key,
  QrCode,
  Download,
  Copy,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  Eye,
  EyeOff
} from 'lucide-react';

/**
 * Мастер настройки Two-Factor Authentication
 * Пошаговая настройка всех методов 2FA
 */
const TwoFactorSetupWizard = ({ onComplete, onCancel }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedMethod, setSelectedMethod] = useState('totp');
  const [setupData, setSetupData] = useState(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);
  const [recoveryEmail, setRecoveryEmail] = useState('');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [showSecret, setShowSecret] = useState(false);

  const steps = [
    { id: 1, title: 'Выбор метода', description: 'Выберите способ двухфакторной аутентификации' },
    { id: 2, title: 'Настройка', description: 'Настройте выбранный метод' },
    { id: 3, title: 'Подтверждение', description: 'Подтвердите настройку' },
    { id: 4, title: 'Резервные коды', description: 'Сохраните резервные коды' },
    { id: 5, title: 'Завершение', description: 'Настройка завершена' }
  ];

  const methods = [
    {
      id: 'totp',
      name: 'Приложение-аутентификатор',
      description: 'Google Authenticator, Authy, Microsoft Authenticator',
      icon: Smartphone,
      color: 'blue',
      recommended: true
    },
    {
      id: 'sms',
      name: 'SMS коды',
      description: 'Коды по SMS на номер телефона',
      icon: Phone,
      color: 'green'
    },
    {
      id: 'email',
      name: 'Email коды',
      description: 'Коды на email адрес',
      icon: Mail,
      color: 'purple'
    }
  ];

  const handleMethodSelect = (methodId) => {
    setSelectedMethod(methodId);
    setError('');
  };

  const handleSetup = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/2fa/setup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          method: selectedMethod,
          recovery_email: recoveryEmail || null,
          recovery_phone: recoveryPhone || null
        })
      });

      const data = await response.json();

      if (response.ok) {
        setSetupData(data);
        setBackupCodes(data.backup_codes || []);
        setCurrentStep(3);
        setSuccess('Настройка создана успешно');
      } else {
        setError(data.detail || 'Ошибка настройки 2FA');
      }
    } catch (err) {
      setError('Ошибка настройки 2FA');
    } finally {
      setLoading(false);
    }
  };

  const handleVerification = async () => {
    if (!verificationCode) {
      setError('Введите код подтверждения');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/2fa/verify-setup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          method: selectedMethod,
          code: verificationCode
        })
      });

      const data = await response.json();

      if (response.ok) {
        setCurrentStep(4);
        setSuccess('Код подтвержден успешно');
      } else {
        setError(data.detail || 'Неверный код');
      }
    } catch (err) {
      setError('Ошибка проверки кода');
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = () => {
    if (onComplete) {
      onComplete();
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setSuccess('Скопировано в буфер обмена');
  };

  const downloadBackupCodes = () => {
    const blob = new Blob([backupCodes.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'backup-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderStepIndicator = () => (
    <div className="flex items-center justify-center space-x-4 mb-8">
      {steps.map((step, index) => (
        <div key={step.id} className="flex items-center">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${currentStep >= step.id
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-600'
            }`}>
            {currentStep > step.id ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              step.id
            )}
          </div>
          {index < steps.length - 1 && (
            <div className={`w-8 h-0.5 ${currentStep > step.id ? 'bg-blue-600' : 'bg-gray-200'
              }`} />
          )}
        </div>
      ))}
    </div>
  );

  const renderStep1 = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold mb-2">Выберите метод 2FA</h3>
        <p className="text-gray-600">
          Выберите наиболее удобный для вас способ двухфакторной аутентификации
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {methods.map((method) => {
          const IconComponent = method.icon;
          return (
            <button
              key={method.id}
              onClick={() => handleMethodSelect(method.id)}
              className={`p-6 border-2 rounded-lg text-left transition-all ${selectedMethod === method.id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
                }`}
            >
              <div className="flex items-start space-x-3">
                <div className={`p-2 rounded-lg ${selectedMethod === method.id ? 'bg-blue-100' : 'bg-gray-100'
                  }`}>
                  <IconComponent className={`w-6 h-6 ${selectedMethod === method.id ? 'text-blue-600' : 'text-gray-600'
                    }`} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h4 className="font-semibold">{method.name}</h4>
                    {method.recommended && (
                      <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
                        Рекомендуется
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{method.description}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex justify-end">
        <Button
          onClick={() => setCurrentStep(2)}
          disabled={!selectedMethod}
        >
          Далее
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold mb-2">Настройка {methods.find(m => m.id === selectedMethod)?.name}</h3>
        <p className="text-gray-600">
          Заполните необходимые данные для настройки
        </p>
      </div>

      <div className="space-y-4">
        {(selectedMethod === 'sms' || selectedMethod === 'email') && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {selectedMethod === 'sms' ? 'Номер телефона' : 'Email адрес'}
            </label>
            <input
              type={selectedMethod === 'sms' ? 'tel' : 'email'}
              value={selectedMethod === 'sms' ? recoveryPhone : recoveryEmail}
              onChange={(e) => {
                if (selectedMethod === 'sms') {
                  setRecoveryPhone(e.target.value);
                } else {
                  setRecoveryEmail(e.target.value);
                }
              }}
              placeholder={selectedMethod === 'sms' ? '+7 (999) 123-45-67' : 'user@example.com'}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Email для восстановления (опционально)
          </label>
          <input
            type="email"
            value={recoveryEmail}
            onChange={(e) => setRecoveryEmail(e.target.value)}
            placeholder="recovery@example.com"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Телефон для восстановления (опционально)
          </label>
          <input
            type="tel"
            value={recoveryPhone}
            onChange={(e) => setRecoveryPhone(e.target.value)}
            placeholder="+7 (999) 123-45-67"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="flex justify-between">
        <Button
          onClick={() => setCurrentStep(1)}
          variant="outline"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Назад
        </Button>
        <Button
          onClick={handleSetup}
          disabled={loading}
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Shield className="w-4 h-4 mr-2" />
          )}
          Настроить
        </Button>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold mb-2">Подтверждение настройки</h3>
        <p className="text-gray-600">
          {selectedMethod === 'totp'
            ? 'Отсканируйте QR-код в приложении-аутентификаторе и введите код'
            : 'Введите код, который мы отправили вам'
          }
        </p>
      </div>

      {selectedMethod === 'totp' && setupData && (
        <div className="text-center">
          <div className="bg-white p-4 rounded-lg border inline-block">
            <div className="flex justify-center mb-4">
              <QrCode className="w-8 h-8 text-gray-600" />
            </div>
            <div className="text-sm text-gray-600 mb-2">
              Отсканируйте QR-код в приложении:
            </div>
            <div className="bg-gray-100 p-4 rounded-lg mb-4">
              {/* Здесь должен быть QR-код */}
              <div className="w-48 h-48 bg-gray-200 rounded flex items-center justify-center">
                <span className="text-gray-500">QR Code</span>
              </div>
            </div>
            <div className="text-sm text-gray-600 mb-2">
              Или введите секретный ключ вручную:
            </div>
            <div className="flex items-center space-x-2">
              <code className="px-3 py-2 bg-gray-100 rounded font-mono text-sm">
                {showSecret ? setupData.secret : '••••••••••••••••'}
              </code>
              <button
                onClick={() => setShowSecret(!showSecret)}
                className="text-gray-400 hover:text-gray-600"
              >
                {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
              <button
                onClick={() => copyToClipboard(setupData.secret)}
                className="text-gray-400 hover:text-gray-600"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Код подтверждения
        </label>
        <input
          type="text"
          value={verificationCode}
          onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="000000"
          className="w-full px-3 py-2 text-center text-2xl font-mono border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          maxLength={6}
        />
      </div>

      <div className="flex justify-between">
        <Button
          onClick={() => setCurrentStep(2)}
          variant="outline"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Назад
        </Button>
        <Button
          onClick={handleVerification}
          disabled={loading || verificationCode.length !== 6}
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <CheckCircle className="w-4 h-4 mr-2" />
          )}
          Подтвердить
        </Button>
      </div>
    </div>
  );

  const renderStep4 = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold mb-2">Резервные коды</h3>
        <p className="text-gray-600">
          Сохраните эти коды в безопасном месте. Каждый код можно использовать только один раз.
        </p>
      </div>

      <Card className="p-6">
        <div className="mb-4">
          <AlertCircle className="w-6 h-6 text-yellow-600 mb-2" />
          <h4 className="font-semibold text-yellow-800">Важно!</h4>
          <p className="text-sm text-yellow-700">
            Сохраните эти коды в безопасном месте. Они понадобятся для восстановления доступа.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
          {backupCodes.map((code, index) => (
            <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <code className="font-mono text-sm">{code}</code>
              <button
                onClick={() => copyToClipboard(code)}
                className="text-gray-400 hover:text-gray-600"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        <div className="flex space-x-2">
          <Button
            onClick={() => copyToClipboard(backupCodes.join('\n'))}
            variant="outline"
            size="sm"
          >
            <Copy className="w-4 h-4 mr-2" />
            Копировать все
          </Button>
          <Button
            onClick={downloadBackupCodes}
            variant="outline"
            size="sm"
          >
            <Download className="w-4 h-4 mr-2" />
            Скачать
          </Button>
        </div>
      </Card>

      <div className="flex justify-end">
        <Button
          onClick={() => setCurrentStep(5)}
        >
          Продолжить
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );

  const renderStep5 = () => (
    <div className="text-center space-y-6">
      <div className="flex justify-center">
        <div className="p-4 bg-green-100 rounded-full">
          <CheckCircle className="w-12 h-12 text-green-600" />
        </div>
      </div>

      <div>
        <h3 className="text-xl font-semibold mb-2">Настройка завершена!</h3>
        <p className="text-gray-600">
          Двухфакторная аутентификация успешно настроена и активирована.
        </p>
      </div>

      <div className="bg-blue-50 p-4 rounded-lg">
        <h4 className="font-semibold text-blue-800 mb-2">Что дальше?</h4>
        <ul className="text-sm text-blue-700 space-y-1 text-left">
          <li>• При входе в систему потребуется код из приложения</li>
          <li>• Резервные коды можно использовать при потере устройства</li>
          <li>• Настройки можно изменить в разделе "Безопасность"</li>
        </ul>
      </div>

      <div className="flex justify-center">
        <Button
          onClick={handleComplete}
        >
          <Shield className="w-4 h-4 mr-2" />
          Завершить
        </Button>
      </div>
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto">
      <Card className="p-8">
        {renderStepIndicator()}

        {currentStep === 1 && renderStep1()}
        {currentStep === 2 && renderStep2()}
        {currentStep === 3 && renderStep3()}
        {currentStep === 4 && renderStep4()}
        {currentStep === 5 && renderStep5()}

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
      </Card>
    </div>
  );
};

export default TwoFactorSetupWizard;

