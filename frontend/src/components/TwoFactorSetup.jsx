import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Shield, Smartphone, Download, Copy, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';

const TwoFactorSetup = ({ onComplete, onCancel }) => {
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
      });
      
      setSetupData(response);
      setBackupCodes(response.backup_codes);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка настройки 2FA');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!totpCode || totpCode.length !== 6) {
      setError('Введите 6-значный код из приложения');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const response = await api.post('/2fa/verify-setup', null, {
        params: { totp_code: totpCode }
      });
      
      if (response.success) {
        setSuccess('2FA успешно настроена!');
        setStep(3);
      } else {
        setError(response.message || 'Неверный код');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка верификации');
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

  const renderStep1 = () => (
    <div style={{ maxWidth: '500px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Shield size={48} style={{ color: 'var(--accent-color)', marginBottom: '16px' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Настройка двухфакторной аутентификации
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Добавьте дополнительный уровень безопасности к вашему аккаунту
        </p>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontWeight: '500',
          color: 'var(--text-primary)'
        }}>
          Email для восстановления (необязательно)
        </label>
        <input
          type="email"
          value={recoveryEmail}
          onChange={(e) => setRecoveryEmail(e.target.value)}
          placeholder="your@email.com"
          style={{
            width: '100%',
            padding: '12px',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            fontSize: '14px'
          }}
        />
      </div>

      <div style={{ marginBottom: '32px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontWeight: '500',
          color: 'var(--text-primary)'
        }}>
          Телефон для восстановления (необязательно)
        </label>
        <input
          type="tel"
          value={recoveryPhone}
          onChange={(e) => setRecoveryPhone(e.target.value)}
          placeholder="+7 (999) 123-45-67"
          style={{
            width: '100%',
            padding: '12px',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            fontSize: '14px'
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button
          onClick={handleSetup}
          disabled={loading}
          style={{
            flex: 1,
            padding: '12px 24px',
            background: 'var(--accent-color)',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <Shield size={16} />}
          {loading ? 'Настройка...' : 'Настроить 2FA'}
        </button>
        
        <button
          onClick={onCancel}
          style={{
            padding: '12px 24px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500'
          }}
        >
          Отмена
        </button>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Smartphone size={48} style={{ color: 'var(--accent-color)', marginBottom: '16px' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          Настройте приложение аутентификатора
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Отсканируйте QR-код в приложении Google Authenticator, Authy или аналогичном
        </p>
      </div>

      <div style={{ 
        background: 'var(--bg-secondary)', 
        padding: '24px', 
        borderRadius: '12px',
        marginBottom: '24px',
        textAlign: 'center'
      }}>
        {setupData?.qr_code_url && (
          <img 
            src={setupData.qr_code_url} 
            alt="QR Code for 2FA Setup"
            style={{ 
              maxWidth: '200px', 
              height: 'auto',
              marginBottom: '16px',
              border: '1px solid var(--border-color)',
              borderRadius: '8px'
            }}
          />
        )}
        
        <div style={{ marginBottom: '16px' }}>
          <label style={{ 
            display: 'block', 
            marginBottom: '8px', 
            fontWeight: '500',
            color: 'var(--text-primary)'
          }}>
            Или введите ключ вручную:
          </label>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px',
            background: 'var(--bg-primary)',
            padding: '8px 12px',
            borderRadius: '6px',
            border: '1px solid var(--border-color)'
          }}>
            <code style={{ 
              flex: 1, 
              fontFamily: 'monospace', 
              fontSize: '12px',
              color: 'var(--text-primary)',
              wordBreak: 'break-all'
            }}>
              {setupData?.secret_key}
            </code>
            <button
              onClick={() => copyToClipboard(setupData?.secret_key, 'secret')}
              style={{
                padding: '4px 8px',
                background: 'var(--accent-color)',
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
              {copiedCode === 'secret' ? <CheckCircle size={12} /> : <Copy size={12} />}
            </button>
          </div>
        </div>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontWeight: '500',
          color: 'var(--text-primary)'
        }}>
          Введите 6-значный код из приложения:
        </label>
        <input
          type="text"
          value={totpCode}
          onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="123456"
          maxLength={6}
          style={{
            width: '100%',
            padding: '12px',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            fontSize: '18px',
            textAlign: 'center',
            letterSpacing: '2px',
            fontFamily: 'monospace'
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button
          onClick={handleVerify}
          disabled={loading || totpCode.length !== 6}
          style={{
            flex: 1,
            padding: '12px 24px',
            background: 'var(--accent-color)',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: (loading || totpCode.length !== 6) ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle size={16} />}
          {loading ? 'Проверка...' : 'Подтвердить'}
        </button>
        
        <button
          onClick={() => setStep(1)}
          style={{
            padding: '12px 24px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500'
          }}
        >
          Назад
        </button>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <CheckCircle size={48} style={{ color: '#10B981', marginBottom: '16px' }} />
        <h2 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
          2FA успешно настроена!
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Сохраните backup коды в безопасном месте
        </p>
      </div>

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
          <button
            onClick={downloadBackupCodes}
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
            <Download size={12} />
            Скачать
          </button>
        </div>
        
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
        </div>
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button
          onClick={() => onComplete && onComplete()}
          style={{
            flex: 1,
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
            justifyContent: 'center',
            gap: '8px'
          }}
        >
          <CheckCircle size={16} />
          Завершить настройку
        </button>
      </div>
    </div>
  );

  if (error) {
    return (
      <div style={{ 
        background: '#FEE2E2', 
        border: '1px solid #FCA5A5', 
        borderRadius: '8px', 
        padding: '16px',
        marginBottom: '16px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        color: '#DC2626'
      }}>
        <AlertCircle size={20} />
        <span>{error}</span>
      </div>
    );
  }

  if (success) {
    return (
      <div style={{ 
        background: '#D1FAE5', 
        border: '1px solid #6EE7B7', 
        borderRadius: '8px', 
        padding: '16px',
        marginBottom: '16px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        color: '#059669'
      }}>
        <CheckCircle size={20} />
        <span>{success}</span>
      </div>
    );
  }

  return (
    <div>
      {step === 1 && renderStep1()}
      {step === 2 && renderStep2()}
      {step === 3 && renderStep3()}
    </div>
  );
};

export default TwoFactorSetup;

