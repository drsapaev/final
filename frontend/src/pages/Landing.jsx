import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useTranslation } from '../hooks/useTranslation';
import {
  MacOSCard,
  MacOSButton,

  MacOSModal } from
'../components/ui/macos';
import {
  Sun,
  Moon,
  User,
  Key,
  MapPin,
  Phone,
  Clock,
  MessageSquare,
  Activity,
  Calendar,
  Stethoscope } from
'lucide-react';
import AppActivation from '../components/activation/AppActivation';

import logger from '../utils/logger';
// Компонент для карточки возможности
const FeatureCard = ({ icon, title, description, color, bgColor }) => {
  const [isHovered, setIsHovered] = React.useState(false);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '16px',
        background: bgColor,
        borderRadius: '12px',
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        border: `1px solid ${isHovered ? color : 'transparent'}`,
        transform: isHovered ? 'translateY(-2px)' : 'translateY(0)',
        boxShadow: isHovered ? '0 8px 25px rgba(0, 0, 0, 0.1)' : 'none'
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          logger.log(`Clicked on ${title}`);
        }
      }}
      role="button"
      tabIndex={0}
      onClick={() => {
        // Можно добавить логику для показа деталей или перехода
        logger.log(`Clicked on ${title}`);
      }}>

      <div style={{
        color: color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0
      }}>
        {icon}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{
          fontSize: '14px',
          fontWeight: '600',
          color: 'var(--mac-text-primary)',
          marginBottom: '4px'
        }}>
          {title}
        </div>
        <div style={{
          fontSize: '12px',
          color: 'var(--mac-text-secondary)',
          lineHeight: '1.4',
          opacity: isHovered ? 1 : 0.8
        }}>
          {description}
        </div>
      </div>
    </div>);

};

export default function Landing() {
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const { language, setLanguage, t } = useTranslation();
  const [showActivation, setShowActivation] = useState(false);

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

  // Используем глобальные переводы из контекста

  return (
    <div style={pageStyle}>
      {/* Основная карточка */}
      <MacOSCard style={{
        ...cardStyle,
        position: 'relative',
        paddingTop: '80px', // Место для кнопок управления
        paddingBottom: '40px' // Дополнительное место для кнопок действий
      }}>

        {/* Кнопки управления внутри карточки */}
        <div style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          display: 'flex',
          gap: '8px',
          alignItems: 'center',
          zIndex: 10
        }}>
          <MacOSButton
            variant="ghost"
            onClick={toggleTheme}
            style={{
              width: '32px',
              height: '32px',
              padding: '0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            title={`Switch to ${isDark ? 'light' : 'dark'} mode`}>

            {isDark ? <Sun style={{ width: '16px', height: '16px' }} /> : <Moon style={{ width: '16px', height: '16px' }} />}
          </MacOSButton>

          <MacOSButton
            variant="ghost"
            onClick={() => {
              const languages = ['ru', 'uz', 'en', 'kk'];
              const currentIndex = languages.indexOf(language);
              const nextIndex = (currentIndex + 1) % languages.length;
              setLanguage(languages[nextIndex]);
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              height: '32px',
              fontSize: '12px',
              minWidth: '60px'
            }}
            title={`Switch language - current: ${language.toUpperCase()}`}>

            <span style={{ fontSize: '14px' }}>
              {language === 'ru' ? '🇷🇺' :
              language === 'uz' ? '🇺🇿' :
              language === 'en' ? '🇺🇸' :
              language === 'kk' ? '🇰🇿' : '🌐'}
            </span>
            <span style={{ fontWeight: '600' }}>{language.toUpperCase()}</span>
          </MacOSButton>
        </div>

        {/* Статус системы внутри карточки */}
        <div style={{
          position: 'absolute',
          top: '16px',
          left: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          background: 'rgba(34, 197, 94, 0.1)',
          border: '1px solid rgba(34, 197, 94, 0.2)',
          borderRadius: '16px',
          fontSize: '12px',
          color: '#22c55e',
          zIndex: 10
        }}>
          <Activity style={{ width: '14px', height: '14px' }} />
          {t('status')}
        </div>
        {/* Логотип и заголовок */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            fontSize: '48px',
            marginBottom: '16px',
            color: 'var(--mac-accent-blue)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <div style={{
              width: '60px',
              height: '60px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, var(--mac-accent-blue), #3b82f6)',
              borderRadius: '16px',
              boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)'
            }}>
              <Stethoscope style={{ width: '32px', height: '32px', color: 'white' }} />
            </div>
          </div>
          <div style={headerStyle}>
            {t('title')}
          </div>
          <div style={subtitleStyle}>{t('subtitle')}</div>
        </div>

        {/* Ключевые возможности */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '20px',
          marginBottom: '32px',
          maxWidth: '600px',
          margin: '0 auto 32px auto'
        }}>
          <FeatureCard
            icon={<Calendar style={{ width: '20px', height: '20px' }} />}
            title={t('appointments')}
            description="Запись и управление приемами"
            color="#10b981"
            bgColor="rgba(16, 185, 129, 0.1)" />


          <FeatureCard
            icon={<Activity style={{ width: '20px', height: '20px' }} />}
            title={t('queue')}
            description="Онлайн-очереди с QR-регистрацией"
            color="#f59e0b"
            bgColor="rgba(245, 158, 11, 0.1)" />

        </div>

        {/* Кнопки действий */}
        <div style={{
          display: 'flex',
          gap: '16px',
          flexWrap: 'wrap',
          justifyContent: 'center',
          marginTop: '40px',
          paddingBottom: '8px'
        }}>
          <MacOSButton
            variant="primary"
            onClick={() => navigate('/login')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '14px 28px',
              fontSize: '16px',
              fontWeight: '600',
              minWidth: '160px'
            }}>

            <User style={{ width: '18px', height: '18px' }} />
            {t('loginButton')}
          </MacOSButton>

          <MacOSButton
            variant="outline"
            onClick={() => setShowActivation(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '14px 28px',
              fontSize: '16px',
              fontWeight: '500',
              minWidth: '160px'
            }}>

            <Key style={{ width: '18px', height: '18px' }} />
            {t('activateButton')}
          </MacOSButton>
        </div>
      </MacOSCard>

      {/* Контактная информация */}
      <MacOSCard style={contactCardStyle}>
        <div style={{
          fontWeight: '600',
          fontSize: '18px',
          color: 'var(--mac-accent-blue)',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <MapPin style={{ width: '20px', height: '20px' }} />
          {t('contacts')}
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '16px',
          fontSize: '15px',
          color: 'var(--mac-text-secondary)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <MapPin style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
            <div>
              <div style={{ fontWeight: '500', color: 'var(--mac-text-primary)' }}>Адрес</div>
              <div>{t('address')}</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Phone style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
            <div>
              <div style={{ fontWeight: '500', color: 'var(--mac-text-primary)' }}>Телефон</div>
              <div>{t('phone')}</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Clock style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
            <div>
              <div style={{ fontWeight: '500', color: 'var(--mac-text-primary)' }}>График работы</div>
              <div>{t('schedule')}</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <MessageSquare style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
            <div>
              <div style={{ fontWeight: '500', color: 'var(--mac-text-primary)' }}>Поддержка</div>
              <div>{t('telegram')}</div>
            </div>
          </div>
        </div>
      </MacOSCard>

      {/* Футер */}
      <div style={{
        opacity: 0.7,
        fontSize: '14px',
        color: 'var(--mac-text-tertiary)',
        textAlign: 'center',
        marginTop: '24px',
        fontWeight: '400'
      }}>
        {t('footer')}
      </div>

      {/* Модальное окно активации */}
      <MacOSModal
        isOpen={showActivation}
        onClose={() => setShowActivation(false)}
        title="Активация лицензии"
        size="md">

        <AppActivation onClose={() => setShowActivation(false)} />
      </MacOSModal>
    </div>);

}
