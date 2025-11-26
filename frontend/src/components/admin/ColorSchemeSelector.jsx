import React, { useState, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { MacOSButton, MacOSCard, MacOSSelect } from '../ui/macos';
import { Palette, Sun, Moon, Monitor, Sparkles, Rainbow, Layers } from 'lucide-react';

const ColorSchemeSelector = () => {
  const { theme, setTheme, isDark, isLight } = useTheme();
  // Initialize with saved scheme or current theme
  const [selectedScheme, setSelectedScheme] = useState(() => {
    const savedScheme = localStorage.getItem('colorScheme');
    if (savedScheme && ['light', 'dark', 'auto', 'vibrant', 'glass', 'gradient'].includes(savedScheme)) {
      return savedScheme;
    }
    return theme;
  });

  const colorSchemes = [
    {
      id: 'light',
      name: 'Светлая тема',
      description: 'Классическая светлая тема macOS',
      icon: Sun,
      type: 'standard',
      colors: {
        primary: '#ffffff',
        secondary: '#f5f5f7',
        accent: '#007aff',
        text: '#000000'
      }
    },
    {
      id: 'dark',
      name: 'Темная тема',
      description: 'Современная темная тема macOS',
      icon: Moon,
      type: 'standard',
      colors: {
        primary: '#1c1c1e',
        secondary: '#2c2c2e',
        accent: '#007aff',
        text: '#ffffff'
      }
    },
    {
      id: 'auto',
      name: 'Автоматически',
      description: 'Следует системным настройкам',
      icon: Monitor,
      type: 'standard',
      colors: {
        primary: 'var(--mac-bg-primary)',
        secondary: 'var(--mac-bg-secondary)',
        accent: 'var(--mac-accent-blue)',
        text: 'var(--mac-text-primary)'
      }
    },
    {
      id: 'vibrant',
      name: 'Яркая многоцветная',
      description: 'Насыщенные яркие цвета для энергичного интерфейса',
      icon: Rainbow,
      type: 'vibrant',
      colors: {
        primary: '#ff6b9d',
        secondary: '#c44569',
        accent: '#ff9500',
        text: '#ffffff',
        gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #f5576c 75%, #4facfe 100%)'
      }
    },
    {
      id: 'glass',
      name: 'Полупрозрачная стеклянная',
      description: 'Эффект размытого стекла с лёгкими оттенками',
      icon: Layers,
      type: 'glass',
      colors: {
        primary: 'rgba(255,255,255,0.25)',
        secondary: 'rgba(245,245,247,0.4)',
        accent: 'rgba(0,122,255,0.6)',
        text: '#1c1c1e',
        backdrop: 'blur(20px)'
      }
    },
    {
      id: 'gradient',
      name: 'Градиентная палитра',
      description: 'Многоцветные градиенты с плавными переходами',
      icon: Sparkles,
      type: 'gradient',
      colors: {
        primary: '#667eea',
        secondary: '#764ba2',
        accent: '#f093fb',
        text: '#ffffff',
        gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)'
      }
    }
  ];

  // Apply color scheme CSS variables
  const applyColorScheme = (schemeId) => {
    const root = document.documentElement;
    const scheme = colorSchemes.find(s => s.id === schemeId);
    
    if (!scheme) return;
    
    // Remove theme classes to prevent ThemeContext from overriding
    document.body.classList.remove('light-theme', 'dark-theme');
    root.removeAttribute('data-theme');
    
    if (scheme.type === 'vibrant') {
      // Apply vibrant theme - матовые приглушённые цвета
      root.style.setProperty('--mac-bg-primary', '#6b8db3'); /* Приглушённый синий */
      root.style.setProperty('--mac-bg-secondary', '#7fa899'); /* Приглушённый бирюзовый */
      root.style.setProperty('--mac-accent-blue', '#d4a063'); /* Приглушённый оранжевый */
      root.style.setProperty('--mac-text-primary', '#ffffff');
      root.style.setProperty('--mac-text-secondary', 'rgba(255,255,255,0.92)');
      root.style.setProperty('--mac-gradient-window', 'linear-gradient(135deg, rgba(107, 141, 179, 0.75) 0%, rgba(127, 168, 153, 0.7) 40%, rgba(212, 160, 99, 0.65) 80%), linear-gradient(135deg, rgba(120, 130, 145, 0.3) 0%, rgba(130, 140, 150, 0.25) 100%)');
      root.style.setProperty('--mac-gradient-sidebar', 'linear-gradient(135deg, rgba(100, 130, 165, 0.7) 0%, rgba(115, 155, 140, 0.65) 45%, rgba(200, 150, 90, 0.6) 100%), linear-gradient(135deg, rgba(130, 140, 150, 0.25) 0%, rgba(140, 150, 160, 0.2) 100%)');
      root.style.setProperty('--bg', '#6b8db3');
      root.style.setProperty('--mac-bg-toolbar', 'rgba(30, 35, 45, 0.4)');
      root.style.setProperty('--mac-separator', 'rgba(255,255,255,0.22)');
      root.style.setProperty('--mac-border', 'rgba(255,255,255,0.22)');
      root.style.setProperty('--mac-border-secondary', 'rgba(255,255,255,0.18)');
      root.setAttribute('data-color-scheme', 'vibrant');
    } else if (scheme.type === 'glass') {
      // Apply glass theme - синхронизировано с macos.css [data-color-scheme="glass"]
      // Улучшенные значения для лучшей видимости карточек
      root.style.setProperty('--mac-bg-primary', 'rgba(50, 55, 65, 0.75)');
      root.style.setProperty('--mac-bg-secondary', 'rgba(60, 65, 75, 0.65)');
      root.style.setProperty('--mac-bg-toolbar', 'rgba(50, 55, 65, 0.85)'); /* Увеличенная непрозрачность для хедера */
      root.style.setProperty('--mac-bg-tertiary', 'rgba(70, 75, 85, 0.55)');
      root.style.setProperty('--mac-accent-blue', 'rgba(0,122,255,0.8)');
      root.style.setProperty('--mac-text-primary', '#f0f1f5');
      root.style.setProperty('--mac-text-secondary', 'rgba(240,240,245,0.9)');
      root.style.setProperty('--mac-border', 'rgba(255, 255, 255, 0.2)');
      root.style.setProperty('--mac-border-secondary', 'rgba(255, 255, 255, 0.15)');
      root.style.setProperty('--mac-blur-light', 'saturate(180%) blur(22px)');
      root.style.setProperty('--surface', 'rgba(255,255,255,0.25)');
      root.style.setProperty('--bg', '#f6f7f9');
      // Очищаем градиент из предыдущих тем
      root.style.setProperty('--mac-gradient-window', 'none');
      // Применяем фон и backdrop-filter на html и body
      document.documentElement.style.background = 'rgba(20, 20, 25, 0.3)';
      document.documentElement.style.backdropFilter = 'blur(22px) saturate(160%)';
      document.documentElement.style.webkitBackdropFilter = 'blur(22px) saturate(160%)';
      document.body.style.background = 'rgba(20, 20, 25, 0.3)';
      document.body.style.backdropFilter = 'blur(22px) saturate(160%)';
      document.body.style.webkitBackdropFilter = 'blur(22px) saturate(160%)';
      root.setAttribute('data-color-scheme', 'glass');
    } else if (scheme.type === 'gradient') {
      // Apply gradient theme
      root.style.setProperty('--mac-bg-primary', scheme.colors.primary);
      root.style.setProperty('--mac-bg-secondary', scheme.colors.secondary);
      root.style.setProperty('--mac-accent-blue', scheme.colors.accent);
      root.style.setProperty('--mac-text-primary', scheme.colors.text);
      root.style.setProperty('--mac-text-secondary', 'rgba(255,255,255,0.9)');
      root.style.setProperty('--mac-gradient-window', scheme.colors.gradient);
      root.style.setProperty('--bg', scheme.colors.primary);
      root.style.setProperty('--mac-bg-toolbar', scheme.colors.primary);
      // Сброс эффектов стекла на html/body, чтобы не влияли при переходе из Glass
      document.documentElement.style.background = '';
      document.documentElement.style.backdropFilter = '';
      document.documentElement.style.webkitBackdropFilter = '';
      document.body.style.background = '';
      document.body.style.backdropFilter = '';
      document.body.style.webkitBackdropFilter = '';
      root.setAttribute('data-color-scheme', 'gradient');
    }
  };

  const handleSchemeChange = (schemeId) => {
    setSelectedScheme(schemeId);
    
    // Clear custom scheme flags first
    localStorage.removeItem('customColorScheme');
    localStorage.removeItem('activeColorSchemeId');
    
    if (schemeId === 'vibrant' || schemeId === 'glass' || schemeId === 'gradient') {
      // Set flags BEFORE applying to prevent ThemeContext override
      localStorage.setItem('customColorScheme', 'true');
      localStorage.setItem('activeColorSchemeId', schemeId);
      // Apply custom color scheme
      applyColorScheme(schemeId);
      // Broadcast change
      window.dispatchEvent(new CustomEvent('colorSchemeChanged', { detail: schemeId }));
    } else if (schemeId === 'auto') {
      // Определяем системную тему
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      setTheme(prefersDark ? 'dark' : 'light');
      // Clear any color scheme attribute
      document.documentElement.removeAttribute('data-color-scheme');
      window.dispatchEvent(new CustomEvent('colorSchemeChanged', { detail: schemeId }));
    } else if (schemeId === 'light' || schemeId === 'dark') {
      // Apply standard theme without reload
      setTheme(schemeId);
      document.documentElement.removeAttribute('data-color-scheme');
      
      // Force update theme context
      const root = document.documentElement;
      if (schemeId === 'dark') {
        root.setAttribute('data-theme', 'dark');
        document.body.classList.remove('light-theme');
        document.body.classList.add('dark-theme');
      } else {
        root.setAttribute('data-theme', 'light');
        document.body.classList.remove('dark-theme');
        document.body.classList.add('light-theme');
      }
      window.dispatchEvent(new CustomEvent('colorSchemeChanged', { detail: schemeId }));
    }
    
    // Save to localStorage
    try {
      localStorage.setItem('colorScheme', schemeId);
    } catch (e) {
      console.warn('Failed to save color scheme:', e);
    }
  };
  
  // Sync selectedScheme with actually applied theme on mount and when theme changes
  useEffect(() => {
    const savedScheme = localStorage.getItem('colorScheme');
    const activeSchemeId = localStorage.getItem('activeColorSchemeId');
    const isCustomScheme = localStorage.getItem('customColorScheme') === 'true';
    
    // Determine what scheme is actually active
    let actualScheme = theme; // default
    if (isCustomScheme && activeSchemeId) {
      actualScheme = activeSchemeId;
    } else if (savedScheme) {
      actualScheme = savedScheme;
    }
    
    // Sync state if needed (but don't trigger handleSchemeChange to avoid reapplication)
    if (actualScheme !== selectedScheme && ['light', 'dark', 'auto', 'vibrant', 'glass', 'gradient'].includes(actualScheme)) {
      setSelectedScheme(actualScheme);
    }
  }, [theme]); // Re-sync when theme changes
  
  // Ensure custom schemes persist (backup application)
  useEffect(() => {
    if (selectedScheme === 'vibrant' || selectedScheme === 'glass' || selectedScheme === 'gradient') {
      // Double-check flags are set (backup)
      if (localStorage.getItem('customColorScheme') !== 'true' || localStorage.getItem('activeColorSchemeId') !== selectedScheme) {
        localStorage.setItem('customColorScheme', 'true');
        localStorage.setItem('activeColorSchemeId', selectedScheme);
        applyColorScheme(selectedScheme);
      }
    }
    // For standard themes (light, dark, auto), ensure flags are cleared
    else {
      localStorage.removeItem('customColorScheme');
      localStorage.removeItem('activeColorSchemeId');
    }
  }, [selectedScheme]);

  // React to external changes (Header menu, other tabs)
  useEffect(() => {
    const onExternalChange = (e) => {
      const schemeId = e?.detail || localStorage.getItem('colorScheme');
      if (schemeId && schemeId !== selectedScheme) {
        setSelectedScheme(schemeId);
      }
    };
    const onStorage = (e) => {
      if (e.key === 'colorScheme' || e.key === 'activeColorSchemeId' || e.key === 'customColorScheme') {
        onExternalChange();
      }
    };
    window.addEventListener('colorSchemeChanged', onExternalChange);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener('colorSchemeChanged', onExternalChange);
      window.removeEventListener('storage', onStorage);
    };
  }, [selectedScheme]);

  const currentScheme = colorSchemes.find(scheme => scheme.id === selectedScheme) || colorSchemes[0];

  return (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
        <Palette style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-accent-blue)' }} />
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-semibold)', 
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          Цветовые схемы
        </h3>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ 
          display: 'block', 
          fontSize: 'var(--mac-font-size-sm)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          marginBottom: '8px',
          color: 'var(--mac-text-primary)'
        }}>
          Выберите цветовую схему
        </label>
        <MacOSSelect
          value={selectedScheme}
          onChange={(e) => handleSchemeChange(e.target.value)}
          options={colorSchemes.map(scheme => ({
            value: scheme.id,
            label: scheme.name
          }))}
          placeholder="Выберите схему"
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <p style={{ 
          fontSize: 'var(--mac-font-size-sm)', 
          color: 'var(--mac-text-secondary)',
          margin: 0
        }}>
          {currentScheme.description}
        </p>
      </div>

      {/* Улучшенный предпросмотр цветовых схем */}
      <div style={{ marginBottom: '20px' }}>
        <h4 style={{ 
          fontSize: 'var(--mac-font-size-base)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          marginBottom: '12px',
          color: 'var(--mac-text-primary)'
        }}>
          Предварительный просмотр
        </h4>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '16px',
          marginTop: '20px'
        }}>
          {colorSchemes.map((scheme) => {
            const isActive = selectedScheme === scheme.id;

            return (
              <div
                key={scheme.id}
                data-preview-card
                onClick={() => handleSchemeChange(scheme.id)}
                style={{
                  cursor: 'pointer',
                  borderRadius: 'var(--mac-radius-lg)',
                  padding: '12px',
                  border: isActive
                    ? '2px solid var(--mac-accent-blue)'
                    : '1px solid var(--mac-border)',
                  background: scheme.colors.gradient
                    ? scheme.colors.gradient
                    : scheme.type === 'glass'
                    ? 'rgba(255, 255, 255, 0.15)'
                    : scheme.colors.primary,
                  color: scheme.colors.text,
                  boxShadow: isActive
                    ? '0 4px 16px rgba(0,0,0,0.25)'
                    : '0 2px 8px rgba(0,0,0,0.1)',
                  backdropFilter: scheme.type === 'glass' ? 'blur(12px) saturate(180%)' : 'none',
                  transition: 'all 0.25s ease-in-out'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                  {React.createElement(scheme.icon, {
                    style: {
                      width: '18px',
                      height: '18px',
                      marginRight: '8px',
                      color: scheme.type === 'vibrant' || scheme.type === 'gradient'
                        ? '#fff'
                        : 'var(--mac-text-secondary)'
                    }
                  })}
                  <span style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 600,
                    color: scheme.type === 'vibrant' || scheme.type === 'gradient'
                      ? '#fff'
                      : 'var(--mac-text-primary)'
                  }}>
                    {scheme.name}
                  </span>
                </div>
                <div style={{
                  display: 'flex',
                  gap: '6px',
                  alignItems: 'center',
                  flexWrap: 'wrap'
                }}>
                  <div style={{
                    width: '40px',
                    height: '20px',
                    borderRadius: '6px',
                    background: scheme.colors.primary,
                    border: '1px solid rgba(255,255,255,0.2)'
                  }} />
                  <div style={{
                    width: '40px',
                    height: '20px',
                    borderRadius: '6px',
                    background: scheme.colors.secondary,
                    border: '1px solid rgba(255,255,255,0.2)'
                  }} />
                  <div style={{
                    width: '40px',
                    height: '20px',
                    borderRadius: '6px',
                    background: scheme.colors.accent,
                    border: '1px solid rgba(255,255,255,0.2)'
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Дополнительные настройки */}
      <div style={{ marginBottom: '20px' }}>
        <h4 style={{ 
          fontSize: 'var(--mac-font-size-base)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          marginBottom: '12px',
          color: 'var(--mac-text-primary)'
        }}>
          Дополнительные настройки
        </h4>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <MacOSButton
            variant="outline"
            size="sm"
            onClick={() => setTheme('light')}
            disabled={theme === 'light'}
          >
            <Sun style={{ width: '16px', height: '16px', marginRight: '6px' }} />
            Светлая
          </MacOSButton>
          <MacOSButton
            variant="outline"
            size="sm"
            onClick={() => setTheme('dark')}
            disabled={theme === 'dark'}
          >
            <Moon style={{ width: '16px', height: '16px', marginRight: '6px' }} />
            Темная
          </MacOSButton>
        </div>
      </div>

      {/* Информация о текущей теме */}
      <div style={{ 
        padding: '12px', 
        backgroundColor: 'var(--mac-bg-tertiary)', 
        borderRadius: 'var(--mac-radius-md)',
        border: '1px solid var(--mac-border)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
          {React.createElement(currentScheme.icon, { 
            style: { width: '16px', height: '16px', marginRight: '8px', color: 'var(--mac-accent-blue)' } 
          })}
          <span style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)'
          }}>
            Текущая тема: {currentScheme.name}
          </span>
        </div>
        <p style={{ 
          fontSize: 'var(--mac-font-size-xs)', 
          color: 'var(--mac-text-secondary)',
          margin: 0
        }}>
          Изменения применяются мгновенно и сохраняются в настройках браузера.
        </p>
      </div>
    </MacOSCard>
  );
};

export default ColorSchemeSelector;
