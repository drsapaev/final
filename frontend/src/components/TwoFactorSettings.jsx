import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { 
  Shield, 
  Smartphone, 
  Key, 
  Settings, 
  Trash2, 
  Download, 
  RefreshCw, 
  CheckCircle, 
  AlertCircle,
  Eye,
  EyeOff,
  Copy
} from 'lucide-react';

const TwoFactorSettings = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [status, setStatus] = useState(null);
  const [showBackupCodes, setShowBackupCodes] = useState(false);
  const [backupCodes, setBackupCodes] = useState([]);
  const [devices, setDevices] = useState([]);
  const [copiedCode, setCopiedCode] = useState('');

  useEffect(() => {
    loadStatus();
    loadDevices();
  }, []);

  const loadStatus = async () => {
    try {
      const response = await api.get('/2fa/status');
      setStatus(response);
    } catch (err) {
      setError('Ошибка загрузки статуса 2FA');
    }
  };

  const loadDevices = async () => {
    try {
      const response = await api.get('/2fa/devices');
      setDevices(response.devices || []);
    } catch (err) {
      console.error('Error loading devices:', err);
    }
  };

  const loadBackupCodes = async () => {
    try {
      const response = await api.get('/2fa/backup-codes');
      setBackupCodes(response.backup_codes || []);
      setShowBackupCodes(true);
    } catch (err) {
      setError('Ошибка загрузки backup кодов');
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
      const response = await api.post('/2fa/disable', {
        password,
        totp_code: totpCode
      });

      if (response.success) {
        setSuccess('2FA успешно отключена');
        loadStatus();
      } else {
        setError('Неверный пароль или код');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка отключения 2FA');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateBackupCodes = async () => {
    if (!confirm('Перегенерировать backup коды? Старые коды станут недействительными.')) {
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.post('/2fa/backup-codes/regenerate');
      setBackupCodes(response.backup_codes || []);
      setShowBackupCodes(true);
      setSuccess('Backup коды перегенерированы');
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка перегенерации кодов');
    } finally {
      setLoading(false);
    }
  };

  const handleUntrustDevice = async (deviceId) => {
    if (!confirm('Отозвать доверие к этому устройству?')) {
      return;
    }

    try {
      await api.delete(`/2fa/devices/${deviceId}`);
      setSuccess('Доверие к устройству отозвано');
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка отзыва доверия');
    }
  };

  const copyToClipboard = (text, code) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(''), 2000);
  };

  const downloadBackupCodes = () => {
    const codesText = backupCodes.join('\n');
    const blob = new Blob([codesText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'backup-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!status) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '200px' 
      }}>
        <RefreshCw size={24} className="animate-spin" />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ 
          margin: '0 0 8px 0', 
          color: 'var(--text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <Shield size={32} />
          Двухфакторная аутентификация
        </h1>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Управление настройками безопасности вашего аккаунта
        </p>
      </div>

      {error && (
        <div style={{ 
          background: '#FEE2E2', 
          border: '1px solid #FCA5A5', 
          borderRadius: '8px', 
          padding: '16px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          color: '#DC2626'
        }}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div style={{ 
          background: '#D1FAE5', 
          border: '1px solid #6EE7B7', 
          borderRadius: '8px', 
          padding: '16px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          color: '#059669'
        }}>
          <CheckCircle size={20} />
          <span>{success}</span>
        </div>
      )}

      {/* Статус 2FA */}
      <div style={{ 
        background: 'var(--bg-secondary)', 
        padding: '24px', 
        borderRadius: '12px',
        marginBottom: '24px'
      }}>
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          marginBottom: '16px'
        }}>
          <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
            Статус 2FA
          </h3>
          <div style={{
            padding: '4px 12px',
            background: status.enabled ? '#D1FAE5' : '#FEE2E2',
            color: status.enabled ? '#059669' : '#DC2626',
            borderRadius: '20px',
            fontSize: '12px',
            fontWeight: '500'
          }}>
            {status.enabled ? 'Включена' : 'Отключена'}
          </div>
        </div>

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px',
          marginBottom: '16px'
        }}>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>
              TOTP
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: '500' }}>
              {status.totp_verified ? 'Настроен' : 'Не настроен'}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>
              Backup коды
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: '500' }}>
              {status.backup_codes_count} осталось
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>
              Восстановление
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: '500' }}>
              {status.recovery_enabled ? 'Настроено' : 'Не настроено'}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>
              Доверенные устройства
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: '500' }}>
              {status.trusted_devices_count}
            </div>
          </div>
        </div>

        {status.last_used && (
          <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
            Последнее использование: {new Date(status.last_used).toLocaleString()}
          </div>
        )}
      </div>

      {/* Backup коды */}
      {status.enabled && (
        <div style={{ 
          background: 'var(--bg-secondary)', 
          padding: '24px', 
          borderRadius: '12px',
          marginBottom: '24px'
        }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            marginBottom: '16px'
          }}>
            <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
              Backup коды
            </h3>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={loadBackupCodes}
                style={{
                  padding: '8px 12px',
                  background: 'var(--accent-color)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <Eye size={12} />
                Показать
              </button>
              <button
                onClick={handleRegenerateBackupCodes}
                disabled={loading}
                style={{
                  padding: '8px 12px',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                Перегенерировать
              </button>
            </div>
          </div>

          {showBackupCodes && backupCodes.length > 0 && (
            <div>
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(2, 1fr)', 
                gap: '8px',
                marginBottom: '16px'
              }}>
                {backupCodes.map((code, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 12px',
                      background: 'var(--bg-primary)',
                      borderRadius: '6px',
                      border: '1px solid var(--border-color)'
                    }}
                  >
                    <code style={{ 
                      flex: 1, 
                      fontFamily: 'monospace', 
                      fontSize: '12px',
                      color: 'var(--text-primary)'
                    }}>
                      {code}
                    </code>
                    <button
                      onClick={() => copyToClipboard(code, `code-${index}`)}
                      style={{
                        padding: '4px',
                        background: 'transparent',
                        color: 'var(--text-secondary)',
                        border: 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center'
                      }}
                    >
                      {copiedCode === `code-${index}` ? <CheckCircle size={12} /> : <Copy size={12} />}
                    </button>
                  </div>
                ))}
              </div>
              
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                padding: '12px',
                background: '#FEF3C7',
                borderRadius: '6px',
                border: '1px solid #F59E0B'
              }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  color: '#92400E',
                  fontSize: '12px'
                }}>
                  <AlertCircle size={16} />
                  <span style={{ fontWeight: '500' }}>Важно:</span>
                  <span>Сохраните эти коды в безопасном месте. Каждый код можно использовать только один раз.</span>
                </div>
                <button
                  onClick={downloadBackupCodes}
                  style={{
                    padding: '4px 8px',
                    background: '#F59E0B',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Download size={12} />
                  Скачать
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Доверенные устройства */}
      {devices.length > 0 && (
        <div style={{ 
          background: 'var(--bg-secondary)', 
          padding: '24px', 
          borderRadius: '12px',
          marginBottom: '24px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', color: 'var(--text-primary)' }}>
            Доверенные устройства
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {devices.map((device) => (
              <div
                key={device.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px',
                  background: 'var(--bg-primary)',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)'
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ 
                    fontWeight: '500', 
                    color: 'var(--text-primary)',
                    marginBottom: '4px'
                  }}>
                    {device.device_name}
                  </div>
                  <div style={{ 
                    fontSize: '12px', 
                    color: 'var(--text-secondary)',
                    marginBottom: '4px'
                  }}>
                    {device.device_type} • {device.ip_address}
                  </div>
                  <div style={{ 
                    fontSize: '12px', 
                    color: 'var(--text-secondary)'
                  }}>
                    {device.last_used ? 
                      `Последнее использование: ${new Date(device.last_used).toLocaleString()}` :
                      'Никогда не использовалось'
                    }
                  </div>
                </div>
                
                <button
                  onClick={() => handleUntrustDevice(device.id)}
                  style={{
                    padding: '8px 12px',
                    background: '#FEE2E2',
                    color: '#DC2626',
                    border: '1px solid #FCA5A5',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Trash2 size={12} />
                  Отозвать
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Действия */}
      <div style={{ 
        background: 'var(--bg-secondary)', 
        padding: '24px', 
        borderRadius: '12px'
      }}>
        <h3 style={{ margin: '0 0 16px 0', color: 'var(--text-primary)' }}>
          Действия
        </h3>
        
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {!status.enabled ? (
            <button
              onClick={() => window.location.href = '/settings/2fa/setup'}
              style={{
                padding: '12px 24px',
                background: 'var(--accent-color)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <Shield size={16} />
              Настроить 2FA
            </button>
          ) : (
            <button
              onClick={handleDisable2FA}
              disabled={loading}
              style={{
                padding: '12px 24px',
                background: '#FEE2E2',
                color: '#DC2626',
                border: '1px solid #FCA5A5',
                borderRadius: '8px',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: '500',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <Trash2 size={16} />
              {loading ? 'Отключение...' : 'Отключить 2FA'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default TwoFactorSettings;

