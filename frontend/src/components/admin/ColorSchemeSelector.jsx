import React, { useState } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { MacOSButton, MacOSCard, MacOSSelect } from '../ui/macos';
import { Palette, Sun, Moon, Monitor } from 'lucide-react';

const ColorSchemeSelector = () => {
  const { theme, setTheme, isDark, isLight } = useTheme();
  const [selectedScheme, setSelectedScheme] = useState(theme);

  const colorSchemes = [
    {
      id: 'light',
      name: 'Светлая тема',
      description: 'Классическая светлая тема macOS',
      icon: Sun,
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
      colors: {
        primary: 'var(--mac-bg-primary)',
        secondary: 'var(--mac-bg-secondary)',
        accent: 'var(--mac-accent-blue)',
        text: 'var(--mac-text-primary)'
      }
    }
  ];

  const handleSchemeChange = (schemeId) => {
    setSelectedScheme(schemeId);
    if (schemeId === 'auto') {
      // Определяем системную тему
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      setTheme(prefersDark ? 'dark' : 'light');
    } else {
      setTheme(schemeId);
    }
  };

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

      {/* Предварительный просмотр цветов */}
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
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', 
          gap: '12px' 
        }}>
          {colorSchemes.map((scheme) => (
            <div
              key={scheme.id}
              style={{
                padding: '12px',
                borderRadius: 'var(--mac-radius-md)',
                border: selectedScheme === scheme.id ? '2px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}
              onClick={() => handleSchemeChange(scheme.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                {React.createElement(scheme.icon, { 
                  style: { width: '16px', height: '16px', marginRight: '6px', color: 'var(--mac-text-secondary)' } 
                })}
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)'
                }}>
                  {scheme.name}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '4px' }}>
                <div style={{ 
                  width: '20px', 
                  height: '20px', 
                  borderRadius: 'var(--mac-radius-sm)',
                  backgroundColor: scheme.colors.primary,
                  border: '1px solid var(--mac-border)'
                }} />
                <div style={{ 
                  width: '20px', 
                  height: '20px', 
                  borderRadius: 'var(--mac-radius-sm)',
                  backgroundColor: scheme.colors.secondary,
                  border: '1px solid var(--mac-border)'
                }} />
                <div style={{ 
                  width: '20px', 
                  height: '20px', 
                  borderRadius: 'var(--mac-radius-sm)',
                  backgroundColor: scheme.colors.accent,
                  border: '1px solid var(--mac-border)'
                }} />
              </div>
            </div>
          ))}
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
