import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth.js';
import { useTheme } from '../../contexts/ThemeContext.jsx';
import CompactConnectionStatus from '../pwa/CompactConnectionStatus';
import { Button, Icon } from '../ui/macos';

/**
 * Новый компактный и предсказуемый хедер.
 * Цели:
 * - Абсолютно исключить растяжение кнопок (inline-flex + flex:0 0 auto + nowrap)
 * - Чёткая сетка: brand | nav (scroll) | controls
 * - Повторить функционал текущего Header.jsx, сохранив роли и роутинг
 */
export default function HeaderNew() {
  const navigate = useNavigate();
  const location = useLocation();

  const [state, setState] = useState(auth.getState());
  const [lang, setLang] = useState(localStorage.getItem('lang') || 'ru');

  useEffect(() => auth.subscribe(setState), []);

  const { theme, toggleTheme } = useTheme();

  // Принудительная перерисовка при смене темы
  useEffect(() => {
    // Этот useEffect заставит компонент перерисоваться при смене темы
  }, [theme]);

  const user = state.profile || state.user || null;
  const role = (user?.role || user?.role_name || 'Guest');
  const roleLower = String(role).toLowerCase();

  const isRegistrarPanel = location.pathname === '/registrar-panel';

  const headerStyle = {
    backgroundColor: 'var(--mac-bg-toolbar)',
    borderBottom: '1px solid var(--mac-separator)',
    backdropFilter: 'var(--mac-blur-light)',
    WebkitBackdropFilter: 'var(--mac-blur-light)',
    boxShadow: 'var(--mac-shadow-sm)',
    display: 'grid',
    gridTemplateColumns: 'auto 1fr auto',
    alignItems: 'center',
    columnGap: '12px',
    overflow: 'hidden',
    borderRadius: 'var(--mac-radius-md)',
    padding: '0 16px',
    height: '54px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
  };

  // Навигация по ролям (как в исходном хедере)
  const navItems = useMemo(() => {
    const items = [];
    if (roleLower !== 'admin') {
      if (roleLower === 'registrar') items.push({ to: '/cashier-panel', label: 'Кассир', icon: 'creditcard' });
      if (roleLower === 'cashier') items.push({ to: '/cashier-panel', label: 'Касса', icon: 'creditcard' });
    }
    return items;
  }, [roleLower]);

  const changeLang = (v) => {
    setLang(v);
    localStorage.setItem('lang', v);
  };

  const brand = (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => navigate('/')}
      title="На главную"
      style={{
        color: 'var(--mac-text-primary)',
        fontWeight: '700',
        fontSize: 'var(--mac-font-size-lg)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px'
      }}
    >
      <Icon name="stethoscope" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
      <span className="hdr-hide-xs">Clinic Management</span>
    </Button>
  );

  const roleNav = (
    <div className="hdr-nav-scroll" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'nowrap', whiteSpace: 'nowrap', overflowX: 'auto' }}>
      {navItems.map((item) => {
        const active = location.pathname === item.to;
        return (
          <Button
            key={item.to}
            variant={active ? "primary" : "outline"}
            size="small"
            onClick={() => navigate(item.to)}
            title={item.label}
            className="hdr-hide-xs"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flexShrink: 0
            }}
          >
            <Icon name={item.icon} size="small" style={{ color: active ? 'white' : 'var(--mac-text-primary)' }} />
            <span className="hdr-hide-sm">{item.label}</span>
          </Button>
        );
      })}

      {roleLower === 'registrar' && isRegistrarPanel && (
        <>
          <Button
            variant="outline"
            size="small"
            title="Главная"
            onClick={() => navigate('/registrar-panel?view=welcome')}
            className="hdr-hide-md"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}
          >
            <Icon name="house" size="small" />
            <span className="hdr-hide-md">Главная</span>
          </Button>
          <Button
            variant="outline"
            size="small"
            title="Онлайн‑записи"
            onClick={() => navigate('/registrar-panel?view=queue')}
            className="hdr-hide-xs"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}
          >
            <Icon name="bell" size="small" style={{ color: 'var(--mac-text-primary)' }} />
            <span className="hdr-hide-sm">Онлайн‑записи</span>
          </Button>
          <Button
            variant="primary"
            size="small"
            title="Новая запись"
            onClick={() => {
              // Отправляем событие для открытия мастера записи
              window.dispatchEvent(new CustomEvent('openAppointmentWizard'));
            }}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}
          >
            <Icon name="plus" size="small" style={{ color: 'white' }} />
            <span className="hdr-hide-md">Новая запись</span>
          </Button>
        </>
      )}
    </div>
  );

  const controls = (
    <div className="hdr-controls" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'nowrap', whiteSpace: 'nowrap' }}>
      {/* 1) Язык */}
      <Button
        variant="ghost"
        size="small"
        onClick={() => changeLang(lang === 'ru' ? 'uz' : lang === 'uz' ? 'en' : 'ru')}
        title={`Switch to ${lang === 'ru' ? 'UZ' : lang === 'uz' ? 'EN' : 'RU'}`}
        style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: '600',
          padding: '6px 10px',
          flex: '0 0 auto',
          border: '1px solid var(--mac-border)',
          display: 'flex',
          alignItems: 'center',
          gap: '4px'
        }}
      >
        <Icon name="magnifyingglass" size="small" />
        {lang.toUpperCase()}
      </Button>

      {/* 2) Сеть */}
      <div style={{ flex: '0 0 auto' }}>
        <CompactConnectionStatus className="mr-2" />
      </div>

      {/* 3) Тема */}
      <Button
        variant="ghost"
        size="small"
        onClick={toggleTheme}
        title="Переключить тему"
        aria-label="Переключить тему"
        style={{
          width: '36px',
          height: '36px',
          padding: 0,
          borderRadius: 'var(--mac-radius-sm)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: '0 0 auto'
        }}
      >
        {theme === 'dark' ? (
          <Icon name="sun" size="small" style={{ color: '#ff9500' }} />
        ) : (
          <Icon name="moon" size="small" style={{ color: '#5ac8fa' }} />
        )}
      </Button>

      {/* 4) Профиль / Войти */}
      {user ? (
        <>
          <Button
            variant="outline"
            size="small"
            onClick={() => navigate('/registrar-panel')}
            title="Панель регистратора"
            className="hdr-hide-sm"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flex: '0 0 auto'
            }}
          >
            <Icon name="person" size="small" style={{ color: 'var(--mac-text-primary)' }} />
            <span style={{ fontWeight: 600 }}>
              {user.full_name || user.username || 'Профиль'}
            </span>
          </Button>

          {/* 5) Выход */}
          <Button
            id="logout-header-btn"
            variant="danger"
            size="small"
            onClick={() => { auth.clearToken(); setProfile(null); navigate('/login'); }}
            title="Выйти"
            className="hdr-hide-sm"
            style={{ 
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flex: '0 0 auto' 
            }}
          >
            <Icon name="person" size="small" style={{ color: 'white' }} />
            <span>Выйти</span>
          </Button>
        </>
      ) : (
        <Button
          variant="primary"
          size="small"
          onClick={() => navigate('/login')}
          className="hdr-hide-sm"
          style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            flex: '0 0 auto' 
          }}
        >
          <Icon name="person" size="small" style={{ color: 'white' }} />
          <span>Войти</span>
        </Button>
      )}
    </div>
  );

  return (
    <div className="app-header" style={headerStyle}>
      <div className="hdr-left" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{brand}</div>
      <div className="hdr-center" style={{ minWidth: 0 }}>{roleNav}</div>
      <div className="hdr-right" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{controls}</div>
    </div>
  );
}




