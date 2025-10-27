import React, { useState } from 'react';
import { Card, Button, Badge } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';
import { useHover } from '../../hooks/useUtils';
import { AnimatedTransition } from '../../hooks/useAnimation';

/**
 * Пример интерактивной панели с эффектами наведения и анимациями
 */
const InteractivePanel = ({
  title,
  children,
  actions,
  status,
  onClick,
  className = '',
  ...props
}) => {
  const { getColor, getSpacing, getFontSize, getShadow } = useTheme();
  const { ref, isHovered } = useHover();
  const [isExpanded, setIsExpanded] = useState(false);

  const panelStyle = {
    position: 'relative',
    overflow: 'hidden',
    transition: 'all 0.3s ease',
    cursor: onClick ? 'pointer' : 'default',
    transform: isHovered ? 'translateY(-2px) scale(1.01)' : 'translateY(0) scale(1)',
    boxShadow: isHovered ? getShadow('lg') : getShadow('md'),
    borderColor: isHovered ? getColor('primary', 200) : getColor('border'),
    backgroundColor: getColor('surface')
  };

  const gradientOverlay = {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: `linear-gradient(135deg, ${getColor('primary', 500)}08 0%, ${getColor('primary', 600)}04 100%)`,
    opacity: isHovered ? 1 : 0,
    transition: 'opacity 0.3s ease',
    pointerEvents: 'none'
  };

  return (
    <AnimatedTransition
      isVisible={true}
      animationType="slideUp"
      className={className}
    >
      <Card
        ref={ref}
        onClick={onClick}
        style={{
          padding: getSpacing('lg'),
          borderRadius: '12px',
          marginBottom: getSpacing('md'),
          ...panelStyle
        }}
        {...props}
      >
        {/* Градиентный overlay эффект */}
        <div style={gradientOverlay} />

        {/* Основное содержимое */}
        <div style={{ position: 'relative', zIndex: 1 }}>
          {/* Заголовок панели */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: getSpacing('md')
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: getSpacing('md')
            }}>
              <h3 style={{
                fontSize: getFontSize('lg'),
                fontWeight: '600',
                color: getColor('text'),
                margin: 0
              }}>
                {title}
              </h3>

              {status && (
                <Badge variant={status === 'active' ? 'success' : 'info'}>
                  {status}
                </Badge>
              )}
            </div>

            {actions && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: getSpacing('sm')
              }}>
                {actions}
              </div>
            )}
          </div>

          {/* Содержимое панели */}
          <div style={{
            marginBottom: getSpacing('md'),
            color: getColor('textSecondary'),
            fontSize: getFontSize('base'),
            lineHeight: '1.5'
          }}>
            {children}
          </div>

          {/* Кнопка развертывания */}
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            style={{
              color: getColor('primary', 500),
              fontSize: getFontSize('sm')
            }}
          >
            {isExpanded ? 'Свернуть' : 'Развернуть'}
          </Button>

          {/* Дополнительное содержимое при развертывании */}
          <AnimatedTransition
            isVisible={isExpanded}
            animationType="slideDown"
            style={{ marginTop: getSpacing('md') }}
          >
            <div style={{
              padding: getSpacing('md'),
              backgroundColor: getColor('background'),
              borderRadius: '8px',
              border: `1px solid ${getColor('border')}`
            }}>
              <p style={{
                fontSize: getFontSize('sm'),
                color: getColor('textSecondary'),
                margin: 0
              }}>
                Дополнительная информация появляется при развертывании панели.
                Здесь могут быть детали, графики или дополнительные элементы управления.
              </p>
            </div>
          </AnimatedTransition>
        </div>

        {/* Эффект свечения при наведении */}
        {isHovered && (
          <div style={{
            position: 'absolute',
            top: '-2px',
            left: '-2px',
            right: '-2px',
            bottom: '-2px',
            background: `linear-gradient(135deg, ${getColor('primary', 400)}, ${getColor('primary', 600)})`,
            borderRadius: '14px',
            zIndex: -1,
            opacity: 0.08,
            filter: 'blur(12px)'
          }} />
        )}
      </Card>
    </AnimatedTransition>
  );
};

/**
 * Пример интерактивной панели с несколькими состояниями
 */
export const StateInteractivePanel = ({
  title,
  initialState = 'idle',
  states = ['idle', 'loading', 'success', 'error'],
  ...props
}) => {
  const [currentState, setCurrentState] = useState(initialState);
  const { getColor, getSpacing, getFontSize } = useTheme();

  const getStateColors = (state) => {
    const stateColors = {
      idle: { bg: getColor('surface'), border: getColor('border'), text: getColor('text') },
      loading: { bg: getColor('primary', 50), border: getColor('primary', 200), text: getColor('primary', 600) },
      success: { bg: getColor('success', 50), border: getColor('success', 200), text: getColor('success', 600) },
      error: { bg: getColor('danger', 50), border: getColor('danger', 200), text: getColor('danger', 600) }
    };
    return stateColors[state] || stateColors.idle;
  };

  const stateColors = getStateColors(currentState);

  return (
    <Card
      style={{
        padding: getSpacing('lg'),
        borderRadius: '12px',
        backgroundColor: stateColors.bg,
        border: `2px solid ${stateColors.border}`,
        transition: 'all 0.3s ease',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* Анимированный индикатор состояния */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        height: '4px',
        width: '100%',
        background: `linear-gradient(90deg, ${getColor('primary', 500)}, ${getColor('primary', 600)})`
      }} />

      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: getSpacing('md')
      }}>
        <h3 style={{
          fontSize: getFontSize('lg'),
          fontWeight: '600',
          color: stateColors.text,
          margin: 0
        }}>
          {title}
        </h3>

        <Badge variant={currentState === 'success' ? 'success' : currentState === 'error' ? 'danger' : 'info'}>
          {currentState}
        </Badge>
      </div>

      <div style={{
        display: 'flex',
        gap: getSpacing('sm'),
        flexWrap: 'wrap'
      }}>
        {states.map((state) => (
          <Button
            key={state}
            variant={currentState === state ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setCurrentState(state)}
          >
            {state}
          </Button>
        ))}
      </div>

      {/* Дополнительный контент в зависимости от состояния */}
      {currentState === 'loading' && (
        <div style={{
          marginTop: getSpacing('md'),
          padding: getSpacing('md'),
          backgroundColor: getColor('primary', 100),
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <div style={{
            width: '20px',
            height: '20px',
            border: `2px solid ${getColor('primary', 300)}`,
            borderTop: `2px solid ${getColor('primary', 500)}`,
            borderRadius: '50%',
            animation: 'spin 1s linear infinite'
          }} />
          <span style={{
            fontSize: getFontSize('sm'),
            color: getColor('primary', 600)
          }}>
            Загрузка данных...
          </span>
        </div>
      )}

      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}
      </style>
    </Card>
  );
};

export default InteractivePanel;
