import React, { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import { ChevronDown } from 'lucide-react';
import { cn } from '../../../utils/cn';

const Dropdown = React.forwardRef(({
  children,
  trigger,
  position = 'bottom-left',
  disabled = false,
  closeOnClick = true,
  className = '',
  triggerClassName = '',
  contentClassName = '',
  ...props
}, ref) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  const triggerRef = useRef(null);

  const positions = {
    'top-left': 'bottom-full left-0 mb-2',
    'top-right': 'bottom-full right-0 mb-2',
    'bottom-left': 'top-full left-0 mt-2',
    'bottom-right': 'top-full right-0 mt-2',
    'left': 'right-full top-0 mr-2',
    'right': 'left-full top-0 ml-2'
  };

  // Закрытие при клике вне компонента
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
      dropdownRef.current &&
      !dropdownRef.current.contains(event.target) &&
      triggerRef.current &&
      !triggerRef.current.contains(event.target))
      {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Закрытие по Escape
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen]);

  const handleTriggerClick = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
    }
  };

  const handleContentClick = () => {
    if (closeOnClick) {
      setIsOpen(false);
    }
  };
  const handleActivationKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };

  return (
    <div
      ref={ref}
      className={cn('relative inline-block', className)}
      {...props}>
      
      {/* Trigger */}
      <div
        ref={triggerRef}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onClick={handleTriggerClick}
        onKeyDown={(event) => handleActivationKeyDown(event, handleTriggerClick)}
        className={cn(
          'cursor-pointer',
          disabled && 'opacity-50 cursor-not-allowed',
          triggerClassName
        )}>
        
        {trigger}
      </div>

      {/* Content */}
      {isOpen &&
      <div
        ref={dropdownRef}
        className={cn(
          'absolute z-50 min-w-full',
          'bg-white border border-gray-200 rounded-md shadow-lg',
          'animate-in fade-in-0 zoom-in-95 duration-200',
          positions[position],
          contentClassName
        )}
        onClickCapture={handleContentClick}>
        
          {children}
        </div>
      }
    </div>);

});

Dropdown.displayName = 'Dropdown';

const DropdownItem = React.forwardRef(({
  children,
  onClick,
  disabled = false,
  className = '',
  ...props
}, ref) =>
<button
  type="button"
  ref={ref}
  onClick={onClick}
  disabled={disabled}
  className={cn(
    'w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 cursor-pointer text-left',
    'first:rounded-t-md last:rounded-b-md',
    disabled && 'opacity-50 cursor-not-allowed hover:bg-transparent',
    className
  )}
  {...props}>
  
    {children}
  </button>
);

DropdownItem.displayName = 'DropdownItem';

const DropdownSeparator = React.forwardRef(({
  className = '',
  ...props
}, ref) =>
<div
  ref={ref}
  className={cn('h-px bg-gray-200 my-1', className)}
  {...props} />

);

DropdownSeparator.displayName = 'DropdownSeparator';

const DropdownLabel = React.forwardRef(({
  children,
  className = '',
  ...props
}, ref) =>
<div
  ref={ref}
  className={cn('px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider', className)}
  {...props}>
  
    {children}
  </div>
);

DropdownLabel.displayName = 'DropdownLabel';

// Готовый компонент Select с Dropdown
const Select = React.forwardRef(({
  value,
  onChange,
  options = [],
  placeholder = 'Выберите...',
  disabled = false,
  className = '',
  ...props
}, ref) => {
  const selectedOption = options.find((opt) => opt.value === value);

  return (
    <Dropdown
      ref={ref}
      disabled={disabled}
      trigger={
      <div className={cn(
        'flex items-center justify-between px-3 py-2',
        'border border-gray-300 rounded-md bg-white',
        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
        disabled && 'bg-gray-100 cursor-not-allowed',
        className
      )}>
          <span className={cn(
          'text-sm',
          selectedOption ? 'text-gray-900' : 'text-gray-500'
        )}>
            {selectedOption ? selectedOption.label : placeholder}
          </span>
          <ChevronDown className="w-4 h-4 text-gray-400" />
        </div>
      }
      className="w-full"
      {...props}>
      
      {options.map((option) =>
      <DropdownItem
        key={option.value}
        onClick={() => onChange?.(option.value)}
        disabled={option.disabled}>
        
          {option.label}
        </DropdownItem>
      )}
    </Dropdown>);

});

Select.displayName = 'Select';

Dropdown.propTypes = {
  children: PropTypes.node,
  trigger: PropTypes.node,
  position: PropTypes.string,
  disabled: PropTypes.bool,
  closeOnClick: PropTypes.bool,
  className: PropTypes.string,
  triggerClassName: PropTypes.string,
  contentClassName: PropTypes.string
};

DropdownItem.propTypes = {
  children: PropTypes.node,
  onClick: PropTypes.func,
  disabled: PropTypes.bool,
  className: PropTypes.string
};

DropdownSeparator.propTypes = {
  className: PropTypes.string
};

DropdownLabel.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string
};

Select.propTypes = {
  value: PropTypes.any,
  onChange: PropTypes.func,
  options: PropTypes.array,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  className: PropTypes.string
};

export default Dropdown;
export { DropdownItem, DropdownSeparator, DropdownLabel, Select };
