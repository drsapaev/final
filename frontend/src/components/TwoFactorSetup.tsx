import { useState } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../api/client';
import { Shield, Smartphone, Download, Copy, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import PropTypes from 'prop-types';
import { Input } from './ui/macos';
import { useTranslation } from '../i18n/useTranslation';

const TwoFactorSetup = ({ onComplete, onCancel }) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [step, setStep] = useState(1); // 1: Setup, 2: Verify, 3: Complete
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Setup data
  const [setupData, setSetupData] = useState(null);
  const [recoveryEmail, setRecoveryEmail] = useState('');
  const [recoveryPhone, setRecoveryPhone] = useState('');

  // Verification
  const [totpCode, setTotpCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);
  const [copiedCode, setCopiedCode] = useState('');

  const handleSetup = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await api.post('/2fa/setup', {
        recovery_email: recoveryEmail || null,
        recovery_phone: recoveryPhone || null
      }) as any;

      setSetupData(response);
      setBackupCodes(response.backup_codes);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.detail || t('misc.tfs_oshibka_nastroyki_2fa'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!totpCode || totpCode.length !== 6) {
      setError(t('misc.tfs_vvedite_6_znachnyy_kod_iz_pr'));
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.post('/2fa/verify-setup', null, {
        params: { totp_code: totpCode }
      }) as any;

      if (response.success) {
        setSuccess(t('misc.tfs_2fa_uspeshno_nastroena'));
        setStep(3);
      } else {
        setError(response.message || t('misc.tfs_nevernyy_kod'));
      }
    } catch (err) {
      setError(err.response?.data?.detail || t('misc.tfs_oshibka_verifikatsii'));
    } finally {
      setLoading(false);
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

  const renderStep1 = () =>
  <div style={{ maxWidth: '500px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Shield size={48} style={{ color: 'var(--accent-color)', marginBottom: 'var(--mac-spacing-4)' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Настройка двухфакторной аутентификации
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Добавьте дополнительный уровень безопасности к вашему аккаунту
        </p>
      </div>

      <div style={{ marginBottom: 'var(--mac-spacing-6)' }}>
        <label htmlFor="two-factor-recovery-email" style={{
        display: 'block',
        marginBottom: 'var(--mac-spacing-2)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--text-primary)'
      }}>
          Email для восстановления (необязательно)
        </label>
        <Input
        id="two-factor-recovery-email"
        type="email"
        aria-label="Two factor recovery email"
        value={recoveryEmail}
        onChange={(e) => setRecoveryEmail(e.target.value)}
        placeholder="your@email.com"
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-3)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)',
          background: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          fontSize: 'var(--mac-font-size-base)'
        }} />
      
      </div>

      <div style={{ marginBottom: '32px' }}>
        <label htmlFor="two-factor-recovery-phone" style={{
        display: 'block',
        marginBottom: 'var(--mac-spacing-2)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--text-primary)'
      }}>
          Телефон для восстановления (необязательно)
        </label>
        <Input
        id="two-factor-recovery-phone"
        type="tel"
        aria-label="Two factor recovery phone"
        value={recoveryPhone}
        onChange={(e) => setRecoveryPhone(e.target.value)}
        placeholder="+7 (999) 123-45-67"
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-3)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)',
          background: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          fontSize: 'var(--mac-font-size-base)'
        }} />
      
      </div>

      <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)' }}>
        <button
        onClick={handleSetup}
        disabled={loading}
        style={{
          flex: 1,
          padding: 'var(--mac-spacing-3) var(--mac-spacing-6)',
          background: 'var(--accent-color)',
          color: 'white',
          border: 'none',
          borderRadius: 'var(--mac-radius-md)',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-medium)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
        
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <Shield size={16} />}
          {loading ? t('misc.tfs_nastroyka') : t('misc.tfs_nastroit_2fa')}
        </button>
        
        <button
        onClick={onCancel}
        style={{
          padding: 'var(--mac-spacing-3) var(--mac-spacing-6)',
          background: 'var(--bg-secondary)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)',
          cursor: 'pointer',
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-medium)'
        }}>
        
          Отмена
        </button>
      </div>
    </div>;


  const renderStep2 = () =>
  <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Smartphone size={48} style={{ color: 'var(--accent-color)', marginBottom: 'var(--mac-spacing-4)' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Настройте приложение аутентификатора
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Отсканируйте QR-код в приложении Google Authenticator, Authy или аналогичном
        </p>
      </div>

      <div style={{
      background: 'var(--bg-secondary)',
      padding: 'var(--mac-spacing-6)',
      borderRadius: 'var(--mac-radius-lg)',
      marginBottom: 'var(--mac-spacing-6)',
      textAlign: 'center'
    }}>
        {setupData?.qr_code_url &&
      <img
        src={setupData.qr_code_url}
        alt="QR Code for 2FA Setup"
        style={{
          maxWidth: '200px',
          height: 'auto',
          marginBottom: 'var(--mac-spacing-4)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)'
        }} />

      }
        
        <div style={{ marginBottom: 'var(--mac-spacing-4)' }}>
          <label style={{
          display: 'block',
          marginBottom: 'var(--mac-spacing-2)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--text-primary)'
        }}>
            Или введите ключ вручную:
          </label>
          <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)',
          background: 'var(--bg-primary)',
          padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
          borderRadius: 'var(--mac-radius-sm)',
          border: '1px solid var(--border-color)'
        }}>
            <code style={{
            flex: 1,
            fontFamily: 'monospace',
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--text-primary)',
            wordBreak: 'break-all'
          }}>
              {setupData?.secret_key}
            </code>
            <button
            onClick={() => copyToClipboard(setupData?.secret_key, 'secret')}
            aria-label={t('misc.tfs_skopirovat_sekretnyy_klyuch_')}
            style={{
              padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
              background: 'var(--accent-color)',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--mac-radius-sm)',
              cursor: 'pointer',
              fontSize: 'var(--mac-font-size-xs)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-1)'
            }}>
            
              {copiedCode === 'secret' ? <CheckCircle size={12} /> : <Copy size={12} />}
            </button>
          </div>
        </div>
      </div>

      <div style={{ marginBottom: 'var(--mac-spacing-6)' }}>
        <label htmlFor="two-factor-totp-code" style={{
        display: 'block',
        marginBottom: 'var(--mac-spacing-2)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--text-primary)'
      }}>
          Введите 6-значный код из приложения:
        </label>
        <Input
        id="two-factor-totp-code"
        type="text"
        aria-label="Two factor authentication code"
        value={totpCode}
        onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
        placeholder="123456"
        maxLength={6}
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-3)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)',
          background: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          fontSize: 'var(--mac-font-size-xl)',
          textAlign: 'center',
          letterSpacing: '2px',
          fontFamily: 'monospace'
        }} />
      
      </div>

      <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)' }}>
        <button
        onClick={handleVerify}
        disabled={loading || totpCode.length !== 6}
        style={{
          flex: 1,
          padding: 'var(--mac-spacing-3) var(--mac-spacing-6)',
          background: 'var(--accent-color)',
          color: 'white',
          border: 'none',
          borderRadius: 'var(--mac-radius-md)',
          cursor: loading || totpCode.length !== 6 ? 'not-allowed' : 'pointer',
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-medium)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
        
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle size={16} />}
          {loading ? t('misc.tfs_proverka') : t('misc.tfs_podtverdit')}
        </button>
        
        <button
        onClick={() => setStep(1)}
        style={{
          padding: 'var(--mac-spacing-3) var(--mac-spacing-6)',
          background: 'var(--bg-secondary)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--mac-radius-md)',
          cursor: 'pointer',
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-medium)'
        }}>
        
          Назад
        </button>
      </div>
    </div>;


  const renderStep3 = () =>
  <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <CheckCircle size={48} style={{ color: 'var(--mac-success)', marginBottom: 'var(--mac-spacing-4)' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          2FA успешно настроена!
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Сохраните backup коды в безопасном месте
        </p>
      </div>

      <div style={{
      background: 'var(--bg-secondary)',
      padding: 'var(--mac-spacing-6)',
      borderRadius: 'var(--mac-radius-lg)',
      marginBottom: 'var(--mac-spacing-6)'
    }}>
        <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 'var(--mac-spacing-4)'
      }}>
          <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
            Backup коды
          </h3>
          <button
          onClick={downloadBackupCodes}
          style={{
            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
            background: 'var(--accent-color)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--mac-radius-sm)',
            cursor: 'pointer',
            fontSize: 'var(--mac-font-size-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-1)'
          }}>
          
            <Download size={12} />
            Скачать
          </button>
        </div>
        
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: 'var(--mac-spacing-2)',
        marginBottom: 'var(--mac-spacing-4)'
      }}>
          {backupCodes.map((code, index) =>
        <div
          key={index}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
            background: 'var(--bg-primary)',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--border-color)'
          }}>
          
              <code style={{
            flex: 1,
            fontFamily: 'monospace',
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--text-primary)'
          }}>
                {code}
              </code>
              <button
            onClick={() => copyToClipboard(code, `code-${index}`)}
            aria-label={t('misc.tfs_skopirovat_rezervnyy_kod_ind', { index: index + 1 })}
            style={{
              padding: 'var(--mac-spacing-1)',
              background: 'transparent',
              color: 'var(--text-secondary)',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}>
            
                {copiedCode === `code-${index}` ? <CheckCircle size={12} /> : <Copy size={12} />}
              </button>
            </div>
        )}
        </div>
        
        <div style={{
        padding: 'var(--mac-spacing-3)',
        background: 'var(--mac-warning-bg)',
        borderRadius: 'var(--mac-radius-sm)',
        border: '1px solid #F59E0B'
      }}>
          <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)',
          color: 'var(--mac-warning)',
          fontSize: 'var(--mac-font-size-xs)'
        }}>
            <AlertCircle size={16} />
            <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>{t('misc.tfs_vazhno')}</span>
            <span>{t('misc.tfs_sohranite_eti_kody_v_bezopas')}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)' }}>
        <button
        onClick={() => onComplete && onComplete()}
        style={{
          flex: 1,
          padding: 'var(--mac-spacing-3) var(--mac-spacing-6)',
          background: 'var(--accent-color)',
          color: 'white',
          border: 'none',
          borderRadius: 'var(--mac-radius-md)',
          cursor: 'pointer',
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-medium)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
        
          <CheckCircle size={16} />
          Завершить настройку
        </button>
      </div>
    </div>;


  if (error) {
    return (
      <div style={{
        background: 'var(--mac-error-bg)',
        border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))',
        borderRadius: 'var(--mac-radius-md)',
        padding: 'var(--mac-spacing-4)',
        marginBottom: 'var(--mac-spacing-4)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)',
        color: 'var(--mac-error)'
      }}>
        <AlertCircle size={20} />
        <span>{error}</span>
      </div>);

  }

  if (success) {
    return (
      <div style={{
        background: 'var(--mac-success-bg)',
        border: '1px solid #6EE7B7',
        borderRadius: 'var(--mac-radius-md)',
        padding: 'var(--mac-spacing-4)',
        marginBottom: 'var(--mac-spacing-4)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)',
        color: 'var(--mac-success)'
      }}>
        <CheckCircle size={20} />
        <span>{success}</span>
      </div>);

  }

  return (
    <div>
      {step === 1 && renderStep1()}
      {step === 2 && renderStep2()}
      {step === 3 && renderStep3()}
    </div>);

};


TwoFactorSetup.propTypes = {
  ...(TwoFactorSetup.propTypes || {}),
  onCancel: PropTypes.any,
  onComplete: PropTypes.any,
};

export default TwoFactorSetup;
