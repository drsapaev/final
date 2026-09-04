import { useState } from 'react';
import { api } from '../api/client';
import { RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import { Input, Checkbox } from './ui/macos';
import { useTranslation } from '../i18n/useTranslation';
import { getErrorMessage } from '../utils/type-guards';

interface TwoFactorVerifyProps {
  onSuccess?: (response: { data?: Record<string, unknown> }) => void;
  onCancel?: () => void;
  method?: string;
  pendingToken?: string;
}

/**
 * Форма подтверждения 2FA (challenge при входе).
 *
 * Живёт внутри стеклянной Card из LoginFormStyled (общий заголовок и
 * «Отмена» — там); здесь только поля ввода и кнопка подтверждения.
 * Слой UI: токены --mac-* (frontend/DESIGN_SYSTEM.md UI Layer Contract).
 */
const TwoFactorVerify = ({ onSuccess, method = 'totp', pendingToken }: TwoFactorVerifyProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [totpCode, setTotpCode] = useState('');
  const [backupCode, setBackupCode] = useState('');
  const [recoveryToken, setRecoveryToken] = useState('');
  const [rememberDevice, setRememberDevice] = useState(false);

  const handleVerify = async () => {
    setLoading(true);
    setError('');

    try {
      const requestData: Record<string, unknown> = {
        remember_device: rememberDevice
      };

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
        setError(t('misc.tfv_vvedite_kod_dlya_verifikatsi'));
        setLoading(false);
        return;
      }

      const response = await api.post('/2fa/verify', requestData);

      if (response.data?.access_token || response.data?.success) {
        setSuccess(t('misc.tfv_verifikatsiya_uspeshna'));
        if (onSuccess) {
          onSuccess(response);
        }
      } else {
        setError(response.data?.message || t('misc.tfv_nevernyy_kod'));
      }
    } catch (err) {
      setError(getErrorMessage(err) || t('misc.tfv_oshibka_verifikatsii'));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleVerify();
    }
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    textAlign: 'center',
    marginBottom: 'var(--mac-spacing-2)',
    fontWeight: 'var(--mac-font-weight-medium)' as React.CSSProperties['fontWeight'],
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-sm)',
  };

  const codeInputStyle: React.CSSProperties = {
    width: '100%',
    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-md)',
    background: 'var(--mac-bg-content)',
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-xl)',
    textAlign: 'center',
    letterSpacing: '0.4em',
    fontFamily: 'var(--mac-font-family-mono, monospace)',
    fontWeight: 'var(--mac-font-weight-medium)' as React.CSSProperties['fontWeight'],
  };

  const hintStyle: React.CSSProperties = {
    textAlign: 'center',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-sm)',
    margin: '0 0 var(--mac-spacing-4) 0',
  };

  return (
    <div style={{ maxWidth: '400px', margin: '0 auto' }}>
      {method === 'totp' && (
        <div>
          <p style={hintStyle}>Откройте приложение аутентификатора и введите 6-значный код</p>
          <label style={labelStyle}>Код аутентификатора</label>
          <Input
            key="totp"
            autoFocus
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            aria-label="Authenticator code"
            value={totpCode}
            onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            onKeyPress={handleKeyPress}
            placeholder="000000"
            maxLength={6}
            style={codeInputStyle}
          />
        </div>
      )}

      {method === 'backup' && (
        <div>
          <p style={hintStyle}>Используйте один из резервных кодов, сохранённых при настройке 2FA</p>
          <label style={labelStyle}>Резервный код</label>
          <Input
            key="backup"
            autoFocus
            type="text"
            aria-label="Backup code"
            value={backupCode}
            onChange={(e) => setBackupCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8))}
            onKeyPress={handleKeyPress}
            placeholder="ABCD1234"
            maxLength={8}
            style={codeInputStyle}
          />
        </div>
      )}

      {method === 'recovery' && (
        <div>
          <p style={hintStyle}>Введите токен восстановления, отправленный на ваш email или телефон</p>
          <label style={labelStyle}>Токен восстановления</label>
          <Input
            key="recovery"
            autoFocus
            type="text"
            aria-label="Recovery token"
            value={recoveryToken}
            onChange={(e) => setRecoveryToken(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={t('misc.tfv_vvedite_token_vosstanovleniy')}
            style={{
              ...codeInputStyle,
              letterSpacing: 'normal',
              fontSize: 'var(--mac-font-size-base)',
            }}
          />
        </div>
      )}

      {method !== 'recovery' &&
        <div style={{ margin: 'var(--mac-spacing-4) 0' }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            cursor: 'pointer',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
          }}>
            <Checkbox aria-label="Remember this device for 30 days" checked={rememberDevice} onChange={(e) => setRememberDevice(e)} style={{ margin: 0 }} />
            <span>Запомнить это устройство на 30 дней</span>
          </label>
        </div>
      }

      {error &&
        <div style={{
          background: 'var(--mac-accent-red-bg)',
          borderRadius: 'var(--mac-radius-md)',
          padding: 'var(--mac-spacing-3)',
          marginBottom: 'var(--mac-spacing-3)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 'var(--mac-spacing-2)',
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-sm)',
        }}>
          <AlertCircle size={16} style={{ color: 'var(--mac-accent-red)', flexShrink: 0, marginTop: 2 }} />
          <span role="alert" aria-live="polite">{error}</span>
        </div>
      }

      {success &&
        <div style={{
          background: 'var(--mac-accent-green-bg)',
          borderRadius: 'var(--mac-radius-md)',
          padding: 'var(--mac-spacing-3)',
          marginBottom: 'var(--mac-spacing-3)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)',
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-sm)',
        }}>
          <CheckCircle size={16} style={{ color: 'var(--mac-accent-green)' }} />
          <span>{success}</span>
        </div>
      }

      <button
        type="button"
        onClick={handleVerify}
        disabled={loading ||
          method === 'totp' && totpCode.length !== 6 ||
          method === 'backup' && backupCode.length !== 8 ||
          method === 'recovery' && !recoveryToken
        }
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-3) var(--mac-spacing-5)',
          background: 'var(--mac-accent-blue)',
          color: 'var(--mac-text-inverse)',
          border: 'none',
          borderRadius: 'var(--mac-radius-md)',
          cursor: 'pointer',
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-medium)' as React.CSSProperties['fontWeight'],
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--mac-spacing-2)',
          font: 'inherit',
          opacity: loading ? 0.7 : 1,
        }}>
        {loading ? <RefreshCw size={18} className="animate-spin" /> : <CheckCircle size={18} />}
        {loading ? t('misc.tfv_proverka') : t('misc.tfv_podtverdit')}
      </button>
    </div>
  );
};

export default TwoFactorVerify;
