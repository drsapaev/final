import PropTypes from 'prop-types';

// SW-01 fix: removed dependency on design-system/getColor.
// Replaced with CSS variables that work with macOS theme system.
const COLORS = {
  primary: 'var(--mac-accent-blue, #007aff)',
  secondary: 'var(--mac-text-secondary, #6b7280)',
  success: 'var(--mac-success, #34c759)',
  danger: 'var(--mac-error, #ff3b30)',
  warning: 'var(--mac-warning, #ff9500)',
  info: 'var(--mac-info, #5ac8fa)',
};

const SKELETON_BG = 'var(--mac-bg-secondary, rgba(0,0,0,0.05))';

const AnimatedLoader = ({
  size = 'md',
  color = 'primary',
  className = '',
  style = {}
}) => {
  const getSizeStyles = () => {
    const sizes = {
      sm: { width: '16px', height: '16px', borderWidth: '2px' },
      md: { width: '24px', height: '24px', borderWidth: '3px' },
      lg: { width: '32px', height: '32px', borderWidth: '4px' }
    };
    return sizes[size] || sizes.md;
  };

  const getColorStyles = () => {
    return COLORS[color] || COLORS.primary;
  };

  const loaderStyles = {
    display: 'inline-block',
    border: `${getSizeStyles().borderWidth} solid transparent`,
    borderTop: `${getSizeStyles().borderWidth} solid ${getColorStyles()}`,
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
    ...getSizeStyles(),
    ...style
  };

  return (
    <div
      className={`animated-loader ${className}`}
      style={loaderStyles}
      role="status"
      aria-label="Загрузка" />);
};


AnimatedLoader.propTypes = {
  ...(AnimatedLoader.propTypes || {}),
  className: PropTypes.any,
  color: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
};

const AnimatedTableSkeleton = ({
  rows = 5,
  columns = 4,
  className = '',
  style = {}
}) => {
  const tableStyles = {
    background: 'var(--mac-bg-primary, white)',
    borderRadius: 'var(--mac-radius-lg)',
    padding: 'var(--mac-spacing-5)',
    boxShadow: 'var(--mac-shadow-md)',
    ...style
  };

  const skeletonRowStyles = {
    display: 'flex',
    gap: 'var(--mac-spacing-4)',
    marginBottom: 'var(--mac-spacing-3)',
    alignItems: 'center'
  };

  const skeletonCellStyles = {
    backgroundColor: SKELETON_BG,
    borderRadius: 'var(--mac-radius-md)',
    animation: 'skeleton-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
    height: '20px'
  };

  return (
    <div
      className={`animated-table-skeleton ${className}`}
      style={tableStyles}>
      <div style={skeletonRowStyles}>
        {Array.from({ length: columns }, (_, i) =>
        <div
          key={i}
          style={{
            ...skeletonCellStyles,
            width: i === 0 ? '60px' : '120px',
            height: '16px'
          }} />
        )}
      </div>
      {Array.from({ length: rows }, (_, rowIndex) =>
      <div key={rowIndex} style={skeletonRowStyles}>
          {Array.from({ length: columns }, (_, colIndex) =>
        <div
          key={colIndex}
          style={{
            ...skeletonCellStyles,
            width: colIndex === 0 ? '60px' : '120px'
          }} />
        )}
        </div>
      )}
    </div>);
};


AnimatedTableSkeleton.propTypes = {
  ...(AnimatedTableSkeleton.propTypes || {}),
  className: PropTypes.any,
  columns: PropTypes.any,
  rows: PropTypes.any,
  style: PropTypes.any,
};

const AnimatedCardSkeleton = ({
  className = '',
  style = {}
}) => {
  const cardStyles = {
    background: 'var(--mac-bg-primary, white)',
    borderRadius: 'var(--mac-radius-lg)',
    padding: 'var(--mac-spacing-5)',
    boxShadow: 'var(--mac-shadow-md)',
    ...style
  };

  const skeletonStyles = {
    backgroundColor: SKELETON_BG,
    borderRadius: 'var(--mac-radius-md)',
    animation: 'skeleton-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
  };

  return (
    <div
      className={`animated-card-skeleton ${className}`}
      style={cardStyles}>
      <div
        style={{
          ...skeletonStyles,
          width: '60%',
          height: '24px',
          marginBottom: 'var(--mac-spacing-4)'
        }} />
      <div
        style={{
          ...skeletonStyles,
          width: '100%',
          height: '16px',
          marginBottom: 'var(--mac-spacing-2)'
        }} />
      <div
        style={{
          ...skeletonStyles,
          width: '80%',
          height: '16px',
          marginBottom: 'var(--mac-spacing-2)'
        }} />
      <div
        style={{
          ...skeletonStyles,
          width: '60%',
          height: '16px',
          marginBottom: 'var(--mac-spacing-4)'
        }} />
      <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)' }}>
        <div
          style={{
            ...skeletonStyles,
            width: '80px',
            height: '32px'
          }} />
        <div
          style={{
            ...skeletonStyles,
            width: '100px',
            height: '32px'
          }} />
      </div>
    </div>);
};


AnimatedCardSkeleton.propTypes = {
  ...(AnimatedCardSkeleton.propTypes || {}),
  className: PropTypes.any,
  style: PropTypes.any,
};

AnimatedLoader.TableSkeleton = AnimatedTableSkeleton;
AnimatedLoader.CardSkeleton = AnimatedCardSkeleton;

export default AnimatedLoader;
