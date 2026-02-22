import PropTypes from 'prop-types';

const MacOSList = ({
  items = [],
  renderItem,
  loading = false,
  emptyState,
  size = 'md',
  variant = 'default',
  dividers = true,
  hoverable = true,
  selectable = false,
  selectedIndex = -1,
  onItemClick,
  onItemSelect,
  className,
  style
}) => {
  const sizeStyles = {
    sm: {
      padding: '8px 0',
      itemPadding: '8px 12px',
      fontSize: 'var(--mac-font-size-xs)',
      gap: '2px'
    },
    md: {
      padding: '12px 0',
      itemPadding: '12px 16px',
      fontSize: 'var(--mac-font-size-sm)',
      gap: '4px'
    },
    lg: {
      padding: '16px 0',
      itemPadding: '16px 20px',
      fontSize: 'var(--mac-font-size-base)',
      gap: '6px'
    }
  };

  const variantStyles = {
    default: {
      background: 'var(--mac-bg-primary)',
      border: '1px solid var(--mac-border)',
      borderRadius: 'var(--mac-radius-md)'
    },
    filled: {
      background: 'var(--mac-bg-secondary)',
      border: 'none',
      borderRadius: 'var(--mac-radius-md)'
    },
    minimal: {
      background: 'transparent',
      border: 'none',
      borderRadius: '0'
    }
  };

  const currentSize = sizeStyles[size];
  const currentVariant = variantStyles[variant];

  const listStyle = {
    padding: currentSize.padding,
    background: currentVariant.background,
    border: currentVariant.border,
    borderRadius: currentVariant.borderRadius,
    ...style
  };

  const itemStyle = (index, isSelected = false) => ({
    padding: currentSize.itemPadding,
    fontSize: currentSize.fontSize,
    color: 'var(--mac-text-primary)',
    cursor: hoverable || selectable ? 'pointer' : 'default',
    background: isSelected ? 'var(--mac-bg-blue)' : 'transparent',
    borderBottom: dividers && index < items.length - 1 ? '1px solid var(--mac-separator)' : 'none',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between'
  });

  const handleItemClick = (item, index) => {
    if (onItemClick) {
      onItemClick(item, index);
    }
    if (selectable && onItemSelect) {
      onItemSelect(index);
    }
  };

  const handleMouseEnter = (e, isSelected) => {
    if (hoverable) {
      e.currentTarget.style.backgroundColor = isSelected ? 'var(--mac-bg-blue)' : 'var(--mac-bg-secondary)';
    }
  };

  const handleMouseLeave = (e, isSelected) => {
    if (hoverable) {
      e.currentTarget.style.backgroundColor = isSelected ? 'var(--mac-bg-blue)' : 'transparent';
    }
  };

  const handleKeyDown = (e, item, index) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleItemClick(item, index);
    }
  };

  const renderDefaultItem = (item) => {
    if (typeof item === 'string') {
      return <span>{item}</span>;
    }

    if (typeof item === 'object' && item.label) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {item.icon && <item.icon size={16} style={{ color: 'var(--mac-text-tertiary)' }} />}
          <span>{item.label}</span>
          {item.badge &&
          <span style={{
            padding: '2px 6px',
            borderRadius: 'var(--mac-radius-sm)',
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)',
            background: 'var(--mac-accent-blue)',
            color: 'white'
          }}>
              {item.badge}
            </span>
          }
        </div>);

    }

    return <span>{JSON.stringify(item)}</span>;
  };

  const renderEmptyState = () => {
    if (emptyState) {
      return emptyState;
    }

    return (
      <div style={{
        padding: '48px 16px',
        textAlign: 'center',
        color: 'var(--mac-text-secondary)',
        fontSize: 'var(--mac-font-size-base)'
      }}>
        Нет элементов для отображения
      </div>);

  };

  const renderLoadingState = () => {
    return (
      <div style={{
        padding: '48px 16px',
        textAlign: 'center',
        color: 'var(--mac-text-secondary)',
        fontSize: 'var(--mac-font-size-base)'
      }}>
        Загрузка...
      </div>);

  };

  if (loading) {
    return (
      <div className={className} style={listStyle}>
        {renderLoadingState()}
      </div>);

  }

  if (!items || items.length === 0) {
    return (
      <div className={className} style={listStyle}>
        {renderEmptyState()}
      </div>);

  }

  return (
    <div className={className} style={listStyle}>
      {items.map((item, index) => {
        const isSelected = selectedIndex === index;
        const isInteractive = selectable || Boolean(onItemClick);

        if (isInteractive) {
          return (
            <div
              key={index}
              style={itemStyle(index, isSelected)}
              onClick={() => handleItemClick(item, index)}
              onPointerEnter={(e) => handleMouseEnter(e, isSelected)}
              onPointerLeave={(e) => handleMouseLeave(e, isSelected)}
              onKeyDown={(e) => handleKeyDown(e, item, index)}
              tabIndex={0}
              role="button"
              aria-selected={selectable ? isSelected : undefined}>
              
              {renderItem ? renderItem(item, index) : renderDefaultItem(item, index)}
            </div>);
        }

        return (
          <div
            key={index}
            style={itemStyle(index, isSelected)}
            onPointerEnter={(e) => handleMouseEnter(e, isSelected)}
            onPointerLeave={(e) => handleMouseLeave(e, isSelected)}
            role="listitem">
            
            {renderItem ? renderItem(item, index) : renderDefaultItem(item, index)}
          </div>);

      })}
    </div>);

};

MacOSList.propTypes = {
  items: PropTypes.arrayOf(
    PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.shape({
        label: PropTypes.node,
        icon: PropTypes.elementType,
        badge: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
      }),
      PropTypes.object
    ])
  ),
  renderItem: PropTypes.func,
  loading: PropTypes.bool,
  emptyState: PropTypes.node,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  variant: PropTypes.oneOf(['default', 'filled', 'minimal']),
  dividers: PropTypes.bool,
  hoverable: PropTypes.bool,
  selectable: PropTypes.bool,
  selectedIndex: PropTypes.number,
  onItemClick: PropTypes.func,
  onItemSelect: PropTypes.func,
  className: PropTypes.string,
  style: PropTypes.object
};

export default MacOSList;
