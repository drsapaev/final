import React from 'react';

function getInitials(name) {
  if (!name) return '';
  const parts = String(name).trim().split(/\s+/);
  const first = parts[0]?.[0] || '';
  const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
  return (first + last).toUpperCase();
}

export const Avatar = ({ src, name, size = 'medium', status, style = {}, className = '' }) => {
  const sizePx = size === 'small' ? 24 : size === 'large' ? 40 : 32;

  const containerStyle = {
    position: 'relative',
    width: `${sizePx}px`,
    height: `${sizePx}px`,
    borderRadius: '50%',
    overflow: 'hidden',
    backgroundColor: 'var(--mac-bg-tertiary)'
  };

  const imgStyle = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    display: src ? 'block' : 'none'
  };

  const fallbackStyle = {
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: size === 'small' ? '10px' : '12px',
    fontWeight: 600,
    color: 'var(--mac-text-secondary)'
  };

  const statusColor = status === 'online' ? '#34c759' : status === 'busy' ? '#ff3b30' : status === 'away' ? '#ffcc00' : null;

  return (
    <div className={`mac-avatar ${className}`} style={{ ...containerStyle, ...style }} title={name}>
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

export default Avatar;


