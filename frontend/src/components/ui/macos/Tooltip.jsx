import React, { useState, useRef, useEffect } from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Tooltip Component
 * Implements Apple's Human Interface Guidelines for tooltips
 */
const Tooltip = ({
  children,
  content,
  position = 'top',
  delay = 700,
  disabled = false,
  className = '',
  style = {},
  ...props
}) => {
  const { theme } = useTheme();
  const [isVisible, setIsVisible] = useState(false);
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);
  const timeoutRef = useRef(null);

  // Position calculations
  const positionMap = {
    top: { x: 'center', y: 'bottom' },
    bottom: { x: 'center', y: 'top' },
    left: { x: 'right', y: 'center' },
    right: { x: 'left', y: 'center' },
    'top-left': { x: 'left', y: 'bottom' },
    'top-right': { x: 'right', y: 'bottom' },
    'bottom-left': { x: 'left', y: 'top' },
    'bottom-right': { x: 'right', y: 'top' }
  };

  const handleMouseEnter = () => {
    if (disabled) return;

    timeoutRef.current = setTimeout(() => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (rect) {
        setCoords({
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2
        });
        setIsVisible(true);
      }
    }, delay);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const tooltipPosition = positionMap[position] || positionMap.top;

  const tooltipStyles = {
    position: 'fixed',
    top: 0,
    left: 0,
    zIndex: 1300,
    pointerEvents: 'none',
    opacity: isVisible ? 1 : 0,
    transform: isVisible ? 'scale(1)' : 'scale(0.95)',
    transition: 'opacity 0.2s cubic-bezier(0.2, 0.8, 0.2, 1), transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
    transformOrigin: `${tooltipPosition.x === 'center' ? 'center' : tooltipPosition.x === 'left' ? 'right' : 'left'} ${tooltipPosition.y === 'center' ? 'center' : tooltipPosition.y === 'top' ? 'bottom' : 'top'}`
  };

  const contentStyles = {
    backgroundColor: 'var(--mac-bg-tertiary)',
    color: 'var(--mac-text-primary)',
    border: '1px solid var(--mac-border)',
    borderRadius: '6px',
    padding: '6px 8px',
    fontSize: '11px',
    fontWeight: '400',
    lineHeight: '1.3',
    maxWidth: '200px',
    wordWrap: 'break-word',
    whiteSpace: 'normal',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)'
  };

  // Position the tooltip
  const getPositionedStyles = () => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return {};

    const tooltipRect = tooltipRef.current?.getBoundingClientRect();
    if (!tooltipRect && isVisible) return {};

    let top = 0;
    let left = 0;

    switch (tooltipPosition.x) {
      case 'left':
        left = coords.x - (tooltipRect?.width || 100) - 8;
        break;
      case 'right':
        left = coords.x + 8;
        break;
      default: // center
        left = coords.x - (tooltipRect?.width || 100) / 2;
        break;
    }

    switch (tooltipPosition.y) {
      case 'top':
        top = coords.y - (tooltipRect?.height || 30) - 8;
        break;
      case 'bottom':
        top = coords.y + 8;
        break;
      default: // center
        top = coords.y - (tooltipRect?.height || 30) / 2;
        break;
    }

    // Ensure tooltip stays within viewport
    const viewport = {
      top: 8,
      left: 8,
      right: window.innerWidth - 8,
      bottom: window.innerHeight - 8
    };

    if (left < viewport.left) left = viewport.left;
    if (left + (tooltipRect?.width || 100) > viewport.right) {
      left = viewport.right - (tooltipRect?.width || 100);
    }
    if (top < viewport.top) top = viewport.top;
    if (top + (tooltipRect?.height || 30) > viewport.bottom) {
      top = viewport.bottom - (tooltipRect?.height || 30);
    }

    return { top: `${top}px`, left: `${left}px` };
  };

  if (!content) return children;

  return (
    <>
      <div
        ref={triggerRef}
        className={`mac-tooltip-trigger ${className}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{ display: 'inline-block', ...style }}
        {...props}
      >
        {children}
      </div>

      {isVisible && (
        <div
          ref={tooltipRef}
          className="mac-tooltip"
          style={{
            ...tooltipStyles,
            ...getPositionedStyles()
          }}
          role="tooltip"
        >
          <div className="mac-tooltip-content" style={contentStyles}>
            {content}
          </div>

          {/* Tooltip arrow */}
          <div
            className="mac-tooltip-arrow"
            style={{
              position: 'absolute',
              width: '8px',
              height: '8px',
              backgroundColor: 'var(--mac-bg-tertiary)',
              border: '1px solid var(--mac-border)',
              transform: 'rotate(45deg)',
              zIndex: -1,
              ...(tooltipPosition.x === 'left' && tooltipPosition.y === 'center' && {
                right: '-5px',
                top: '50%',
                transform: 'translateY(-50%) rotate(45deg)'
              }),
              ...(tooltipPosition.x === 'right' && tooltipPosition.y === 'center' && {
                left: '-5px',
                top: '50%',
                transform: 'translateY(-50%) rotate(45deg)'
              }),
              ...(tooltipPosition.x === 'center' && tooltipPosition.y === 'top' && {
                bottom: '-5px',
                left: '50%',
                transform: 'translateX(-50%) rotate(45deg)'
              }),
              ...(tooltipPosition.x === 'center' && tooltipPosition.y === 'bottom' && {
                top: '-5px',
                left: '50%',
                transform: 'translateX(-50%) rotate(45deg)'
              })
            }}
          />

          <style>{`
            /* Dark mode adjustments */
            @media (prefers-color-scheme: dark) {
              .mac-tooltip-content {
                background-color: rgba(255, 255, 255, 0.05) !important;
                border-color: rgba(255, 255, 255, 0.1) !important;
                color: #f5f5f7 !important;
              }

              .mac-tooltip-arrow {
                background-color: rgba(255, 255, 255, 0.05) !important;
                border-color: rgba(255, 255, 255, 0.1) !important;
              }
            }

            /* High contrast mode */
            @media (prefers-contrast: high) {
              .mac-tooltip-content {
                border-width: 2px !important;
              }
            }

            /* Reduced motion */
            @media (prefers-reduced-motion: reduce) {
              .mac-tooltip {
                transition: none !important;
              }
            }
          `}</style>
        </div>
      )}
    </>
  );
};

Tooltip.displayName = 'macOS Tooltip';

export default Tooltip;

