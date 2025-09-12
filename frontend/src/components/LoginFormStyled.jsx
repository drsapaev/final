import React, { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';

const LoginFormStyled = ({ onLogin, onRegister, onForgotPassword }) => {
  const { theme } = useTheme();
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    loginType: 'username'
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [rememberMe, setRememberMe] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      // Здесь будет логика входа
      console.log('Login attempt:', formData);
      if (onLogin) {
        await onLogin(formData);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '12px',
        boxShadow: '0 20px 40px rgba(0,0,0,0.1)',
        padding: '40px',
        width: '100%',
        maxWidth: '400px',
        position: 'relative'
      }}>
        {/* Заголовок */}
        <div style={{
          textAlign: 'center',
          marginBottom: '30px'
        }}>
          <div style={{
            width: '60px',
            height: '60px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px',
            fontSize: '24px',
            color: 'white'
          }}>
            🏥
          </div>
          <h1 style={{
            fontSize: '24px',
            fontWeight: 'bold',
            color: '#333',
            margin: '0 0 8px 0'
          }}>
            Вход в систему
          </h1>
          <p style={{
            color: '#666',
            margin: '0',
            fontSize: '14px'
          }}>
            Система управления клиникой
          </p>
        </div>

        {/* Форма */}
        <form onSubmit={handleSubmit}>
          {/* Тип входа */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: '#333'
            }}>
              Тип входа
            </label>
            <select
              name="loginType"
              value={formData.loginType}
              onChange={handleInputChange}
              style={{
                width: '100%',
                padding: '12px',
                border: '2px solid #e1e5e9',
                borderRadius: '8px',
                fontSize: '14px',
                background: 'white',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
            >
              <option value="username">Имя пользователя</option>
              <option value="email">Email</option>
              <option value="phone">Телефон</option>
            </select>
          </div>

          {/* Имя пользователя */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: '#333'
            }}>
              {formData.loginType === 'username' ? 'Имя пользователя' : 
               formData.loginType === 'email' ? 'Email' : 'Телефон'} *
            </label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleInputChange}
              required
              style={{
                width: '100%',
                padding: '12px',
                border: '2px solid #e1e5e9',
                borderRadius: '8px',
                fontSize: '14px',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
              placeholder={`Введите ${formData.loginType === 'username' ? 'имя пользователя' : 
                          formData.loginType === 'email' ? 'email' : 'телефон'}`}
            />
          </div>

          {/* Пароль */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: '#333'
            }}>
              Пароль *
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                required
                style={{
                  width: '100%',
                  padding: '12px 40px 12px 12px',
                  border: '2px solid #e1e5e9',
                  borderRadius: '8px',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'border-color 0.2s'
                }}
                placeholder="Введите пароль"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#666',
                  fontSize: '18px'
                }}
              >
                {showPassword ? '👁️' : '👁️‍🗨️'}
              </button>
            </div>
          </div>

          {/* Запомнить меня и забыли пароль */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '30px'
          }}>
            <label style={{
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
              fontSize: '14px',
              color: '#333'
            }}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                style={{ marginRight: '8px' }}
              />
              Запомнить меня
            </label>
            <button
              type="button"
              onClick={onForgotPassword}
              style={{
                background: 'none',
                border: 'none',
                color: '#667eea',
                cursor: 'pointer',
                fontSize: '14px',
                textDecoration: 'underline'
              }}
            >
              Забыли пароль?
            </button>
          </div>

          {/* Ошибка */}
          {error && (
            <div style={{
              background: '#fee',
              color: '#c33',
              padding: '12px',
              borderRadius: '8px',
              marginBottom: '20px',
              fontSize: '14px',
              textAlign: 'center'
            }}>
              {error}
            </div>
          )}

          {/* Кнопка входа */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '14px',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: 'bold',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              transition: 'opacity 0.2s'
            }}
          >
            {loading ? 'Вход...' : 'ВОЙТИ →'}
          </button>
        </form>

        {/* Разделитель */}
        <div style={{
          margin: '30px 0',
          textAlign: 'center',
          position: 'relative'
        }}>
          <div style={{
            height: '1px',
            background: '#e1e5e9',
            position: 'relative'
          }}>
            <span style={{
              background: 'white',
              padding: '0 20px',
              color: '#666',
              fontSize: '14px',
              position: 'absolute',
              top: '-10px',
              left: '50%',
              transform: 'translateX(-50%)'
            }}>
              или
            </span>
          </div>
        </div>

        {/* Кнопки регистрации */}
        <div style={{
          display: 'flex',
          gap: '10px'
        }}>
          <button
            type="button"
            onClick={onRegister}
            style={{
              flex: 1,
              padding: '12px',
              background: 'white',
              border: '2px solid #e1e5e9',
              borderRadius: '8px',
              fontSize: '14px',
              cursor: 'pointer',
              transition: 'border-color 0.2s'
            }}
          >
            Регистрация
          </button>
          <button
            type="button"
            style={{
              flex: 1,
              padding: '12px',
              background: 'white',
              border: '2px solid #e1e5e9',
              borderRadius: '8px',
              fontSize: '14px',
              cursor: 'pointer',
              transition: 'border-color 0.2s'
            }}
          >
            Гость
          </button>
        </div>
      </div>
    </div>
  );
};

export default LoginFormStyled;
