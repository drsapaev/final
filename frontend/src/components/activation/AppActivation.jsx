import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Key, 
  Shield, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Smartphone,
  Calendar,
  Download,
  Copy
} from 'lucide-react';
import { Card, Button } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';

const AppActivation = ({ onClose }) => {
  const navigate = useNavigate();
  const { theme, isDark, getColor, getSpacing } = useTheme();
  
  const [activationKey, setActivationKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [step, setStep] = useState('input'); // input, success, error

  const handleActivate = async () => {
    if (!activationKey.trim()) {
      setError('Введите ключ активации');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      // Отправляем ключ активации на сервер
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
        
        // Сохраняем информацию об активации
        localStorage.setItem('app_activated', 'true');
        localStorage.setItem('activation_info', JSON.stringify(result));
        
        // Перезагружаем страницу через 2 секунды
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      } else {
        throw new Error(result.detail || result.message || 'Ошибка активации');
      }
    } catch (err) {
      console.error('Ошибка активации:', err);
      setError(err.message || 'Ошибка активации. Проверьте ключ и попробуйте снова.');
      setStep('error');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleActivate();
    }
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
  };

  const cardStyle = {
    background: isDark 
      ? 'rgba(30, 41, 59, 0.95)' 
      : 'rgba(255, 255, 255, 0.95)',
    border: `1px solid ${isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.3)'}`,
    borderRadius: '16px',
    padding: getSpacing('2xl'),
    boxShadow: isDark 
      ? '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)'
      : '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.05)',
    backdropFilter: 'blur(10px)',
    maxWidth: '500px',
    width: '100%',
    margin: '0 auto'
  };

  const inputStyle = {
    width: '100%',
    padding: getSpacing('md'),
    border: `2px solid ${isDark ? getColor('gray', 600) : getColor('gray', 300)}`,
    borderRadius: '8px',
    background: isDark ? getColor('gray', 800) : 'white',
    color: isDark ? 'white' : getColor('gray', 900),
    fontSize: '16px',
    fontFamily: 'monospace',
    marginBottom: getSpacing('md'),
    transition: 'border-color 0.2s'
  };

  const buttonStyle = {
    width: '100%',
    padding: `${getSpacing('md')} ${getSpacing('lg')}`,
    background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: '600',
    transition: 'all 0.3s ease',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    marginBottom: getSpacing('sm')
  };

  const secondaryButtonStyle = {
    ...buttonStyle,
    background: `linear-gradient(135deg, ${getColor('secondary', 500)} 0%, ${getColor('secondary', 600)} 100%)`,
    boxShadow: '0 4px 14px 0 rgba(107, 114, 128, 0.3)'
  };

  if (step === 'success') {
    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: getSpacing('lg')
      }}>
        <Card style={cardStyle}>
          <div style={{ textAlign: 'center' }}>
            <CheckCircle 
              size={64} 
              style={{ color: getColor('success', 500), marginBottom: getSpacing('lg') }} 
            />
            <h2 style={{ 
              fontSize: '24px', 
              fontWeight: 'bold', 
              marginBottom: getSpacing('md'),
              color: isDark ? 'white' : getColor('gray', 900)
            }}>
              Активация успешна!
            </h2>
            <p style={{ 
              color: isDark ? getColor('gray', 300) : getColor('gray', 600),
              marginBottom: getSpacing('lg')
            }}>
              Приложение активировано. Страница будет перезагружена...
            </p>
            <div style={{ 
              background: isDark ? getColor('success', 900) : getColor('success', 50),
              border: `1px solid ${isDark ? getColor('success', 700) : getColor('success', 200)}`,
              borderRadius: '8px',
              padding: getSpacing('md'),
              marginBottom: getSpacing('lg')
            }}>
              <p style={{ 
                color: isDark ? getColor('success', 300) : getColor('success', 700),
                fontSize: '14px',
                margin: 0
              }}>
                ✅ Полный доступ к системе<br/>
                ✅ AI функции<br/>
                ✅ Telegram интеграция<br/>
                ✅ Система печати
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: getSpacing('lg')
    }}>
      <Card style={cardStyle}>
        <div style={{ textAlign: 'center', marginBottom: getSpacing('lg') }}>
          <Shield 
            size={48} 
            style={{ color: getColor('primary', 500), marginBottom: getSpacing('md') }} 
          />
          <h2 style={{ 
            fontSize: '24px', 
            fontWeight: 'bold', 
            marginBottom: getSpacing('sm'),
            color: isDark ? 'white' : getColor('gray', 900)
          }}>
            Активация приложения
          </h2>
          <p style={{ 
            color: isDark ? getColor('gray', 300) : getColor('gray', 600),
            fontSize: '14px'
          }}>
            Введите ключ активации для разблокировки всех функций
          </p>
        </div>

        {error && (
          <div style={{
            background: isDark ? getColor('error', 900) : getColor('error', 50),
            border: `1px solid ${isDark ? getColor('error', 700) : getColor('error', 200)}`,
            borderRadius: '8px',
            padding: getSpacing('md'),
            marginBottom: getSpacing('md'),
            display: 'flex',
            alignItems: 'center'
          }}>
            <AlertCircle 
              size={20} 
              style={{ color: isDark ? getColor('error', 300) : getColor('error', 600), marginRight: getSpacing('sm') }} 
            />
            <span style={{ 
              color: isDark ? getColor('error', 300) : getColor('error', 600),
              fontSize: '14px'
            }}>
              {error}
            </span>
          </div>
        )}

        {success && (
          <div style={{
            background: isDark ? getColor('success', 900) : getColor('success', 50),
            border: `1px solid ${isDark ? getColor('success', 700) : getColor('success', 200)}`,
            borderRadius: '8px',
            padding: getSpacing('md'),
            marginBottom: getSpacing('md'),
            display: 'flex',
            alignItems: 'center'
          }}>
            <CheckCircle 
              size={20} 
              style={{ color: isDark ? getColor('success', 300) : getColor('success', 600), marginRight: getSpacing('sm') }} 
            />
            <span style={{ 
              color: isDark ? getColor('success', 300) : getColor('success', 600),
              fontSize: '14px'
            }}>
              {success}
            </span>
          </div>
        )}

        <div style={{ marginBottom: getSpacing('lg') }}>
          <label style={{
            display: 'block',
            fontSize: '14px',
            fontWeight: '600',
            marginBottom: getSpacing('sm'),
            color: isDark ? 'white' : getColor('gray', 700)
          }}>
            <Key size={16} style={{ marginRight: getSpacing('xs'), display: 'inline' }} />
            Ключ активации
          </label>
          <input
            type="text"
            value={activationKey}
            onChange={(e) => setActivationKey(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Введите ключ активации..."
            style={inputStyle}
            disabled={loading}
          />
        </div>

        <div style={{ display: 'flex', gap: getSpacing('sm'), marginBottom: getSpacing('lg') }}>
          <Button
            onClick={handleActivate}
            disabled={loading || !activationKey.trim()}
            style={buttonStyle}
          >
            {loading ? (
              <>
                <RefreshCw size={16} style={{ marginRight: getSpacing('xs'), animation: 'spin 1s linear infinite' }} />
                Активация...
              </>
            ) : (
              <>
                <Shield size={16} style={{ marginRight: getSpacing('xs') }} />
                Активировать
              </>
            )}
          </Button>
        </div>

        <div style={{ display: 'flex', gap: getSpacing('sm') }}>
          <Button
            onClick={copyDeviceInfo}
            style={secondaryButtonStyle}
          >
            <Copy size={16} style={{ marginRight: getSpacing('xs') }} />
            Скопировать ID устройства
          </Button>
          <Button
            onClick={onClose}
            style={secondaryButtonStyle}
          >
            Отмена
          </Button>
        </div>

        <div style={{
          marginTop: getSpacing('lg'),
          padding: getSpacing('md'),
          background: isDark ? getColor('gray', 800) : getColor('gray', 50),
          borderRadius: '8px',
          border: `1px solid ${isDark ? getColor('gray', 700) : getColor('gray', 200)}`
        }}>
          <h4 style={{
            fontSize: '14px',
            fontWeight: '600',
            marginBottom: getSpacing('sm'),
            color: isDark ? 'white' : getColor('gray', 700)
          }}>
            <Smartphone size={16} style={{ marginRight: getSpacing('xs'), display: 'inline' }} />
            Информация об устройстве
          </h4>
          <div style={{ fontSize: '12px', color: isDark ? getColor('gray', 400) : getColor('gray', 600) }}>
            <div>Платформа: {navigator.platform}</div>
            <div>Язык: {navigator.language}</div>
            <div>Время: {new Date().toLocaleString()}</div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default AppActivation;
