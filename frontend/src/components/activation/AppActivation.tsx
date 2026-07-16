// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { api } from '../../api/client';
import { useState } from 'react';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import {
  Key,
  Shield,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Smartphone,
  Copy,
  Lock
} from 'lucide-react';

const AppActivation = () => {
  const { t } = useTranslation();
  const [activationKey, setActivationKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [step, setStep] = useState('input'); // input, success

  const handleActivate = async () => {
    if (!activationKey.trim()) {
      setError(t('misc.aa_vvedite_klyuch_aktivatsii'));
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await api.post('/activation/activate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken() || ''}`
        },
        body: JSON.stringify({
          activation_key: activationKey.trim(),
          device_info: {
            user_agent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            timestamp: new Date().toISOString()
          }
        })
      });

      const result = await response.json();

      if (response.ok) {
        setSuccess(t('misc.aa_prilozhenie_uspeshno_aktivir'));
        setStep('success');

        localStorage.setItem('app_activated', 'true');
        localStorage.setItem('activation_info', JSON.stringify(result));

        setTimeout(() => {
          window.location.reload();
        }, 2000);
      } else {
        throw new Error(result.detail || result.message || t('misc.aa_oshibka_aktivatsii'));
      }
    } catch (err) {
      logger.error('Ошибка активации:', err);
      setError(err.message || t('misc.aa_oshibka_aktivatsii_proverte_'));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleActivate();
  };

  const copyDeviceInfo = () => {
    const deviceInfo = {
      user_agent: navigator.userAgent,
      platform: navigator.platform,
      language: navigator.language,
      timestamp: new Date().toISOString()
    };

    navigator.clipboard.writeText(JSON.stringify(deviceInfo, null, 2));
    setSuccess(t('misc.aa_informatsiya_ob_ustroystve_s'));
    setTimeout(() => setSuccess(''), 3000);
  };

  if (step === 'success') {
    return (
      <div style={{ textAlign: 'center', padding: '20px 0' }}>
        <div style={{
          width: '80px',
          height: '80px',
          background: 'rgba(52, 199, 89, 0.1)',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 24px',
          color: 'var(--mac-success)'
        }}>
          <CheckCircle size={40} />
        </div>

        <h2 style={{ fontSize: 'var(--mac-font-size-3xl)', fontWeight: 'var(--mac-font-weight-bold)', marginBottom: 'var(--mac-spacing-3)' }}>
          Активация успешна!
        </h2>

        <p style={{ color: 'var(--mac-text-secondary)', marginBottom: '32px' }}>
          Приложение активировано. Перезагрузка...
        </p>

        <div className="info-panel" style={{ textAlign: 'left', background: 'rgba(52, 199, 89, 0.05)', borderColor: 'var(--mac-success-border, color-mix(in srgb, var(--mac-success), transparent 80%))' }}>
          <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', marginBottom: 'var(--mac-spacing-2)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-success)' }}>
            <CheckCircle size={16} /> Доступные функции:
          </div>
          <ul style={{ margin: 0, paddingLeft: '24px', color: 'var(--mac-text-primary)', lineHeight: '1.6' }}>
            <li>{t('misc.aa_polnyy_dostup_k_sisteme')}</li>
            <li>AI функции и аналитика</li>
            <li>Telegram интеграция</li>
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <div style={{
          width: '64px',
          height: '64px',
          background: 'var(--mac-accent-bg)',
          borderRadius: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px',
          color: 'var(--mac-accent-blue)',
          boxShadow: '0 0 20px rgba(0, 122, 255, 0.2)'
        }}>
          <Shield size={32} />
        </div>
        <p style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-lg)' }}>
          Введите лицензионный ключ для разблокировки всех функций приложения
        </p>
      </div>

      {error && (
        <div className="status-message status-error">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {success && (
        <div className="status-message status-success">
          <CheckCircle size={18} />
          {success}
        </div>
      )}

      <div style={{ marginBottom: 'var(--mac-spacing-6)' }}>
        <label htmlFor="activation-key" style={{
          display: 'block',
          marginBottom: 'var(--mac-spacing-2)',
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-secondary)',
          marginLeft: 'var(--mac-spacing-1)'
        }}>
          КЛЮЧ АКТИВАЦИИ
        </label>
        <div style={{ position: 'relative' }}>
          <Key size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--mac-text-secondary)' }} />
          <Input
            id="activation-key"
            type="text"
            aria-label={t('misc.aa_klyuch_aktivatsii')}
            className="glass-input"
            style={{ paddingLeft: '44px' }}
            value={activationKey}
            onChange={(e) => setActivationKey(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="XXXX-XXXX-XXXX-XXXX"
            disabled={loading}
          />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
        <button
          className="btn-premium btn-primary"
          onClick={handleActivate}
          disabled={loading || !activationKey.trim()}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          {loading ? <RefreshCw size={20} className="spin" /> : <Lock size={20} />}
          {loading ? t('misc.aa_aktivatsiya') : t('misc.aa_aktivirovat')}
        </button>

        <button
          className="btn-premium btn-glass"
          onClick={copyDeviceInfo}
          style={{ width: '100%', justifyContent: 'center', fontSize: 'var(--mac-font-size-base)', padding: 'var(--mac-spacing-3)' }}
        >
          <Copy size={16} />
          Скопировать ID устройства
        </button>
      </div>

      <div className="info-panel">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', marginBottom: 'var(--mac-spacing-2)', color: 'var(--mac-text-primary)' }}>
          <Smartphone size={14} />
          <span style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>Device Info</span>
        </div>
        <div style={{ fontFamily: 'monospace', opacity: 0.7 }}>
          <div>Platform: {navigator.platform}</div>
          <div>Lang: {navigator.language}</div>
        </div>
      </div>
    </div>
  );
};

export default AppActivation;
