import React, { useEffect, useState } from 'react';
import auth, { setProfile } from '../stores/auth.js';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext.jsx';
import { 
  Hospital, 
  Sun, 
  Moon, 
  LogOut,
  Home,
  User,
  Settings,
  Globe
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
    if (roleLower === 'registrar') navItems.push({ to: '/registrar-panel', label: 'Регистратор', icon: '📋' });
    if (roleLower === 'doctor')    navItems.push({ to: '/doctor-panel',    label: 'Врач', icon: '👨‍⚕️' });
    if (roleLower === 'cashier')   navItems.push({ to: '/cashier-panel',   label: 'Касса', icon: '💰' });
    if (roleLower === 'lab')       navItems.push({ to: '/lab-panel',       label: 'Лаборатория', icon: '🧪' });
    if (roleLower === 'patient')   navItems.push({ to: '/patient-panel',   label: 'Пациент', icon: '👤' });
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
    transform: 'translateY(-1px)'
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
    boxShadow: '0 4px 14px 0 rgba(239, 68, 68, 0.3)'
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
    <div style={headerStyle}>
      {/* Логотип */}
      <div style={logoStyle} onClick={() => navigate('/')}>
        <Hospital size={24} color={getColor('primary', 500)} />
        <span>Clinic</span>
        <span style={{ opacity: 0.6, fontSize: getFontSize('xs'), fontWeight: '400' }}>v0.1.0</span>
      </div>

      {/* Навигация */}
      <div style={navStyle}>
        {navItems.map(item => {
          const isActive = location.pathname === item.to;
          return (
            <button 
              key={item.to} 
              style={isActive ? activeNavButtonStyle : navButtonStyle}
              onClick={() => navigate(item.to)}
              onMouseOver={(e) => {
                if (!isActive && e.target.style.background === 'transparent') {
                  e.target.style.background = theme === 'light' ? getColor('gray', 100) : getColor('gray', 800);
                }
              }}
              onMouseOut={(e) => {
                if (!isActive && e.target.style.background !== `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`) {
                  e.target.style.background = 'transparent';
                }
              }}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Управление */}
      <div style={controlsStyle}>
        {/* Переключатель темы */}
        <button 
          onClick={toggleTheme} 
          style={buttonStyle}
          title="Переключить тему"
          onMouseOver={(e) => e.target.style.transform = 'scale(1.05)'}
          onMouseOut={(e) => e.target.style.transform = 'scale(1)'}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        {/* Переключатель языка */}
        <select 
          value={lang} 
          onChange={(e) => changeLang(e.target.value)} 
          style={selectStyle}
        >
          <option value="ru">RU</option>
          <option value="uz">UZ</option>
          <option value="en">EN</option>
        </select>

        {/* Информация о пользователе */}
        {user ? (
          <>
            <div style={userInfoStyle}>
              <User size={16} />
              <span style={{ fontWeight: '600' }}>{displayName}</span>
              {showRoleBadge && (
                <span style={roleBadgeStyle}>{roleLabel}</span>
              )}
            </div>
            <button
              onClick={() => { auth.clearToken(); setProfile(null); navigate('/login'); }}
              style={logoutButtonStyle}
              onMouseOver={(e) => e.target.style.transform = 'translateY(-1px)'}
              onMouseOut={(e) => e.target.style.transform = 'translateY(0)'}
            >
              <LogOut size={16} />
              <span>Выйти</span>
            </button>
          </>
        ) : (
          <button 
            onClick={() => navigate('/login')} 
            style={{
              ...buttonStyle,
              background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
              color: 'white',
              border: 'none',
              boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)'
            }}
            onMouseOver={(e) => e.target.style.transform = 'translateY(-1px)'}
            onMouseOut={(e) => e.target.style.transform = 'translateY(0)'}
          >
            <User size={16} />
            <span>Войти</span>
          </button>
        )}
      </div>
    </div>
  );
}


