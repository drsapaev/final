import React, { useState } from 'react';
import { Plus, X } from 'lucide-react';
import ModernButton from './ModernButton';
import { useTheme } from '../../contexts/ThemeContext';
import './FloatingActionButton.css';

const FloatingActionButton = ({
  icon = Plus,
  position = 'bottom-right',
  size = 'large',
  variant = 'primary',
  actions = [],
  tooltip,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [isExpanded, setIsExpanded] = useState(false);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const handleActionClick = (action) => {
    action.onClick?.();
    setIsExpanded(false);
  };

  const positionClasses = {
    'top-left': 'fab-top-left',
    'top-right': 'fab-top-right',
    'bottom-left': 'fab-bottom-left',
    'bottom-right': 'fab-bottom-right'
  };

  return (
    <>
      {/* Backdrop */}
      {isExpanded && actions.length > 0 && (
        <div 
          className="fab-backdrop"
          onClick={() => setIsExpanded(false)}
        />
      )}

      {/* FAB Container */}
      <div className={`fab-container ${positionClasses[position]} ${className}`}>
        {/* Действия */}
        {actions.length > 0 && (
          <div className={`fab-actions ${isExpanded ? 'expanded' : ''}`}>
            {actions.map((action, index) => (
              <div
                key={index}
                className="fab-action-item"
                style={{
                  animationDelay: `${index * 50}ms`
                }}
              >
                {action.label && (
                  <span 
                    className="fab-action-label"
                    style={{
                      backgroundColor: getColor('cardBg'),
                      color: getColor('textPrimary'),
                      borderColor: getColor('border')
                    }}
                  >
                    {action.label}
                  </span>
                )}
                <ModernButton
                  icon={action.icon}
                  size="medium"
                  variant={action.variant || 'secondary'}
                  rounded
                  className="fab-action-button"
                  onClick={() => handleActionClick(action)}
                  title={action.tooltip}
                />
              </div>
            ))}
          </div>
        )}

        {/* Основная кнопка */}
        <ModernButton
          icon={isExpanded && actions.length > 0 ? X : icon}
          size={size}
          variant={variant}
          rounded
          className={`fab-main ${isExpanded ? 'expanded' : ''}`}
          onClick={actions.length > 0 ? toggleExpanded : props.onClick}
          title={tooltip}
          {...props}
        />
      </div>
    </>
  );
};

export default FloatingActionButton;


