/**
 * Улучшенная система форм для медицинских интерфейсов.
 * Основана на принципах доступности и медицинских стандартах UX.
 */

import { useCallback, useState } from 'react';
import type { ReactNode, CSSProperties, FormEvent, ChangeEvent, FocusEvent } from 'react';
import { useAnimation } from './useAnimation';
import { useReducedMotion } from './useEnhancedMediaQuery';
import logger from '../utils/logger';

// @ts-expect-error — ui/macos not yet migrated (Phase 4 redo)
import { Input } from '../../ui/macos';

// ============================================================================
// Validators
// ============================================================================

type ValidatorFn = (value: unknown) => boolean;
type CurriedValidator = (param: unknown) => ValidatorFn;

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- validators return mixed types; Phase 9 cleanup
export const validators: Record<string, (...args: unknown[]) => any> = {
  required: (value: unknown): boolean => {
    if (typeof value === 'string') return value.trim() !== '';
    return value != null && value !== '';
  },

  email: (value: unknown): boolean => {
    if (!value) return true;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(String(value));
  },

  phone: (value: unknown): boolean => {
    if (!value) return true;
    const phoneRegex = /^\+?[\d\s-()]{10,}$/;
    return phoneRegex.test(String(value).replace(/\s/g, ''));
  },

  minLength: (min: number): ValidatorFn => (value: unknown): boolean => {
    if (!value) return true;
    return String(value).length >= min;
  },

  maxLength: (max: number): ValidatorFn => (value: unknown): boolean => {
    if (!value) return true;
    return String(value).length <= max;
  },

  pattern: (regex: RegExp): ValidatorFn => (value: unknown): boolean => {
    if (!value) return true;
    return regex.test(String(value));
  },

  numeric: (value: unknown): boolean => {
    if (!value) return true;
    return !isNaN(Number(value));
  },

  min: (min: number): ValidatorFn => (value: unknown): boolean => {
    if (!value) return true;
    const num = Number(value);
    return !isNaN(num) && num >= min;
  },

  max: (max: number): ValidatorFn => (value: unknown): boolean => {
    if (!value) return true;
    const num = Number(value);
    return !isNaN(num) && num <= max;
  },

  date: (value: unknown): boolean => {
    if (!value) return true;
    const d = new Date(String(value));
    return !isNaN(d.getTime());
  },

  future: (value: unknown): boolean => {
    if (!value) return true;
    const d = new Date(String(value));
    return !isNaN(d.getTime()) && d > new Date();
  },

  past: (value: unknown): boolean => {
    if (!value) return true;
    const d = new Date(String(value));
    return !isNaN(d.getTime()) && d < new Date();
  },
};

// ============================================================================
// useForm hook
// ============================================================================

interface ValidationRule {
  message?: string;
  [key: string]: unknown;
}

interface UseFormOptions<T> {
  validateOnChange?: boolean;
  validateOnBlur?: boolean;
  validateOnSubmit?: boolean;
  resetOnSubmit?: boolean;
  validation?: Record<string, Record<string, ValidationRule>>;
  onSubmit?: ((values: T) => void | Promise<void>) | null;
}

interface FieldProps {
  name: string;
  value: unknown;
  onChange: (value: unknown) => void;
  onBlur: () => void;
  onFocus: () => void;
  error: string | undefined;
  touched: boolean;
  isValid: boolean;
}

interface FormStats {
  totalFields: number;
  touchedFields: number;
  errorFields: number;
  isValid: boolean;
  isSubmitting: boolean;
  hasChanges: boolean;
}

interface UseFormReturn<T> {
  values: T;
  errors: Record<string, string[]>;
  touched: Record<string, boolean>;
  isValid: boolean;
  isSubmitting: boolean;
  handleChange: (name: string, value: unknown) => void;
  handleBlur: (name: string) => void;
  handleFocus: () => void;
  handleSubmit: (e?: FormEvent) => Promise<void>;
  reset: () => void;
  validateForm: () => boolean;
  getFieldProps: (name: string) => FieldProps;
  getFormStats: () => FormStats;
  setValues: React.Dispatch<React.SetStateAction<T>>;
  setErrors: React.Dispatch<React.SetStateAction<Record<string, string[]>>>;
  setTouched: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
}

export const useForm = <T extends Record<string, unknown> = Record<string, unknown>>(
  initialValues: T = {} as T,
  options: UseFormOptions<T> = {},
): UseFormReturn<T> => {
  const {
    validateOnChange = true,
    validateOnBlur = true,
    validateOnSubmit = true,
    resetOnSubmit = false,
    validation = {},
    onSubmit = null,
  } = options;

  const [values, setValues] = useState<T>(initialValues);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isValid, setIsValid] = useState<boolean>(true);

  const validateField = useCallback(
    (name: string, value: unknown, rules: Record<string, ValidationRule> = {}): string[] => {
      const fieldErrors: string[] = [];

      Object.entries(rules).forEach(([ruleName, ruleValue]) => {
        const validator = validators[ruleName];
        if (validator) {
          const result = validator(ruleValue)(value);
          if (!result) {
            fieldErrors.push(ruleValue.message || `Ошибка валидации: ${ruleName}`);
          }
        }
      });

      return fieldErrors;
    },
    [],
  );

  const validateForm = useCallback((): boolean => {
    const allErrors: Record<string, string[]> = {};
    let formIsValid = true;

    Object.entries(values).forEach(([name, value]) => {
      const fieldRules = validation?.[name] || {};
      const fieldErrors = validateField(name, value, fieldRules);

      if (fieldErrors.length > 0) {
        allErrors[name] = fieldErrors;
        formIsValid = false;
      }
    });

    setErrors(allErrors);
    setIsValid(formIsValid);
    return formIsValid;
  }, [values, validation, validateField]);

  const handleChange = useCallback(
    (name: string, value: unknown): void => {
      setValues((prev) => ({ ...prev, [name]: value }));

      if (validateOnChange && validation?.[name]) {
        const fieldErrors = validateField(name, value, validation[name]);
        setErrors((prev) => ({ ...prev, [name]: fieldErrors }));
      }

      if (errors[name]) {
        setErrors((prev) => ({ ...prev, [name]: [] }));
      }
    },
    [validateOnChange, validation, validateField, errors],
  );

  const handleBlur = useCallback(
    (name: string): void => {
      setTouched((prev) => ({ ...prev, [name]: true }));

      if (validateOnBlur && validation?.[name]) {
        const value = values[name];
        const fieldErrors = validateField(name, value, validation[name]);
        setErrors((prev) => ({ ...prev, [name]: fieldErrors }));
      }
    },
    [validateOnBlur, validation, validateField, values],
  );

  const handleFocus = useCallback((): void => {
    // Можно добавить логику для фокуса
  }, []);

  const reset = useCallback((): void => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
    setIsValid(true);
  }, [initialValues]);

  const handleSubmit = useCallback(
    async (e?: FormEvent): Promise<void> => {
      e?.preventDefault();

      setTouched(
        Object.keys(values).reduce(
          (acc: Record<string, boolean>, key: string) => {
            acc[key] = true;
            return acc;
          },
          {},
        ),
      );

      if (validateOnSubmit) {
        const formIsValid = validateForm();
        if (!formIsValid) return;
      }

      setIsSubmitting(true);

      try {
        if (onSubmit) {
          await onSubmit(values);
        }

        if (resetOnSubmit) {
          reset();
        }
      } catch (error) {
        logger.error('Form submission error:', error);
      } finally {
        setIsSubmitting(false);
      }
    },
    [values, validateOnSubmit, validateForm, onSubmit, resetOnSubmit, reset],
  );

  const getFieldProps = useCallback(
    (name: string): FieldProps => {
      return {
        name,
        value: values[name] || '',
        onChange: (value: unknown) => handleChange(name, value),
        onBlur: () => handleBlur(name),
        onFocus: () => handleFocus(),
        error: errors[name]?.[0],
        touched: Boolean(touched[name]),
        isValid: !errors[name] || errors[name].length === 0,
      };
    },
    [values, errors, touched, handleChange, handleBlur, handleFocus],
  );

  const getFormStats = useCallback((): FormStats => {
    return {
      totalFields: Object.keys(values).length,
      touchedFields: Object.keys(touched).length,
      errorFields: Object.keys(errors).length,
      isValid,
      isSubmitting,
      hasChanges: JSON.stringify(values) !== JSON.stringify(initialValues),
    };
  }, [values, touched, errors, isValid, isSubmitting, initialValues]);

  return {
    values,
    errors,
    touched,
    isValid,
    isSubmitting,
    handleChange,
    handleBlur,
    handleFocus,
    handleSubmit,
    reset,
    validateForm,
    getFieldProps,
    getFormStats,
    setValues,
    setErrors,
    setTouched,
  };
};

// ============================================================================
// FormField component
// ============================================================================

interface FormFieldProps {
  name: string;
  label?: ReactNode;
  type?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  value?: unknown;
  onChange?: (value: unknown) => void;
  onBlur?: (e: FocusEvent<HTMLInputElement>) => void;
  className?: string;
  [key: string]: unknown;
}

export const FormField = ({
  name,
  label,
  type = 'text',
  placeholder,
  required = false,
  disabled = false,
  error,
  value,
  onChange,
  onBlur,
  className = '',
  ...props
}: FormFieldProps): React.ReactElement => {
  const { prefersReducedMotion } = useReducedMotion();
  const { shouldRender, animationStyles } = useAnimation(!!error, 'slideDown', 200);

  const handleChange = (e: ChangeEvent<HTMLInputElement>): void => {
    const newValue =
      e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    if (onChange) {
      onChange(newValue);
    }
  };

  return (
    <div className={`form-field ${className}`} style={{ marginBottom: 'var(--mac-spacing-4)' }}>
      {label && (
        <label
          htmlFor={name}
          style={{
            display: 'block',
            marginBottom: 'var(--mac-spacing-1)',
            fontSize: 'var(--mac-font-size-base)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: error ? 'var(--mac-error)' : 'var(--mac-text-primary)',
          }}
        >
          {label}
          {required && <span style={{ color: 'var(--mac-error)' }}> *</span>}
        </label>
      )}

      <Input
        id={name}
        name={name}
        type={type}
        value={(value as string) || ''}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
          fontSize: 'var(--mac-font-size-base)',
          border: `1px solid ${error ? 'var(--mac-error)' : 'var(--mac-border)'}`,
          borderRadius: 'var(--mac-radius-sm)',
          backgroundColor: disabled ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
          color: 'var(--mac-text-primary)',
          outline: 'none',
          transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease, box-shadow 0.2s ease',
        }}
        onFocus={(e: FocusEvent<HTMLInputElement>) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-accent-blue)';
            e.target.style.boxShadow = `0 0 0 3px ${error ? 'var(--mac-error-bg)' : 'var(--mac-accent-bg)'}`;
          }
        }}
        onBlur={(e: FocusEvent<HTMLInputElement>) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-border)';
            e.target.style.boxShadow = 'none';
          }
          if (onBlur) onBlur(e);
        }}
        {...props}
      />

      {shouldRender && error && (
        <div
          className={`form-field-error ${animationStyles}`}
          style={{
            marginTop: 'var(--mac-spacing-1)',
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-error)',
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// FormTextarea component
// ============================================================================

interface FormTextareaProps {
  name: string;
  label?: ReactNode;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  value?: unknown;
  onChange?: (value: string) => void;
  onBlur?: (e: FocusEvent<HTMLTextAreaElement>) => void;
  rows?: number;
  className?: string;
  [key: string]: unknown;
}

export const FormTextarea = ({
  name,
  label,
  placeholder,
  required = false,
  disabled = false,
  error,
  value,
  onChange,
  onBlur,
  rows = 3,
  className = '',
  ...props
}: FormTextareaProps): React.ReactElement => {
  const { prefersReducedMotion } = useReducedMotion();

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>): void => {
    if (onChange) {
      onChange(e.target.value);
    }
  };

  return (
    <div className={`form-textarea ${className}`} style={{ marginBottom: 'var(--mac-spacing-4)' }}>
      {label && (
        <label
          htmlFor={name}
          style={{
            display: 'block',
            marginBottom: 'var(--mac-spacing-1)',
            fontSize: 'var(--mac-font-size-base)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: error ? 'var(--mac-error)' : 'var(--mac-text-primary)',
          }}
        >
          {label}
          {required && <span style={{ color: 'var(--mac-error)' }}> *</span>}
        </label>
      )}

      <textarea
        id={name}
        name={name}
        value={(value as string) || ''}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        rows={rows}
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
          fontSize: 'var(--mac-font-size-base)',
          fontFamily: 'inherit',
          border: `1px solid ${error ? 'var(--mac-error)' : 'var(--mac-border)'}`,
          borderRadius: 'var(--mac-radius-sm)',
          backgroundColor: disabled ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
          color: 'var(--mac-text-primary)',
          outline: 'none',
          resize: 'vertical',
          transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease, box-shadow 0.2s ease',
        }}
        onFocus={(e: FocusEvent<HTMLTextAreaElement>) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-accent-blue)';
            e.target.style.boxShadow = `0 0 0 3px ${error ? 'var(--mac-error-bg)' : 'var(--mac-accent-bg)'}`;
          }
        }}
        onBlur={(e: FocusEvent<HTMLTextAreaElement>) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-border)';
            e.target.style.boxShadow = 'none';
          }
          if (onBlur) onBlur(e);
        }}
        {...props}
      />

      {error && (
        <div
          style={{
            marginTop: 'var(--mac-spacing-1)',
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-error)',
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// FormSelect component
// ============================================================================

interface SelectOption {
  value: string;
  label: string;
}

interface FormSelectProps {
  name: string;
  label?: ReactNode;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  value?: unknown;
  onChange?: (value: string) => void;
  onBlur?: (e: FocusEvent<HTMLSelectElement>) => void;
  options?: SelectOption[];
  className?: string;
  [key: string]: unknown;
}

export const FormSelect = ({
  name,
  label,
  placeholder = 'Выберите...',
  required = false,
  disabled = false,
  error,
  value,
  onChange,
  onBlur,
  options = [],
  className = '',
  ...props
}: FormSelectProps): React.ReactElement => {
  const { prefersReducedMotion } = useReducedMotion();

  const handleChange = (e: ChangeEvent<HTMLSelectElement>): void => {
    if (onChange) {
      onChange(e.target.value);
    }
  };

  return (
    <div className={`form-select ${className}`} style={{ marginBottom: 'var(--mac-spacing-4)' }}>
      {label && (
        <label
          htmlFor={name}
          style={{
            display: 'block',
            marginBottom: 'var(--mac-spacing-1)',
            fontSize: 'var(--mac-font-size-base)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: error ? 'var(--mac-error)' : 'var(--mac-text-primary)',
          }}
        >
          {label}
          {required && <span style={{ color: 'var(--mac-error)' }}> *</span>}
        </label>
      )}

      <select
        id={name}
        name={name}
        value={(value as string) || ''}
        onChange={handleChange}
        disabled={disabled}
        required={required}
        style={{
          width: '100%',
          padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
          fontSize: 'var(--mac-font-size-base)',
          border: `1px solid ${error ? 'var(--mac-error)' : 'var(--mac-border)'}`,
          borderRadius: 'var(--mac-radius-sm)',
          backgroundColor: disabled ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
          color: 'var(--mac-text-primary)',
          outline: 'none',
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease, box-shadow 0.2s ease',
        }}
        onFocus={(e: FocusEvent<HTMLSelectElement>) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-accent-blue)';
            e.target.style.boxShadow = `0 0 0 3px ${error ? 'var(--mac-error-bg)' : 'var(--mac-accent-bg)'}`;
          }
        }}
        onBlur={(e: FocusEvent<HTMLSelectElement>) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-border)';
            e.target.style.boxShadow = 'none';
          }
          if (onBlur) onBlur(e);
        }}
        {...props}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option: SelectOption) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      {error && (
        <div
          style={{
            marginTop: 'var(--mac-spacing-1)',
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-error)',
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Form component
// ============================================================================

interface FormComponentProps {
  children: ReactNode;
  onSubmit?: (e: FormEvent) => void;
  className?: string;
  style?: CSSProperties;
  [key: string]: unknown;
}

export const Form = ({
  children,
  onSubmit,
  className = '',
  style = {},
  ...props
}: FormComponentProps): React.ReactElement => {
  const handleSubmit = (e: FormEvent): void => {
    e.preventDefault();
    if (onSubmit) {
      onSubmit(e);
    }
  };

  return (
    <form
      className={`form ${className}`}
      onSubmit={handleSubmit}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--mac-spacing-4)',
        ...style,
      }}
      {...props}
    >
      {children}
    </form>
  );
};

export default useForm;
