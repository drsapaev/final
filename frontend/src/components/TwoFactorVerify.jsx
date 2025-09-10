import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Shield, Smartphone, Key, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';

const TwoFactorVerify = ({ onSuccess, onCancel, method = 'totp' }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Verification data
  const [totpCode, setTotpCode] = useState('');
  const [backupCode, setBackupCode] = useState('');
  const [recoveryToken, setRecoveryToken] = useState('');
  const [rememberDevice, setRememberDevice] = useState(false);

  const handleVerify = async () => {
    setLoading(true);
    setError('');
    
    try {
      const requestData = {
        remember_device: rememberDevice
      };

      if (method === 'totp' && totpCode) {
        requestData.totp_code = totpCode;
      } else if (method === 'backup' && backupCode) {
        requestData.backup_code = backupCode;
      } else if (method === 'recovery' && recoveryToken) {
        requestData.recovery_token = recoveryToken;
      } else {
        setError('Введите код для верификации');
        setLoading(false);
        return;
      }

      const response = await api.post('/2fa/verify', requestData);
      
      if (response.success) {
        setSuccess('Верификация успешна!');
        if (onSuccess) {
          onSuccess(response);
        }
      } else {
        setError(response.message || 'Неверный код');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка верификации');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleVerify();
    }
  };

  const renderTOTPForm = () => (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Smartphone size={48} style={{ color: 'var(--accent-color)', marginBottom: '16px' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Введите код из приложения
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Откройте приложение аутентификатора и введите 6-значный код
        </p>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontWeight: '500',
          color: 'var(--text-primary)'
        }}>
          Код аутентификатора:
        </label>
        <input
          type="text"
          value={totpCode}
          onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          onKeyPress={handleKeyPress}
          placeholder="123456"
          maxLength={6}
          style={{
            width: '100%',
            padding: '16px',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            fontSize: '24px',
            textAlign: 'center',
            letterSpacing: '4px',
            fontFamily: 'monospace',
            fontWeight: '500'
          }}
        />
      </div>
    </div>
  );

  const renderBackupCodeForm = () => (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Key size={48} style={{ color: 'var(--accent-color)', marginBottom: '16px' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Введите backup код
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Используйте один из ваших backup кодов для входа
        </p>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontWeight: '500',
          color: 'var(--text-primary)'
        }}>
          Backup код:
        </label>
        <input
          type="text"
          value={backupCode}
          onChange={(e) => setBackupCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8))}
          onKeyPress={handleKeyPress}
          placeholder="ABCD1234"
          maxLength={8}
          style={{
            width: '100%',
            padding: '16px',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            fontSize: '18px',
            textAlign: 'center',
            letterSpacing: '2px',
            fontFamily: 'monospace',
            fontWeight: '500'
          }}
        />
      </div>
    </div>
  );

  const renderRecoveryForm = () => (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Shield size={48} style={{ color: 'var(--accent-color)', marginBottom: '16px' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Восстановление доступа
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Введите токен восстановления, отправленный на ваш email или телефон
        </p>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontWeight: '500',
          color: 'var(--text-primary)'
        }}>
          Токен восстановления:
        </label>
        <input
          type="text"
          value={recoveryToken}
          onChange={(e) => setRecoveryToken(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Введите токен восстановления"
          style={{
            width: '100%',
            padding: '16px',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            fontSize: '14px',
            fontFamily: 'monospace'
          }}
        />
      </div>
    </div>
  );

  return (
    <div style={{ maxWidth: '400px', margin: '0 auto' }}>
      {method === 'totp' && renderTOTPForm()}
      {method === 'backup' && renderBackupCodeForm()}
      {method === 'recovery' && renderRecoveryForm()}

      {method !== 'recovery' && (
        <div style={{ marginBottom: '24px' }}>
          <label style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px',
            cursor: 'pointer',
            color: 'var(--text-primary)'
          }}>
            <input
              type="checkbox"
              checked={rememberDevice}
              onChange={(e) => setRememberDevice(e.target.checked)}
              style={{ margin: 0 }}
            />
            <span style={{ fontSize: '14px' }}>
              Запомнить это устройство на 30 дней
            </span>
          </label>
        </div>
      )}

      {error && (
        <div style={{ 
          background: '#FEE2E2', 
          border: '1px solid #FCA5A5', 
          borderRadius: '8px', 
          padding: '12px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          color: '#DC2626',
          fontSize: '14px'
        }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div style={{ 
          background: '#D1FAE5', 
          border: '1px solid #6EE7B7', 
          borderRadius: '8px', 
          padding: '12px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          color: '#059669',
          fontSize: '14px'
        }}>
          <CheckCircle size={16} />
          <span>{success}</span>
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px' }}>
        <button
          onClick={handleVerify}
          disabled={loading || (
            (method === 'totp' && totpCode.length !== 6) ||
            (method === 'backup' && backupCode.length !== 8) ||
            (method === 'recovery' && !recoveryToken)
          )}
          style={{
            flex: 1,
            padding: '16px 24px',
            background: 'var(--accent-color)',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: (loading || (
              (method === 'totp' && totpCode.length !== 6) ||
              (method === 'backup' && backupCode.length !== 8) ||
              (method === 'recovery' && !recoveryToken)
            )) ? 'not-allowed' : 'pointer',
            fontSize: '16px',
            fontWeight: '500',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw size={20} className="animate-spin" /> : <CheckCircle size={20} />}
          {loading ? 'Проверка...' : 'Подтвердить'}
        </button>
        
        {onCancel && (
          <button
            onClick={onCancel}
            style={{
              padding: '16px 24px',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: '500'
            }}
          >
            Отмена
          </button>
        )}
      </div>
    </div>
  );
};

export default TwoFactorVerify;
