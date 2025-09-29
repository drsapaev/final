import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import AppActivation from '../components/activation/AppActivation';

export default function Landing() {
  const navigate = useNavigate();
  const [language, setLanguage] = useState('RU');
  const [showActivation, setShowActivation] = useState(false);
  
  // Используем централизованную систему темизации
  const { 
    theme, 
    isDark, 
    isLight, 
    toggleTheme, 
    getColor, 
    getSpacing, 
    getFontSize,
    getShadow,
    designTokens 
  } = useTheme();

  const textColor = isDark ? getColor('secondary', 200) : getColor('secondary', 700);
  const bgColor = isDark ? getColor('secondary', 900) : getColor('secondary', 50);

  const pageStyle = {
    minHeight: '100vh',
    background: isLight 
      ? `linear-gradient(135deg, ${getColor('primary', 50)} 0%, ${getColor('secondary', 50)} 100%)`
      : `linear-gradient(135deg, ${getColor('secondary', 900)} 0%, ${getColor('secondary', 800)} 100%)`,
    padding: getSpacing('lg'),
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
    color: textColor,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center'
  };

  const cardStyle = {
    background: isLight 
      ? 'rgba(255, 255, 255, 0.9)' 
      : 'rgba(30, 41, 59, 0.9)',
    border: `1px solid ${isLight ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRadius: '20px',
    padding: getSpacing('2xl'),
    marginBottom: getSpacing('lg'),
    boxShadow: isLight 
      ? getShadow('xl')
      : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
    backdropFilter: 'blur(10px)',
    maxWidth: '600px',
    width: '100%'
  };

  const buttonStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'white',
    border: 'none',
    borderRadius: '12px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: '600',
    transition: 'all 0.3s ease',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    marginRight: getSpacing('sm'),
    marginBottom: getSpacing('sm')
  };

  const buttonSecondaryStyle = {
    ...buttonStyle,
    background: `linear-gradient(135deg, ${getColor('secondary', 500)} 0%, ${getColor('secondary', 600)} 100%)`,
    boxShadow: '0 4px 14px 0 rgba(107, 114, 128, 0.3)'
  };

  const headerStyle = {
    fontSize: '48px',
    fontWeight: '800',
          marginBottom: getSpacing('md'),
    background: `linear-gradient(135deg, ${getColor('primary', 600)} 0%, ${getColor('primary', 400)} 100%)`,
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    textAlign: 'center'
  };

  const subtitleStyle = {
    fontSize: '18px',
    opacity: 0.8,
          marginBottom: getSpacing('xl'),
    textAlign: 'center',
    lineHeight: '1.6'
  };

  const contactCardStyle = {
    ...cardStyle,
    padding: getSpacing('lg'),
          marginBottom: getSpacing('sm')
  };

  const toggleButtonStyle = {
    padding: getSpacing('xs'),
    background: 'transparent',
    border: `1px solid ${isLight ? getColor('secondary', 300) : getColor('secondary', 600)}`,
    borderRadius: '8px',
    cursor: 'pointer',
    color: textColor,
    marginLeft: getSpacing('sm')
  };

  const translations = {
    RU: {
      title: '🏥 Clinic Manager',
      subtitle: 'Добро пожаловать в современную систему управления клиникой',
      login: 'Войти',
      activate: 'Активировать аккаунт',
      contacts: 'Контакты',
      address: 'Адрес: г. Ташкент, ул. Примерная 1',
      phone: 'Телефон: +998 (90) 000-00-00',
      schedule: 'График: Пн–Сб 9:00–18:00',
      telegram: 'Telegram: @clinic',
      footer: 'v1.0.0 · Политика конфиденциальности · Условия использования'
    },
    UZ: {
      title: '🏥 Klinika Menejeri',
      subtitle: 'Zamonaviy klinika boshqaruv tizimiga xush kelibsiz',
      login: 'Kirish',
      activate: 'Akkauntni faollashtirish',
      contacts: 'Kontaktlar',
      address: 'Manzil: Toshkent sh., Namunaviy k., 1-uy',
      phone: 'Telefon: +998 (90) 000-00-00',
      schedule: 'Ish vaqti: Du–Sha 9:00–18:00',
      telegram: 'Telegram: @clinic',
      footer: 'v1.0.0 · Maxfiylik siyosati · Foydalanish shartlari'
    },
    EN: {
      title: '🏥 Clinic Manager',
      subtitle: 'Welcome to the modern clinic management system',
      login: 'Login',
      activate: 'Activate Account',
      contacts: 'Contacts',
      address: 'Address: Tashkent, Example St. 1',
      phone: 'Phone: +998 (90) 000-00-00',
      schedule: 'Schedule: Mon–Sat 9:00–18:00',
      telegram: 'Telegram: @clinic',
      footer: 'v1.0.0 · Privacy Policy · Terms of Use'
    }
  };

  const t = translations[language];

  return (
    <div style={pageStyle}>
      {/* Переключатели темы и языка */}
              <div style={{ position: 'absolute', top: getSpacing('lg'), right: getSpacing('lg'), display: 'flex', alignItems: 'center' }}>
        <button 
          onClick={toggleTheme}
          style={toggleButtonStyle}
          title="Переключить тему"
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        <select 
          value={language} 
          onChange={(e) => setLanguage(e.target.value)}
          style={{
            ...toggleButtonStyle,
            marginLeft: getSpacing('sm'),
            background: isLight ? 'white' : getColor('secondary', 800)
          }}
        >
          <option value="RU">RU</option>
          <option value="UZ">UZ</option>
          <option value="EN">EN</option>
        </select>
      </div>

      {/* Главная карточка */}
      <div style={cardStyle}>
        <div style={headerStyle}>{t.title}</div>
        <div style={subtitleStyle}>{t.subtitle}</div>
        
        <div style={{ display: 'flex', gap: getSpacing('sm'), flexWrap: 'wrap', justifyContent: 'center', marginBottom: getSpacing('lg') }}>
          <button 
            onClick={() => navigate('/login')} 
            style={buttonStyle}
            onMouseOver={(e) => e.target.style.transform = 'translateY(-2px)'}
            onMouseOut={(e) => e.target.style.transform = 'translateY(0)'}
          >
            {t.login}
          </button>
          <button 
            onClick={() => setShowActivation(true)} 
            style={buttonSecondaryStyle}
            onMouseOver={(e) => e.target.style.transform = 'translateY(-2px)'}
            onMouseOut={(e) => e.target.style.transform = 'translateY(0)'}
          >
            {t.activate}
          </button>
        </div>
      </div>

      {/* Карточка контактов */}
      <div style={contactCardStyle}>
        <div style={{ fontWeight: '700', marginBottom: getSpacing('sm'), fontSize: '18px', color: getColor('primary', 600) }}>
          {t.contacts}
        </div>
        <div style={{ lineHeight: '1.6' }}>
          <div style={{ marginBottom: '4px' }}>{t.address}</div>
          <div style={{ marginBottom: '4px' }}>{t.phone}</div>
          <div style={{ marginBottom: '4px' }}>{t.schedule}</div>
          <div>{t.telegram}</div>
        </div>
      </div>

      {/* Футер */}
      <div style={{ 
        opacity: 0.6, 
        fontSize: '14px', 
        textAlign: 'center',
        marginTop: getSpacing('lg') 
      }}>
        {t.footer}
      </div>

      {/* Модальное окно активации */}
      {showActivation && (
        <AppActivation onClose={() => setShowActivation(false)} />
      )}
    </div>
  );
}
