import React, { useState } from 'react';
import logger from '../../utils/logger';
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

const AppActivation = ({ onClose }) => {
  const [activationKey, setActivationKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [step, setStep] = useState('input'); // input, success

  const handleActivate = async () => {
    if (!activationKey.trim()) {
      setError('Введите ключ активации');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch('/api/v1/activation/activate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
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
        setSuccess('Приложение успешно активировано!');
        setStep('success');

        localStorage.setItem('app_activated', 'true');
        localStorage.setItem('activation_info', JSON.stringify(result));

        setTimeout(() => {
          window.location.reload();
        }, 2000);
      } else {
        throw new Error(result.detail || result.message || 'Ошибка активации');
      }
    } catch (err) {
      logger.error('Ошибка активации:', err);
      setError(err.message || 'Ошибка активации. Проверьте ключ.');
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
    setSuccess('Информация об устройстве скопирована');
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
          color: '#34c759'
        }}>
          <CheckCircle size={40} />
        </div>

        <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '12px' }}>
          Активация успешна!
        </h2>

        <p style={{ color: 'var(--mac-text-secondary)', marginBottom: '32px' }}>
          Приложение активировано. Перезагрузка...
        </p>

        <div className="info-panel" style={{ textAlign: 'left', background: 'rgba(52, 199, 89, 0.05)', borderColor: 'rgba(52, 199, 89, 0.2)' }}>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', fontWeight: 600, color: '#34c759' }}>
            <CheckCircle size={16} /> Доступные функции:
          </div>
          <ul style={{ margin: 0, paddingLeft: '24px', color: 'var(--mac-text-primary)', lineHeight: '1.6' }}>
            <li>Полный доступ к системе</li>
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
          background: 'rgba(0, 122, 255, 0.1)',
          borderRadius: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px',
          color: '#007aff',
          boxShadow: '0 0 20px rgba(0, 122, 255, 0.2)'
        }}>
          <Shield size={32} />
        </div>
        <p style={{ color: 'var(--mac-text-secondary)', fontSize: '15px' }}>
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

      <div style={{ marginBottom: '24px' }}>
        <label style={{
          display: 'block',
          marginBottom: '8px',
          fontSize: '13px',
          fontWeight: 600,
          color: 'var(--mac-text-secondary)',
          marginLeft: '4px'
        }}>
          КЛЮЧ АКТИВАЦИИ
        </label>
        <div style={{ position: 'relative' }}>
          <Key size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--mac-text-secondary)' }} />
          <input
            type="text"
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <button
          className="btn-premium btn-primary"
          onClick={handleActivate}
          disabled={loading || !activationKey.trim()}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          {loading ? <RefreshCw size={20} className="spin" /> : <Lock size={20} />}
          {loading ? 'Активация...' : 'Активировать'}
        </button>

        <button
          className="btn-premium btn-glass"
          onClick={copyDeviceInfo}
          style={{ width: '100%', justifyContent: 'center', fontSize: '14px', padding: '12px' }}
        >
          <Copy size={16} />
          Скопировать ID устройства
        </button>
      </div>

      <div className="info-panel">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: 'var(--mac-text-primary)' }}>
          <Smartphone size={14} />
          <span style={{ fontWeight: 600 }}>Device Info</span>
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
