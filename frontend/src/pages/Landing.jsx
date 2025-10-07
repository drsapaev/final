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
    toggleTheme
  } = useTheme();

  const textColor = isDark ? 'var(--color-text-secondary)' : 'var(--color-text-primary)';
  const bgColor = isDark ? 'var(--color-background-primary)' : 'var(--color-background-secondary)';

  const pageStyle = {
    minHeight: '100vh',
    background: isLight 
      ? 'linear-gradient(135deg, var(--color-background-secondary) 0%, var(--color-background-tertiary) 100%)'
      : 'linear-gradient(135deg, var(--color-background-primary) 0%, var(--color-background-secondary) 100%)',
    padding: '1.5rem',
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
    color: textColor,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center'
  };

  const cardStyle = {
    background: isLight 
      ? 'rgba(255, 255, 255, 0.95)' 
      : 'rgba(30, 41, 59, 0.9)',
    border: `1px solid ${isLight ? 'rgba(0, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRadius: '20px',
    padding: '2rem',
    marginBottom: '1.5rem',
    boxShadow: isLight 
      ? 'var(--shadow-xl)'
      : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
    backdropFilter: 'blur(10px)',
    maxWidth: '600px',
    width: '100%'
  };

  const buttonStyle = {
    padding: '0.5rem 1.5rem',
    background: 'linear-gradient(135deg, var(--color-primary-500) 0%, var(--color-primary-600) 100%)',
    color: 'white',
    border: 'none',
    borderRadius: '12px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: '600',
    transition: 'all 0.3s ease',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    marginRight: '0.5rem',
    marginBottom: '0.5rem'
  };

  const buttonSecondaryStyle = {
    ...buttonStyle,
    background: 'linear-gradient(135deg, var(--color-text-secondary) 0%, var(--color-text-tertiary) 100%)',
    boxShadow: '0 4px 14px 0 rgba(107, 114, 128, 0.3)'
  };

  const headerStyle = {
    fontSize: '48px',
    fontWeight: '800',
    marginBottom: '1rem',
    background: 'linear-gradient(135deg, var(--color-primary-600) 0%, var(--color-primary-400) 100%)',
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    textAlign: 'center'
  };

  const subtitleStyle = {
    fontSize: '18px',
    opacity: 0.8,
    marginBottom: '2rem',
    textAlign: 'center',
    lineHeight: '1.6'
  };

  const contactCardStyle = {
    ...cardStyle,
    padding: '1.5rem',
    marginBottom: '0.5rem'
  };

  const toggleButtonStyle = {
    padding: '0.25rem',
    background: isLight ? 'rgba(255, 255, 255, 0.9)' : 'transparent',
    border: `1px solid ${isLight ? 'rgba(0, 0, 0, 0.2)' : 'var(--color-border-light)'}`,
    borderRadius: '8px',
    cursor: 'pointer',
    color: textColor,
    marginLeft: '0.5rem'
  };

  const translations = {
    RU: {
      title: '🏥 Clinic Manager',
      subtitle: 'Добро пожаловать в современную систему управления клиникой',
      login: 'Войти',
      activate: 'Активировать аккаунт',
      contacts: 'Контакты',
      address: 'Адрес: г. Турткул, ул. Беруний',
      phone: 'Телефон: +998 (95) 104-34-34',
      schedule: 'График: Пн–Сб 9:00–17:00',
      telegram: 'Telegram: @doktor_cosmed_clinic',
      footer: 'v1.0.0 · Политика конфиденциальности · Условия использования'
    },
    UZ: {
      title: '🏥 Klinika Menejeri',
      subtitle: 'Zamonaviy klinika boshqaruv tizimiga xush kelibsiz',
      login: 'Kirish',
      activate: 'Akkauntni faollashtirish',
      contacts: 'Kontaktlar',
      address: 'Manzil: Tortkul sh., Beruniy k.',
      phone: 'Telefon: +998 (95) 104-34-34',
      schedule: 'Ish vaqti: Du–Sha 9:00–17:00',
      telegram: 'Telegram: @doktor_cosmed_clinic',
      footer: 'v1.0.0 · Maxfiylik siyosati · Foydalanish shartlari'
    },
    EN: {
      title: '🏥 Clinic Manager',
      subtitle: 'Welcome to the modern clinic management system',
      login: 'Login',
      activate: 'Activate Account',
      contacts: 'Contacts',
      address: 'Address: Tortkul, Beruniy St.',
      phone: 'Phone: +998 (95) 104-34-34',
      schedule: 'Schedule: Mon–Sat 9:00–17:00',
      telegram: 'Telegram: @doktor_cosmed_clinic',
      footer: 'v1.0.0 · Privacy Policy · Terms of Use'
    }
  };

  const t = translations[language];

  return (
    <div style={pageStyle}>
      {/* Переключатели темы и языка */}
              <div style={{ position: 'absolute', top: '1.5rem', right: '1.5rem', display: 'flex', alignItems: 'center' }}>
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
            marginLeft: '0.5rem',
            background: isLight ? 'rgba(255, 255, 255, 0.95)' : 'var(--color-background-secondary)',
            color: isLight ? 'var(--color-text-primary)' : 'var(--color-text-primary)'
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
        
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center', marginBottom: '1.5rem' }}>
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
        <div style={{ fontWeight: '700', marginBottom: '0.5rem', fontSize: '18px', color: 'var(--color-primary-600)' }}>
          {t.contacts}
        </div>
        <div style={{ lineHeight: '1.6', color: isLight ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}>
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
        marginTop: '1.5rem' 
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
