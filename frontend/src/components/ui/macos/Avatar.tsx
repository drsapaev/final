import PropTypes from 'prop-types';
import type { CSSProperties } from 'react';

type AvatarSize = 'small' | 'medium' | 'large';
type AvatarStatus = 'online' | 'busy' | 'away';

interface AvatarProps {
  src?: string | null;
  name?: string | null;
  size?: AvatarSize;
  status?: AvatarStatus | null;
  style?: CSSProperties;
  className?: string;
}

function getInitials(name: string | null | undefined): string {
  if (!name) return '';
  const parts = String(name).trim().split(/\s+/);
  const first = parts[0]?.[0] || '';
  const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
  return (first + last).toUpperCase();
}

export const Avatar = ({ src, name, size = 'medium', status, style = {}, className = '' }: AvatarProps) => {
  const sizePx = size === 'small' ? 24 : size === 'large' ? 40 : 32;

  const containerStyle: CSSProperties = {
    position: 'relative',
    width: `${sizePx}px`,
    height: `${sizePx}px`,
    borderRadius: '50%',
    overflow: 'hidden',
    backgroundColor: 'var(--mac-bg-tertiary)'
  };

  const imgStyle: CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    display: src ? 'block' : 'none'
  };

  const fallbackStyle: CSSProperties = {
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: size === 'small' ? '10px' : '12px',
    fontWeight: 600,
    color: 'var(--mac-text-secondary)'
  };

  const statusColor: string | null = status === 'online' ? 'var(--mac-success)' : status === 'busy' ? 'var(--mac-error)' : status === 'away' ? 'var(--mac-warning)' : null;

  return (
    <div className={`mac-avatar ${className}`} style={{ ...containerStyle, ...style }} title={name ?? undefined}>
      <img src={src} alt={name || 'User'} style={imgStyle} />
      {!src && (
        <div style={fallbackStyle} aria-hidden>{getInitials(name)}</div>
      )}
      {statusColor && (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            right: 0,
            bottom: 0,
            width: Math.max(6, Math.round(sizePx * 0.28)),
            height: Math.max(6, Math.round(sizePx * 0.28)),
            borderRadius: '50%',
            backgroundColor: statusColor,
            border: '2px solid var(--mac-bg-toolbar)'
          }}
        />
      )}
    </div>
  );
};


Avatar.propTypes = {
  ...(Avatar.propTypes || {}),
  className: PropTypes.any,
  name: PropTypes.any,
  size: PropTypes.any,
  src: PropTypes.any,
  status: PropTypes.any,
  style: PropTypes.any,
};

export default Avatar;
