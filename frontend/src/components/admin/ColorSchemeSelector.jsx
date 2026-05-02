import PropTypes from 'prop-types';
import { useMemo } from 'react';
import { Layers, Monitor, Moon, Palette, Rainbow, Sparkles, Sun, SwatchBook } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { useMacOSTheme } from '../../theme/macosTheme.jsx';
import { COLOR_SCHEMES } from '../../theme/colorScheme.js';
import { MacOSCard, MacOSSelect } from '../ui/macos';

const ICONS = {
  light: Sun,
  dark: Moon,
  auto: Monitor,
  vibrant: Rainbow,
  glass: Layers,
  gradient: Sparkles,
};

const METRICS = [
  { key: 'mood', label: 'Характер' },
  { key: 'surfaces', label: 'Поверхности' },
  { key: 'contrast', label: 'Контраст' },
  { key: 'bestFor', label: 'Лучше всего для' },
];

const ACCENT_LABELS = {
  blue: 'Blue',
  purple: 'Purple',
  pink: 'Pink',
  red: 'Red',
  orange: 'Orange',
  yellow: 'Yellow',
  green: 'Green',
  graphite: 'Graphite',
};

function ThemePreviewCard({ scheme, isActive, onSelect }) {
  const Icon = ICONS[scheme.id] || Sun;
  const preview = scheme.preview;

  return (
    <button
      type="button"
      data-preview-card="true"
      onClick={() => onSelect(scheme.id)}
      aria-pressed={isActive}
      style={{
        cursor: 'pointer',
        borderRadius: '18px',
        padding: '16px',
        border: isActive ? '2px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)',
        background: preview.background,
        color: preview.text,
        boxShadow: isActive ? '0 10px 28px rgba(15, 23, 42, 0.26)' : '0 8px 20px rgba(15, 23, 42, 0.12)',
        textAlign: 'left',
        display: 'grid',
        gap: '14px',
        minHeight: '196px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
        <div style={{ display: 'grid', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Icon style={{ width: '18px', height: '18px' }} />
            <span style={{ fontSize: '15px', fontWeight: 700 }}>
              {scheme.name}
            </span>
          </div>
          <span style={{ fontSize: '12px', opacity: 0.84 }}>
            {scheme.mood} атмосфера
          </span>
        </div>
        {isActive ?
          <span style={{ fontSize: '12px', padding: '4px 8px', borderRadius: '999px', background: 'rgba(255,255,255,0.18)' }}>
            Активна
          </span> :
          null}
      </div>

      <div style={{
        borderRadius: '14px',
        border: `1px solid ${preview.border}`,
        background: preview.surface,
        padding: '12px',
        display: 'grid',
        gap: '10px',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '56px 1fr', gap: '10px', alignItems: 'stretch' }}>
          <div style={{
            borderRadius: '10px',
            background: preview.surfaceAlt,
            border: `1px solid ${preview.border}`,
          }} />
          <div style={{ display: 'grid', gap: '8px' }}>
            <div style={{
              height: '12px',
              width: '72%',
              borderRadius: '999px',
              background: preview.text,
              opacity: 0.22,
            }} />
            <div style={{
              height: '10px',
              width: '48%',
              borderRadius: '999px',
              background: preview.text,
              opacity: 0.12,
            }} />
            <div style={{
              height: '24px',
              width: '42%',
              borderRadius: '10px',
              background: preview.accent,
            }} />
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        <span style={{
          fontSize: '11px',
          padding: '4px 8px',
          borderRadius: '999px',
          background: 'rgba(255,255,255,0.14)',
          border: `1px solid ${preview.border}`,
        }}>
          {scheme.surfaces}
        </span>
        <span style={{
          fontSize: '11px',
          padding: '4px 8px',
          borderRadius: '999px',
          background: 'rgba(255,255,255,0.14)',
          border: `1px solid ${preview.border}`,
        }}>
          {scheme.contrast}
        </span>
      </div>
    </button>
  );
}

ThemePreviewCard.propTypes = {
  scheme: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    mood: PropTypes.string.isRequired,
    surfaces: PropTypes.string.isRequired,
    contrast: PropTypes.string.isRequired,
    preview: PropTypes.shape({
      background: PropTypes.string.isRequired,
      surface: PropTypes.string.isRequired,
      surfaceAlt: PropTypes.string.isRequired,
      accent: PropTypes.string.isRequired,
      text: PropTypes.string.isRequired,
      border: PropTypes.string.isRequired,
    }).isRequired,
  }).isRequired,
  isActive: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
};

export default function ColorSchemeSelector() {
  const { colorScheme, setColorScheme } = useTheme();
  const { accent } = useMacOSTheme();

  const colorSchemes = useMemo(() =>
    COLOR_SCHEMES.map((scheme) => ({
      ...scheme,
      icon: ICONS[scheme.id] || Sun,
    })), []);

  const currentScheme = colorSchemes.find((scheme) => scheme.id === colorScheme) || colorSchemes[0];
  const currentAccentLabel = ACCENT_LABELS[accent] || accent;
  const ActiveIcon = currentScheme.icon;

  return (
    <MacOSCard style={{ padding: '24px', display: 'grid', gap: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Palette style={{ width: '20px', height: '20px', color: 'var(--mac-accent-blue)' }} />
          <div style={{ display: 'grid', gap: '4px' }}>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0,
            }}>
              Цветовая схема интерфейса
            </h3>
            <p style={{
              margin: 0,
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)',
            }}>
              Тема управляет фоном, карточками, header и sidebar. Accent отдельно задаёт цвет интерактивных элементов.
            </p>
          </div>
        </div>

        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 12px',
          borderRadius: '14px',
          background: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          color: 'var(--mac-text-secondary)',
          fontSize: '12px',
        }}>
          <SwatchBook style={{ width: '14px', height: '14px', color: 'var(--mac-accent-blue)' }} />
          Accent сейчас: <strong style={{ color: 'var(--mac-text-primary)' }}>{currentAccentLabel}</strong>
        </div>
      </div>

      <div style={{
        padding: '14px 16px',
        borderRadius: '16px',
        background: 'linear-gradient(135deg, var(--mac-bg-primary), var(--mac-bg-secondary))',
        border: '1px solid var(--mac-border)',
        display: 'grid',
        gap: '8px',
      }}>
        <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--mac-text-primary)' }}>
          Что именно меняет настройка
        </div>
        <div style={{ display: 'grid', gap: '6px', fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
          <div>Цветовая схема сохраняется в профиле пользователя и подтягивается после входа.</div>
          <div>Accent color хранится локально в браузере и перекрашивает primary buttons, focus states и status chips.</div>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '10px' }}>
        <label style={{
          display: 'block',
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)',
        }}>
          Быстрый выбор схемы
        </label>
        <MacOSSelect
          value={colorScheme}
          onChange={(event) => setColorScheme(event.target.value)}
          options={colorSchemes.map((scheme) => ({
            value: scheme.id,
            label: scheme.name,
          }))}
          placeholder="Выберите схему"
        />
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '16px',
      }}>
        {colorSchemes.map((scheme) => (
          <ThemePreviewCard
            key={scheme.id}
            scheme={scheme}
            isActive={scheme.id === colorScheme}
            onSelect={setColorScheme}
          />
        ))}
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(240px, 1.15fr) minmax(260px, 1fr)',
        gap: '18px',
      }}>
        <div style={{
          padding: '18px',
          borderRadius: '18px',
          border: '1px solid var(--mac-border)',
          background: currentScheme.preview.background,
          color: currentScheme.preview.text,
          display: 'grid',
          gap: '16px',
          minHeight: '220px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <ActiveIcon style={{ width: '18px', height: '18px' }} />
              <div style={{ display: 'grid', gap: '2px' }}>
                <strong>{currentScheme.name}</strong>
                <span style={{ fontSize: '12px', opacity: 0.84 }}>{currentScheme.description}</span>
              </div>
            </div>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: '72px 1fr',
            gap: '14px',
            flex: 1,
          }}>
            <div style={{
              borderRadius: '14px',
              background: currentScheme.preview.surfaceAlt,
              border: `1px solid ${currentScheme.preview.border}`,
              display: 'grid',
              gap: '8px',
              padding: '10px',
            }}>
              <div style={{ height: '10px', borderRadius: '999px', background: 'rgba(255,255,255,0.16)' }} />
              <div style={{ height: '10px', borderRadius: '999px', background: 'rgba(255,255,255,0.08)' }} />
              <div style={{ marginTop: 'auto', height: '28px', borderRadius: '10px', background: currentScheme.preview.accent }} />
            </div>

            <div style={{
              borderRadius: '16px',
              border: `1px solid ${currentScheme.preview.border}`,
              background: currentScheme.preview.surface,
              padding: '14px',
              display: 'grid',
              gap: '12px',
              backdropFilter: 'blur(14px)',
              WebkitBackdropFilter: 'blur(14px)',
            }}>
              <div style={{
                height: '36px',
                borderRadius: '12px',
                border: `1px solid ${currentScheme.preview.border}`,
                background: 'rgba(255,255,255,0.08)',
              }} />
              <div style={{ display: 'grid', gap: '8px' }}>
                <div style={{ height: '12px', width: '76%', borderRadius: '999px', background: currentScheme.preview.text, opacity: 0.22 }} />
                <div style={{ height: '10px', width: '58%', borderRadius: '999px', background: currentScheme.preview.text, opacity: 0.12 }} />
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <div style={{
                  flex: 1,
                  height: '36px',
                  borderRadius: '12px',
                  background: 'var(--mac-accent-blue)',
                }} />
                <div style={{
                  width: '38%',
                  height: '36px',
                  borderRadius: '12px',
                  border: `1px solid ${currentScheme.preview.border}`,
                  background: 'rgba(255,255,255,0.08)',
                }} />
              </div>
            </div>
          </div>
        </div>

        <div style={{
          padding: '18px',
          borderRadius: '18px',
          border: '1px solid var(--mac-border)',
          background: 'linear-gradient(180deg, var(--mac-bg-primary), var(--mac-bg-secondary))',
          display: 'grid',
          gap: '14px',
          alignContent: 'start',
        }}>
          <div style={{ display: 'grid', gap: '6px' }}>
            <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Активная схема
            </div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--mac-text-primary)' }}>
              {currentScheme.name}
            </div>
          </div>

          <div style={{ display: 'grid', gap: '10px' }}>
            {METRICS.map((metric) => (
              <div
                key={metric.key}
                style={{
                  display: 'grid',
                  gap: '6px',
                  padding: '12px 14px',
                  borderRadius: '14px',
                  background: 'var(--mac-bg-tertiary)',
                  border: '1px solid var(--mac-border)',
                }}
              >
                <span style={{ fontSize: '11px', color: 'var(--mac-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  {metric.label}
                </span>
                <span style={{ fontSize: '14px', color: 'var(--mac-text-primary)', fontWeight: 600 }}>
                  {currentScheme[metric.key]}
                </span>
              </div>
            ))}
          </div>

          <div style={{
            padding: '12px 14px',
            borderRadius: '14px',
            background: 'var(--mac-accent-bg)',
            border: '1px solid var(--mac-accent-border)',
            color: 'var(--mac-text-primary)',
            fontSize: '12px',
            lineHeight: 1.5,
          }}>
            Для полной смены характера интерфейса сначала выберите цветовую схему, затем при необходимости подстройте Accent ниже.
          </div>
        </div>
      </div>
    </MacOSCard>
  );
}
