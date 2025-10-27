import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSSelect, 
  MacOSModal,
  MacOSBadge,
  MacOSEmptyState,
  MacOSLoadingSkeleton
} from '../components/ui/macos';
import { 
  Sun, 
  Moon, 
  User, 
  Key, 
  MapPin, 
  Phone, 
  Clock, 
  MessageSquare,
  Globe
} from 'lucide-react';
import AppActivation from '../components/activation/AppActivation';

// macOS-стиль анимации для декоративных элементов
const floatingAnimation = `
  @keyframes float {
    0%, 100% { transform: translateY(0px) rotate(0deg); }
    50% { transform: translateY(-20px) rotate(180deg); }
  }
`;

// Добавляем стили в head
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = floatingAnimation;
  document.head.appendChild(style);
}

export default function Landing() {
  const navigate = useNavigate();
  const [language, setLanguage] = useState('RU');
  const [showActivation, setShowActivation] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Detect system theme preference
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const systemIsDark = mediaQuery.matches;
    setIsDarkMode(systemIsDark);
    
    // Initialize theme classes
    document.documentElement.style.colorScheme = systemIsDark ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', systemIsDark ? 'dark' : 'light');
    
    if (systemIsDark) {
      document.documentElement.classList.add('dark-theme');
      document.documentElement.classList.remove('light-theme');
    } else {
      document.documentElement.classList.add('light-theme');
      document.documentElement.classList.remove('dark-theme');
    }
    
    const handleChange = (e) => {
      const newIsDark = e.matches;
      setIsDarkMode(newIsDark);
      
      document.documentElement.style.colorScheme = newIsDark ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', newIsDark ? 'dark' : 'light');
      
      if (newIsDark) {
        document.documentElement.classList.add('dark-theme');
        document.documentElement.classList.remove('light-theme');
      } else {
        document.documentElement.classList.add('light-theme');
        document.documentElement.classList.remove('dark-theme');
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Toggle dark mode with system integration
  const toggleDarkMode = () => {
    const newDarkMode = !isDarkMode;
    setIsDarkMode(newDarkMode);
    
    // Update system color scheme and theme class
    document.documentElement.style.colorScheme = newDarkMode ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newDarkMode ? 'dark' : 'light');
    
    // Force CSS variables update
    if (newDarkMode) {
      document.documentElement.classList.add('dark-theme');
      document.documentElement.classList.remove('light-theme');
    } else {
      document.documentElement.classList.add('light-theme');
      document.documentElement.classList.remove('dark-theme');
    }
  };

  const pageStyle = {
    minHeight: '100vh',
    background: 'var(--mac-bg-primary)',
    backdropFilter: 'var(--mac-blur-heavy)',
    WebkitBackdropFilter: 'var(--mac-blur-heavy)',
    padding: 'var(--mac-spacing-lg)',
    fontFamily: 'var(--mac-font-family)',
    color: 'var(--mac-text-primary)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    position: 'relative'
  };

  const cardStyle = {
    backgroundColor: 'var(--mac-bg-glass)',
    backdropFilter: 'var(--mac-blur-heavy)',
    WebkitBackdropFilter: 'var(--mac-blur-heavy)',
    border: '1px solid var(--mac-border-glass)',
    borderRadius: 'var(--mac-radius-xl)',
    padding: '48px 40px',
    marginBottom: '32px',
    boxShadow: 'var(--mac-shadow-lg)',
    maxWidth: '650px',
    width: '100%',
    minHeight: '280px',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    position: 'relative',
    zIndex: 1
  };

  const headerStyle = {
    fontSize: '52px',
    fontWeight: 'var(--mac-font-weight-bold)',
    marginBottom: '24px',
    color: 'var(--mac-text-primary)',
    textAlign: 'center',
    letterSpacing: '-0.02em',
    lineHeight: '1.1'
  };

  const subtitleStyle = {
    fontSize: '20px',
    color: 'var(--mac-text-secondary)',
    marginBottom: '40px',
    textAlign: 'center',
    lineHeight: '1.5',
    fontWeight: 'var(--mac-font-weight-normal)',
    maxWidth: '500px',
    margin: '0 auto 40px auto'
  };

  const contactCardStyle = {
    ...cardStyle,
    padding: '32px 28px',
    marginBottom: '24px',
    minHeight: '200px'
  };

  const translations = {
    RU: {
      title: 'Clinic Manager',
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
      title: 'Klinika Menejeri',
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
      title: 'Clinic Manager',
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
      {/* Главная карточка (macOS UI) */}
      <MacOSCard style={cardStyle}>
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div style={headerStyle}>
            {t.title}
          </div>
          <div style={subtitleStyle}>{t.subtitle}</div>
        </div>
        
        {/* Кнопки темы и языка */}
        <div style={{ 
          display: 'flex', 
          gap: '12px', 
          justifyContent: 'center', 
          marginBottom: '32px',
          alignItems: 'center'
        }}>
          {/* Theme Toggle */}
          <MacOSButton 
            variant="ghost" 
            onClick={toggleDarkMode}
            style={{
              minWidth: '32px',
              width: '32px',
              height: '32px',
              padding: '0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            title={`Switch to ${isDarkMode ? 'light' : 'dark'} mode`}
          >
            {isDarkMode ? <Sun style={{ width: '16px', height: '16px' }} /> : <Moon style={{ width: '16px', height: '16px' }} />}
          </MacOSButton>
          
          {/* Language Selector */}
          <MacOSSelect
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{
              width: '60px',
              height: '32px',
              padding: '0 var(--mac-spacing-xs)'
            }}
          >
            <option value="RU">RU</option>
            <option value="UZ">UZ</option>
            <option value="EN">EN</option>
          </MacOSSelect>
        </div>
        
        <div style={{ 
          display: 'flex', 
          gap: '16px', 
          flexWrap: 'wrap', 
          justifyContent: 'center', 
          marginBottom: '0' 
        }}>
          <MacOSButton 
            variant="primary" 
            onClick={() => navigate('/login')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 24px',
              fontSize: '16px',
              fontWeight: '600'
            }}
          >
            <User style={{ width: '18px', height: '18px' }} />
            {t.login}
          </MacOSButton>
          <MacOSButton 
            variant="outline" 
            onClick={() => setShowActivation(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 24px',
              fontSize: '16px',
              fontWeight: '500'
            }}
          >
            <Key style={{ width: '18px', height: '18px' }} />
            {t.activate}
          </MacOSButton>
        </div>
      </MacOSCard>

      {/* Карточка контактов (macOS UI) */}
      <MacOSCard style={contactCardStyle}>
        <div style={{ marginBottom: '24px' }}>
          <div style={{ 
            fontWeight: '600', 
            fontSize: '20px', 
            color: 'var(--mac-accent-blue)',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
          }}>
            <MapPin style={{ width: '22px', height: '22px', color: 'var(--mac-accent-blue)' }} />
            {t.contacts}
          </div>
        </div>
        
        <div style={{ 
          lineHeight: '1.7', 
          color: 'var(--mac-text-secondary)',
          fontSize: '16px'
        }}>
          <div style={{ 
            marginBottom: '12px', 
            display: 'flex', 
            alignItems: 'center',
            gap: '12px'
          }}>
            <MapPin style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
            {t.address}
          </div>
          <div style={{ 
            marginBottom: '12px', 
            display: 'flex', 
            alignItems: 'center',
            gap: '12px'
          }}>
            <Phone style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
            {t.phone}
          </div>
          <div style={{ 
            marginBottom: '12px', 
            display: 'flex', 
            alignItems: 'center',
            gap: '12px'
          }}>
            <Clock style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
            {t.schedule}
          </div>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center',
            gap: '12px'
          }}>
            <MessageSquare style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
            {t.telegram}
          </div>
        </div>
      </MacOSCard>

      {/* Футер */}
      <div style={{ 
        opacity: 0.7, 
        fontSize: '14px', 
        color: 'var(--mac-text-tertiary)',
        textAlign: 'center',
        marginTop: '32px',
        fontWeight: '400',
        padding: '16px 0'
      }}>
        {t.footer}
      </div>

      {/* Модальное окно активации */}
      <MacOSModal
        isOpen={showActivation}
        onClose={() => setShowActivation(false)}
        title="Активация аккаунта"
        size="md"
      >
        <AppActivation onClose={() => setShowActivation(false)} />
      </MacOSModal>
    </div>
  );
}
