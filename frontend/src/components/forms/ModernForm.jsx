import React, { useState, useRef } from 'react';
import { AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernForm.css';

const ModernForm = ({
  children,
  onSubmit,
  validation,
  initialValues = {},
  loading = false,
  error,
  success,
  className = '',
  layout = 'vertical',
  spacing = 'medium',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const formRef = useRef(null);

  // Обновление значения поля
  const updateValue = (name, value) => {
    setValues(prev => ({ ...prev, [name]: value }));
    
    // Очистка ошибки при изменении значения
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  // Пометка поля как затронутого
  const markTouched = (name) => {
    setTouched(prev => ({ ...prev, [name]: true }));
  };

  // Валидация поля
  const validateField = (name, value) => {
    if (!validation || !validation[name]) return null;
    
    const fieldValidation = validation[name];
    
    if (typeof fieldValidation === 'function') {
      return fieldValidation(value, values);
    }
    
    if (Array.isArray(fieldValidation)) {
      for (const validator of fieldValidation) {
        const result = validator(value, values);
        if (result !== true) return result;
      }
    }
    
    return null;
  };

  // Валидация всей формы
  const validateForm = () => {
    const newErrors = {};
    let hasErrors = false;
    
    if (validation) {
      Object.keys(validation).forEach(fieldName => {
        const error = validateField(fieldName, values[fieldName]);
        if (error) {
          newErrors[fieldName] = error;
          hasErrors = true;
        }
      });
    }
    
    setErrors(newErrors);
    return !hasErrors;
  };

  // Обработка отправки формы
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (isSubmitting || loading) return;
    
    // Пометить все поля как затронутые
    const allFields = Object.keys(validation || {});
    const newTouched = {};
    allFields.forEach(field => {
      newTouched[field] = true;
    });
    setTouched(newTouched);
    
    // Валидация
    if (!validateForm()) {
      // Фокус на первое поле с ошибкой
      const firstErrorField = Object.keys(errors)[0];
      if (firstErrorField) {
        const field = formRef.current?.querySelector(`[name="${firstErrorField}"]`);
        field?.focus();
      }
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      await onSubmit?.(values);
    } catch (error) {
      console.error('Form submission error:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Клонирование дочерних элементов с передачей пропсов
  const cloneChildren = (children) => {
    return React.Children.map(children, (child) => {
      if (!React.isValidElement(child)) return child;
      
      // Если это поле формы
      if (child.props.name) {
        const name = child.props.name;
        const fieldError = touched[name] ? errors[name] : null;
        
        return React.cloneElement(child, {
          value: values[name] || '',
          onChange: (e) => {
            const value = e.target ? e.target.value : e;
            updateValue(name, value);
            child.props.onChange?.(e);
          },
          onBlur: (e) => {
            markTouched(name);
            const error = validateField(name, values[name]);
            if (error) {
              setErrors(prev => ({ ...prev, [name]: error }));
            }
            child.props.onBlur?.(e);
          },
          error: fieldError,
          ...child.props
        });
      }
      
      // Рекурсивная обработка вложенных элементов
      if (child.props.children) {
        return React.cloneElement(child, {
          ...child.props,
          children: cloneChildren(child.props.children)
        });
      }
      
      return child;
    });
  };

  return (
    <form
      ref={formRef}
      className={`modern-form ${layout} ${spacing} ${className}`}
      onSubmit={handleSubmit}
      noValidate
      {...props}
    >
      {/* Общие сообщения формы */}
      {error && (
        <div 
          className="form-message error"
          style={{ color: getColor('danger') }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}
      
      {success && (
        <div 
          className="form-message success"
          style={{ color: getColor('success') }}
        >
          <CheckCircle size={16} />
          <span>{success}</span>
        </div>
      )}

      {/* Поля формы */}
      <div className="form-fields">
        {cloneChildren(children)}
      </div>

      {/* Индикатор загрузки */}
      {(loading || isSubmitting) && (
        <div className="form-loading">
          <Loader size={16} className="spinning" />
          <span>Обработка...</span>
        </div>
      )}
    </form>
  );
};

// Компонент группы полей
export const FormGroup = ({ 
  title, 
  description, 
  children, 
  className = '',
  collapsible = false,
  defaultExpanded = true,
  ...props 
}) => {
  const { getColor } = useTheme();
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className={`form-group ${className}`} {...props}>
      {title && (
        <div 
          className={`form-group-header ${collapsible ? 'collapsible' : ''}`}
          onClick={collapsible ? () => setExpanded(!expanded) : undefined}
        >
          <h3 
            className="form-group-title"
            style={{ color: getColor('textPrimary') }}
          >
            {title}
          </h3>
          {description && (
            <p 
              className="form-group-description"
              style={{ color: getColor('textSecondary') }}
            >
              {description}
            </p>
          )}
        </div>
      )}
      
      {(!collapsible || expanded) && (
        <div className="form-group-content">
          {children}
        </div>
      )}
    </div>
  );
};

// Компонент ряда полей
export const FormRow = ({ 
  children, 
  className = '',
  gap = 'medium',
  align = 'stretch',
  ...props 
}) => {
  return (
    <div 
      className={`form-row ${gap} ${align} ${className}`} 
      {...props}
    >
      {children}
    </div>
  );
};

// Компонент колонки
export const FormColumn = ({ 
  children, 
  className = '',
  width = 'auto',
  ...props 
}) => {
  return (
    <div 
      className={`form-column ${className}`}
      style={{ flex: width === 'auto' ? 1 : `0 0 ${width}` }}
      {...props}
    >
      {children}
    </div>
  );
};

export default ModernForm;


