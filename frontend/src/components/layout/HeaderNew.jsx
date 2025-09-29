import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import auth, { setProfile } from '../../stores/auth.js';
import { useTheme } from '../../contexts/ThemeContext.jsx';

import {
  Home,
  User,
  LogOut,
  Sun,
  Moon,
  CreditCard
} from 'lucide-react';

import '../../styles/header-new.css';

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

  const { theme, toggleTheme, getColor, getSpacing } = useTheme();

  const user = state.profile || state.user || null;
  const role = (user?.role || user?.role_name || 'Guest');
  const roleLower = String(role).toLowerCase();

  const isRegistrarPanel = location.pathname === '/registrar-panel';

  const textColor = theme === 'light' ? getColor('gray', 900) : getColor('gray', 50);
  const borderColor = theme === 'light' ? getColor('gray', 200) : getColor('gray', 700);

  const headerStyle = {
    background: theme === 'light' ? 'rgba(255, 255, 255, 0.9)' : 'rgba(15, 23, 42, 0.9)',
    borderBottom: `1px solid ${borderColor}`,
    backdropFilter: 'blur(20px)'
  };

  // Навигация по ролям (как в исходном хедере)
  const navItems = useMemo(() => {
    const items = [];
    if (roleLower !== 'admin') {
      if (roleLower === 'registrar') items.push({ to: '/cashier-panel', label: 'Кассир', icon: <CreditCard size={16} /> });
      if (roleLower === 'cashier') items.push({ to: '/cashier-panel', label: 'Касса', icon: <CreditCard size={16} /> });
    }
    return items;
  }, [roleLower]);

  const changeLang = (v) => {
    setLang(v);
    localStorage.setItem('lang', v);
  };

  const brand = (
    <button
      className="hdr-btn hdr-btn--brand"
      onClick={() => navigate('/')}
      title="На главную"
      style={{ color: textColor }}
    >
      <span className="hdr-logo" aria-hidden>🏥</span>
      <span className="hdr-title hdr-hide-xs">Clinic Management</span>
    </button>
  );

  const roleNav = (
    <div className="hdr-nav-scroll">
      {navItems.map((item) => {
        const active = location.pathname === item.to;
        return (
          <button
            key={item.to}
            className={`hdr-btn hdr-btn--nav ${active ? 'is-active' : ''} hdr-hide-xs`}
            onClick={() => navigate(item.to)}
            title={item.label}
          >
            {item.icon}
            <span className="hdr-hide-sm">{item.label}</span>
          </button>
        );
      })}

      {roleLower === 'registrar' && isRegistrarPanel && (
        <>
          <button
            className="hdr-btn hdr-btn--nav"
            title="Главная"
            onClick={() => navigate('/registrar-panel?view=welcome')}
          >
            <Home size={16} />
            <span className="hdr-hide-md">Главная</span>
          </button>
          <button
            className="hdr-btn hdr-btn--nav hdr-hide-xs"
            title="Онлайн‑записи"
            onClick={() => navigate('/registrar-panel?view=queue')}
          >
            <span aria-hidden>📱</span>
            <span className="hdr-hide-sm">Онлайн‑записи</span>
          </button>
          <button
            className="hdr-btn hdr-btn--primary"
            title="Новая запись"
            onClick={() => {
              // Отправляем событие для открытия мастера записи
              window.dispatchEvent(new CustomEvent('openAppointmentWizard'));
            }}
          >
            <span aria-hidden>➕</span>
            <span className="hdr-hide-md">Новая запись</span>
          </button>
        </>
      )}
    </div>
  );

  const controls = (
    <div className="hdr-controls">
      <button
        className="hdr-btn hdr-btn--icon"
        onClick={toggleTheme}
        title="Переключить тему"
        aria-label="Переключить тему"
      >
        {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      <select
        className="hdr-select"
        value={lang}
        onChange={(e) => changeLang(e.target.value)}
        aria-label="Выбор языка"
      >
        <option value="ru">RU</option>
        <option value="uz">UZ</option>
        <option value="en">EN</option>
      </select>

      {user ? (
        <>
          <button
            className="hdr-btn hdr-btn--ghost"
            onClick={() => navigate('/registrar-panel')}
            title="Панель регистратора"
          >
            <User size={16} />
            <span className="hdr-hide-sm" style={{ fontWeight: 700 }}>
              {user.full_name || user.username || 'Профиль'}
            </span>
          </button>

          <button
            id="logout-header-btn"
            className="hdr-btn hdr-btn--danger logout-button"
            onClick={() => { auth.clearToken(); setProfile(null); navigate('/login'); }}
            title="Выйти"
          >
            <LogOut size={16} />
            <span className="hdr-hide-sm">Выйти</span>
          </button>
        </>
      ) : (
        <button
          className="hdr-btn hdr-btn--primary"
          onClick={() => navigate('/login')}
        >
          <User size={16} />
          <span className="hdr-hide-sm">Войти</span>
        </button>
      )}
    </div>
  );

  return (
    <div className="app-header" style={headerStyle}>
      <div className="hdr-left">{brand}</div>
      <div className="hdr-center">{roleNav}</div>
      <div className="hdr-right">{controls}</div>
    </div>
  );
}




