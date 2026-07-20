// Система форм с валидацией
import React, { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useTheme } from '../../contexts/ThemeContext';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * Контекст для форм
 */
const FormContext = React.createContext({} as any);

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

  const validateForm = useCallback((validationRules) => {
    const errors: Record<string, unknown> = {};
    const values = form?.values || {};

    Object.entries(validationRules).forEach(([name, rules]: [string, any]) => {
      const value = values[name];

      if (rules.required && (!value || value.toString().trim() === '')) {
        errors[name] = rules.required;
        return;
      }

      if (value && rules.minLength && value.length < rules.minLength) {
        errors[name] = rules.minLength;
        return;
      }

      if (value && rules.maxLength && value.length > rules.maxLength) {
        errors[name] = rules.maxLength;
        return;
      }

      if (value && rules.pattern && !rules.pattern.test(value)) {
        errors[name] = rules.pattern;
        return;
      }

      if (value && rules.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        errors[name] = rules.email;
        return;
      }

      if (value && rules.phone && !/^[+]?[1-9][\d]{0,15}$/.test(value.replace(/\s/g, ''))) {
        errors[name] = rules.phone;
        return;
      }

      if (value && rules.custom && !rules.custom(value)) {
        errors[name] = rules.custom;
        return;
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
export function FormField({
  name,
  label,
  type = 'text',
  placeholder,
  required = false,
  validationRules = {},
  formId,
  ...props
}) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = form?.values?.[name] || '';
  const error = form?.errors?.[name];
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
      const rules = validationRules as any;

      if (rules.required && (!value || value.toString().trim() === '')) {
        setError(name, rules.required);
        return;
      }

      if (value && rules.minLength && value.length < rules.minLength) {
        setError(name, rules.minLength);
        return;
      }

      if (value && rules.maxLength && value.length > rules.maxLength) {
        setError(name, rules.maxLength);
        return;
      }

      if (value && rules.pattern && !rules.pattern.test(value)) {
        setError(name, rules.pattern);
        return;
      }

      if (value && rules.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        setError(name, rules.email);
        return;
      }

      if (value && rules.phone && !/^[+]?[1-9][\d]{0,15}$/.test(value.replace(/\s/g, ''))) {
        setError(name, rules.phone);
        return;
      }

      if (value && rules.custom && !rules.custom(value)) {
        setError(name, rules.custom);
        return;
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
  const inputId = props.id || `field-${name}`;
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
export function FormTextArea({
  name,
  label,
  placeholder,
  required = false,
  validationRules = {},
  formId,
  rows = 4,
  ...props
}) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = form?.values?.[name] || '';
  const error = form?.errors?.[name];
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
      const rules = validationRules as any;

      if (rules.required && (!value || value.toString().trim() === '')) {
        setError(name, rules.required);
        return;
      }

      if (value && rules.minLength && value.length < rules.minLength) {
        setError(name, rules.minLength);
        return;
      }

      if (value && rules.maxLength && value.length > rules.maxLength) {
        setError(name, rules.maxLength);
        return;
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
  const inputId = props.id || `field-${name}`;
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
        style={textareaStyle}
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
export function FormSelect({
  name,
  label,
  options = [],
  placeholder = 'Выберите...',
  required = false,
  validationRules = {},
  formId,
  ...props
}) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = form?.values?.[name] || '';
  const error = form?.errors?.[name];
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
      const rules = validationRules as any;

      if (rules.required && (!value || value === '')) {
        setError(name, rules.required);
        return;
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
  const inputId = props.id || `field-${name}`;
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
        {options.map((option) =>
        <option key={option.value} value={option.value}>
            {option.label}
          </option>
        )}
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
