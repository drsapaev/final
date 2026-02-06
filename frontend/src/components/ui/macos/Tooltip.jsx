import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
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
  followCursor = false, // ✅ NEW: Тултип следует за курсором
  className = '',
  style = {},
  ...props
}) => {
  const { theme } = useTheme();
  const [isVisible, setIsVisible] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const [mouseCoords, setMouseCoords] = useState({ x: 0, y: 0 });
  const [tooltipSize, setTooltipSize] = useState(null); // ✅ NEW: Размеры тултипа

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

  const handleMouseEnter = (e) => {
    if (disabled) return;

    // ✅ FIXED: Запоминаем начальную позицию курсора сразу
    if (followCursor) {
      setMouseCoords({ x: e.clientX, y: e.clientY });
    }

    timeoutRef.current = setTimeout(() => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (rect) {
        setCoords({
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2
        });
        setShouldRender(true); // Сначала рендерим (невидимым) для замера
      }
    }, delay);
  };

  // ✅ FIXED: Обновляем позицию при любом движении мыши
  const handleMouseMove = (e) => {
    if (followCursor) {
      setMouseCoords({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
    // Даем время на анимацию исчезновения
    setTimeout(() => {
      if (!timeoutRef.current) setShouldRender(false);
    }, 200);
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // ✅ NEW: Измеряем размеры сразу после рендера через useLayoutEffect
  useLayoutEffect(() => {
    if (shouldRender && tooltipRef.current) {
      const rect = tooltipRef.current.getBoundingClientRect();
      setTooltipSize({ width: rect.width, height: rect.height });
      // Теперь можно показывать
      requestAnimationFrame(() => setIsVisible(true));
    } else if (!shouldRender) {
      setTooltipSize(null);
      setIsVisible(false);
    }
  }, [shouldRender]);

  const tooltipPosition = positionMap[position] || positionMap.top;

  const tooltipStyles = {
    position: 'fixed',
    top: 0,
    left: 0,
    zIndex: 9999, // Поверх всего (Portal)
    pointerEvents: 'none',
    opacity: isVisible && tooltipSize ? 1 : 0, // Показываем только когда измерено
    transform: isVisible && tooltipSize ? 'scale(1)' : 'scale(0.95)',
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
    if (!tooltipSize) return {}; // Ждем измерения

    let top = 0;
    let left = 0;

    // ✅ NEW: Если followCursor включен, позиционируем относительно курсора
    if (followCursor) {
      const tooltipWidth = tooltipSize.width;
      const tooltipHeight = tooltipSize.height;
      const offset = 16;

      // Проверяем, хватает ли места справа и снизу
      const spaceRight = window.innerWidth - mouseCoords.x;
      const spaceBottom = window.innerHeight - mouseCoords.y;

      // Позиционируем по горизонтали
      if (spaceRight > tooltipWidth + offset) {
        left = mouseCoords.x + offset;
      } else {
        left = mouseCoords.x - tooltipWidth - offset;
      }

      // Позиционируем по вертикали
      if (spaceBottom > tooltipHeight + offset) {
        top = mouseCoords.y + offset;
      } else {
        top = mouseCoords.y - tooltipHeight - offset;
      }
    } else {
      // Стандартное позиционирование (без followCursor)
      // Здесь используем сохраненные coords (центр триггера)

      const tooltipWidth = tooltipSize.width;
      const tooltipHeight = tooltipSize.height;

      switch (tooltipPosition.x) {
        case 'left':
          left = coords.x - tooltipWidth - 8;
          break;
        case 'right':
          left = coords.x + 8;
          break;
        default: // center
          left = coords.x - tooltipWidth / 2;
          break;
      }

      switch (tooltipPosition.y) {
        case 'top':
          top = coords.y - tooltipHeight - 8;
          break;
        case 'bottom':
          top = coords.y + 8;
          break;
        default: // center
          top = coords.y - tooltipHeight / 2;
          break;
      }
    }

    // Ensure tooltip stays within viewport
    const viewport = {
      top: 8,
      left: 8,
      right: window.innerWidth - 8,
      bottom: window.innerHeight - 8
    };

    // Проверка границ
    if (left < viewport.left) left = viewport.left;
    const currentWidth = tooltipSize.width;
    if (left + currentWidth > viewport.right) {
      left = viewport.right - currentWidth;
    }

    if (top < viewport.top) top = viewport.top;
    const currentHeight = tooltipSize.height;
    if (top + currentHeight > viewport.bottom) {
      top = viewport.bottom - currentHeight;
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
        onMouseMove={followCursor ? handleMouseMove : undefined}
        onMouseLeave={handleMouseLeave}
        style={{ display: 'inline-block', ...style }}
        {...props}
      >
        {children}
      </div>

      {shouldRender && createPortal(
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

          {/* Стрелочку показываем только если НЕ followCursor */}
          {!followCursor && (
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
                  marginTop: '-5px'
                }),
                ...(tooltipPosition.x === 'right' && tooltipPosition.y === 'center' && {
                  left: '-5px',
                  top: '50%',
                  marginTop: '-5px'
                }),
                ...(tooltipPosition.x === 'center' && tooltipPosition.y === 'top' && {
                  bottom: '-5px',
                  left: '50%',
                  marginLeft: '-5px'
                }),
                ...(tooltipPosition.x === 'center' && tooltipPosition.y === 'bottom' && {
                  top: '-5px',
                  left: '50%',
                  marginLeft: '-5px'
                })
              }}
            />
          )}

          <style>{`
            /* Dark mode adjustments */
            @media (prefers-color-scheme: dark) {
              .mac-tooltip-content {
                background-color: rgba(30, 30, 30, 0.9) !important;
                border-color: rgba(255, 255, 255, 0.1) !important;
                color: #f5f5f7 !important;
              }
              .mac-tooltip-arrow {
                 background-color: rgba(30, 30, 30, 0.9) !important;
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
        </div>,
        document.body
      )}
    </>
  );
};

Tooltip.displayName = 'macOS Tooltip';

export default Tooltip;
