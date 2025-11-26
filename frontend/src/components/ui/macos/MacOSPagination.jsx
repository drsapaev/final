import React from 'react';
import { ChevronLeft, ChevronRight, MoreHorizontal } from 'lucide-react';

const MacOSPagination = ({
  currentPage = 1,
  totalPages = 1,
  onPageChange,
  showFirstLast = true,
  showPrevNext = true,
  maxVisiblePages = 5,
  size = 'md',
  variant = 'default',
  className,
  style
}) => {
  const sizeStyles = {
    sm: {
      padding: '6px 12px',
      fontSize: 'var(--mac-font-size-xs)',
      height: '32px',
      gap: '4px'
    },
    md: {
      padding: '8px 16px',
      fontSize: 'var(--mac-font-size-sm)',
      height: '36px',
      gap: '6px'
    },
    lg: {
      padding: '12px 20px',
      fontSize: 'var(--mac-font-size-base)',
      height: '44px',
      gap: '8px'
    }
  };

  const variantStyles = {
    default: {
      border: '1px solid var(--mac-border)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)'
    },
    filled: {
      border: '1px solid transparent',
      background: 'var(--mac-bg-secondary)',
      color: 'var(--mac-text-primary)'
    },
    minimal: {
      border: 'none',
      background: 'transparent',
      color: 'var(--mac-text-primary)'
    }
  };

  const currentSize = sizeStyles[size];
  const currentVariant = variantStyles[variant];

  const containerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: currentSize.gap,
    ...style
  };

  const buttonStyle = (isActive = false, isDisabled = false) => ({
    padding: currentSize.padding,
    height: currentSize.height,
    fontSize: currentSize.fontSize,
    fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-medium)',
    borderRadius: 'var(--mac-radius-md)',
    border: currentVariant.border,
    background: isActive ? 'var(--mac-accent-blue)' : currentVariant.background,
    color: isActive ? 'white' : (isDisabled ? 'var(--mac-text-tertiary)' : currentVariant.color),
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    outline: 'none',
    minWidth: currentSize.height,
    opacity: isDisabled ? 0.6 : 1
  });

  const handlePageClick = (page) => {
    if (page >= 1 && page <= totalPages && page !== currentPage) {
      onPageChange(page);
    }
  };

  const handleKeyDown = (e, page) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handlePageClick(page);
    }
  };

  const handleMouseEnter = (e, isActive, isDisabled) => {
    if (!isActive && !isDisabled) {
      e.target.style.background = 'var(--mac-bg-secondary)';
      e.target.style.borderColor = 'var(--mac-border-hover)';
    }
  };

  const handleMouseLeave = (e, isActive) => {
    if (!isActive) {
      e.target.style.background = currentVariant.background;
      e.target.style.borderColor = currentVariant.border.split(' ')[2];
    }
  };

  const handleFocus = (e) => {
    e.target.style.outline = '2px solid var(--mac-accent-blue)';
    e.target.style.outlineOffset = '2px';
  };

  const handleBlur = (e) => {
    e.target.style.outline = 'none';
  };

  const getVisiblePages = () => {
    const pages = [];
    const halfVisible = Math.floor(maxVisiblePages / 2);
    
    let startPage = Math.max(1, currentPage - halfVisible);
    const endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage + 1 < maxVisiblePages) {
      startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }
    
    return pages;
  };

  const visiblePages = getVisiblePages();
  const showStartEllipsis = visiblePages[0] > 2;
  const showEndEllipsis = visiblePages[visiblePages.length - 1] < totalPages - 1;

  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className={className} style={containerStyle}>
      {showFirstLast && (
        <button
          onClick={() => handlePageClick(1)}
          onKeyDown={(e) => handleKeyDown(e, 1)}
          onMouseEnter={(e) => handleMouseEnter(e, false, currentPage === 1)}
          onMouseLeave={(e) => handleMouseLeave(e, false)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          style={buttonStyle(false, currentPage === 1)}
          disabled={currentPage === 1}
          aria-label="Первая страница"
        >
          1
        </button>
      )}

      {showStartEllipsis && (
        <span style={{ padding: '0 8px', color: 'var(--mac-text-tertiary)' }}>
          <MoreHorizontal size={16} />
        </span>
      )}

      {visiblePages.map((page) => (
        <button
          key={page}
          onClick={() => handlePageClick(page)}
          onKeyDown={(e) => handleKeyDown(e, page)}
          onMouseEnter={(e) => handleMouseEnter(e, page === currentPage, false)}
          onMouseLeave={(e) => handleMouseLeave(e, page === currentPage)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          style={buttonStyle(page === currentPage)}
          aria-label={`Страница ${page}`}
          aria-current={page === currentPage ? 'page' : undefined}
        >
          {page}
        </button>
      ))}

      {showEndEllipsis && (
        <span style={{ padding: '0 8px', color: 'var(--mac-text-tertiary)' }}>
          <MoreHorizontal size={16} />
        </span>
      )}

      {showFirstLast && totalPages > 1 && (
        <button
          onClick={() => handlePageClick(totalPages)}
          onKeyDown={(e) => handleKeyDown(e, totalPages)}
          onMouseEnter={(e) => handleMouseEnter(e, false, currentPage === totalPages)}
          onMouseLeave={(e) => handleMouseLeave(e, false)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          style={buttonStyle(false, currentPage === totalPages)}
          disabled={currentPage === totalPages}
          aria-label="Последняя страница"
        >
          {totalPages}
        </button>
      )}
    </div>
  );
};

export default MacOSPagination;
