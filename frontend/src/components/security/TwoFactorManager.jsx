import React, { useState, useEffect } from 'react';
import { Card, Button } from '../ui/native';
import { 
  Shield, 
  Smartphone, 
  Mail, 
  Key, 
  Settings, 
  Trash2, 
  Download, 
  RefreshCw, 
  CheckCircle, 
  AlertCircle,
  Eye,
  EyeOff,
  Copy,
  Plus,
  Minus,
  Clock,
  Lock,
  Unlock,
  Smartphone as Phone,
  QrCode,
  AlertTriangle
} from 'lucide-react';

/**
 * Расширенный менеджер Two-Factor Authentication
 * Включает все методы 2FA и управление безопасностью
 */
const TwoFactorManager = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [status, setStatus] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [showBackupCodes, setShowBackupCodes] = useState(false);
  const [backupCodes, setBackupCodes] = useState([]);
  const [devices, setDevices] = useState([]);
  const [securityLogs, setSecurityLogs] = useState([]);
  const [recoveryMethods, setRecoveryMethods] = useState([]);

  useEffect(() => {
    loadStatus();
    loadDevices();
    loadSecurityLogs();
    loadRecoveryMethods();
  }, []);

  const loadStatus = async () => {
    try {
      const response = await fetch('/api/v1/2fa/status', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setStatus(data);
    } catch (err) {
      setError('Ошибка загрузки статуса 2FA');
    }
  };

  const loadDevices = async () => {
    try {
      const response = await fetch('/api/v1/2fa/devices', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setDevices(data.devices || []);
    } catch (err) {
      console.error('Error loading devices:', err);
    }
  };

  const loadSecurityLogs = async () => {
    try {
      const response = await fetch('/api/v1/2fa/security-logs', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setSecurityLogs(data.logs || []);
    } catch (err) {
      console.error('Error loading security logs:', err);
    }
  };

  const loadRecoveryMethods = async () => {
    try {
      const response = await fetch('/api/v1/2fa/recovery-methods', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setRecoveryMethods(data.methods || []);
    } catch (err) {
      console.error('Error loading recovery methods:', err);
    }
  };

  const handleEnable2FA = async (method = 'totp') => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/2fa/setup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          method: method,
          recovery_email: status?.recovery_email || '',
          recovery_phone: status?.recovery_phone || ''
        })
      });

      const data = await response.json();
      
      if (response.ok) {
        setStatus(data);
        setSuccess('2FA успешно настроен');
        loadStatus();
      } else {
        setError(data.detail || 'Ошибка настройки 2FA');
      }
    } catch (err) {
      setError('Ошибка настройки 2FA');
    } finally {
      setLoading(false);
    }
  };

  const handleDisable2FA = async () => {
    const password = prompt('Введите пароль для отключения 2FA:');
    if (!password) return;

    const totpCode = prompt('Введите код из приложения аутентификатора:');
    if (!totpCode) return;

    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/2fa/disable', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          password: password,
          totp_code: totpCode
        })
      });

      const data = await response.json();
      
      if (response.ok) {
        setStatus(data);
        setSuccess('2FA успешно отключен');
        loadStatus();
      } else {
        setError(data.detail || 'Ошибка отключения 2FA');
      }
    } catch (err) {
      setError('Ошибка отключения 2FA');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateBackupCodes = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/2fa/regenerate-backup-codes', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      const data = await response.json();
      
      if (response.ok) {
        setBackupCodes(data.backup_codes);
        setShowBackupCodes(true);
        setSuccess('Резервные коды обновлены');
      } else {
        setError(data.detail || 'Ошибка генерации резервных кодов');
      }
    } catch (err) {
      setError('Ошибка генерации резервных кодов');
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeDevice = async (deviceId) => {
    if (!confirm('Вы уверены, что хотите отозвать доступ для этого устройства?')) {
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`/api/v1/2fa/devices/${deviceId}/revoke`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        setSuccess('Доступ устройства отозван');
        loadDevices();
      } else {
        const data = await response.json();
        setError(data.detail || 'Ошибка отзыва доступа');
      }
    } catch (err) {
      setError('Ошибка отзыва доступа');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setSuccess('Скопировано в буфер обмена');
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'enabled': return 'text-green-600 bg-green-50';
      case 'disabled': return 'text-red-600 bg-red-50';
      case 'pending': return 'text-yellow-600 bg-yellow-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'enabled': return 'Включен';
      case 'disabled': return 'Отключен';
      case 'pending': return 'Ожидает настройки';
      default: return 'Неизвестно';
    }
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Статус 2FA */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <Shield className="w-6 h-6 text-blue-600" />
            <h3 className="text-lg font-semibold">Статус двухфакторной аутентификации</h3>
          </div>
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(status?.enabled ? 'enabled' : 'disabled')}`}>
            {getStatusLabel(status?.enabled ? 'enabled' : 'disabled')}
          </div>
        </div>

        {status?.enabled ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <CheckCircle className="w-8 h-8 text-green-600 mx-auto mb-2" />
                <div className="text-sm font-medium text-green-800">TOTP</div>
                <div className="text-xs text-green-600">Активен</div>
              </div>
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <Key className="w-8 h-8 text-blue-600 mx-auto mb-2" />
                <div className="text-sm font-medium text-blue-800">Резервные коды</div>
                <div className="text-xs text-blue-600">{status.backup_codes_remaining || 0} осталось</div>
              </div>
              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <Smartphone className="w-8 h-8 text-purple-600 mx-auto mb-2" />
                <div className="text-sm font-medium text-purple-800">Устройства</div>
                <div className="text-xs text-purple-600">{devices.length} доверенных</div>
              </div>
            </div>

            <div className="flex space-x-2">
              <Button
                onClick={() => setShowBackupCodes(true)}
                variant="outline"
                size="sm"
              >
                <Key className="w-4 h-4 mr-2" />
                Показать резервные коды
              </Button>
              <Button
                onClick={handleRegenerateBackupCodes}
                variant="outline"
                size="sm"
                disabled={loading}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Обновить коды
              </Button>
              <Button
                onClick={handleDisable2FA}
                variant="outline"
                size="sm"
                className="text-red-600 hover:text-red-700"
                disabled={loading}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Отключить 2FA
              </Button>
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <Shield className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h4 className="text-lg font-medium text-gray-900 mb-2">
              Двухфакторная аутентификация отключена
            </h4>
            <p className="text-gray-600 mb-4">
              Включите 2FA для дополнительной защиты вашего аккаунта
            </p>
            <Button
              onClick={() => handleEnable2FA('totp')}
              disabled={loading}
            >
              <Shield className="w-4 h-4 mr-2" />
              Включить 2FA
            </Button>
          </div>
        )}
      </Card>

      {/* Методы восстановления */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Методы восстановления</h3>
        <div className="space-y-3">
          {recoveryMethods.map((method, index) => (
            <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
              <div className="flex items-center space-x-3">
                {method.type === 'email' ? (
                  <Mail className="w-5 h-5 text-blue-600" />
                ) : (
                  <Phone className="w-5 h-5 text-green-600" />
                )}
                <div>
                  <div className="font-medium">{method.label}</div>
                  <div className="text-sm text-gray-600">{method.value}</div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  method.verified ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {method.verified ? 'Подтвержден' : 'Не подтвержден'}
                </span>
                <Button variant="ghost" size="sm">
                  <Settings className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  const renderDevices = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Доверенные устройства</h3>
        <Button
          onClick={loadDevices}
          variant="outline"
          size="sm"
          disabled={loading}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Обновить
        </Button>
      </div>

      {devices.length === 0 ? (
        <Card className="p-8 text-center">
          <Smartphone className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h4 className="text-lg font-medium text-gray-900 mb-2">
            Нет доверенных устройств
          </h4>
          <p className="text-gray-600">
            Устройства появятся здесь после первого входа с 2FA
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {devices.map((device) => (
            <Card key={device.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Smartphone className="w-5 h-5 text-gray-600" />
                  <div>
                    <div className="font-medium">{device.name || 'Неизвестное устройство'}</div>
                    <div className="text-sm text-gray-600">
                      {device.browser} • {device.os} • {device.location}
                    </div>
                    <div className="text-xs text-gray-500">
                      Последний вход: {formatDate(device.last_used)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {device.current && (
                    <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded-full">
                      Текущее
                    </span>
                  )}
                  <Button
                    onClick={() => handleRevokeDevice(device.id)}
                    variant="ghost"
                    size="sm"
                    className="text-red-600 hover:text-red-700"
                    disabled={loading}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );

  const renderSecurityLogs = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Журнал безопасности</h3>
        <Button
          onClick={loadSecurityLogs}
          variant="outline"
          size="sm"
          disabled={loading}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Обновить
        </Button>
      </div>

      {securityLogs.length === 0 ? (
        <Card className="p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h4 className="text-lg font-medium text-gray-900 mb-2">
            Нет записей в журнале
          </h4>
          <p className="text-gray-600">
            Записи о действиях с 2FA появятся здесь
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {securityLogs.map((log, index) => (
            <Card key={index} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-full ${
                    log.type === 'success' ? 'bg-green-100' :
                    log.type === 'warning' ? 'bg-yellow-100' : 'bg-red-100'
                  }`}>
                    {log.type === 'success' ? (
                      <CheckCircle className="w-4 h-4 text-green-600" />
                    ) : log.type === 'warning' ? (
                      <AlertTriangle className="w-4 h-4 text-yellow-600" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-red-600" />
                    )}
                  </div>
                  <div>
                    <div className="font-medium">{log.action}</div>
                    <div className="text-sm text-gray-600">{log.description}</div>
                    <div className="text-xs text-gray-500">
                      {formatDate(log.timestamp)} • {log.ip_address} • {log.user_agent}
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );

  const renderBackupCodes = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Резервные коды</h3>
        <Button
          onClick={handleRegenerateBackupCodes}
          variant="outline"
          size="sm"
          disabled={loading}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Обновить коды
        </Button>
      </div>

      {backupCodes.length > 0 ? (
        <Card className="p-6">
          <div className="mb-4">
            <AlertTriangle className="w-6 h-6 text-yellow-600 mb-2" />
            <h4 className="font-semibold text-yellow-800">Важно!</h4>
            <p className="text-sm text-yellow-700">
              Сохраните эти коды в безопасном месте. Каждый код можно использовать только один раз.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
            {backupCodes.map((code, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <code className="font-mono text-sm">{code}</code>
                <Button
                  onClick={() => copyToClipboard(code)}
                  variant="ghost"
                  size="sm"
                >
                  <Copy className="w-4 h-4" />
                </Button>
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
              onClick={() => {
                const blob = new Blob([backupCodes.join('\n')], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'backup-codes.txt';
                a.click();
                URL.revokeObjectURL(url);
              }}
              variant="outline"
              size="sm"
            >
              <Download className="w-4 h-4 mr-2" />
              Скачать
            </Button>
          </div>
        </Card>
      ) : (
        <Card className="p-8 text-center">
          <Key className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h4 className="text-lg font-medium text-gray-900 mb-2">
            Нет резервных кодов
          </h4>
          <p className="text-gray-600 mb-4">
            Сгенерируйте резервные коды для восстановления доступа
          </p>
          <Button
            onClick={handleRegenerateBackupCodes}
            disabled={loading}
          >
            <Key className="w-4 h-4 mr-2" />
            Сгенерировать коды
          </Button>
        </Card>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Безопасность аккаунта</h2>
          <p className="text-gray-600">Управление двухфакторной аутентификацией</p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            onClick={loadStatus}
            variant="outline"
            size="sm"
            disabled={loading}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>
      </div>

      {/* Навигация */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {[
            { id: 'overview', label: 'Обзор', icon: Shield },
            { id: 'devices', label: 'Устройства', icon: Smartphone },
            { id: 'backup', label: 'Резервные коды', icon: Key },
            { id: 'logs', label: 'Журнал', icon: Clock }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Уведомления */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <span className="text-red-800">{error}</span>
          </div>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-5 h-5 text-green-600" />
            <span className="text-green-800">{success}</span>
          </div>
        </div>
      )}

      {/* Контент */}
      {activeTab === 'overview' && renderOverview()}
      {activeTab === 'devices' && renderDevices()}
      {activeTab === 'backup' && renderBackupCodes()}
      {activeTab === 'logs' && renderSecurityLogs()}
    </div>
  );
};

export default TwoFactorManager;

