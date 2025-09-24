import React, { useEffect, useState } from 'react';
import auth, { setProfile } from '../../stores/auth.js';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext.jsx';
import '../../styles/cursor-effects.css';
import '../../styles/animations.css';
import '../ui/animations.css';
import { 
  Hospital, 
  Sun, 
  Moon, 
  LogOut,
  Home,
  User,
  Settings,
  Globe,
  CreditCard,
  Search as SearchIcon
} from 'lucide-react';

export default function Header() {
  const [st, setSt] = useState(auth.getState());
  const [lang, setLang] = useState(localStorage.getItem('lang') || 'ru');
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  useEffect(() => auth.subscribe(setSt), []);

  function changeLang(v) {
    setLang(v);
    localStorage.setItem('lang', v);
  }

  const user = st.profile || st.user || null;
  const role = (user?.role || user?.role_name || 'Guest');
  const roleLower = String(role).toLowerCase();
  const view = new URLSearchParams(location.search).get('view');

  // Используем централизованную систему дизайна вместо дублированных токенов
  const { 
    getColor, 
    getSpacing, 
    getFontSize, 
    designTokens 
  } = useTheme();

  // Адаптивные цвета для тем
  const textColor = theme === 'light' ? getColor('gray', 900) : getColor('gray', 50);
  const bgColor = theme === 'light' ? getColor('gray', 50) : getColor('gray', 900);
  const borderColor = theme === 'light' ? getColor('gray', 200) : getColor('gray', 700);

  const navItems = [];
  // Для администратора навигационные пункты скрыты
  if (roleLower !== 'admin') {
    if (roleLower === 'registrar') navItems.push({ to: '/cashier-panel', label: 'Кассир', icon: <CreditCard size={16} /> });
    if (roleLower === 'cashier')   navItems.push({ to: '/cashier-panel', label: 'Касса',  icon: <CreditCard size={16} /> });
  }
  
  // Специализированные роли
  if (roleLower === 'cardio') navItems.push({ to: '/cardiologist', label: 'Кардиолог', icon: '❤️' });
  if (roleLower === 'derma') navItems.push({ to: '/dermatologist', label: 'Дерматолог', icon: '✨' });
  if (roleLower === 'dentist') navItems.push({ to: '/dentist', label: 'Стоматолог', icon: '🦷' });

  // Стили в стиле RegistrarPanel - на весь экран
  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: `${getSpacing('md')} ${getSpacing('xl')}`,
    background: theme === 'light' 
      ? 'rgba(255, 255, 255, 0.9)' 
      : 'rgba(15, 23, 42, 0.9)',
    backdropFilter: 'blur(20px)',
    borderBottom: `1px solid ${borderColor}`,
    position: 'sticky',
    top: 0,
    left: 0,
    right: 0,
    width: '100%',
    zIndex: 1000,
    boxShadow: theme === 'light' 
      ? '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
      : '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
    boxSizing: 'border-box'
  };

  const logoStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    cursor: 'pointer',
    fontWeight: '800',
    fontSize: getFontSize('xl'),
    color: textColor,
    transition: 'all 0.3s ease'
  };

  const navStyle = {
    display: 'flex',
    gap: getSpacing('sm'),
    alignItems: 'center'
  };

  const historyPanelStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    marginLeft: getSpacing('xl')
  };

  const inputStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('md')}`,
    border: `1px solid ${borderColor}`,
    borderRadius: '8px',
    background: theme === 'light' ? 'white' : getColor('gray', 800),
    color: textColor,
    fontSize: getFontSize('sm')
  };

  const navButtonStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('xs'),
    padding: `${getSpacing('sm')} ${getSpacing('md')}`,
    border: 'none',
    borderRadius: '12px',
    background: 'transparent',
    color: textColor,
    cursor: 'pointer',
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    transition: 'all 0.3s ease',
    textDecoration: 'none'
  };

  const activeNavButtonStyle = {
    ...navButtonStyle,
    background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'white',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    transform: 'translateY(-1px)',
    textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
  };

  const controlsStyle = {
    display: 'flex',
    gap: getSpacing('sm'),
    alignItems: 'center'
  };

  const buttonStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('xs'),
    padding: `${getSpacing('sm')} ${getSpacing('md')}`,
    border: `1px solid ${borderColor}`,
    borderRadius: '8px',
    background: theme === 'light' ? 'white' : getColor('gray', 800),
    color: textColor,
    cursor: 'pointer',
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    transition: 'all 0.3s ease'
  };

  const selectStyle = {
    ...buttonStyle,
    padding: `${getSpacing('sm')} ${getSpacing('sm')}`,
    minWidth: '60px'
  };

  const userInfoStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    padding: `${getSpacing('sm')} ${getSpacing('md')}`,
    background: theme === 'light' ? getColor('gray', 100) : getColor('gray', 800),
    borderRadius: '8px',
    fontSize: getFontSize('sm'),
    color: textColor
  };

  const logoutButtonStyle = {
    ...buttonStyle,
    background: `linear-gradient(135deg, ${getColor('danger', 500)} 0%, ${getColor('danger', 600)} 100%)`,
    color: 'white',
    border: 'none',
    boxShadow: '0 4px 14px 0 rgba(239, 68, 68, 0.3)',
    textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
  };

  // Ролевые метки на русском
  function getRoleLabel(r) {
    const x = String(r || '').toLowerCase();
    if (x === 'admin') return 'Админ';
    if (x === 'registrar') return 'Регистратор';
    if (x === 'doctor') return 'Врач';
    if (x === 'lab') return 'Лаборатория';
    if (x === 'cashier') return 'Кассир';
    if (x === 'cardio' || x === 'cardiologist') return 'Кардиолог';
    if (x === 'derma' || x === 'dermatologist') return 'Дерматолог';
    if (x === 'dentist' || x === 'dental') return 'Стоматолог';
    if (x === 'patient') return 'Пациент';
    return r || '';
  }

  function capitalize(s) {
    if (!s) return '';
    const str = String(s);
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  const displayNameRaw = (user?.full_name && String(user.full_name).trim()) || (user?.username && String(user.username).trim()) || '';
  const roleLabel = getRoleLabel(roleLower);
  // Если username совпадает с ролью (admin/Admin), показываем только аккуратную роль
  const isNameEqualsRole = displayNameRaw && displayNameRaw.toLowerCase() === roleLower;
  const displayName = isNameEqualsRole ? roleLabel : (user?.full_name ? displayNameRaw : capitalize(displayNameRaw));
  const showRoleBadge = !isNameEqualsRole && !!roleLabel;

  const roleBadgeStyle = {
    padding: '2px 8px',
    borderRadius: 999,
    fontSize: '12px',
    border: `1px solid ${borderColor}`,
    background: theme === 'light' ? getColor('gray', 100) : getColor('gray', 800),
    color: textColor,
    whiteSpace: 'nowrap'
  };

  return (
    <header 
      className="interactive-element app-header-2025"
      style={{
        position: 'sticky',
        top: 0,
        left: 0,
        right: 0,
        width: '100%',
        zIndex: 50,
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid',
        transition: 'all 0.2s ease',
        backgroundColor: theme === 'light' ? 'rgba(255, 255, 255, 0.9)' : 'rgba(15, 23, 42, 0.9)',
        borderColor: theme === 'light' ? getColor('gray', 200) : getColor('gray', 700),
        boxShadow: theme === 'light' 
          ? '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
          : '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
        fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans", "Liberation Sans", sans-serif',
        fontFeatureSettings: '"calt" 1, "liga" 1',
        WebkitFontSmoothing: 'antialiased',
        MozOsxFontSmoothing: 'grayscale'
      }}>
      <style>{`
        /* Локальные правила, чтобы победить глобальные !important из dark-theme-visibility-fix.css */
        [data-theme="dark"] .app-header-2025 button,
        [data-theme="dark"] .app-header-2025 select,
        [data-theme="dark"] .app-header-2025 input {
          color: #f8fafc !important;
        }
        [data-theme="dark"] .app-header-2025 .role-badge {
          color: #e2e8f0 !important;
        }
        /* Современная типографика кнопок */
        .app-header-2025 button,
        .app-header-2025 select,
        .app-header-2025 input {
          letter-spacing: 0.01em;
          font-weight: 600;
        }
      `}</style>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 24px',
        maxWidth: '100%'
      }}>
      {/* Логотип */}
        <button 
          className="interactive-element hover-lift focus-ring"
          onClick={() => navigate('/')}
          style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            color: textColor 
          }}
        >
        <Hospital size={24} color={getColor('primary', 500)} />
          <span style={{ fontSize: '20px', fontWeight: 'bold' }}>Clinic</span>
          <span style={{ fontSize: '12px', fontWeight: 'normal', opacity: 0.6 }}>v0.1.0</span>
        </button>

      {/* Навигация */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {navItems.map(item => {
          const isActive = location.pathname === item.to;
          return (
            <button 
              key={item.to} 
                className="interactive-element hover-lift ripple-effect focus-ring"
                style={{
                  height: '40px',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '500',
                  transition: 'all 0.2s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  cursor: 'pointer',
                  ...(isActive ? {
                    background: `linear-gradient(135deg, ${getColor('primary', 600)} 0%, ${getColor('primary', 700)} 100%)`,
                    color: 'white',
                    border: 'none',
                    boxShadow: '0 4px 6px -1px rgba(59, 130, 246, 0.3)',
                    transform: 'translateY(-1px)'
                  } : {
                    background: theme === 'light' ? 'white' : getColor('gray', 700),
                    color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100),
                    border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
                    boxShadow: 'none'
                  })
                }}
              onClick={() => navigate(item.to)}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}

          {/* Быстрые ссылки для регистратора внутри панели */}
          {roleLower === 'registrar' && location.pathname === '/registrar-panel' && (
            <>
              <button
                className="interactive-element hover-lift ripple-effect focus-ring"
                style={{
                  height: '40px',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '500',
                  transition: 'all 0.2s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  cursor: 'pointer',
                  ...(new URLSearchParams(location.search).get('view') === 'welcome' ? {
                    background: `linear-gradient(135deg, ${getColor('success', 600)} 0%, ${getColor('success', 700)} 100%)`,
                    color: 'white',
                    border: 'none',
                    boxShadow: '0 4px 6px -1px rgba(34, 197, 94, 0.3)',
                    transform: 'translateY(-1px)'
                  } : {
                    background: theme === 'light' ? 'white' : getColor('gray', 700),
                    color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100),
                    border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
                    boxShadow: 'none'
                  })
                }}
                onClick={() => navigate('/registrar-panel?view=welcome')}
                title="Главная"
              >
                <Home size={16} />
                <span>Главная</span>
              </button>
              <button
                className="interactive-element hover-lift ripple-effect focus-ring"
                style={{
                  height: '40px',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '500',
                  transition: 'all 0.2s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  cursor: 'pointer',
                  ...(new URLSearchParams(location.search).get('view') === 'queue' ? {
                    background: `linear-gradient(135deg, #9333ea 0%, #7c3aed 100%)`,
                    color: 'white',
                    border: 'none',
                    boxShadow: '0 4px 6px -1px rgba(147, 51, 234, 0.3)',
                    transform: 'translateY(-1px)'
                  } : {
                    background: theme === 'light' ? 'white' : getColor('gray', 700),
                    color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100),
                    border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
                    boxShadow: 'none'
                  })
                }}
                onClick={() => navigate('/registrar-panel?view=queue')}
                title="Онлайн‑записи"
              >
                <span>📱</span>
                <span>Онлайн‑записи</span>
              </button>

              {/* История (календарь+поиск) в контексте кнопки "Главная" */}
              {view === 'welcome' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginLeft: '24px' }}>
                  <input
                    type="date"
                    className="interactive-element focus-ring"
                    style={{
                      height: '40px',
                      padding: '8px 12px',
                      border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
                      borderRadius: '8px',
                      fontSize: '14px',
                      transition: 'all 0.2s ease',
                      backgroundColor: theme === 'light' ? 'white' : getColor('gray', 700),
                      color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100)
                    }}
                    defaultValue={new URLSearchParams(location.search).get('date') || ''}
                    onChange={(e) => {
                      const params = new URLSearchParams(location.search);
                      const val = e.currentTarget.value;
                      if (val) params.set('date', val); else params.delete('date');
                      params.set('view', 'welcome');
                      navigate(`/registrar-panel?${params.toString()}`, { replace: true });
                    }}
                  />
                  <div style={{ position: 'relative' }}>
                    <SearchIcon 
                      size={16} 
                      style={{ 
                        position: 'absolute',
                        left: '12px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        opacity: 0.6,
                        color: theme === 'light' ? getColor('gray', 600) : getColor('gray', 300)
                      }}
                    />
                    <input
                      type="search"
                      placeholder="Поиск по истории..."
                      className="interactive-element focus-ring"
                      style={{
                        height: '40px',
                        paddingLeft: '40px',
                        paddingRight: '12px',
                        border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
                        borderRadius: '8px',
                        fontSize: '14px',
                        minWidth: '240px',
                        transition: 'all 0.2s ease',
                        backgroundColor: theme === 'light' ? 'white' : getColor('gray', 700),
                        color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100)
                      }}
                      defaultValue={new URLSearchParams(location.search).get('q') || ''}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          const params = new URLSearchParams(location.search);
                          const val = e.currentTarget.value.trim();
                          if (val) params.set('q', val); else params.delete('q');
                          params.set('view', 'welcome');
                          navigate(`/registrar-panel?${params.toString()}`, { replace: true });
                        }
                      }}
                    />
                  </div>
      </div>
              )}
            </>
          )}
        </nav>

      {/* Управление */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '12px',
          whiteSpace: 'nowrap'
        }}>
        {/* Переключатель темы */}
        <button 
          onClick={toggleTheme} 
            className="interactive-element hover-lift ripple-effect focus-ring"
            style={{
              width: '40px',
              height: '40px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
              borderRadius: '8px',
              transition: 'all 0.2s ease',
              backgroundColor: theme === 'light' ? 'white' : getColor('gray', 700),
              color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100),
              cursor: 'pointer'
            }}
          title="Переключить тему"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        {/* Переключатель языка */}
        <select 
          value={lang} 
          onChange={(e) => changeLang(e.target.value)} 
            className="interactive-element focus-ring"
            style={{
              height: '40px',
              padding: '8px 12px',
              border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '500',
              transition: 'all 0.2s ease',
              minWidth: '64px',
              backgroundColor: theme === 'light' ? 'white' : getColor('gray', 700),
              color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100),
              cursor: 'pointer'
            }}
        >
          <option value="ru">RU</option>
          <option value="uz">UZ</option>
          <option value="en">EN</option>
        </select>

        {/* Информация о пользователе */}
        {user ? (
          <>
              <button
                onClick={() => navigate('/registrar-panel')}
                className="interactive-element hover-lift ripple-effect focus-ring user-profile-button"
                style={{
                  height: '40px',
                  padding: '8px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '500',
                  transition: 'all 0.2s ease',
                  backgroundColor: theme === 'light' ? 'white' : getColor('gray', 700),
                  color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100),
                  cursor: 'pointer',
                  flexShrink: 0,
                  minWidth: 'auto',
                  maxWidth: '200px',
                  whiteSpace: 'nowrap'
                }}
                title="Открыть панель регистратора"
              >
              <User size={16} />
                <span style={{ fontWeight: '700' }}>{displayName}</span>
              {showRoleBadge && (
                  <span 
                    className="role-badge"
                    style={{
                      padding: '2px 8px',
                      fontSize: '12px',
                      borderRadius: '999px',
                      border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 500)}`,
                      backgroundColor: theme === 'light' ? getColor('gray', 100) : getColor('gray', 600),
                      color: theme === 'light' ? getColor('gray', 700) : getColor('gray', 200),
                      whiteSpace: 'nowrap'
                    }}
                  >
                    {roleLabel}
                  </span>
                )}
              </button>
            <button
                id="logout-header-btn"
              onClick={() => { auth.clearToken(); setProfile(null); navigate('/login'); }}
                className="interactive-element hover-lift ripple-effect action-button-hover focus-ring logout-button"
                style={{
                  height: '40px',
                  padding: '8px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '500',
                  color: 'white',
                  transition: 'all 0.2s ease',
                  background: `linear-gradient(135deg, ${getColor('danger', 500)} 0%, ${getColor('danger', 600)} 100%)`,
                  boxShadow: '0 4px 6px -1px rgba(239, 68, 68, 0.3)',
                  border: 'none',
                  cursor: 'pointer',
                  flexShrink: 0,
                  flexGrow: 0,
                  width: 'auto',
                  minWidth: 'fit-content',
                  maxWidth: '160px',
                  whiteSpace: 'nowrap',
                  alignSelf: 'center',
                  overflow: 'visible'
                }}
            >
              <LogOut size={16} />
              <span>Выйти</span>
            </button>
          </>
        ) : (
          <button 
            onClick={() => navigate('/login')} 
              className="interactive-element hover-lift ripple-effect action-button-hover focus-ring"
            style={{
                height: '40px',
                padding: '8px 12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: '500',
                color: 'white',
                transition: 'all 0.2s ease',
              background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
                boxShadow: '0 4px 6px -1px rgba(59, 130, 246, 0.3)',
              border: 'none',
                cursor: 'pointer'
            }}
          >
            <User size={16} />
            <span>Войти</span>
          </button>
        )}
      </div>
    </div>
    </header>
  );
}


