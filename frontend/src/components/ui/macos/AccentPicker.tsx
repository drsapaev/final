import { ACCENT_OPTIONS, useMacOSTheme, type AccentName } from '../../../theme/macosTheme.jsx';
import PropTypes from 'prop-types';
import type { CSSProperties } from 'react';

type AccentKey = typeof ACCENT_OPTIONS[number];

const LABELS: Record<string, string> = {
  blue: 'Blue',
  purple: 'Purple',
  pink: 'Pink',
  red: 'Red',
  orange: 'Orange',
  yellow: 'Yellow',
  green: 'Green',
  graphite: 'Graphite'
};

interface AccentPickerProps {
  size?: number;
  className?: string;
  style?: CSSProperties;
}

export default function AccentPicker({ size = 22, className = '', style = {} }: AccentPickerProps) {
  const { accent, setAccent } = useMacOSTheme();

  return (
    <div
      role="radiogroup"
      aria-label="Accent color"
      className={className}
      style={{ display: 'flex', gap: '8px', alignItems: 'center', ...style }}
    >
      {ACCENT_OPTIONS.map((key) => {
        const isActive = accent === key;
        const colorVar = `var(--accent-${key})`;
        return (
          <button
            key={key}
            role="radio"
            aria-checked={isActive}
            aria-label={LABELS[key] || key}
            onClick={() => setAccent(key as AccentName)}
            title={LABELS[key] || key}
            style={{
              width: `${size}px`,
              height: `${size}px`,
              borderRadius: '50% ',
              background: `radial-gradient(120% 120% at 30% 30%, ${colorVar}, color-mix(in oklab, ${colorVar}, black 12%))`,
              border: isActive ? '2px solid white' : '1px solid rgba(0,0,0,0.15)',
              boxShadow: isActive ? '0 0 0 2px color-mix(in oklab, var(--accent), white 35%)' : '0 1px 4px rgba(0,0,0,0.12)',
              cursor: 'pointer',
              outline: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setAccent(key as AccentName);
              }
            }}
          />
        );
      })}
    </div>
  );
}


AccentPicker.propTypes = {
  ...(AccentPicker.propTypes || {}),
  className: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
};

// Silence unused-import warning in environments that strip type-only imports.
export type { AccentKey };
