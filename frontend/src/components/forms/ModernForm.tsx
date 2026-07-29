
import React, { useState, useRef } from 'react';
import PropTypes from 'prop-types';
import { AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import logger from '../../utils/logger';
import './ModernForm.css';
import { useTranslation } from '../../i18n/useTranslation';

type Validator = (value: unknown, values: Record<string, unknown>) => true | string;
type FieldValidation = Validator | Validator[];

interface ModernFormProps {
  children?: React.ReactNode;
  onSubmit?: (values: Record<string, unknown>) => void | Promise<void>;
  validation?: Record<string, FieldValidation>;
  initialValues?: Record<string, unknown>;
  loading?: boolean;
  error?: React.ReactNode;
  success?: React.ReactNode;
  className?: string;
  layout?: 'vertical' | 'horizontal';
  spacing?: 'small' | 'medium' | 'large';
  [key: string]: unknown;
}

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
}: ModernFormProps) => {
  const { getColor } = useTheme();
  const [values, setValues] = useState<Record<string, unknown>>(initialValues);
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  // Обновление значения поля
  const updateValue = (name: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [name]: value }));

    // Очистка ошибки при изменении значения
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: null }));
    }
  };

  // Пометка поля как затронутого
  const markTouched = (name: string) => {
    setTouched((prev) => ({ ...prev, [name]: true }));
  };

  // Валидация поля
  const validateField = (name: string, value: unknown) => {
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
    const newErrors: Record<string, string | null> = {};
    let hasErrors = false;

    if (validation) {
      Object.keys(validation).forEach((fieldName) => {
        const error = validateField(fieldName, values[fieldName]);
        if (error && error !== true) {
          newErrors[fieldName] = error;
          hasErrors = true;
        }
      });
    }

    setErrors(newErrors);
    return !hasErrors;
  };

  // Обработка отправки формы
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (isSubmitting || loading) return;

    // Пометить все поля как затронутые
    const allFields = Object.keys(validation || {});
    const newTouched: Record<string, boolean> = {};
    allFields.forEach((field) => {
      newTouched[field] = true;
    });
    setTouched(newTouched);

    // Валидация
    if (!validateForm()) {
      // Фокус на первое поле с ошибкой
      const firstErrorField = Object.keys(errors)[0];
      if (firstErrorField) {
        const field = formRef.current?.querySelector<HTMLElement>(`[name="${firstErrorField}"]`);
        field?.focus();
      }
      return;
    }

    setIsSubmitting(true);

    try {
      await onSubmit?.(values);
    } catch (error) {
      logger.error('Form submission error:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Клонирование дочерних элементов с передачей пропсов
  const cloneChildren = (children: React.ReactNode): React.ReactNode => {
    return React.Children.map(children, (child) => {
      if (!React.isValidElement(child)) return child;

      // Если это поле формы
      if ((child.props as Record<string, unknown>).name) {
        const name = String((child.props as Record<string, unknown>).name);
        const fieldError = touched[name] ? errors[name] : null;

        return (React.cloneElement as unknown as (el: React.ReactElement, props: Record<string, unknown>) => React.ReactElement)(child as React.ReactElement, {
          value: values[name] || '',
          onChange: (e: { target?: { value: unknown } } | unknown) => {
            const value = (e as { target?: { value: unknown } })?.target ? (e as { target: { value: unknown } }).target.value : e;
            updateValue(name, value);
            ((child.props as Record<string, unknown>).onChange as ((...args: unknown[]) => void) | undefined)?.(e);
          },
          onBlur: (e: unknown) => {
            markTouched(name);
            const error = validateField(name, values[name]);
            if (error && error !== true) {
              setErrors((prev) => ({ ...prev, [name]: String(error) }));
            }
            ((child.props as Record<string, unknown>).onBlur as ((...args: unknown[]) => void) | undefined)?.(e);
          },
          error: fieldError,
          ...(child.props as Record<string, unknown>)
        });
      }

      // Рекурсивная обработка вложенных элементов
      if ((child.props as Record<string, unknown>).children) {
        return (React.cloneElement as unknown as (el: React.ReactElement, props: Record<string, unknown>) => React.ReactElement)(child as React.ReactElement, {
          ...(child.props as Record<string, unknown>),
          children: cloneChildren((child.props as Record<string, unknown>).children as React.ReactNode)
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
      {...props}>
      
      {/* Общие сообщения формы */}
      {error &&
      <div
        className="form-message error"
        style={{ color: getColor('danger') }}>
        
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      }
      
      {success &&
      <div
        className="form-message success"
        style={{ color: getColor('success') }}>
        
          <CheckCircle size={16} />
          <span>{success}</span>
        </div>
      }

      {/* Поля формы */}
      <div className="form-fields">
        {cloneChildren(children)}
      </div>

      {/* Индикатор загрузки */}
      {(loading || isSubmitting) &&
      <div className="form-loading">
          <Loader size={16} className="spinning" />
          <span>Обработка...</span>
        </div>
      }
    </form>);

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
}: {
  title?: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  [key: string]: unknown;
}) => {
  const { getColor } = useTheme();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const headerContent = (
    <>
      <h3
        className="form-group-title"
        style={{ color: getColor('textPrimary') }}>

        {title}
      </h3>
      {description &&
      <p
        className="form-group-description"
        style={{ color: getColor('textSecondary') }}>

          {description}
        </p>
      }
    </>
  );

  return (
    <div className={`form-group ${className}`} {...props}>
      {title && collapsible &&
      <div
        className="form-group-header collapsible"
        role="button"
        tabIndex={0}
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            setExpanded(!expanded);
          }
        }}>

          {headerContent}
        </div>
      }
      {title && !collapsible &&
      <div className="form-group-header">
          {headerContent}
        </div>
      }
      
      {(!collapsible || expanded) &&
      <div className="form-group-content">
          {children}
        </div>
      }
    </div>);

};

// Компонент ряда полей
export const FormRow = ({
  children,
  className = '',
  gap = 'medium',
  align = 'stretch',
  ...props
}: {
  children?: React.ReactNode;
  className?: string;
  gap?: string;
  align?: string;
  [key: string]: unknown;
}) => {
  return (
    <div
      className={`form-row ${gap} ${align} ${className}`}
      {...props}>
      
      {children}
    </div>);

};

// Компонент колонки
export const FormColumn = ({
  children,
  className = '',
  width = 'auto',
  ...props
}: {
  children?: React.ReactNode;
  className?: string;
  width?: string;
  [key: string]: unknown;
}) => {
  return (
    <div
      className={`form-column ${className}`}
      style={{ flex: width === 'auto' ? 1 : `0 0 ${width}` }}
      {...props}>
      
      {children}
    </div>);

};

ModernForm.propTypes = {
  children: PropTypes.node,
  onSubmit: PropTypes.func,
  validation: PropTypes.object,
  initialValues: PropTypes.object,
  loading: PropTypes.bool,
  error: PropTypes.node,
  success: PropTypes.node,
  className: PropTypes.string,
  layout: PropTypes.string,
  spacing: PropTypes.string
};

FormGroup.propTypes = {
  title: PropTypes.node,
  description: PropTypes.node,
  children: PropTypes.node,
  className: PropTypes.string,
  collapsible: PropTypes.bool,
  defaultExpanded: PropTypes.bool
};

FormRow.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  gap: PropTypes.string,
  align: PropTypes.string
};

FormColumn.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  width: PropTypes.string
};

export default ModernForm;
