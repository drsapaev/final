import { useState } from 'react';
import { api } from '../api/client';
import { Shield, Smartphone, Key, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import PropTypes from 'prop-types';
import { Input,
  Checkbox} from '../ui/macos';

const TwoFactorVerify = ({ onSuccess, onCancel, method = 'totp', pendingToken }) => {
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

      // Добавляем pending_2fa_token если он есть
      if (pendingToken) {
        requestData.pending_2fa_token = pendingToken;
      }

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

      if (response.data?.access_token || response.success) {
        setSuccess('Верификация успешна!');
        if (onSuccess) {
          onSuccess(response);
        }
      } else {
        setError(response.data?.message || response.message || 'Неверный код');
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

  const renderTOTPForm = () =>
  <div>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Smartphone size={48} style={{ color: 'var(--accent-color)', marginBottom: 'var(--mac-spacing-4)' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Введите код из приложения
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Откройте приложение аутентификатора и введите 6-значный код
        </p>
      </div>

      <div style={{ marginBottom: 'var(--mac-spacing-6)' }}>
        <label style={{
        display: 'block',
        marginBottom: 'var(--mac-spacing-2)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--text-primary)'
      }}>
          Код аутентификатора:
        </label>
        <Input
        type="text"
        aria-label="Authenticator code"
        value={totpCode}
        onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
        onKeyPress={handleKeyPress}
        placeholder="123456"
        maxLength={6}
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-4)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)',
          background: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          fontSize: 'var(--mac-font-size-3xl)',
          textAlign: 'center',
          letterSpacing: '4px',
          fontFamily: 'monospace',
          fontWeight: 'var(--mac-font-weight-medium)'
        }} />

      </div>
    </div>;


  const renderBackupCodeForm = () =>
  <div>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Key size={48} style={{ color: 'var(--accent-color)', marginBottom: 'var(--mac-spacing-4)' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Введите backup код
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Используйте один из ваших backup кодов для входа
        </p>
      </div>

      <div style={{ marginBottom: 'var(--mac-spacing-6)' }}>
        <label style={{
        display: 'block',
        marginBottom: 'var(--mac-spacing-2)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--text-primary)'
      }}>
          Backup код:
        </label>
        <Input
        type="text"
        aria-label="Backup code"
        value={backupCode}
        onChange={(e) => setBackupCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8))}
        onKeyPress={handleKeyPress}
        placeholder="ABCD1234"
        maxLength={8}
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-4)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)',
          background: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          fontSize: 'var(--mac-font-size-xl)',
          textAlign: 'center',
          letterSpacing: '2px',
          fontFamily: 'monospace',
          fontWeight: 'var(--mac-font-weight-medium)'
        }} />

      </div>
    </div>;


  const renderRecoveryForm = () =>
  <div>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Shield size={48} style={{ color: 'var(--accent-color)', marginBottom: 'var(--mac-spacing-4)' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Восстановление доступа
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Введите токен восстановления, отправленный на ваш email или телефон
        </p>
      </div>

      <div style={{ marginBottom: 'var(--mac-spacing-6)' }}>
        <label style={{
        display: 'block',
        marginBottom: 'var(--mac-spacing-2)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--text-primary)'
      }}>
          Токен восстановления:
        </label>
        <Input
        type="text"
        aria-label="Recovery token"
        value={recoveryToken}
        onChange={(e) => setRecoveryToken(e.target.value)}
        onKeyPress={handleKeyPress}
        placeholder="Введите токен восстановления"
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-4)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)',
          background: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          fontSize: 'var(--mac-font-size-base)',
          fontFamily: 'monospace'
        }} />

      </div>
    </div>;


  return (
    <div style={{ maxWidth: '400px', margin: '0 auto' }}>
      {method === 'totp' && renderTOTPForm()}
      {method === 'backup' && renderBackupCodeForm()}
      {method === 'recovery' && renderRecoveryForm()}

      {method !== 'recovery' &&
      <div style={{ marginBottom: 'var(--mac-spacing-6)' }}>
          <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)',
          cursor: 'pointer',
          color: 'var(--text-primary)'
        }}>
            <Checkbox aria-label="Remember this device for 30 days" checked={rememberDevice} onChange={(e) => setRememberDevice(e.target.checked)}
            style={{ margin: 0 }} />

            <span style={{ fontSize: 'var(--mac-font-size-base)' }}>
              Запомнить это устройство на 30 дней
            </span>
          </label>
        </div>
      }

      {error &&
      <div style={{
        background: 'var(--mac-error-bg)',
        border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))',
        borderRadius: 'var(--mac-radius-md)',
        padding: 'var(--mac-spacing-3)',
        marginBottom: 'var(--mac-spacing-4)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)',
        color: 'var(--mac-error)',
        fontSize: 'var(--mac-font-size-base)'
      }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      }

      {success &&
      <div style={{
        background: 'var(--mac-success-bg)',
        border: '1px solid #6EE7B7',
        borderRadius: 'var(--mac-radius-md)',
        padding: 'var(--mac-spacing-3)',
        marginBottom: 'var(--mac-spacing-4)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)',
        color: 'var(--mac-success)',
        fontSize: 'var(--mac-font-size-base)'
      }}>
          <CheckCircle size={16} />
          <span>{success}</span>
        </div>
      }

      <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)' }}>
        <button
          onClick={handleVerify}
          disabled={loading ||
          method === 'totp' && totpCode.length !== 6 ||
          method === 'backup' && backupCode.length !== 8 ||
          method === 'recovery' && !recoveryToken
          }
          style={{
            flex: 1,
            padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
            background: 'var(--accent-color)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--mac-radius-md)',
            cursor: loading ||
            method === 'totp' && totpCode.length !== 6 ||
            method === 'backup' && backupCode.length !== 8 ||
            method === 'recovery' && !recoveryToken ?
            'not-allowed' : 'pointer',
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-medium)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--mac-spacing-2)'
          }}>

          {loading ? <RefreshCw size={20} className="animate-spin" /> : <CheckCircle size={20} />}
          {loading ? 'Проверка...' : 'Подтвердить'}
        </button>
        
        {onCancel &&
        <button
          onClick={onCancel}
          style={{
            padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-medium)'
          }}>

            Отмена
          </button>
        }
      </div>
    </div>);

};


TwoFactorVerify.propTypes = {
  ...(TwoFactorVerify.propTypes || {}),
  method: PropTypes.any,
  onCancel: PropTypes.any,
  onSuccess: PropTypes.any,
  pendingToken: PropTypes.any,
};

export default TwoFactorVerify;
