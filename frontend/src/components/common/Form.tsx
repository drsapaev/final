// Система форм с валидацией
import React, { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useTheme } from '../../contexts/ThemeContext';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

// === Domain types ===
// Per-field validation rules. Each rule's value is the error message (or
// truthy value) shown when the rule fails. `pattern` is a RegExp, `custom`
// is a predicate function.
//
// Note: existing callers sometimes pass `validationRules={{ required: 'msg' }}`
// where `required` is BOTH the field name AND the rule kind. To stay
// backward-compatible with that shape, ValidationRule accepts a string
// index signature so a plain string maps to a "required" error message
// for the field of the same name.

export interface ValidationRule {
  /** Required-field error message (or truthy value to flag failure). */
  required?: string | true;
  /** Minimum-length error message; numeric threshold is on the rule too. */
  minLength?: string | number;
  /** Maximum-length error message; numeric threshold is on the rule too. */
  maxLength?: string | number;
  /** Pattern to test against (RegExp). The RegExp itself is the error value. */
  pattern?: RegExp;
  /** Email-format error message (truthy value enables the email regex check). */
  email?: string | true;
  /** Phone-format error message (truthy value enables the phone regex check). */
  phone?: string | true;
  /** Custom predicate; returns true when value is valid. The function is the error value. */
  custom?: ((value: unknown) => boolean) | string;
  [key: string]: unknown;
}

/**
 * validationRules is a map of fieldName → rule spec. Backward-compat:
 * existing callers pass `{ required: 'msg' }` where the field name is
 * `required` and the value is a plain string used as the error message.
 * To accept both shapes, the value type is `ValidationRule | string`.
 */
export type ValidationRules = Record<string, ValidationRule | string>;

/**
 * Validate a single value against a rule spec. Returns the error value
 * (string/RegExp/function/etc.) for the first failing rule, or null if
 * all rules pass. Extracted so FormField / FormTextArea / FormSelect
 * share the same logic without re-casting.
 *
 * Accepts both `ValidationRule` (object with required/minLength/etc.)
 * and a plain string (treated as the `required` error message).
 */
function validateValueAgainstRules(value: unknown, rules: ValidationRule | string): unknown {
  // Backward-compat: plain string is treated as { required: <string> }.
  if (typeof rules === 'string') {
    if (!value || String(value).trim() === '') {
      return rules;
    }
    return null;
  }

  const strValue = value == null ? '' : String(value);

  if (rules.required && (!value || strValue.trim() === '')) {
    return rules.required;
  }

  if (value && rules.minLength && typeof rules.minLength === 'number' && strValue.length < rules.minLength) {
    return rules.minLength;
  }

  if (value && rules.maxLength && typeof rules.maxLength === 'number' && strValue.length > rules.maxLength) {
    return rules.maxLength;
  }

  if (value && rules.pattern instanceof RegExp && !rules.pattern.test(strValue)) {
    return rules.pattern;
  }

  if (value && rules.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(strValue)) {
    return rules.email;
  }

  if (value && rules.phone && !/^[+]?[1-9][\d]{0,15}$/.test(strValue.replace(/\s/g, ''))) {
    return rules.phone;
  }

  if (value && typeof rules.custom === 'function' && !rules.custom(value)) {
    return rules.custom;
  }

  return null;
}

// Form state shape stored in FormProvider's `forms` map.
export interface FormState {
  values: Record<string, unknown>;
  errors: Record<string, unknown>;
  touched: Record<string, boolean>;
  isSubmitting: boolean;
  [key: string]: unknown;
}

export interface FormContextValue {
  /** All registered forms keyed by formId. */
  forms: Record<string, FormState>;
  /** Register a new form with initial values. */
  registerForm: (formId: string, initialValues?: Record<string, unknown>) => void;
  /** Merge updates into a specific form's state. */
  updateForm: (formId: string, updates: Partial<FormState>) => void;
  /** Get a form's current state (or null if not registered). */
  getForm: (formId: string) => FormState | null;
  [key: string]: unknown;
}

/**
 * Контекст для форм
 */
const FormContext = React.createContext<FormContextValue | null>(null);

/**
 * Провайдер контекста форм
 */
export function FormProvider({ children }) {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [forms, setForms] = useState({});

  const registerForm = useCallback((formId, initialValues = {}) => {
    setForms((prev) => ({
      ...prev,
      [formId]: {
        values: initialValues,
        errors: {},
        touched: {},
        isSubmitting: false
      }
    }));
  }, []);

  const updateForm = useCallback((formId, updates) => {
    setForms((prev) => ({
      ...prev,
      [formId]: {
        ...prev[formId],
        ...updates
      }
    }));
  }, []);

  const getForm = useCallback((formId) => {
    return forms[formId] || null;
  }, [forms]);

  const value = {
    forms,
    registerForm,
    updateForm,
    getForm
  };

  return (
    <FormContext.Provider value={value}>
      {children}
    </FormContext.Provider>);

}

/**
 * Хук для использования форм
 */
export function useForm(formId, initialValues = {}) {
  const context = React.useContext(FormContext);
  if (!context) {
    throw new Error('useForm must be used within a FormProvider');
  }

  const { registerForm, updateForm, getForm } = context;
  const form = getForm(formId);

  React.useEffect(() => {
    if (!form) {
      registerForm(formId, initialValues);
    }
  }, [formId, initialValues, form, registerForm]);

  const setValue = useCallback((name, value) => {
    updateForm(formId, {
      values: {
        ...form?.values,
        [name]: value
      }
    });
  }, [formId, form?.values, updateForm]);

  const setError = useCallback((name, error) => {
    updateForm(formId, {
      errors: {
        ...form?.errors,
        [name]: error
      }
    });
  }, [formId, form?.errors, updateForm]);

  const setTouched = useCallback((name, touched = true) => {
    updateForm(formId, {
      touched: {
        ...form?.touched,
        [name]: touched
      }
    });
  }, [formId, form?.touched, updateForm]);

  const setSubmitting = useCallback((isSubmitting) => {
    updateForm(formId, { isSubmitting });
  }, [formId, updateForm]);

  const resetForm = useCallback(() => {
    updateForm(formId, {
      values: initialValues,
      errors: {},
      touched: {},
      isSubmitting: false
    });
  }, [formId, initialValues, updateForm]);

  const validateForm = useCallback((validationRules: ValidationRules) => {
    const errors: Record<string, unknown> = {};
    const values = form?.values || {};

    Object.entries(validationRules).forEach(([name, rules]) => {
      const error = validateValueAgainstRules(values[name], rules);
      if (error != null) {
        errors[name] = error;
      }
    });

    updateForm(formId, { errors });
    return Object.keys(errors).length === 0;
  }, [formId, form?.values, updateForm]);

  return {
    form,
    setValue,
    setError,
    setTouched,
    setSubmitting,
    resetForm,
    validateForm
  };
}

/**
 * Компонент формы
 */
export function Form({
  formId,
  initialValues = {},
  onSubmit,
  validationRules = {},
  children,
  ...props
}) {
  const { form, setSubmitting, validateForm } = useForm(formId, initialValues);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();

    if (Object.keys(validationRules).length > 0) {
      const isValid = validateForm(validationRules);
      if (!isValid) return;
    }

    setSubmitting(true);
    try {
      await onSubmit?.(form?.values, form);
    } finally {
      setSubmitting(false);
    }
  }, [form, onSubmit, validateForm, setSubmitting, validationRules]);

  return (
    <form onSubmit={handleSubmit} {...props}>
      {children}
    </form>);

}

/**
 * Компонент поля ввода
 */
interface FormFieldProps {
  name: string;
  label?: React.ReactNode;
  type?: string;
  placeholder?: string;
  required?: boolean;
  validationRules?: ValidationRules;
  formId?: string;
  style?: React.CSSProperties;
  [key: string]: unknown;
}

export function FormField({
  name,
  label,
  type = 'text',
  placeholder,
  required = false,
  validationRules = {},
  formId,
  ...props
}: FormFieldProps) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = String(form?.values?.[name] ?? '');
  const error = form?.errors?.[name] as string | undefined;
  const touched = form?.touched?.[name];

  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setValue(name, newValue);

    // Очищаем ошибку при изменении
    if (error) {
      setError(name, null);
    }
  }, [name, setValue, error, setError]);

  const handleBlur = useCallback(() => {
    setTouched(name, true);

    // Валидация при потере фокуса
    if (Object.keys(validationRules).length > 0) {
      const rules = validationRules[name];
      if (rules) {
        const error = validateValueAgainstRules(value, rules);
        if (error != null) {
          setError(name, error);
        }
      }
    }
  }, [name, value, validationRules, setTouched, setError]);

  const containerStyle = {
    marginBottom: getSpacing('md')
  };

  const labelStyle = {
    display: 'block',
    fontSize: getFontSize('sm'),
    fontWeight: 'var(--mac-font-weight-medium)',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('xs')
  };

  const inputStyle = {
    width: '100%',
    padding: getSpacing('sm'),
    fontSize: getFontSize('md'),
    border: `1px solid ${error && touched ? getColor('error', 'main') : getColor('border', 'main')}`,
    borderRadius: 'var(--mac-radius-sm)',
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary'),
    transition: 'border-color 0.2s ease',
    ...props.style
  };

  const errorStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('error', 'main'),
    marginTop: getSpacing('xs')
  };

  const requiredStyle = {
    color: getColor('error', 'main')
  };
  const inputId = (props.id as string | undefined) || `field-${name}`;
  const errorId = `error-${name}`;

  return (
    <div style={containerStyle}>
      {label &&
      <label htmlFor={inputId} style={labelStyle}>
          {label}
          {required && <span style={requiredStyle}> *</span>}
        </label>
      }
      
      <Input
        id={inputId}
        type={type}
        name={name}
        value={value}
        placeholder={placeholder}
        onChange={handleChange}
        onBlur={handleBlur}
        aria-invalid={!!(error && touched)}
        aria-describedby={error && touched ? errorId : undefined}
        aria-required={required}
        style={inputStyle}
        {...props} />
      
      
      {error && touched &&
      <div id={errorId} role="alert" style={errorStyle}>{error}</div>
      }
    </div>);

}


FormField.propTypes = {
  ...(FormField.propTypes || {}),
  id: PropTypes.any,
};

/**
 * Компонент текстовой области
 */
interface FormTextAreaProps {
  name: string;
  label?: React.ReactNode;
  placeholder?: string;
  required?: boolean;
  validationRules?: ValidationRules;
  formId?: string;
  rows?: number;
  style?: React.CSSProperties;
  [key: string]: unknown;
}

export function FormTextArea({
  name,
  label,
  placeholder,
  required = false,
  validationRules = {},
  formId,
  rows = 4,
  ...props
}: FormTextAreaProps) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = String(form?.values?.[name] ?? '');
  const error = form?.errors?.[name] as string | undefined;
  const touched = form?.touched?.[name];

  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setValue(name, newValue);

    if (error) {
      setError(name, null);
    }
  }, [name, setValue, error, setError]);

  const handleBlur = useCallback(() => {
    setTouched(name, true);

    if (Object.keys(validationRules).length > 0) {
      const rules = validationRules[name];
      if (rules) {
        const error = validateValueAgainstRules(value, rules);
        if (error != null) {
          setError(name, error);
        }
      }
    }
  }, [name, value, validationRules, setTouched, setError]);

  const containerStyle = {
    marginBottom: getSpacing('md')
  };

  const labelStyle = {
    display: 'block',
    fontSize: getFontSize('sm'),
    fontWeight: 'var(--mac-font-weight-medium)',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('xs')
  };

  const textareaStyle = {
    width: '100%',
    padding: getSpacing('sm'),
    fontSize: getFontSize('md'),
    border: `1px solid ${error && touched ? getColor('error', 'main') : getColor('border', 'main')}`,
    borderRadius: 'var(--mac-radius-sm)',
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary'),
    resize: 'vertical',
    minHeight: `${rows * 1.5}em`,
    transition: 'border-color 0.2s ease',
    ...props.style
  };

  const errorStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('error', 'main'),
    marginTop: getSpacing('xs')
  };

  const requiredStyle = {
    color: getColor('error', 'main')
  };
  const inputId = (props.id as string | undefined) || `field-${name}`;
  const errorId = `error-${name}`;

  return (
    <div style={containerStyle}>
      {label &&
      <label htmlFor={inputId} style={labelStyle}>
          {label}
          {required && <span style={requiredStyle}> *</span>}
        </label>
      }
      
      <textarea
        id={inputId}
        name={name}
        value={value}
        placeholder={placeholder}
        onChange={handleChange}
        onBlur={handleBlur}
        rows={rows}
        aria-invalid={!!(error && touched)}
        aria-describedby={error && touched ? errorId : undefined}
        aria-required={required}
        style={textareaStyle as React.CSSProperties}
        {...props} />
      
      
      {error && touched &&
      <div id={errorId} role="alert" style={errorStyle}>{error}</div>
      }
    </div>);

}


FormTextArea.propTypes = {
  ...(FormTextArea.propTypes || {}),
  id: PropTypes.any,
};

/**
 * Компонент селекта
 */
interface FormSelectProps {
  name: string;
  label?: React.ReactNode;
  options?: Array<{ value: string; label: string } | string>;
  placeholder?: string;
  required?: boolean;
  validationRules?: ValidationRules;
  formId?: string;
  style?: React.CSSProperties;
  [key: string]: unknown;
}

export function FormSelect({
  name,
  label,
  options = [],
  placeholder = 'Выберите...',
  required = false,
  validationRules = {},
  formId,
  ...props
}: FormSelectProps) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = String(form?.values?.[name] ?? '');
  const error = form?.errors?.[name] as string | undefined;
  const touched = form?.touched?.[name];

  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setValue(name, newValue);

    if (error) {
      setError(name, null);
    }
  }, [name, setValue, error, setError]);

  const handleBlur = useCallback(() => {
    setTouched(name, true);

    if (Object.keys(validationRules).length > 0) {
      const rules = validationRules[name];
      if (rules) {
        const error = validateValueAgainstRules(value, rules);
        if (error != null) {
          setError(name, error);
        }
      }
    }
  }, [name, value, validationRules, setTouched, setError]);

  const containerStyle = {
    marginBottom: getSpacing('md')
  };

  const labelStyle = {
    display: 'block',
    fontSize: getFontSize('sm'),
    fontWeight: 'var(--mac-font-weight-medium)',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('xs')
  };

  const selectStyle = {
    width: '100%',
    padding: getSpacing('sm'),
    fontSize: getFontSize('md'),
    border: `1px solid ${error && touched ? getColor('error', 'main') : getColor('border', 'main')}`,
    borderRadius: 'var(--mac-radius-sm)',
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary'),
    transition: 'border-color 0.2s ease',
    ...props.style
  };

  const errorStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('error', 'main'),
    marginTop: getSpacing('xs')
  };

  const requiredStyle = {
    color: getColor('error', 'main')
  };
  const inputId = (props.id as string | undefined) || `field-${name}`;
  const errorId = `error-${name}`;

  return (
    <div style={containerStyle}>
      {label &&
      <label htmlFor={inputId} style={labelStyle}>
          {label}
          {required && <span style={requiredStyle}> *</span>}
        </label>
      }
      
      <select
        id={inputId}
        name={name}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        aria-invalid={!!(error && touched)}
        aria-describedby={error && touched ? errorId : undefined}
        aria-required={required}
        style={selectStyle}
        {...props}>
        
        <option value="">{placeholder}</option>
        {options.map((option) => {
          const opt = typeof option === 'string' ? { value: option, label: option } : option;
          return (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
          );
        })}
      </select>
      
      {error && touched &&
      <div id={errorId} role="alert" style={errorStyle}>{error}</div>
      }
    </div>);

}


FormSelect.propTypes = {
  ...(FormSelect.propTypes || {}),
  id: PropTypes.any,
};

/**
 * Компонент кнопки отправки
 */
export function SubmitButton({
  children = 'Отправить',
  formId,
  ...props
}) {
  const { form } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const buttonStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    fontSize: getFontSize('md'),
    fontWeight: 'var(--mac-font-weight-medium)',
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    border: 'none',
    borderRadius: 'var(--mac-radius-sm)',
    cursor: form?.isSubmitting ? 'not-allowed' : 'pointer',
    opacity: form?.isSubmitting ? 0.7 : 1,
    transition: 'all 0.2s ease',
    ...props.style
  };

  return (
    <button
      type="submit"
      disabled={form?.isSubmitting}
      style={buttonStyle}
      {...props}>
      
      {form?.isSubmitting ? 'Отправка...' : children}
    </button>);

}

FormProvider.propTypes = {
  children: PropTypes.node
};

Form.propTypes = {
  formId: PropTypes.string,
  initialValues: PropTypes.object,
  onSubmit: PropTypes.func,
  validationRules: PropTypes.object,
  children: PropTypes.node
};

FormField.propTypes = {
  name: PropTypes.string,
  label: PropTypes.node,
  type: PropTypes.string,
  placeholder: PropTypes.string,
  required: PropTypes.bool,
  validationRules: PropTypes.object,
  formId: PropTypes.string,
  style: PropTypes.object
};

FormTextArea.propTypes = {
  name: PropTypes.string,
  label: PropTypes.node,
  placeholder: PropTypes.string,
  required: PropTypes.bool,
  validationRules: PropTypes.object,
  formId: PropTypes.string,
  rows: PropTypes.number,
  style: PropTypes.object
};

FormSelect.propTypes = {
  name: PropTypes.string,
  label: PropTypes.node,
  options: PropTypes.array,
  placeholder: PropTypes.string,
  required: PropTypes.bool,
  validationRules: PropTypes.object,
  formId: PropTypes.string,
  style: PropTypes.object
};

SubmitButton.propTypes = {
  children: PropTypes.node,
  formId: PropTypes.string,
  style: PropTypes.object
};
