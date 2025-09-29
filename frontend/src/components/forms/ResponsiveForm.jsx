import React from 'react';
import { useBreakpoint } from '../../hooks/useMediaQuery';
import { Button } from '../ui';

const ResponsiveForm = ({
  children,
  onSubmit,
  className = '',
  style = {}
}) => {
  const { isMobile, isTablet } = useBreakpoint();

  return (
    <form
      onSubmit={onSubmit}
      className={`responsive-form ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: isMobile ? '16px' : '20px',
        ...style
      }}
    >
      {children}
    </form>
  );
};

// Компонент для группы полей
const FormGroup = ({ 
  children, 
  label, 
  error, 
  required = false,
  className = '',
  style = {}
}) => {
  const { isMobile } = useBreakpoint();

  return (
    <div
      className={`form-group ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: isMobile ? '6px' : '8px',
        ...style
      }}
    >
      {label && (
        <label
          style={{
            fontSize: isMobile ? '14px' : '16px',
            fontWeight: '500',
            color: '#374151'
          }}
        >
          {label}
          {required && <span style={{ color: '#ef4444', marginLeft: '4px' }}>*</span>}
        </label>
      )}
      {children}
      {error && (
        <span
          style={{
            fontSize: isMobile ? '12px' : '14px',
            color: '#ef4444'
          }}
        >
          {error}
        </span>
      )}
    </div>
  );
};

// Компонент для поля ввода
const FormInput = ({
  type = 'text',
  placeholder,
  value,
  onChange,
  disabled = false,
  required = false,
  className = '',
  style = {}
}) => {
  const { isMobile } = useBreakpoint();

  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      disabled={disabled}
      required={required}
      className={className}
      style={{
        padding: isMobile ? '12px' : '16px',
        border: '1px solid #d1d5db',
        borderRadius: isMobile ? '8px' : '12px',
        fontSize: isMobile ? '16px' : '16px', // Предотвращает zoom на iOS
        fontFamily: 'inherit',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        outline: 'none',
        ...style
      }}
      onFocus={(e) => {
        e.target.style.borderColor = '#3b82f6';
        e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)';
      }}
      onBlur={(e) => {
        e.target.style.borderColor = '#d1d5db';
        e.target.style.boxShadow = 'none';
      }}
    />
  );
};

// Компонент для селекта
const FormSelect = ({
  value,
  onChange,
  children,
  disabled = false,
  required = false,
  className = '',
  style = {}
}) => {
  const { isMobile } = useBreakpoint();

  return (
    <select
      value={value}
      onChange={onChange}
      disabled={disabled}
      required={required}
      className={className}
      style={{
        padding: isMobile ? '12px' : '16px',
        border: '1px solid #d1d5db',
        borderRadius: isMobile ? '8px' : '12px',
        fontSize: isMobile ? '16px' : '16px',
        fontFamily: 'inherit',
        backgroundColor: 'white',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        outline: 'none',
        ...style
      }}
      onFocus={(e) => {
        e.target.style.borderColor = '#3b82f6';
        e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)';
      }}
      onBlur={(e) => {
        e.target.style.borderColor = '#d1d5db';
        e.target.style.boxShadow = 'none';
      }}
    >
      {children}
    </select>
  );
};

// Компонент для textarea
const FormTextarea = ({
  placeholder,
  value,
  onChange,
  disabled = false,
  required = false,
  rows = 4,
  className = '',
  style = {}
}) => {
  const { isMobile } = useBreakpoint();

  return (
    <textarea
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      disabled={disabled}
      required={required}
      rows={rows}
      className={className}
      style={{
        padding: isMobile ? '12px' : '16px',
        border: '1px solid #d1d5db',
        borderRadius: isMobile ? '8px' : '12px',
        fontSize: isMobile ? '16px' : '16px',
        fontFamily: 'inherit',
        resize: 'vertical',
        minHeight: isMobile ? '80px' : '100px',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        outline: 'none',
        ...style
      }}
      onFocus={(e) => {
        e.target.style.borderColor = '#3b82f6';
        e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)';
      }}
      onBlur={(e) => {
        e.target.style.borderColor = '#d1d5db';
        e.target.style.boxShadow = 'none';
      }}
    />
  );
};

// Компонент для кнопок формы
const FormActions = ({ 
  children, 
  className = '', 
  style = {} 
}) => {
  const { isMobile } = useBreakpoint();

  return (
    <div
      className={`form-actions ${className}`}
      style={{
        display: 'flex',
        gap: isMobile ? '12px' : '16px',
        justifyContent: isMobile ? 'stretch' : 'flex-end',
        marginTop: isMobile ? '20px' : '24px',
        ...style
      }}
    >
      {children}
    </div>
  );
};

// Экспортируем все компоненты
ResponsiveForm.Group = FormGroup;
ResponsiveForm.Input = FormInput;
ResponsiveForm.Select = FormSelect;
ResponsiveForm.Textarea = FormTextarea;
ResponsiveForm.Actions = FormActions;

export default ResponsiveForm;

